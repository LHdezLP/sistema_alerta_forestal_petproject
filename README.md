# Fire Smoke AI - Vigilancia forestal con YOLOv8

Aplicativo local para detectar `fire` y `smoke` con YOLOv8 y contextualizar cada alerta sobre un mapa territorial de Gran Canaria. El proyecto combina tres piezas:

- Un modelo de deteccion entrenado con imagenes de fuego, humo y negativos.
- Una API FastAPI que ejecuta inferencia, registra alertas y calcula riesgo territorial.
- Un dashboard Streamlit con mapa, KPIs, historial, prueba por imagen y prueba por pantalla/video.

Forma parte del Trabajo Final del Master de Especializacion en Inteligencia Artificial y Big Data del IES El Rincon.

## Que puede hacer

- Detectar fuego y humo en imagenes, carpetas, videos, GIFs o pantalla completa.
- Probar el flujo completo desde una imagen subida al dashboard.
- Probar un video de YouTube en pantalla completa enviando frames a la API.
- Registrar alertas en SQLite con clase, confianza, imagen anotada, coordenadas y nivel de riesgo.
- Calcular riesgo territorial usando ZARI, combustible, historico NASA FIRMS y meteorologia AEMET.
- Mostrar en mapa capas de ZARI, combustible, hotspots FIRMS, camara simulada y alertas recientes.
- Seleccionar un foco con click en el mapa y recalcular el riesgo inmediato de su entorno.
- Reiniciar el historial de alertas desde el dashboard para mantener limpia la demo.
- Enviar alertas por Telegram si las credenciales estan configuradas.

## Estructura principal

```text
.
|-- api/                         # FastAPI: inferencia, riesgo, alertas y Telegram
|-- dashboard/                   # Streamlit + Folium
|-- geo_pipeline/                # Carga territorial, AEMET, FIRMS, ZARI, combustible
|-- data/
|   |-- raw/                     # Datos originales extraidos
|   `-- processed/               # Dataset YOLO final
|-- Datasets Territoriales/      # FIRMS, ZARI y combustible de Canarias
|-- models/runs/                 # Runs de entrenamiento YOLO
|-- exports/                     # Modelo actual .pt y .onnx
|-- notebooks/                   # Exploracion, preparacion, entrenamiento y territorio
|-- inference.py                 # Inferencia local directa
|-- screen_to_api.py             # Utilidad de desarrollo para captura por consola
|-- Seguimiento.md               # Registro de fases, resultados y decisiones
`-- README.md
```

## Instalacion local

Desde la raiz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

El entorno usado en este proyecto incluye GPU NVIDIA RTX 4070, CUDA y Python 3.10+. Para entrenamiento con GPU, comprueba en Python:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

## Configuracion

El archivo `.env` local contiene las claves de AEMET y Telegram. No debe subirse ni copiarse a documentacion publica.

Variables importantes:

```text
AEMET_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
MODEL_PATH=exports/best_fire_smoke.onnx
MODEL_PT_FALLBACK=exports/best_fire_smoke.pt
CONF_THRESHOLD_FIRE=0.25
CONF_THRESHOLD_SMOKE=0.10
ALERT_COOLDOWN_SECONDS=30
ALERT_CONFIRM_SECONDS=5
TEMPORAL_MAX_GAP_SECONDS=4
SIMULATE_RANDOM_ALERT_POINT=1
```

`SIMULATE_RANDOM_ALERT_POINT=1` hace que cada alerta se ubique en una coordenada aleatoria dentro de 5 km de la camara simulada. Esto permite demostrar mejor el flujo territorial sin fijar siempre el foco en el mismo punto.

## Arrancar el aplicativo

Terminal 1, API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, dashboard:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

URLs:

- API health: http://127.0.0.1:8000/health
- Riesgo actual: http://127.0.0.1:8000/risk
- Alertas registradas: http://127.0.0.1:8000/alerts
- Dashboard: http://127.0.0.1:8501

## Probar el flujo completo con imagen

1. Abre http://127.0.0.1:8501.
2. En la barra lateral, sube una imagen `.jpg` o `.png`.
3. Pulsa `Analizar imagen`.
4. Si el modelo detecta fuego o humo, la API:
   - ejecuta inferencia con `exports/best_fire_smoke.onnx`;
   - calcula el riesgo territorial para el foco simulado;
   - guarda la imagen anotada en `api/alert_images/`;
   - registra la alerta en `api/alerts.db`;
   - intenta enviar Telegram si las credenciales son validas.
5. Revisa el historial en el dashboard o abre http://127.0.0.1:8000/alerts.

El dashboard no vuelve a analizar la imagen automaticamente en cada refresco. Solo llama a `/predict` cuando se pulsa `Analizar imagen`.

## Analizar riesgo de un foco en el mapa

El mapa es interactivo:

1. Haz click sobre cualquier punto del mapa.
2. El dashboard toma ese punto como foco seleccionado.
3. La API recalcula `/risk` usando esa latitud/longitud.
4. Los anillos se dibujan alrededor del foco, no alrededor de la camara.
5. El panel `Riesgo del foco` muestra el indice, la zona ZARI, combustible ponderado y FIRMS historicos del entorno.

Los anillos tienen significado operativo:

- `Riesgo inmediato`: 1 km alrededor del foco, mas oscuro.
- `Riesgo alto`: 2.5 km, intermedio.
- `Riesgo potencial`: 5 km, mas tenue.

La intensidad se acentua con el peso ponderado de combustible en 5 km, pero el color base de cada anillo se mantiene estable para que sea comparable entre focos.

