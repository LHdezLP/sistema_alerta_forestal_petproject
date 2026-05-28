# agent_02_dashboard.md â€” Pipeline territorial, backend de alertas y dashboard

## Contexto y punto de partida

Este fichero es la **segunda fase** del proyecto. El entorno ya estÃ¡ montado por `agent_01_training.md`. No recrear carpetas ni ficheros existentes. Leer la estructura del proyecto antes de escribir nada.

El proyecto completo estÃ¡ en la carpeta raÃ­z que el usuario indique. La estructura relevante que ya existe:
```
<raiz>/
â”œâ”€â”€ data/processed/          # dataset YOLO ya preparado
â”œâ”€â”€ models/runs/             # entrenamientos YOLO
â”œâ”€â”€ exports/                 # modelo best_fire_smoke.pt y .onnx
â”œâ”€â”€ inference.py             # ya existe, no modificar
â”œâ”€â”€ requirements.txt         # ya existe
â””â”€â”€ Datasets Territoriales/  # â† NUEVA, creada manualmente por el usuario
    â”œâ”€â”€ NASA Firms/
    â”œâ”€â”€ ZARI/
    â””â”€â”€ Modelos de Combustible por Isla/
        â”œâ”€â”€ Gran Canaria/
        â”œâ”€â”€ Gomera/
        â”œâ”€â”€ Hierro/
        â”œâ”€â”€ Tenerife/
        â””â”€â”€ La Palma/
```

---

## Paso 0 â€” AnÃ¡lisis previo obligatorio

Antes de escribir ningÃºn fichero:

1. Inspecciona `Datasets Territoriales/` y lista todos los ficheros presentes en cada subcarpeta (extensiones, nombres, tamaÃ±os aproximados).
2. Para `NASA Firms/`: detecta si los ficheros son CSV, SHP u otro formato. Identifica las columnas disponibles. Si hay varios ficheros, determina si son aÃ±os distintos o fuentes distintas (MODIS vs VIIRS).
3. Para `ZARI/`: detecta el SHP principal e inspecciona sus atributos (campos del .dbf).
4. Para `Modelos de Combustible por Isla/Gran Canaria/`: detecta el SHP e inspecciona sus atributos, especialmente el campo que contiene el cÃ³digo de modelo de combustible.
5. Con toda esa informaciÃ³n, adapta rutas y nombres de campo en el cÃ³digo antes de generarlo. Si algÃºn campo tiene un nombre distinto al asumido en este documento, usa el nombre real e incluye un comentario `# ADAPTADO: campo real = X`.

---

## Ãrea geogrÃ¡fica de trabajo

El proyecto se acota al **municipio de Tejeda, Gran Canaria**, tomando como referencia el incendio forestal de agosto de 2023, uno de los mÃ¡s graves de la historia reciente de la isla.

**Punto de cÃ¡mara simulada (hardcodeado):**
```python
CAMERA = {
    "nombre": "CÃ¡mara Forestal â€” Tejeda GC (simulada)",
    "lat": 27.9938,
    "lon": -15.5963,
    "descripcion": "Punto de vigilancia simulado en el tÃ©rmino municipal de Tejeda, "
                   "Ã¡rea afectada por el incendio de agosto de 2023."
}
```

**Radios de anÃ¡lisis:**
```python
RADIO_ANILLOS_KM = [1.0, 2.5, 5.0]   # tres anillos concÃ©ntricos en el mapa
RADIO_FIRMS_KM   = 15.0               # radio de bÃºsqueda de hotspots histÃ³ricos
RADIO_AEMET_KM   = 50.0               # radio de bÃºsqueda de estaciÃ³n AEMET mÃ¡s cercana
```

**Bounding box de Gran Canaria** (para filtrado espacial):
```python
GC_BBOX = {
    "lon_min": -15.85, "lon_max": -15.35,
    "lat_min":  27.70, "lat_max":  28.20
}
```

---

## Paso 1 â€” Nuevas carpetas a crear

Crear dentro de la raÃ­z del proyecto:

```
geo_pipeline/
    __init__.py
    firms_loader.py
    zari_loader.py
    combustible_loader.py
    risk_index.py
    aemet_client.py
    geojson_export.py

api/
    __init__.py
    main.py
    models.py
    alerts_db.py
    telegram_bot.py
    config.py

dashboard/
    app.py
    map_builder.py
    kpi_panel.py

deploy/
    Dockerfile
    requirements_prod.txt
    .env.example
    README_deploy.md

notebooks/
    03_analisis_territorial.ipynb    # aÃ±adir a los notebooks ya existentes
```

