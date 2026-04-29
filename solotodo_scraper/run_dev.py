from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
API_PORT = "8001"
WEB_PORT = "5188"


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((HOST, port)) == 0


def main() -> int:
    web_dir = ROOT / "web"
    env = os.environ.copy()
    env["VITE_API_BASE"] = f"http://{HOST}:{API_PORT}/api"

    processes: list[subprocess.Popen] = []

    if port_open(int(API_PORT)):
        print(f"Backend ya activo en http://{HOST}:{API_PORT}")
    else:
        print(f"Iniciando backend SoloTodo en http://{HOST}:{API_PORT}")
        processes.append(subprocess.Popen([
            sys.executable,
            "-m",
            "uvicorn",
            "solotodo_server:app",
            "--host",
            HOST,
            "--port",
            API_PORT,
            "--reload",
        ], cwd=ROOT, env=env))

    if port_open(int(WEB_PORT)):
        print(f"Frontend ya activo en http://{HOST}:{WEB_PORT}")
    else:
        print(f"Iniciando frontend SoloTodo en http://{HOST}:{WEB_PORT}")
        processes.append(subprocess.Popen([
            "npm",
            "run",
            "dev",
            "--",
            "--host",
            HOST,
            "--port",
            WEB_PORT,
            "--strictPort",
        ], cwd=web_dir, env=env))

    time.sleep(2)
    webbrowser.open(f"http://{HOST}:{WEB_PORT}")

    try:
        while any(proc.poll() is None for proc in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nCerrando SoloTodo...")
        for proc in processes:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
