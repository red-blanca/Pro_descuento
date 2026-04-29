from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
LOG_DIR = ROOT / ".dev_logs"
VENV_DIR = ROOT / ".venv"


@dataclass(frozen=True)
class Service:
    key: str
    label: str
    root: Path
    backend_module: str
    api_port: int
    web_dir: Path
    web_port: int
    web_kind: str = "vite"  # "vite" or "static"
    health_path: str = "/api/health"


SERVICES = [
    Service("mercadolibre", "MercadoLibre", ROOT, "server:app", 8000, ROOT / "web", 5173),
    Service("facebook", "Facebook Marketplace", ROOT / "facebook_marketplace", "server_http:app", 8010, ROOT / "facebook_marketplace" / "web", 5184),
    Service("pulga", "Pulga", ROOT / "pulga", "server:app", 8015, ROOT / "pulga" / "web", 5186),
    Service("knasta", "Knasta", ROOT / "knasta_scraper", "server:app", 8020, ROOT / "knasta_scraper" / "web", 5185),
    Service("solotodo", "SoloTodo", ROOT / "solotodo_scraper", "solotodo_server:app", 8001, ROOT / "solotodo_scraper" / "web", 5188),
    Service("travel", "Travel Tienda", ROOT / "travel_scraper", "server:app", 8050, ROOT / "travel_scraper" / "web", 5189),
    Service("tuganga", "TuGanga", ROOT / "tuganga_scraper", "server:app", 8030, ROOT / "tuganga_scraper" / "web", 5187),
    Service(
        "descuentosrata",
        "DescuentosRata",
        ROOT / "descuentosrata_scraper",
        "server:app",
        8040,
        ROOT / "descuentosrata_scraper" / "web",
        8040,
        web_kind="static",
    ),
]