---

## Paso 2 â€” geo_pipeline/firms_loader.py

Carga y limpia los datos de NASA FIRMS. Expone una funciÃ³n principal:

```python
def cargar_firms(ruta_firms_dir: str, bbox: dict, confianza_minima: str = "nominal") -> gpd.GeoDataFrame:
```

LÃ³gica interna:
- Detectar automÃ¡ticamente si los ficheros son CSV o SHP. Si son CSV, leer con Pandas. Si son SHP, leer con GeoPandas.
- Si hay mÃºltiples ficheros (varios aÃ±os o satÃ©lites), concatenarlos todos.
- Filtrar por bounding box usando `GC_BBOX`.
- Filtrar por confianza: para VIIRS el campo `confidence` tiene valores `low`, `nominal`, `high`; para MODIS es numÃ©rico (0-100). Detectar cuÃ¡l es y aplicar el filtro correspondiente (`nominal` y `high` para VIIRS; >= 30 para MODIS).
- Columnas a conservar: `latitude`, `longitude`, `acq_date`, `acq_time`, `confidence`, `frp`, `bright_ti4` (o `brightness` si es MODIS). Las que no existan, omitirlas sin error.
- Convertir a GeoDataFrame con CRS EPSG:4326.
- Imprimir resumen: nÂº registros totales, nÂº tras filtrado, rango de fechas, distribuciÃ³n por confianza.
- Retornar el GeoDataFrame limpio.

FunciÃ³n auxiliar:
```python
def densidad_hotspots(gdf_firms: gpd.GeoDataFrame, punto_lat: float, punto_lon: float, radio_km: float) -> dict:
```
Calcula dentro del radio indicado:
- `n_hotspots`: nÃºmero total de puntos de calor
- `frp_max`: FRP mÃ¡ximo registrado (MW)
- `frp_medio`: FRP medio
- `anio_pico`: aÃ±o con mÃ¡s detecciones
- `mes_pico`: mes con mÃ¡s detecciones (nombre en espaÃ±ol)
- `n_por_anio`: dict {aÃ±o: conteo}

---

## Paso 3 â€” geo_pipeline/zari_loader.py

```python
def cargar_zari(ruta_zari_dir: str) -> gpd.GeoDataFrame:
```
- Detectar el fichero .shp en el directorio.
- Leer con GeoPandas, reproyectar a EPSG:4326 si es necesario.
- Retornar GeoDataFrame con al menos: geometry, nombre de zona (campo a detectar del .dbf), referencia BOC si existe.

```python
def punto_en_zari(gdf_zari: gpd.GeoDataFrame, lat: float, lon: float) -> dict:
```
- Retorna `{"dentro": bool, "zona": str_o_None, "boc": str_o_None}`.

---

## Paso 4 â€” geo_pipeline/combustible_loader.py

```python
def cargar_combustible_gc(ruta_gc_dir: str) -> gpd.GeoDataFrame:
```
- Cargar Ãºnicamente los datos de **Gran Canaria** desde `Modelos de Combustible por Isla/Gran Canaria/`.
- Detectar el campo que contiene el cÃ³digo de modelo de combustible (probablemente algo como `MOD_COMB`, `MODELO`, `FUEL_MODEL` o similar â€” usar el nombre real tras inspecciÃ³n).
- Reproyectar a EPSG:4326.

Tabla de pesos por modelo de combustible (Scott & Burgan adaptado Canarias). Usar esta tabla como diccionario en el cÃ³digo:

