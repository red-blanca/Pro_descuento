from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.6)
        return sock.connect_ex((host, port)) == 0


def main() -> int:
    if not WEB_DIR.exists():
        print("No existe carpeta web/.")
        return 1

    env = os.environ.copy()
    node_path = r"C:\Program Files\nodejs"
    if node_path not in env.get("PATH", ""):
        env["PATH"] = f"{env.get('PATH','')};{node_path}"
    popen_kwargs: dict = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    api_cmd = [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8000"]
    node_exe = Path(node_path) / "node.exe"
    vite_js = WEB_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    web_cmd = [str(node_exe), str(vite_js), "dev", "--host", "127.0.0.1", "--port", "5173"]

    api = None
    if _is_port_open("127.0.0.1", 8000):
        print("API ya activa en http://127.0.0.1:8000 (se reutiliza).")
    else:
        print("Iniciando API en http://127.0.0.1:8000")
        api = subprocess.Popen(api_cmd, cwd=str(ROOT), env=env, **popen_kwargs)
        time.sleep(1.5)
        if api.poll() is not None:
            print("La API no pudo iniciar.")
            return 1

    print("Iniciando Frontend en http://127.0.0.1:5173")
    web = subprocess.Popen(web_cmd, cwd=str(WEB_DIR), env=env, **popen_kwargs)

    try:
        while True:
            if api is not None and api.poll() is not None:
                print("La API se detuvo.")
                break
            if web.poll() is not None:
                print("El frontend se detuvo.")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nDeteniendo servicios...")
    finally:
        for proc in (web, api):
            if proc is None:
                continue
            if proc.poll() is None:
                proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
