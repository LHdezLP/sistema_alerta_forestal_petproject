---
title: Sistema Alerta Forestal
sdk: docker
app_port: 7860
pinned: false
---

# Fire Smoke AI - Sistema de alerta forestal

Aplicacion para detectar `fire` y `smoke` con un modelo YOLOv8 exportado a ONNX, registrar alertas y contextualizarlas sobre un mapa territorial de Gran Canaria con ZARI, combustible, NASA FIRMS y meteorologia AEMET.

Proyecto del Trabajo Final del Master de Especializacion en Inteligencia Artificial y Big Data, IES El Rincon.

## Que incluye el repositorio

- API FastAPI en `api/`.
- Dashboard Streamlit en `dashboard/`.
- Pipeline territorial en `geo_pipeline/`.
- Modelo activo de demo en `exports/best_fire_smoke.onnx` y `exports/best_fire_smoke.pt`.
- Datos territoriales necesarios para Gran Canaria: ZARI, NASA FIRMS y combustible de Gran Canaria.
- Docker Compose para servidor Linux/Isard en `deploy/`.
- Dockerfile raiz para Hugging Face Spaces Docker.
- Notebooks y scripts de entrenamiento/reproducibilidad.
- Registro de decisiones y resultados en `Seguimiento.md`.

No se incluyen `.env`, `.venv`, datasets crudos, datasets procesados, runs de entrenamiento, modelos candidatos ni alertas generadas.

## Requisitos

Para ejecucion local nativa en Windows:

- Python 3.11 o superior.
- Git.
- Git LFS, necesario para descargar el modelo y algunos datos territoriales binarios.
- Navegador moderno.
- Opcional: GPU NVIDIA/CUDA para entrenamiento. La aplicacion desplegada usa ONNX CPU.

Para Docker local, Isard o Hugging Face:

- Docker y Docker Compose.
- Acceso a red para AEMET y Telegram si se quieren esas integraciones.

## Variables de entorno

El proyecto no sube secretos. Crea un archivo `.env` en la raiz para ejecucion local nativa, o `deploy/.env` para Docker Compose.

Ejemplo:

```env
AEMET_API_KEY=pon_aqui_tu_api_key_de_aemet
TELEGRAM_BOT_TOKEN=pon_aqui_tu_token_de_telegram
TELEGRAM_CHAT_ID=pon_aqui_tu_chat_id
MODEL_PATH=exports/best_fire_smoke.onnx
MODEL_PT_FALLBACK=exports/best_fire_smoke.pt
CONF_THRESHOLD_FIRE=0.25
CONF_THRESHOLD_SMOKE=0.10
ALERT_COOLDOWN_SECONDS=30
ALERT_CONFIRM_SECONDS=5
TEMPORAL_MAX_GAP_SECONDS=4
SIMULATE_RANDOM_ALERT_POINT=1
```

Notas:

- AEMET y Telegram son opcionales para arrancar, pero si no se configuran no habra meteorologia real ni envio de avisos.
- `ALERT_CONFIRM_SECONDS=5` hace que video/pantalla solo genere alerta si la deteccion persiste durante 5 segundos.
- En imagenes sueltas se alerta por confianza, porque el tiempo no aplica.
- `SIMULATE_RANDOM_ALERT_POINT=1` coloca alertas en un punto aleatorio dentro de 5 km de la camara simulada para hacer la demo territorial mas clara.

## Ejecucion local nativa

Desde PowerShell:

```powershell
git clone https://github.com/LHdezLP/sistema_alerta_forestal_petproject.git
cd sistema_alerta_forestal_petproject
git lfs pull
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item deploy\.env.example .env
notepad .env
```

Arranca la API en una terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Arranca el dashboard en otra terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

Comprueba:

- API: http://127.0.0.1:8000/health
- Documentacion API: http://127.0.0.1:8000/docs
- Dashboard: http://127.0.0.1:8501
- Captura de pantalla/video: http://127.0.0.1:8000/screen-capture

Si `/health` devuelve `{"status":"ok","model_loaded":true,"db_ok":true}`, la API esta cargada.

## Probar una imagen