```python
PESOS_COMBUSTIBLE = {
    # Pastizales (GR) â€” alta velocidad de propagaciÃ³n
    "GR1": 0.40, "GR2": 0.55, "GR3": 0.65, "GR4": 0.75,
    "GR5": 0.70, "GR6": 0.80, "GR7": 0.85, "GR8": 0.80, "GR9": 0.85,
    # Matorral (SH) â€” alta intensidad
    "SH1": 0.55, "SH2": 0.65, "SH3": 0.70, "SH4": 0.75,
    "SH5": 0.80, "SH6": 0.85, "SH7": 0.90, "SH8": 0.85, "SH9": 0.90,
    # Arbolado con matorral (TU)
    "TU1": 0.45, "TU2": 0.50, "TU3": 0.60, "TU4": 0.65, "TU5": 0.70,
    # Hojarasca bajo arbolado (TL) â€” propagaciÃ³n lenta pero difÃ­cil extinciÃ³n
    "TL1": 0.30, "TL2": 0.35, "TL3": 0.40, "TL4": 0.45,
    "TL5": 0.50, "TL6": 0.45, "TL7": 0.55, "TL8": 0.50, "TL9": 0.60,
    # Sin combustible / agua / urbano
    "NB1": 0.00, "NB2": 0.00, "NB3": 0.00, "NB8": 0.00, "NB9": 0.00,
}
PESO_COMBUSTIBLE_DESCONOCIDO = 0.30   # valor por defecto si el cÃ³digo no estÃ¡ en la tabla
```

```python
def combustible_en_punto(gdf_comb: gpd.GeoDataFrame, lat: float, lon: float, radio_km: float) -> dict:
```
Retorna para el radio indicado:
- `codigo_predominante`: cÃ³digo del modelo con mÃ¡s superficie en el radio
- `descripcion`: texto descriptivo del modelo
- `peso`: valor numÃ©rico 0-1
- `distribucion`: dict {codigo: porcentaje_superficie} de los modelos presentes

---

## Paso 5 â€” geo_pipeline/aemet_client.py

```python
def obtener_datos_meteorologicos(lat: float, lon: float, api_key: str, radio_km: float = 50.0) -> dict:
```

Flujo:
1. Llamar a `https://opendata.aemet.es/opendata/api/observacion/convencional/todas` con la API key en el header `api_key`.
2. El endpoint devuelve un JSON con una URL temporal en el campo `datos`. Hacer una segunda peticiÃ³n a esa URL para obtener los datos reales.
3. Parsear el JSON resultante (lista de estaciones con sus observaciones).
4. Calcular distancia haversine desde cada estaciÃ³n al punto dado.
5. Seleccionar la estaciÃ³n mÃ¡s cercana dentro del radio.
6. Extraer y retornar:

```python
{
    "estacion_nombre": str,
    "estacion_id": str,
    "distancia_km": float,
    "temperatura": float,      # Â°C
    "humedad": float,          # %
    "viento_vel": float,       # km/h
    "viento_dir": float,       # grados 0-360
    "viento_dir_texto": str,   # "N", "NE", "E", etc.
    "precipitacion": float,    # mm
    "timestamp": str,          # ISO format
    "error": None              # o mensaje de error si falla
}
```

Si la llamada falla (sin conexiÃ³n, API key invÃ¡lida, sin estaciones en radio), retornar el dict con `error` relleno y el resto en None. **Nunca lanzar excepciÃ³n**, el dashboard debe funcionar aunque AEMET no responda.

Incluir funciÃ³n auxiliar:
```python
def grados_a_texto(grados: float) -> str:
```
Convierte 0-360 a texto ("N", "NNE", "NE", "ENE", "E", â€¦, 16 puntos cardinales).

---

## Paso 6 â€” geo_pipeline/risk_index.py

```python
def calcular_indice_riesgo(
    dentro_zari: bool,
    peso_combustible: float,
    densidad_firms: dict,
    datos_meteo: dict,
    n_hotspots_max_referencia: int = 50
) -> dict:
```

FÃ³rmula del Ã­ndice compuesto (todos los componentes normalizados a 0-1):

```python
w_zari        = 0.30
w_combustible = 0.30
w_firms       = 0.25
w_viento      = 0.15

factor_zari        = 1.0 if dentro_zari else 0.0
factor_combustible = peso_combustible  # ya estÃ¡ en 0-1
factor_firms       = min(densidad_firms.get("n_hotspots", 0) / n_hotspots_max_referencia, 1.0)
viento_vel         = datos_meteo.get("viento_vel") or 0.0
factor_viento      = min(viento_vel / 80.0, 1.0)  # 80 km/h = mÃ¡ximo esperado

indice = (w_zari        * factor_zari +
          w_combustible * factor_combustible +
          w_firms       * factor_firms +
          w_viento      * factor_viento)
```

