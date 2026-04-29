# TuGanga Scraper

Scraper HTTP para `tuganga.cl`, usando el endpoint interno `/fce`.

## Correr solo TuGanga

```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8030
cd web
npm run dev -- --host 127.0.0.1 --port 5187
```

## Correr junto a todas las vistas

Desde la raiz del proyecto:

```bash
python3 run_dev.py
```
