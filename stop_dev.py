from __future__ import annotations

import os
import subprocess
import sys
import socket
from pathlib import Path

# Add current directory to path so we can import run_all
sys.path.append(str(Path(__file__).resolve().parent))

try:
    from run_all import SERVICES
except ImportError:
    print("Error: No se pudo importar SERVICES de run_all.py")
    sys.exit(1)

def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.1)
        return sock.connect_ex((host, port)) == 0

def kill_process_on_port(port: int):
    if not is_port_open(port):
        return

    print(f"Buscando proceso en puerto {port}...")
    
    if os.name == "nt":  # Windows
        try:
            # Encontrar el PID
            output = subprocess.check_output(f"netstat -ano | findstr LISTENING | findstr :{port}", shell=True, text=True)
            pids = set()
            for line in output.strip().splitlines():
                parts = line.split()
                if len(parts) > 4:
                    pid = parts[-1]
                    if pid != "0": # Evitar el proceso Idle
                        pids.add(pid)
            
            for pid in pids:
                print(f"  Deteniendo PID {pid} (Puerto {port})...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass
    else:  # Unix/Linux/macOS
        try:
            # Usar lsof para encontrar PIDs
            output = subprocess.check_output(["lsof", "-t", "-i", f":{port}"], text=True)
            pids = output.strip().splitlines()
            for pid in pids:
                print(f"  Deteniendo PID {pid} (Puerto {port})...")
                subprocess.run(["kill", "-9", pid], capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Probar con fuser si lsof falla
            subprocess.run(f"fuser -k {port}/tcp", shell=True, capture_output=True)

def main():
    print("--- Deteniendo servicios de Pro Descuento ---")
    
    ports_to_check = set()
    for svc in SERVICES:
        ports_to_check.add(svc.api_port)
        ports_to_check.add(svc.web_port)
    
    # Ordenar y limpiar
    ports = sorted(list(ports_to_check))
    
    for port in ports:
        kill_process_on_port(port)
    
    print("\nVerificación final:")
    all_clear = True
    for port in ports:
        if is_port_open(port):
            print(f"[!] El puerto {port} sigue abierto.")
            all_clear = False
    
    if all_clear:
        print("Todos los servicios se han detenido correctamente.")
    else:
        print("Algunos servicios no pudieron ser detenidos.")

if __name__ == "__main__":
    main()