Retornar:
```python
{
    "indice": float,          # 0.0 a 1.0
    "nivel": str,             # "BAJO", "MODERADO", "ALTO", "EXTREMO"
    "color_hex": str,         # "#2ecc71", "#f39c12", "#e67e22", "#c0392b"
    "componentes": {
        "zari": factor_zari,
        "combustible": factor_combustible,
        "firms": factor_firms,
        "viento": factor_viento
    }
}
```

Umbrales de nivel:
- 0.00 â€“ 0.30 â†’ BAJO â†’ `#2ecc71`
- 0.30 â€“ 0.55 â†’ MODERADO â†’ `#f39c12`
- 0.55 â€“ 0.75 â†’ ALTO â†’ `#e67e22`
- 0.75 â€“ 1.00 â†’ EXTREMO â†’ `#c0392b`

---

## Paso 7 â€” geo_pipeline/geojson_export.py

Genera los GeoJSON estÃ¡ticos que usarÃ¡ el mapa. Se ejecuta una sola vez (o cuando se actualicen los datos territoriales):

```python
def exportar_geojsons(ruta_base: str):
```

Exporta a `dashboard/static/geo/`:
- `zari_gc.geojson` â€” polÃ­gonos ZARI de Gran Canaria simplificados (tolerancia 0.001 grados para reducir tamaÃ±o)
- `combustible_gc.geojson` â€” polÃ­gonos de combustible de Gran Canaria con campo `peso` aÃ±adido, simplificados (tolerancia 0.0005)
- `firms_heatmap_gc.geojson` â€” puntos de calor histÃ³ricos de Gran Canaria (solo lat/lon/frp/aÃ±o, sin columnas innecesarias)
- `camara.geojson` â€” punto Ãºnico de la cÃ¡mara con sus metadatos
- `anillos_riesgo.geojson` â€” tres cÃ­rculos (1km, 2.5km, 5km) centrados en la cÃ¡mara, sin color todavÃ­a (el color lo asigna el dashboard segÃºn el Ã­ndice calculado en tiempo de ejecuciÃ³n)

Imprimir tamaÃ±o de cada fichero exportado. Si algÃºn GeoJSON supera 5MB, advertir y sugerir simplificaciÃ³n adicional.

---

## Paso 8 â€” api/config.py

```python
# Leer desde variables de entorno con defaults razonables
AEMET_API_KEY     = os.getenv("AEMET_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
MODEL_PATH         = os.getenv("MODEL_PATH", "exports/best_fire_smoke.onnx")
CONF_THRESHOLD_FIRE  = float(os.getenv("CONF_THRESHOLD_FIRE", "0.25"))
CONF_THRESHOLD_SMOKE = float(os.getenv("CONF_THRESHOLD_SMOKE", "0.10"))
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "30"))
```

---

## Paso 9 â€” api/alerts_db.py

Base de datos SQLite local para registro de alertas. Crear en `api/alerts.db`.

Tabla `alerts`:
```sql
CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    clase       TEXT NOT NULL,       -- "fire" o "smoke"
    confianza   REAL NOT NULL,
    imagen_path TEXT,                -- ruta a la imagen guardada con detecciones
    lat         REAL,
    lon         REAL,
    indice_riesgo REAL,
    nivel_riesgo  TEXT
);
```

Exponer funciones:
- `insertar_alerta(clase, confianza, imagen_path, lat, lon, indice, nivel) -> int`
- `obtener_alertas(limite=50) -> list[dict]`
- `obtener_ultima_alerta() -> dict | None`

---

## Paso 10 â€” api/telegram_bot.py

```python
def enviar_alerta_telegram(clase: str, confianza: float, indice_riesgo: dict, imagen_path: str = None):
```

- Si `TELEGRAM_BOT_TOKEN` o `TELEGRAM_CHAT_ID` estÃ¡n vacÃ­os, loguear advertencia y retornar sin error.
- Construir mensaje:
```
ðŸ”¥ ALERTA DE INCENDIO FORESTAL
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
DetecciÃ³n: FUEGO / HUMO
Confianza: 87%
Zona: Tejeda, Gran Canaria
Riesgo: ALTO (0.72)
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
ZARI: âœ… Zona declarada alto riesgo
Combustible: SH7 â€” Matorral denso (peso: 0.90)
Focos histÃ³ricos (15km): 34
Viento: 28 km/h Â· NE
Humedad: 22%
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
â± 14:32:07 UTC
```
- Si hay `imagen_path`, enviar como foto con el mensaje como caption usando `sendPhoto`.
- Si no hay imagen, enviar como `sendMessage`.
- Usar `requests`, no librerÃ­as de terceros para Telegram. Manejo de errores: si falla, loguear y continuar.

