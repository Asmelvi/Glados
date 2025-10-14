FROM python:3.12-slim
# Paquetes base que usamos para las tareas
RUN pip install --no-cache-dir polars==1.8.2 numpy==2.1.2 requests beautifulsoup4 lxml aiohttp
WORKDIR /app
