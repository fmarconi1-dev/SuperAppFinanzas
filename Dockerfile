# Superapp de Finanzas — imagen de deploy (Fly.io)
FROM python:3.12-slim

WORKDIR /app

# Dependencias primero (cache de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["streamlit", "run", "app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