---

## Paso 11 â€” api/main.py

FastAPI con los siguientes endpoints:

### POST /predict
- Recibe: `multipart/form-data` con campo `file` (imagen).
- Carga el modelo ONNX desde `MODEL_PATH` usando `onnxruntime`.
- Ejecuta inferencia.
- Si hay detecciÃ³n con confianza >= umbral por clase:
  - Guarda la imagen con detecciones dibujadas en `api/alert_images/` con timestamp en el nombre.
  - Calcula Ã­ndice de riesgo (cargar datos territoriales en startup, no en cada request).
  - Inserta alerta en SQLite.
  - Llama a `enviar_alerta_telegram` en un background task (no bloquear la respuesta).
- Retorna JSON:
```json
{
  "detecciones": [
    {"clase": "fire", "confianza": 0.87, "bbox": [x1, y1, x2, y2]},
    {"clase": "smoke", "confianza": 0.62, "bbox": [x1, y1, x2, y2]}
  ],
  "alerta_enviada": true,
  "indice_riesgo": {"indice": 0.72, "nivel": "ALTO", "color_hex": "#e67e22"},
  "imagen_resultado_url": "/images/alert_20260524_143207.jpg"
}
```

### GET /risk
- Retorna el Ã­ndice de riesgo actual para la cÃ¡mara hardcodeada.
- Incluye todos los componentes del Ã­ndice y los datos meteorolÃ³gicos de AEMET.
- Cachear la respuesta de AEMET durante 10 minutos para no saturar la API.

### GET /alerts
- ParÃ¡metros opcionales: `limite` (default 50), `clase` (filtrar por "fire" o "smoke").
- Retorna lista de alertas del SQLite.

### GET /images/{filename}
- Sirve las imÃ¡genes guardadas en `api/alert_images/`.

### GET /geo/{filename}
- Sirve los GeoJSON estÃ¡ticos desde `dashboard/static/geo/`.

### GET /health
- Retorna `{"status": "ok", "model_loaded": bool, "db_ok": bool}`.

**Startup:** al arrancar la API, cargar en memoria:
- El modelo ONNX (una sola vez).
- Los GeoDataFrames de ZARI y combustible de Gran Canaria.
- Los puntos FIRMS filtrados a Gran Canaria.
- Calcular y cachear el Ã­ndice de riesgo base (sin datos de viento, que varÃ­an).

---

## Paso 12 â€” dashboard/map_builder.py

```python
def construir_mapa(indice_riesgo: dict, datos_meteo: dict, alertas: list, firms_points: gpd.GeoDataFrame) -> str:
```

Retorna HTML del mapa Folium como string (para embeber en Streamlit con `components.html`).

Capas del mapa (en orden de renderizado, de abajo a arriba):

**1. Base:** `CartoDB positron` (mÃ¡s limpio para datos temÃ¡ticos).

**2. ZARI Gran Canaria:** carga `zari_gc.geojson`. PolÃ­gonos con:
- Fill: rojo `#e74c3c`, opacidad 0.20
- Borde: rojo `#c0392b`, grosor 2
- Tooltip: nombre de zona

**3. Combustible Gran Canaria:** carga `combustible_gc.geojson`. Colorear cada polÃ­gono segÃºn el campo `peso`:
- 0.0â€“0.3 â†’ `#27ae60` (verde)
- 0.3â€“0.6 â†’ `#f1c40f` (amarillo)
- 0.6â€“0.8 â†’ `#e67e22` (naranja)
- 0.8â€“1.0 â†’ `#e74c3c` (rojo)
- Fill opacidad 0.35, borde 0.5px mismo color
- Tooltip: cÃ³digo modelo + descripciÃ³n + peso

**4. Mapa de calor FIRMS:** usar `folium.plugins.HeatMap` sobre los puntos de `firms_heatmap_gc.geojson`. Radio=15, blur=20, min_opacity=0.3. Usar `frp` como peso si estÃ¡ disponible.

**5. Anillos de riesgo:** tres cÃ­rculos centrados en `CAMERA`:
- Radio 1.0 km: fill `indice_riesgo["color_hex"]`, opacidad 0.50, borde sÃ³lido
- Radio 2.5 km: fill `indice_riesgo["color_hex"]`, opacidad 0.30, borde discontinuo
- Radio 5.0 km: fill `indice_riesgo["color_hex"]`, opacidad 0.15, borde punteado
- Tooltip en cada anillo: nivel de riesgo + Ã­ndice numÃ©rico

