# Despliegue

Este proyecto tiene dos servicios:

- `api`: FastAPI, modelo ONNX, riesgo territorial, SQLite y Telegram.
- `dashboard`: Streamlit, mapa y controles de usuario.

Para despliegues reales conviene usar contenedores. El modelo ONNX evita depender de PyTorch en produccion.

## Local

Desde la raiz:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

En otra terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

## Docker local

Crea `deploy/.env` a partir de `deploy/.env.example` y ejecuta:

```bash
cd deploy
docker compose up --build
```

URLs:

- API: `http://localhost:8000`
- Dashboard: `http://localhost:8501`
- Captura por navegador: `http://localhost:8000/screen-capture`

El contenedor del dashboard usa dos URLs:

- `API_INTERNAL_URL`: URL de red interna Docker, por defecto `http://api:8000`.
- `API_PUBLIC_URL`: URL que ve el navegador del usuario, por defecto `http://localhost:8000`.

Si se despliega en un dominio o IP publica, cambia `API_PUBLIC_URL` en `docker-compose.yml` o en el entorno del servicio.

## GitHub

Repositorio objetivo:

```bash
https://github.com/LHdezLP/sistema_alerta_forestal_petproject.git
```

No se sube `.env`, `.venv`, datasets crudos, datasets procesados, runs de entrenamiento ni alertas generadas. Si GitHub pide credenciales, usa una de estas opciones:

- Recomendada: GitHub CLI con `gh auth login`, HTTPS y login por navegador.
- Alternativa: token Fine-grained de GitHub con permiso `Contents: Read and write` sobre el repositorio. Al hacer `git push`, usuario `LHdezLP` y password = token.

No pegues tokens en el chat ni los guardes en archivos del proyecto.

## IsardVDI

Opcion recomendada: servidor con Docker y Compose.

1. Subir el proyecto a GitHub sin `.env`, datos privados ni tokens.
2. En Isard:

```bash
git clone https://github.com/LHdezLP/sistema_alerta_forestal_petproject.git
cd sistema_alerta_forestal_petproject/deploy
cp .env.example .env
nano .env
docker compose up -d --build
```

3. Comprobar servicios:

```bash
docker compose ps
docker compose logs -f
curl http://localhost:8000/health
```

4. Publicar/abrir los puertos `8000` y `8501` segun la configuracion del centro.

Ventajas:

- Reproducible.
- No ensucia el Python del servidor.
- Facil de reiniciar con `docker compose restart`.

Alternativa sencilla sin Docker: clonar repo, crear `.venv`, instalar `deploy/requirements_prod.txt` y lanzar API/dashboard con `nohup` o `screen`. Es mas rapida si Docker no esta disponible, pero menos limpia.

## Hugging Face Spaces

Para este proyecto interesa un Space con `sdk: docker`, porque necesitamos API y dashboard juntos. Un Space Streamlit simple es mas comodo, pero se queda corto para servir FastAPI, endpoints de imagenes y captura `/screen-capture` en el mismo paquete.

El `Dockerfile` de la raiz esta preparado para Spaces: lanza FastAPI en `127.0.0.1:8000`, Streamlit en `127.0.0.1:8501` y Nginx en `7860`. Hugging Face expone por defecto el puerto `7860` en Spaces Docker.

Estrategia recomendada:

- Crear un Space Docker.
- Subir o sincronizar el repositorio con `Dockerfile`, `api/`, `dashboard/`, `geo_pipeline/`, `exports/best_fire_smoke.onnx`, `dashboard/static/geo/` y `Datasets Territoriales/`.
- Usar secretos del Space para `AEMET_API_KEY`, `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.
- Configurar variables no secretas si se desea ajustar umbrales: `CONF_THRESHOLD_FIRE`, `CONF_THRESHOLD_SMOKE`, `ALERT_CONFIRM_SECONDS`, etc.

Limitacion importante: la persistencia de SQLite y las imagenes de alerta no debe asumirse como permanente salvo que se configure almacenamiento persistente o se envie el historial a un servicio externo.

## AWS

Opcion sencilla: AWS App Runner con imagen Docker.

Flujo:

1. Construir imagen.
2. Subirla a Amazon ECR.
3. Crear servicio App Runner desde esa imagen.
4. Configurar variables de entorno/secrets.

Es adecuado para demo web de CPU con ONNX. Si el proyecto necesita GPU, historico persistente serio o varias piezas separadas, conviene mirar ECS/Fargate o EC2.

## Azure

Opcion sencilla: Azure Container Apps.

Flujo:

1. Construir imagen.
2. Subir a Azure Container Registry o desplegar desde repo.
3. Crear Container App para API/dashboard.
4. Configurar secretos y variables de entorno.

Para una cuenta academica, Container Apps suele ser una ruta razonable por simplicidad. Si se necesita GPU o control fino de VM, Azure VM seria mas directo aunque menos automatico.

## Recomendacion

Para memoria y defensa:

1. Local: `.venv` para desarrollo.
2. IsardVDI: Docker Compose desde GitHub.
3. Hugging Face: Space Docker como demo publica.
4. Cloud academico: Azure Container Apps o AWS App Runner si basta CPU; VM/ECS si se requiere mas control.