1. Abre http://127.0.0.1:8501.
2. En la barra lateral, sube una imagen `.jpg`, `.jpeg` o `.png`.
3. Pulsa `Analizar imagen`.
4. Si se detecta fuego o humo, la API registra la alerta, guarda la imagen anotada y actualiza el historial.
5. Si Telegram esta configurado, intenta enviar aviso.

La imagen no se reenvia automaticamente en cada refresco: solo se analiza al pulsar el boton.

Logica de alerta en imagen:

- Si `/predict` devuelve al menos una deteccion por encima de umbral, se registra alerta.
- No se exige persistencia temporal porque una imagen estatica no tiene duracion.
- El foco se situa en una coordenada aleatoria dentro de 5 km de la camara si `SIMULATE_RANDOM_ALERT_POINT=1`.
- La alerta puede no enviarse a Telegram si faltan credenciales o si Telegram rechaza la peticion.

## Modo simulacion de alerta

El modo simulacion sirve para probar el flujo territorial sin depender del modelo. Al activarlo aparece el boton `Generar alerta simulada`.

Al pulsarlo:

- No se analiza ninguna imagen.
- Se crea una alerta artificial de clase `fire`.
- Se calcula el riesgo territorial del foco simulado.
- Se inserta en el historial.
- Si Telegram esta configurado, se envia un mensaje sin imagen anotada.

Sirve para comprobar mapa, historial, foco aleatorio, indice territorial y Telegram. No sirve para medir la calidad del modelo.

## Probar un video o YouTube desde el frontend

1. Abre el dashboard.
2. Pulsa `Abrir detector de pantalla`.
3. En la nueva pagina, pulsa `Iniciar captura`.
4. El navegador pedira compartir pantalla, ventana o pestana.
5. Selecciona el video de YouTube, la ventana o la pantalla completa.
6. Deja correr el video. El navegador enviara frames a la API.
7. Si una deteccion se mantiene durante `ALERT_CONFIRM_SECONDS`, se crea alerta.
8. Para parar, pulsa `Detener` o deja de compartir pantalla desde el navegador.

En local funciona con `localhost` o `127.0.0.1`. En remoto, la captura de pantalla del navegador normalmente necesita HTTPS o una configuracion segura del navegador.

Logica de alerta en pantalla/video:

- El navegador captura un frame cada `Intervalo (s)`, por defecto 2 segundos.
- Cada frame se envia a `/predict` con `temporal_confirm=true`.
- Puede haber detecciones visibles sin alerta.
- Para crear alerta, la misma clase (`fire` o `smoke`) debe mantenerse durante `ALERT_CONFIRM_SECONDS`, por defecto 5 segundos.
- Si entre detecciones pasan mas de `TEMPORAL_MAX_GAP_SECONDS`, por defecto 4 segundos, la sesion temporal se reinicia.
- Tras una alerta, `ALERT_COOLDOWN_SECONDS`, por defecto 30 segundos, evita spam de alertas repetidas.
- Con intervalo de 2 segundos normalmente hacen falta varios frames positivos seguidos para confirmar. Si el video cambia rapido, baja el intervalo a 1 segundo.

## Uso del mapa

- Click en el mapa: cambia el foco y recalcula el riesgo territorial.
- Anillos: riesgo inmediato, alto y potencial alrededor del foco seleccionado.
- Capas: ZARI, combustible, FIRMS historico y alertas recientes.
- Flecha de viento: aparece cuando AEMET responde; al pasar el cursor muestra viento, temperatura y efecto en riesgo.
- `Reiniciar historial`: borra alertas SQLite e imagenes anotadas generadas.

Paneles del dashboard:

- `Riesgo del foco`: indice 0-1 calculado para el foco seleccionado o para el foco de alerta.
- `Meteorologia`: ultima observacion AEMET cercana a la camara; viento y temperatura afectan al indice.
- `Contexto territorial`: ZARI, zona, combustible principal, peligrosidad ponderada y FIRMS historico.
- `Historial de alertas`: alertas SQLite recientes generadas por imagen, pantalla/video o simulacion.

Indice territorial:

- ZARI aporta contexto estructural.
- Combustible ponderado en 5 km es el factor de mayor peso.
- FIRMS historico representa recurrencia de focos.
- Viento y temperatura elevan el riesgo operativo; la temperatura empieza a pesar por encima de 25 C y se nota mas desde 30 C.
- Los combustibles `0` y `11` se consideran sin combustible/no combustibles y no dominan la lista de combustibles presentes.