**6. Marcador de cÃ¡mara:** usar `folium.Marker` con Ã­cono personalizado. Si hay alertas recientes (Ãºltima < 5 minutos), usar Ã­cono de llama roja ðŸ”¥; si no, Ã­cono de cÃ¡mara gris ðŸ“·. Popup con: nombre de la cÃ¡mara, Ãºltima detecciÃ³n, timestamp.

**7. EstaciÃ³n AEMET:** marcador pequeÃ±o con Ã­cono de termÃ³metro. Popup con los datos meteorolÃ³gicos formateados.

**8. Alertas recientes en el mapa:** para cada alerta de las Ãºltimas 24h, aÃ±adir un cÃ­rculo pequeÃ±o (radio 200m) rojo semitransparente en las coordenadas de la cÃ¡mara. Si hay varias alertas, usar `folium.plugins.MarkerCluster`.

Control de capas (`folium.LayerControl`) para que el usuario pueda activar/desactivar cada capa.

Centrar el mapa en `CAMERA` con zoom inicial 13.

---

## Paso 13 â€” dashboard/app.py

AplicaciÃ³n Streamlit principal.

**Layout:** dos columnas, proporciÃ³n 7:3.
- Columna izquierda (70%): mapa Folium.
- Columna derecha (30%): KPIs y alertas.

**Columna derecha â€” secciones:**

*Bloque 1 â€” Indicador de riesgo global:*
Una mÃ©trica grande con color de fondo segÃºn el nivel:
```
RIESGO ACTUAL
â–“â–“â–“â–“â–“â–“â–“â–‘â–‘â–‘
ALTO â€” 0.72
```

*Bloque 2 â€” MeteorologÃ­a (AEMET):*
MÃ©tricas de Streamlit (`st.metric`):
- ðŸŒ¡ï¸ Temperatura
- ðŸ’§ Humedad
- ðŸ’¨ Viento (velocidad + direcciÃ³n)
- ðŸŒ§ï¸ PrecipitaciÃ³n
- Timestamp de la observaciÃ³n
- Nombre de la estaciÃ³n

*Bloque 3 â€” Contexto territorial:*
- Â¿Dentro de ZARI? â†’ badge verde/rojo
- Combustible predominante â†’ nombre + cÃ³digo + barra de peligrosidad visual (st.progress)
- Focos histÃ³ricos en 15km â†’ nÃºmero con delta respecto a la media de Canarias si es posible

*Bloque 4 â€” Historial de alertas:*
- Tabla `st.dataframe` con las Ãºltimas 10 alertas (timestamp, clase, confianza, nivel de riesgo)
- BotÃ³n "Ver imagen" para abrir la imagen de cada alerta

**Sidebar:**
- TÃ­tulo del proyecto y logo (si existe)
- BotÃ³n "ðŸ”„ Actualizar datos" que fuerza recarga de AEMET y recalcula el Ã­ndice
- Uploader de imagen manual (`st.file_uploader`) para probar la inferencia del modelo directamente desde el dashboard:
  - Al subir imagen â†’ POST a `/predict` â†’ mostrar imagen con detecciones + resultado del Ã­ndice
- Checkbox "Modo simulaciÃ³n de alerta" que manda una alerta de prueba a Telegram

**Frecuencia de actualizaciÃ³n:**
Usar `st.rerun()` con `time.sleep(60)` en un hilo separado, o mejor: aÃ±adir `st_autorefresh` de `streamlit-autorefresh` (pip install) con intervalo de 60 segundos.

---

## Paso 14 â€” Notebook 03: AnÃ¡lisis territorial

Crear `notebooks/03_analisis_territorial.ipynb` con:

**SecciÃ³n 1 â€” Carga y exploraciÃ³n de FIRMS:**
- Cargar con `firms_loader.cargar_firms()`
- Mostrar mapa estÃ¡tico (matplotlib) con todos los puntos de Gran Canaria
- Histograma de distribuciÃ³n temporal (incendios por aÃ±o y mes)
- Top 10 eventos por FRP mÃ¡ximo

