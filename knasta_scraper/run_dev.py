import subprocess
import time
import os
import sys
import webbrowser

def is_port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def kill_port(port):
    if is_port_in_use(port):
        print(f"Puerto {port} en uso. Intentando liberar...")
        subprocess.run(f"FOR /F \"tokens=5\" %a IN ('netstat -aon ^| find \":{port}\" ^| find \"LISTENING\"') DO taskkill /F /PID %a", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)

def main():
    print("Iniciando Knasta Scraper...")
    
    kill_port(8020)
    kill_port(5185)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(base_dir, "web")

    print("Iniciando backend FastAPI (Puerto 8020)...")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8020", "--reload"],
        cwd=base_dir
    )

    print("Iniciando frontend Vite (Puerto 5185)...")
    frontend = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", "5185"],
        cwd=web_dir,
        shell=True
    )

    time.sleep(3)
    webbrowser.open("http://localhost:5185")

    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\nCerrando servidores...")
        backend.kill()
        frontend.kill()
        
if __name__ == "__main__":
    main()
