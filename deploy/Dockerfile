FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgdal-dev libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/requirements_prod.txt .
RUN pip install --no-cache-dir -r requirements_prod.txt

COPY exports/best_fire_smoke.onnx ./exports/
COPY api/ ./api/
COPY geo_pipeline/ ./geo_pipeline/
COPY dashboard/ ./dashboard/
COPY ["Datasets Territoriales/", "Datasets Territoriales/"]

EXPOSE 8000
EXPOSE 8501

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