**SecciÃ³n 2 â€” ZARI:**
- Cargar y visualizar los polÃ­gonos sobre un mapa base simple
- Tabla de zonas ZARI con Ã¡rea en kmÂ²
- Verificar si el punto de la cÃ¡mara cae dentro

**SecciÃ³n 3 â€” Combustible:**
- Cargar Gran Canaria y visualizar por tipo de combustible (mapa de colores)
- DistribuciÃ³n de superficie por modelo (grÃ¡fico de barras)
- AnÃ¡lisis del radio de 5km alrededor de la cÃ¡mara: quÃ© modelos predominan

**SecciÃ³n 4 â€” CÃ¡lculo del Ã­ndice de riesgo:**
- Ejecutar `risk_index.calcular_indice_riesgo()` para el punto de la cÃ¡mara
- Mostrar los componentes en un grÃ¡fico de radar (matplotlib)
- Mapa final con todos los elementos superpuestos (Folium)

**SecciÃ³n 5 â€” ExportaciÃ³n:**
- Llamar a `geojson_export.exportar_geojsons()` y confirmar los ficheros generados

---

## Paso 15 â€” Despliegue

### deploy/requirements_prod.txt
```
fastapi>=0.111.0
uvicorn>=0.29.0
onnxruntime>=1.18.0
opencv-python-headless>=4.9.0
Pillow>=10.0.0
numpy>=1.26.0
geopandas>=0.14.0
shapely>=2.0.0
pandas>=2.2.0
requests>=2.31.0
python-multipart>=0.0.9
```
Sin `ultralytics`, sin `torch`. El modelo se sirve solo con `onnxruntime`.

### deploy/Dockerfile
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Dependencias del sistema para GeoPandas
RUN apt-get update && apt-get install -y \
    libgdal-dev libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/requirements_prod.txt .
RUN pip install --no-cache-dir -r requirements_prod.txt

COPY exports/best_fire_smoke.onnx ./exports/
COPY api/ ./api/
COPY geo_pipeline/ ./geo_pipeline/
COPY dashboard/static/geo/ ./dashboard/static/geo/
COPY "Datasets Territoriales/" "./Datasets Territoriales/"

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### deploy/.env.example
```
AEMET_API_KEY=pon_aqui_tu_api_key_de_aemet
TELEGRAM_BOT_TOKEN=pon_aqui_tu_token_de_telegram
TELEGRAM_CHAT_ID=pon_aqui_tu_chat_id
MODEL_PATH=exports/best_fire_smoke.onnx
CONF_THRESHOLD_FIRE=0.25
CONF_THRESHOLD_SMOKE=0.10
ALERT_COOLDOWN_SECONDS=30
```

### deploy/README_deploy.md
Incluir instrucciones para:
1. **Local (desarrollo):** `uvicorn api.main:app --reload` + `streamlit run dashboard/app.py`
2. **IsardVDI:** copiar ficheros al servidor, instalar dependencias, ejecutar con `nohup` o `screen`
3. **Docker local:** `docker build` + `docker run` con el `.env`
4. **Hugging Face Spaces:** crear Space de tipo Streamlit, subir `dashboard/app.py` + `requirements_prod.txt` + GeoJSONs + modelo ONNX, configurar secrets para las API keys

---

## Notas finales para Codex

- **SeparaciÃ³n clara de responsabilidades:** `geo_pipeline/` es agnÃ³stico al framework (sin FastAPI ni Streamlit); `api/` orquesta; `dashboard/` solo visualiza. Si algo falla en la API, el notebook debe seguir funcionando.
- **Los GeoJSONs se generan una sola vez** (notebook 03 o script manual) y se sirven como estÃ¡ticos. No recalcular geometrÃ­as en cada request.
- **AEMET puede fallar.** Cada funciÃ³n que la llame debe tener try/except y retornar valores por defecto, nunca romper el flujo principal.
- **El modelo ONNX es prioritario sobre el .pt** en producciÃ³n. Si el ONNX no existe en `exports/`, intentar con el `.pt` como fallback con un warning.
- **Todos los scripts de `geo_pipeline/` deben poder ejecutarse de forma independiente** desde la lÃ­nea de comandos para depuraciÃ³n: `python -m geo_pipeline.firms_loader` imprime un resumen de los datos cargados.
- Comentar en castellano las partes de lÃ³gica de negocio (Ã­ndice de riesgo, umbrales); en inglÃ©s el resto del cÃ³digo.
