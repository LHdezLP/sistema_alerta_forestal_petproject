#!/usr/bin/env bash
set -euo pipefail

uvicorn api.main:app --host 127.0.0.1 --port 8000 &
streamlit run dashboard/app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false &

nginx -g "daemon off;"
