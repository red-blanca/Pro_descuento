from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import browser_cookie3

ROOT = Path(__file__).resolve().parent


def _load_cookiejar(browser_name: str):
    loaders: dict[str, Callable] = {
        "chrome": browser_cookie3.chrome,
        "edge": browser_cookie3.edge,
        "brave": browser_cookie3.brave,
        "firefox": browser_cookie3.firefox,
    }
    if browser_name not in loaders:
        raise ValueError(f"Navegador no soportado: {browser_name}")
    return loaders[browser_name](domain_name=".facebook.com")


def _cookie_to_storage_state(cookie) -> dict:
    expires = -1
    try:
        expires = float(cookie.expires) if cookie.expires else -1
    except Exception:
        expires = -1

    same_site = "Lax"
    if str(getattr(cookie, "_rest", {}).get("SameSite", "")).lower() == "none":
        same_site = "None"
    elif str(getattr(cookie, "_rest", {}).get("SameSite", "")).lower() == "strict":
        same_site = "Strict"

    return {
        "name": cookie.name,
        "value": cookie.value,
        "domain": cookie.domain,
        "path": cookie.path or "/",
        "expires": expires,
        "httpOnly": bool(cookie.has_nonstandard_attr("HttpOnly")),
        "secure": bool(cookie.secure),
        "sameSite": same_site,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importa cookies autenticadas de Facebook desde el navegador local a storage_state.json"
    )
    parser.add_argument(
        "--browser",
        default="chrome",
        choices=["chrome", "edge", "brave", "firefox"],
        help="Navegador desde donde leer cookies",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "storage_state.json"),
        help="Ruta de salida del storage state",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    jar = _load_cookiejar(args.browser)
    cookies = [_cookie_to_storage_state(cookie) for cookie in jar]
    has_c_user = any(cookie["name"] == "c_user" and cookie["value"] for cookie in cookies)

    if not cookies:
        print(f"No encontre cookies de Facebook en {args.browser}.")
        return 1

    if not has_c_user:
        print(
            f"Encontre cookies de Facebook en {args.browser}, pero no una sesion autenticada "
            "(falta c_user)."
        )
        return 1

    payload = {
        "cookies": cookies,
        "origins": [],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Sesion importada desde {args.browser} a: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
