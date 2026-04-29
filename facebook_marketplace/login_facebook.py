from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent


def _is_logged_in(context) -> bool:
    cookies = context.cookies()
    return any(cookie.get("name") == "c_user" and cookie.get("value") for cookie in cookies)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Abre Facebook en un navegador controlado y guarda storage_state.json"
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "storage_state.json"),
        help="Ruta de salida del storage state",
    )
    parser.add_argument(
        "--user-data-dir",
        default=str(ROOT / "chrome_profile"),
        help="Perfil persistente de Chrome a reutilizar",
    )
    parser.add_argument(
        "--url",
        default="https://www.facebook.com/",
        help="URL inicial a abrir",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    user_data_dir = Path(args.user_data_dir)
    if not user_data_dir.is_absolute():
        user_data_dir = ROOT / user_data_dir
    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            channel="chrome",
            headless=False,
            locale="es-CL",
            viewport={"width": 1440, "height": 1080},
        )
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")

        print("")
        print("1. Inicia sesion en Facebook si hace falta.")
        print("2. Si Facebook muestra revision o verificacion, completala en esa ventana.")
        print("3. Cuando ya estes dentro, navega manualmente a Marketplace.")
        print("4. Vuelve a esta terminal y presiona Enter para guardar la sesion.")
        input()

        if not _is_logged_in(context):
            print("No detecte una sesion autenticada de Facebook.")
            print("No voy a guardar storage_state porque faltaria la cookie c_user.")
            context.close()
            return 1

        context.storage_state(path=str(output_path))
        print(f"Sesion guardada en: {output_path}")
        print(f"Perfil persistente listo en: {user_data_dir}")

        context.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