Modelos de combustible:

- La capa original de Gran Canaria usa codigos numericos `mc`.
- Cuando existe equivalencia operativa clara, el dashboard muestra descripciones como `Pastizal/herbaceas`, `Matorral/pastizal`, `Matorral-arbolado` o `Arbolado con sotobosque`.
- Algunas etiquetas son agrupaciones descriptivas para hacer legible la demo; el codigo original se mantiene en la tabla para trazabilidad.

## Ejecucion con Docker local

Docker usa el modelo ONNX y no instala PyTorch ni Ultralytics.

```powershell
git clone https://github.com/LHdezLP/sistema_alerta_forestal_petproject.git
cd sistema_alerta_forestal_petproject\deploy
Copy-Item .env.example .env
notepad .env
docker compose up -d --build
docker compose ps
```

URLs:

- API: http://localhost:8000
- Dashboard: http://localhost:8501

Comprobaciones:

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8501/_stcore/health
```

Parar:

```powershell
docker compose down
```

Ver logs:

```powershell
docker compose logs -f
```

## Despliegue en Isard

Ruta recomendada: maquina Ubuntu con Docker Compose.

1. Entra en tu escritorio/maquina Ubuntu de Isard.
2. Abre terminal.
3. Instala Docker si no esta instalado:

```bash
docker --version
docker compose version
```

Si esos comandos fallan, instala Docker siguiendo la politica del centro. En Ubuntu suele ser:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Cierra sesion y vuelve a entrar para que el grupo `docker` aplique.

Si `docker compose version` no existe y `docker-compose` falla con `No module named 'distutils'`, instala Compose v2 manualmente:

```bash
cd ~
mkdir -p ~/.docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v5.1.4/docker-compose-linux-x86_64 -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose
docker compose version
```

Si `docker compose` existe pero aparece `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`, el usuario no tiene permisos sobre Docker. Solucion temporal:

```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo cp ~/.docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
sudo docker compose version
sudo docker compose up -d --build
```

Solucion persistente:

```bash
sudo usermod -aG docker $USER
newgrp docker
docker ps
docker compose up -d --build
```

Si `newgrp docker` no aplica el permiso, cierra sesion en Isard, vuelve a entrar y repite `docker ps`.

4. Clona el repositorio:

```bash
git clone https://github.com/LHdezLP/sistema_alerta_forestal_petproject.git
cd sistema_alerta_forestal_petproject/deploy
```

5. Configura variables:

```bash
cp .env.example .env
nano .env
```

En Isard cambia al menos:

```env
API_PUBLIC_URL=http://IP_O_DOMINIO_DE_ISARD:8000
API_PORT=8000
DASHBOARD_PORT=8501
```

Y rellena si quieres:

```env
AEMET_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

6. Levanta servicios:

```bash
docker compose up -d --build
```

7. Comprueba:

```bash
docker compose ps
docker compose logs -f
curl http://localhost:8000/health
curl http://localhost:8501/_stcore/health
```

8. Abre desde navegador:

- Dashboard: `http://IP_O_DOMINIO_DE_ISARD:8501`
- API: `http://IP_O_DOMINIO_DE_ISARD:8000/health`
- Captura: `http://IP_O_DOMINIO_DE_ISARD:8000/screen-capture`

9. Si no carga desde fuera, revisa en Isard:

- Que los puertos `8000` y `8501` esten publicados o permitidos.
- Que la maquina no tenga firewall bloqueando esos puertos.
- Que `API_PUBLIC_URL` apunte a la URL visible desde tu navegador, no a `localhost`.

Comandos utiles en Isard:

```bash
docker compose restart
docker compose logs api -f
docker compose logs dashboard -f
docker compose down
git pull
docker compose up -d --build
```

### Arranque habitual en Isard

Cuando vuelvas a abrir la maquina de Isard otro dia, normalmente no hace falta reinstalar nada. Entra en la terminal y ejecuta:

```bash
cd ~/Desktop/sistema_alerta_forestal_petproject/deploy
sudo docker compose up -d
```

Si has cambiado codigo en GitHub y quieres actualizar antes de arrancar:

