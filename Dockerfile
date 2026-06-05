FROM node:22-alpine AS web-build

WORKDIR /app/web

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

COPY mercadolibre.py global_search.py server.py run_dev.py README.md ./
COPY automation ./automation
COPY facebook_marketplace ./facebook_marketplace
COPY pulga ./pulga
COPY knasta_scraper ./knasta_scraper
COPY solotodo_scraper ./solotodo_scraper
COPY travel_scraper ./travel_scraper
COPY tuganga_scraper ./tuganga_scraper
COPY descuentosrata_scraper ./descuentosrata_scraper
COPY pcfactory_scraper ./pcfactory_scraper
COPY aliexpress_scraper ./aliexpress_scraper
COPY --from=web-build /app/web/dist ./web/dist

EXPOSE 10000

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-10000}"]
