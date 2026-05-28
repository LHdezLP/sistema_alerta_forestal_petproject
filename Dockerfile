FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    nginx libgdal-dev libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/requirements_prod.txt .
RUN pip install --no-cache-dir -r requirements_prod.txt

COPY exports/best_fire_smoke.onnx ./exports/
COPY api/ ./api/
COPY geo_pipeline/ ./geo_pipeline/
COPY dashboard/ ./dashboard/
COPY "Datasets Territoriales/" "./Datasets Territoriales/"
COPY deploy/huggingface_nginx.conf /etc/nginx/nginx.conf
COPY deploy/start_huggingface.sh ./deploy/start_huggingface.sh

RUN chmod +x ./deploy/start_huggingface.sh

ENV API_INTERNAL_URL=http://127.0.0.1:8000
ENV API_PUBLIC_URL=

EXPOSE 7860

CMD ["./deploy/start_huggingface.sh"]