```bash
cd ~/Desktop/sistema_alerta_forestal_petproject
git pull
cd deploy
sudo docker compose up -d --build
```

Comprobar que esta vivo:

```bash
sudo docker compose ps
curl http://localhost:8000/health
curl http://localhost:8501/_stcore/health
```

Abrir desde el navegador:

```text
http://IP_O_DOMINIO_DE_ISARD:8501
```

Parar la aplicacion:

```bash
cd ~/Desktop/sistema_alerta_forestal_petproject/deploy
sudo docker compose down
```

Ver logs si algo falla:

```bash
sudo docker compose logs -f
```

## Despliegue en Hugging Face Spaces

Usa un Space con SDK Docker. El `Dockerfile` de la raiz lanza FastAPI, Streamlit y Nginx en el puerto `7860`.

1. Entra en https://huggingface.co/spaces.
2. Pulsa `Create new Space`.
3. Elige:
   - Owner: tu usuario.
   - Space name: por ejemplo `sistema-alerta-forestal`.
   - SDK: `Docker`.
   - Docker template: `Blank`.
   - Hardware: CPU basic para demo.
   - Storage Bucket: desactivado.
   - Dev Mode: desactivado.
   - Visibility: public o private.
4. En `Settings > Variables and secrets`, crea secretos:
   - `AEMET_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Desde local, anade el Space como remoto y empuja:

```powershell
git remote add hf https://huggingface.co/spaces/TU_USUARIO/sistema-alerta-forestal
git push hf main:main
```

Si pide credenciales:

- Usuario: tu usuario de Hugging Face.
- Password: token de Hugging Face con permiso de escritura. La contrasena normal ya no sirve para `git push`.

No pegues el token en archivos ni en el chat.

Crear token:

1. En Hugging Face, abre tu perfil.
2. Entra en `Settings`.
3. Abre `Access Tokens`.
4. Crea un token con permiso de escritura (`Write`) o un fine-grained token con permiso de escritura sobre el Space.
5. Copia el token una sola vez y usalo como password cuando Git lo pida.

Si Git no pregunta de nuevo y sigue fallando por credenciales antiguas en Windows, borra la credencial cacheada:

```powershell
@"
protocol=https
host=huggingface.co

"@ | git credential-manager erase
```

Luego repite:

```powershell
git push hf main:main
```

Si el Space fue creado con plantilla `Blank` y ya tenia un commit inicial, puede rechazar el primer push. En ese caso, solo para un Space recien creado:

```powershell
git push hf main:main --force
```

6. En la pagina del Space, abre `Logs` y espera a que termine el build.
7. Cuando aparezca `Running`, abre la URL publica del Space.

Notas importantes:

- Hugging Face expone un unico puerto. Por eso el Dockerfile raiz usa Nginx en `7860`.
- El historial SQLite y las imagenes de alerta no deben considerarse persistentes en Spaces sin almacenamiento persistente.
- La captura de pantalla desde navegador puede depender de HTTPS y permisos del navegador. En Hugging Face deberia funcionar mejor que en HTTP puro porque el Space se sirve por HTTPS.

## Entrenamiento

Los notebooks de entrenamiento estan en `notebooks/`. El modelo activo del repositorio es el modelo de demo actual, no los candidatos descartados.

Orden recomendado:

1. `notebooks/00_exploracion_dataset.ipynb`
2. `notebooks/01_preparacion_dataset.ipynb`
3. `notebooks/02_entrenamiento_evaluacion.ipynb`
4. `notebooks/03_analisis_territorial.ipynb`

Las fases, metricas, problemas detectados y mejoras sugeridas estan documentadas en `Seguimiento.md`.

## Estado del modelo activo

Modelo activo:

- `exports/best_fire_smoke.pt`
- `exports/best_fire_smoke.onnx`

Metricas de test del modelo activo:

| Clase | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| fire | 0.618 | 0.609 | 0.623 | 0.311 |
| smoke | 0.832 | 0.582 | 0.678 | 0.289 |
| media | 0.725 | 0.596 | 0.650 | 0.300 |

Limitaciones observadas:

- A veces clasifica humo como fuego.
- Puede marcar objetos rojizos de baja resolucion como fuego.
- Detecta llamas con sensibilidad razonable, pero aun necesita mejora de precision y separacion fuego/humo.
