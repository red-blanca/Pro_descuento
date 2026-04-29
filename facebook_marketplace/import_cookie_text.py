from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _parse_expires(raw: str) -> float:
    value = str(raw or "").strip()
    if not value or value.lower() == "session":
        return -1
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return -1


def _parse_bool(raw: str) -> bool:
    return str(raw or "").strip() in {"✓", "?", "true", "True", "1", "yes", "Yes"}


def parse_cookie_line(line: str) -> dict | None:
    raw = line.strip()
    if not raw:
        return None
    if raw.lower().startswith("name\tvalue\t"):
        return None

    if "\t" in raw:
        parts = [part.strip() for part in raw.split("\t")]
        if len(parts) >= 2:
            name = parts[0]
            value = parts[1]
            if not name or not value:
                return None

            domain = parts[2] if len(parts) >= 3 and parts[2].startswith(".") else ".facebook.com"
            path = parts[3] if len(parts) >= 4 and parts[3].startswith("/") else "/"
            expires = _parse_expires(parts[4] if len(parts) >= 5 else "")
            http_only = _parse_bool(parts[6] if len(parts) >= 7 else "")
            secure = _parse_bool(parts[7] if len(parts) >= 8 else "")
            same_site_raw = parts[8] if len(parts) >= 9 else "None"
            same_site = same_site_raw if same_site_raw in {"Lax", "Strict", "None"} else "None"

            return {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
                "expires": expires,
                "httpOnly": http_only,
                "secure": secure,
                "sameSite": same_site,
            }

    parts = raw.split()
    if len(parts) < 2:
        return None

    name = parts[0].strip()
    value = parts[1].strip()
    domain = ".facebook.com"
    path = "/"
    secure = True
    http_only = True
    same_site = "None"
    expires = -1

    if len(parts) >= 3 and parts[2].startswith("."):
        domain = parts[2]
    if len(parts) >= 4 and parts[3].startswith("/"):
        path = parts[3]

    return {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
        "expires": expires,
        "httpOnly": http_only,
        "secure": secure,
        "sameSite": same_site,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convierte texto de cookies de Facebook a storage_state.json"
    )
    parser.add_argument(
        "--input",
        default=str(ROOT / "facebook_cookies.txt"),
        help="Archivo de texto con cookies pegadas linea por linea",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "storage_state.json"),
        help="Archivo storage_state.json de salida",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"No existe archivo de entrada: {input_path}")
        return 1

    cookies: list[dict] = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        parsed = parse_cookie_line(line)
        if parsed:
            cookies.append(parsed)

    has_c_user = any(cookie["name"] == "c_user" and cookie["value"] for cookie in cookies)
    has_xs = any(cookie["name"] == "xs" and cookie["value"] for cookie in cookies)

    if not has_c_user:
        print("No encontre la cookie c_user. Asi no sirve como sesion autenticada.")
        return 1
    if not has_xs:
        print("No encontre la cookie xs. Asi no sirve como sesion autenticada.")
        return 1

    payload = {"cookies": cookies, "origins": []}
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Storage state generado en: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