Para limpiar la demo, en la barra lateral activa `Confirmar limpieza` y pulsa `Reiniciar historial`. Esto borra las alertas SQLite y las imagenes anotadas de alerta.

Las capas del mapa se controlan desde el sidebar (`ZARI`, `Combustible`, `FIRMS historico`, `Alertas recientes`) para que su estado no se pierda al cambiar de foco o refrescar el dashboard.

El foco muestra una flecha de viento cuando AEMET responde. La flecha sale desde el foco y apunta hacia donde empuja el viento. Al pasar el cursor se muestran velocidad, temperatura y los factores de riesgo asociados a viento y temperatura.

El indice de riesgo no depende solo de estar dentro de ZARI. Se ponderan combustible, FIRMS historico, viento y temperatura; temperaturas altas empiezan a incrementar el factor termico por encima de 25 C y pesan mas a partir de 30 C.

## Probar el flujo completo con video o YouTube desde el frontend

La deteccion de pantalla/video se activa desde el dashboard. El usuario no necesita ejecutar comandos adicionales.

1. Abre http://127.0.0.1:8501.
2. En la barra lateral, pulsa `Abrir detector de pantalla`.
3. En la nueva pagina, pulsa `Iniciar captura`.
4. El navegador pedira compartir una pantalla, ventana o pestana.
5. Selecciona el video de YouTube, una ventana o la pantalla completa.
6. Cada pocos segundos el frontend envia un frame a la API.
7. En video/pantalla no se alerta por un unico frame: la deteccion debe mantenerse durante `ALERT_CONFIRM_SECONDS` segundos, por defecto 5.
8. Si se confirma, se registra la alerta, se calcula riesgo territorial y se envia Telegram.
9. Para parar, pulsa `Detener` o deja de compartir pantalla desde el navegador.

La pagina de captura tambien puede abrirse directamente en http://127.0.0.1:8000/screen-capture.

Nota: la captura de pantalla del navegador requiere un contexto seguro. En local funciona con `localhost`/`127.0.0.1`; en servidor remoto conviene servir por HTTPS.

## Inferencia directa sin API

`inference.py` sirve para probar el modelo sin dashboard ni registro de alertas.

```powershell
.\.venv\Scripts\python.exe inference.py --source ruta\imagen.jpg --model exports\best_fire_smoke.pt
.\.venv\Scripts\python.exe inference.py --source ruta\video.mp4 --model exports\best_fire_smoke.pt --show
.\.venv\Scripts\python.exe inference.py --source screen --model exports\best_fire_smoke.pt --conf 0.15 --show
```

Para humo puede ser util bajar el umbral a `--conf 0.10` o `--conf 0.15`. Para fuego, `0.25` suele ser mas conservador.

## Estado del modelo actual

El modelo activo conservado para pruebas es:

- PyTorch: `exports/best_fire_smoke.pt`
- ONNX API: `exports/best_fire_smoke.onnx`
- Run origen: `models/runs/fire_smoke_v3_balanced`

Metricas de test del modelo actual:

| Clase | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| fire | 0.618 | 0.609 | 0.623 | 0.311 |
| smoke | 0.832 | 0.582 | 0.678 | 0.289 |
| media | 0.725 | 0.596 | 0.650 | 0.300 |

Observaciones manuales:

- El modelo detecta llamas con bastante sensibilidad.
- A veces clasifica humo como fuego.
- Hay falsos positivos de fuego sobre objetos rojizos y baja resolucion, como adornos o banderines.
- En pantalla normal, antes de reproducir video, no se observaron detecciones espurias.

## Entrenamiento y notebooks

Orden recomendado:

1. `notebooks/00_exploracion_dataset.ipynb`: explora datasets y formatos.
2. `notebooks/01_preparacion_dataset.ipynb`: genera `data/processed/` y `data/dataset.yaml`.
3. `notebooks/02_entrenamiento_evaluacion.ipynb`: entrena, evalua y exporta.
4. `notebooks/03_analisis_territorial.ipynb`: analiza FIRMS, ZARI, combustible y exporta GeoJSON.

Todas las decisiones de dataset, entrenamiento, resultados e interpretacion se documentan en `Seguimiento.md`.

## Datos usados

- D-Fire: imagenes con etiquetas YOLO de fuego y humo.
- Open Wildfire Smoke Dataset: refuerzo de humo forestal.
- Cloud/Fog Dataset: negativos para reducir falsos positivos.
- NASA FIRMS: hotspots historicos.
- ZARI Canarias: zonas de alto riesgo de incendio.
- Modelos de combustible por isla: combustible de Gran Canaria.

Los datos originales se mantienen en `data/raw/` y no deben modificarse.

## Despliegue

La carpeta `deploy/` contiene:

- `Dockerfile`
- `docker-compose.yml`
- `requirements_prod.txt`
- `.env.example` con placeholders
- `README_deploy.md`

Ademas, el `Dockerfile` de la raiz esta pensado para Hugging Face Spaces Docker: publica una unica app por el puerto `7860` y enruta internamente dashboard + API.

Para produccion se prioriza ONNX (`exports/best_fire_smoke.onnx`) y se evita depender de `torch` o `ultralytics` en la API desplegada.

Rutas recomendadas:

- IsardVDI: clonar el proyecto desde GitHub y levantar `api` + `dashboard` con Docker Compose.
- Hugging Face: Space tipo Docker, no Streamlit simple, porque necesitamos servir API y dashboard.
- Azure: Azure Container Apps si basta CPU y despliegue containerizado.
- AWS: revisar App Runner solo si la cuenta ya permite usarlo; AWS indica que App Runner no aceptara nuevos clientes desde el 30 de abril de 2026. Como alternativa, ECS/Fargate o una VM academica.