def _is_port_open(port: int, host: str = HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _wait_for_port(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_port_open(port):
            return True
        time.sleep(0.2)
    return False


def _parse_node_major(version: str) -> tuple[int, int, int]:
    raw = version.strip().lstrip("v")
    parts = raw.split(".")
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return major, minor, patch


def _node_version_ok(version: str) -> bool:
    major, minor, patch = _parse_node_major(version)
    return (major == 20 and (minor, patch) >= (19, 0)) or (major > 20)


def _node_version(node_path: Path) -> str | None:
    try:
        return subprocess.check_output([str(node_path), "-v"], text=True).strip()
    except Exception:
        return None


def _nvm_node_22() -> Path | None:
    nvm_sh = Path.home() / ".nvm" / "nvm.sh"
    if not nvm_sh.exists():
        return None
    try:
        out = subprocess.check_output(
            ["bash", "-lc", f'source "{nvm_sh}" && nvm which 22'],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None
    path = Path(out)
    return path if path.exists() else None


def _find_node() -> Path:
    current = shutil.which("node")
    if current:
        path = Path(current)
        version = _node_version(path)
        if version and _node_version_ok(version):
            return path

    nvm_node = _nvm_node_22()
    if nvm_node:
        version = _node_version(nvm_node)
        if version and _node_version_ok(version):
            return nvm_node

    raise RuntimeError(
        "Se necesita Node 20.19+ o 22.12+. Instala Node 22 con: "
        'bash -lc \'source "$HOME/.nvm/nvm.sh" && nvm install 22\''
    )


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _ensure_python_env() -> Path:
    python_path = _venv_python()
    if not python_path.exists():
        print("[Python] Creando entorno virtual .venv...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=str(ROOT), check=True)

    requirements = ROOT / "requirements.txt"
    probe = subprocess.run(
        [str(python_path), "-c", "import fastapi, uvicorn, pydantic"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode != 0:
        print("[Python] Instalando dependencias backend...")
        subprocess.run(
            [str(python_path), "-m", "pip", "install", "--upgrade", "pip"],
            cwd=str(ROOT),
            check=True,
        )
        subprocess.run(
            [str(python_path), "-m", "pip", "install", "-r", str(requirements)],
            cwd=str(ROOT),
            check=True,
        )
    return python_path


def _npm_for_node(node_path: Path) -> Path:
    npm = node_path.parent / "npm"
    if npm.exists():
        return npm
    found = shutil.which("npm")
    if found:
        return Path(found)
    raise RuntimeError("No se encontro npm junto a Node.")


def _ensure_frontend_deps(service: Service, node_path: Path | None) -> None:
    if service.web_kind != "vite":
        return
    if node_path is None:
        raise RuntimeError(f"[{service.label}] Falta Node.js para iniciar frontend Vite.")
    vite_js = service.web_dir / "node_modules" / "vite" / "bin" / "vite.js"
    if vite_js.exists():
        return
    npm = _npm_for_node(node_path)
    print(f"[{service.label}] Instalando dependencias frontend...")
    subprocess.run([str(npm), "ci"], cwd=str(service.web_dir), check=True)


def _start_process(name: str, cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    LOG_DIR.mkdir(exist_ok=True)
    log_file = (LOG_DIR / f"{name}.log").open("a", encoding="utf-8")
    log_file.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    log_file.flush()
    return subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _start_service(
    service: Service,
    python_path: Path,
    node_path: Path | None,
    env: dict[str, str],
    reload: bool,
) -> list[tuple[str, subprocess.Popen | None]]:
    started: list[tuple[str, subprocess.Popen | None]] = []

    api_proc: subprocess.Popen | None = None
    if _is_port_open(service.api_port):
        print(f"[{service.label}] API ya activa: http://{HOST}:{service.api_port}")
    else:
        cmd = [
            str(python_path),
            "-m",
            "uvicorn",
            service.backend_module,
            "--host",
            HOST,
            "--port",
            str(service.api_port),
        ]
        if reload:
            cmd.append("--reload")
        print(f"[{service.label}] API -> http://{HOST}:{service.api_port}")
        api_proc = _start_process(f"{service.key}-api", cmd, service.root, env)
        if not _wait_for_port(service.api_port):
            raise RuntimeError(f"No pudo iniciar API de {service.label}. Revisa {LOG_DIR / f'{service.key}-api.log'}")
    started.append((f"{service.key}-api", api_proc))

    if service.web_kind == "vite":
        if node_path is None:
            raise RuntimeError(f"[{service.label}] Se necesita Node.js para iniciar el frontend.")
        web_proc: subprocess.Popen | None = None
        if _is_port_open(service.web_port):
            print(f"[{service.label}] Web ya activa: http://{HOST}:{service.web_port}")
        else:
            vite_js = service.web_dir / "node_modules" / "vite" / "bin" / "vite.js"
            cmd = [
                str(node_path),
                str(vite_js),
                "--host",
                HOST,
                "--port",
                str(service.web_port),
                "--strictPort",
            ]
            print(f"[{service.label}] Web -> http://{HOST}:{service.web_port}")
            web_proc = _start_process(f"{service.key}-web", cmd, service.web_dir, env)
            if not _wait_for_port(service.web_port):
                raise RuntimeError(
                    f"No pudo iniciar web de {service.label}. Revisa {LOG_DIR / f'{service.key}-web.log'}"
                )
        started.append((f"{service.key}-web", web_proc))
    else:
        print(f"[{service.label}] Web (estático) -> http://{HOST}:{service.web_port}")
        started.append((f"{service.key}-web", None))

    return started


def _stop_processes(processes: list[tuple[str, subprocess.Popen | None]]) -> None:
    for _name, proc in reversed(processes):
        if proc is None or proc.poll() is not None:
            continue
        proc.send_signal(signal.SIGTERM)
    for name, proc in reversed(processes):
        if proc is None or proc.poll() is not None:
            continue
        try:
            proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            print(f"[{name}] Forzando cierre...")
            proc.kill()


def _selected_services(names: list[str]) -> list[Service]:
    if not names or "all" in names:
        return SERVICES
    wanted = set(names)
    services = [svc for svc in SERVICES if svc.key in wanted]
    missing = wanted - {svc.key for svc in services}
    if missing:
        valid = ", ".join(["all"] + [svc.key for svc in SERVICES])
        raise RuntimeError(f"Servicio desconocido: {', '.join(sorted(missing))}. Opciones: {valid}")
    return services


def main() -> int:
    parser = argparse.ArgumentParser(description="Levanta todas las vistas de Pro Descuento.")
    parser.add_argument(
        "services",
        nargs="*",
        help=(
            "Servicios a levantar: all, mercadolibre, facebook, pulga, knasta, solotodo, travel, tuganga, descuentosrata. "
            "Default: all."
        ),
    )
    parser.add_argument("--no-open", action="store_true", help="No abrir URLs en el navegador.")
    parser.add_argument("--reload", action="store_true", help="Activa --reload en uvicorn.")
    parser.add_argument("--check", action="store_true", help="Solo valida dependencias y puertos; no deja procesos corriendo.")
    args = parser.parse_args()

    services = _selected_services(args.services)
    python_path = _ensure_python_env()
    print(f"Python: {python_path}")

    needs_node = any(svc.web_kind == "vite" for svc in services)
    node_path: Path | None = None
    if needs_node:
        node_path = _find_node()
        node_version = _node_version(node_path) or "desconocida"
        print(f"Node: {node_version} ({node_path})")

    for svc in services:
        if not svc.root.exists():
            raise RuntimeError(f"No existe carpeta de {svc.label}: {svc.root}")
        if not svc.web_dir.exists():
            raise RuntimeError(f"No existe frontend de {svc.label}: {svc.web_dir}")
        _ensure_frontend_deps(svc, node_path)

    env = os.environ.copy()
    if node_path is not None:
        env["PATH"] = f"{node_path.parent}{os.pathsep}{env.get('PATH', '')}"

    processes: list[tuple[str, subprocess.Popen | None]] = []
    stop_requested = False

    def _request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    previous_term = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _request_stop)
    try:
        for svc in services:
            processes.extend(_start_service(svc, python_path, node_path, env, reload=args.reload))

        print("\nListo. Vistas disponibles:")
        for svc in services:
            if svc.web_kind == "vite":
                print(f"- {svc.label}: http://{HOST}:{svc.web_port}  (API http://{HOST}:{svc.api_port})")
            else:
                print(f"- {svc.label}: http://{HOST}:{svc.web_port}  (UI + API)")
        print(f"\nLogs: {LOG_DIR}")
        print("Presiona Ctrl+C para detener los procesos iniciados por este comando.")

        if not args.no_open:
            for svc in services:
                webbrowser.open(f"http://{HOST}:{svc.web_port}")

        if args.check:
            return 0

        while not stop_requested:
            for name, proc in processes:
                if proc is not None and proc.poll() is not None:
                    raise RuntimeError(f"El proceso {name} se detuvo. Revisa {LOG_DIR / f'{name}.log'}")
            time.sleep(0.8)
    except KeyboardInterrupt:
        print("\nDeteniendo servicios...")
        return 0
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        _stop_processes(processes)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
