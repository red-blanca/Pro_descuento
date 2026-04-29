FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build frontend (if node is available and dist doesn't exist)
# On Render, pre-build dist/ and commit it, or add a build step
EXPOSE 8010

CMD ["uvicorn", "server_http:app", "--host", "0.0.0.0", "--port", "8010"]
