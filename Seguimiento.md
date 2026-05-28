# Seguimiento del entrenamiento - PlantVision Fire/Smoke

Este documento registra las fases de preparacion, entrenamiento, resultados, interpretacion y decisiones de mejora. La idea es que sirva como base directa para redactar la memoria del proyecto.

## Fase 1 - Baseline YOLOv8s con 1.000 imagenes

Fecha de ejecucion: 2026-05-24.

### Configuracion del dataset

Se preparo un primer dataset procesado en formato YOLO con 1.000 imagenes:

| Bloque | Imagenes | Uso |
|---|---:|---|
| D-Fire | 500 | Deteccion de fuego y humo, con etiquetas YOLO remapeadas a `0=fire`, `1=smoke`. |
| Open Wildfire Smoke | 300 | Refuerzo de humo incipiente en entorno forestal, convertido desde Pascal VOC a YOLO. |
| Cloud/Fog | 200 | Negativos sin fuego ni humo para reducir falsos positivos. |

Division estratificada:

| Split | Imagenes |
|---|---:|
| Train | 700 |
| Val | 150 |
| Test | 150 |

### Configuracion de entrenamiento

Modelo: `YOLOv8s` con pesos preentrenados COCO (`yolov8s.pt`).

Hiperparametros principales:

| Parametro | Valor |
|---|---:|
| epochs | 100 |
| patience | 20 |
| batch | 16 |
| imgsz | 640 |
| optimizer | AdamW |
| lr0 | 0.001 |
| cos_lr | True |
| mosaic | 1.0 |
| mixup | 0.1 |
| fliplr | 0.5 |
| device | GPU 0 |
| run | `models/runs/fire_smoke_v1` |

### Resultados obtenidos

Entrenamiento completado en 100 epocas, con mejor validacion en la epoca 80.

| Metrica | Valor |
|---|---:|
| Mejor val mAP50 | 0.649 |
| Val mAP50-95 en mejor epoca | 0.303 |
| Val precision final | 0.644 |
| Val recall final | 0.649 |
| Val mAP50 final | 0.641 |
| Val mAP50-95 final | 0.285 |

Evaluacion en test:

| Clase | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| fire | 0.688 | 0.582 | 0.680 | 0.333 |
| smoke | 0.538 | 0.368 | 0.371 | 0.147 |
| media | 0.613 | 0.475 | 0.525 | 0.240 |

F1 por umbral:

| Clase | Umbral optimo | F1 | Precision | Recall |
|---|---:|---:|---:|---:|
| fire | 0.25 | 0.680 | 0.735 | 0.633 |
| smoke | 0.10 | 0.497 | 0.469 | 0.529 |

Tiempo medio de inferencia medido sobre test: 19.9 ms/imagen.

### Interpretacion

El modelo aprende mejor la clase `fire` que la clase `smoke`. Esto es esperable porque el fuego suele tener rasgos visuales mas definidos: color, contraste, bordes y textura. El humo, en cambio, es mas difuso, puede ocupar regiones amplias y translucidas, y se parece visualmente a nubes, niebla, calima o bruma.

Tambien aparece una brecha entre train y validacion. Al final del entrenamiento, `train/box_loss` fue 1.023 frente a `val/box_loss` 2.034, y `train/cls_loss` fue 0.640 frente a `val/cls_loss` 1.444. Esto sugiere dificultad de generalizacion y cierto sobreajuste, especialmente en localizacion y clasificacion de humo.

La diferencia entre validacion y test tambien es relevante: el mejor mAP50 de validacion fue 0.649, pero el mAP50 medio en test fue 0.525. Por tanto, el baseline es util como primera prueba, pero aun no es suficientemente robusto para humo en despliegue real.

### Mejoras propuestas tras la fase 1

1. Aumentar el refuerzo de humo de 300 a 700 imagenes para mejorar recall y mAP de `smoke`.
2. Mantener imagenes negativas de cloud/fog para controlar falsos positivos.
3. Conservar el run `fire_smoke_v1` como baseline y entrenar una nueva version `fire_smoke_v2_smoke700`.
4. Analizar si la subida de datos de humo reduce la brecha de generalizacion y mejora especialmente el recall de `smoke`.
5. Si smoke sigue siendo debil, revisar calidad de etiquetas y aplicar hard-negative mining sobre falsos positivos de nubes/niebla/calima.

## Fase 2 - Refuerzo de humo ampliado a 700 imagenes

Estado: entrenamiento finalizado y analizado.

### Objetivo

Incrementar el peso de ejemplos reales de humo forestal para atacar el principal problema observado en fase 1: bajo rendimiento de `smoke`, especialmente en recall y mAP50-95.

### Configuracion prevista del dataset

| Bloque | Imagenes | Cambio frente a fase 1 |
|---|---:|---|
| D-Fire | 500 | Igual que baseline. |
| Open Wildfire Smoke | 700 | Sube de 300 a 700. |
| Cloud/Fog | 200 | Igual que baseline. |

Total previsto: 1.400 imagenes.

Division prevista:

| Split | Imagenes |
|---|---:|
| Train | 980 |
| Val | 210 |
| Test | 210 |

### Dataset generado

Se regenero `data/processed/` con 1.400 imagenes y se guardaron manifests de ambas fases:

- Baseline: `data/processed/selection_manifest_fire_smoke_v1.csv`
- Fase 2 activa: `data/processed/selection_manifest_fire_smoke_v2_smoke700.csv`

Distribucion generada:

| Split | D-Fire | Wildfire Smoke | Cloud/Fog | Total |
|---|---:|---:|---:|---:|
| Train | 347 | 493 | 140 | 980 |
| Val | 77 | 103 | 30 | 210 |
| Test | 76 | 104 | 30 | 210 |

Distribucion por estrato:

| Split | fire | smoke | background |
|---|---:|---:|---:|
| Train | 175 | 665 | 140 |
| Val | 37 | 143 | 30 |
| Test | 38 | 142 | 30 |

### Hipotesis

Al aumentar los ejemplos de humo, el modelo deberia ver mas variabilidad de humo incipiente y forestal, por lo que se espera mejorar el recall de `smoke`. Puede bajar ligeramente la precision si el modelo se vuelve mas sensible a patrones parecidos a humo, por eso se mantienen 200 negativos cloud/fog y se revisara la matriz de confusion.

### Configuracion prevista de entrenamiento

Se mantiene YOLOv8s y los hiperparametros base de la fase 1 para que la comparacion sea lo mas justa posible. El nuevo run sera:

```text
models/runs/fire_smoke_v2_smoke700
```

El objetivo de esta fase no es cambiar arquitectura ni augmentacion, sino aislar el efecto de aumentar ejemplos de humo.

### Resultados obtenidos

El entrenamiento finalizo por early stopping en la epoca 80. La mejor validacion se alcanzo en la epoca 75.

| Metrica | Valor |
|---|---:|
| Mejor val mAP50 | 0.692 |
| Val mAP50-95 en mejor epoca | 0.331 |
| Val precision final | 0.728 |
| Val recall final | 0.674 |
| Val mAP50 final | 0.680 |
| Val mAP50-95 final | 0.327 |

Evaluacion en test:

| Clase | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| fire | 0.522 | 0.475 | 0.468 | 0.234 |
| smoke | 0.607 | 0.559 | 0.551 | 0.248 |
| media | 0.565 | 0.517 | 0.509 | 0.241 |

F1 por clase:

| Clase | F1 |
|---|---:|
| fire | 0.500 |
| smoke | 0.616 |
| media | 0.558 |

Tiempo medio de inferencia medido sobre test: 22.4 ms/imagen.

### Comparacion con fase 1

| Metrica test | Fase 1 | Fase 2 | Cambio |
|---|---:|---:|---:|
| fire mAP50 | 0.680 | 0.468 | -0.212 |
| smoke mAP50 | 0.371 | 0.551 | +0.180 |
| media mAP50 | 0.525 | 0.509 | -0.016 |
| fire recall | 0.582 | 0.475 | -0.107 |
| smoke recall | 0.368 | 0.559 | +0.191 |
| media recall | 0.475 | 0.517 | +0.042 |
| media mAP50-95 | 0.240 | 0.241 | +0.001 |

### Interpretacion

La hipotesis principal se confirma parcialmente: aumentar el refuerzo de humo mejora claramente la clase `smoke`. El recall de humo sube de 0.368 a 0.559, y su mAP50 sube de 0.371 a 0.551. Esto indica que el modelo ve ahora mas variabilidad de humo y detecta mas casos que antes pasaban desapercibidos.

Sin embargo, el rendimiento de `fire` cae de forma importante. La causa mas probable es que el dataset queda muy sesgado hacia humo: en train hay 665 imagenes etiquetadas como `smoke` frente a 175 imagenes del estrato `fire` y 140 negativas. Aunque D-Fire sigue aportando fuego, el peso relativo de humo domina el aprendizaje. El modelo se vuelve mas sensible a humo, pero pierde capacidad relativa para fuego.

El resultado medio apenas cambia: mAP50 baja ligeramente de 0.525 a 0.509, mientras que mAP50-95 queda practicamente igual. Por tanto, esta fase es util porque demuestra que mas humo funciona para humo, pero no es la configuracion final ideal.

### Mejoras propuestas tras la fase 2

1. Reequilibrar la fase 3 aumentando tambien ejemplos de fuego. Propuesta: pasar a un dataset de aproximadamente 1.700 imagenes con 700 D-Fire, 700 Wildfire Smoke y 300 Cloud/Fog. En D-Fire conviene mantener balance interno aproximado entre `fire` y `smoke`.
2. Mantener las 700 imagenes de humo, porque han mejorado recall y mAP50 de `smoke`.
3. Subir negativos de 200 a 300 para compensar la mayor sensibilidad a patrones difusos parecidos a humo.
4. Probar `imgsz=768` en la fase 3 si la RTX 4070 lo permite, ya que humo lejano y pequeno puede beneficiarse de mayor resolucion.
5. Si el coste de entrenamiento sube demasiado, mantener `imgsz=640` y cambiar solo balance de datos para aislar el efecto del reequilibrado.

## Fase 3 - Reequilibrado tras la mejora de humo

Estado: entrenamiento finalizado y analizado.

### Ajuste de criterio

Tras revisar la fase 2, se matiza la propuesta anterior. D-Fire contiene tanto fuego como humo, por lo que subir D-Fire de forma simplemente "balanceada" podria mantener un sesgo global hacia humo al combinarse con las 700 imagenes de Wildfire Smoke.

La fase 3 usara D-Fire principalmente para recuperar senal de `fire`: se seleccionaran 700 imagenes D-Fire con presencia de fuego, priorizando imagenes exclusivas de fuego cuando sea posible. Esto se combina con 700 imagenes de Wildfire Smoke y 300 negativas Cloud/Fog.

### Configuracion prevista del dataset

| Bloque | Imagenes | Criterio |
|---|---:|---|
| D-Fire | 700 | Presencia de `fire`; prioridad a imagenes solo fuego para compensar el sesgo de humo. |
| Open Wildfire Smoke | 700 | Refuerzo de humo forestal mantenido desde fase 2. |
| Cloud/Fog | 300 | Negativos para controlar falsos positivos. |

Total previsto: 1.700 imagenes.

Division prevista:

| Split | Imagenes |
|---|---:|
| Train | 1.190 |
| Val | 255 |
| Test | 255 |

### Hipotesis

Esta configuracion deberia conservar la mejora de `smoke` obtenida en fase 2, pero recuperar parte del rendimiento perdido en `fire`. El incremento de negativos busca que la mayor sensibilidad al humo no se traduzca en demasiados falsos positivos sobre nubes, niebla o calima.

### Dataset generado

Se regenero `data/processed/` con 1.700 imagenes y se guardo el manifest:

- Fase 3 activa: `data/processed/selection_manifest_fire_smoke_v3_balanced.csv`

Distribucion generada:

| Split | D-Fire | Wildfire Smoke | Cloud/Fog | Total |
|---|---:|---:|---:|---:|
| Train | 490 | 490 | 210 | 1.190 |
| Val | 105 | 105 | 45 | 255 |
| Test | 105 | 105 | 45 | 255 |

Distribucion por estrato:

| Split | fire_only | smoke | background |
|---|---:|---:|---:|
| Train | 490 | 490 | 210 |
| Val | 105 | 105 | 45 |
| Test | 105 | 105 | 45 |

### Configuracion prevista de entrenamiento

Se mantiene YOLOv8s y los hiperparametros principales de las fases anteriores para aislar el efecto del reequilibrado del dataset. El nuevo run es:

```text
models/runs/fire_smoke_v3_balanced
```

### Resultados obtenidos

El entrenamiento finalizo en la epoca 97, con mejor validacion en la epoca 80.

| Metrica | Valor |
|---|---:|
| Mejor val mAP50 | 0.669 |
| Val mAP50-95 en mejor epoca | 0.321 |
| Val precision final | 0.702 |
| Val recall final | 0.639 |
| Val mAP50 final | 0.638 |
| Val mAP50-95 final | 0.314 |

Evaluacion en test:

| Clase | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| fire | 0.618 | 0.609 | 0.623 | 0.311 |
| smoke | 0.832 | 0.582 | 0.678 | 0.289 |
| media | 0.725 | 0.596 | 0.650 | 0.300 |

F1 por clase:

| Clase | F1 |
|---|---:|
| fire | 0.648 |
| smoke | 0.717 |
| media | 0.683 |

Tiempo medio de inferencia medido sobre test: 15.9 ms/imagen.

### Comparacion global de fases

| Metrica test | Fase 1 baseline | Fase 2 smoke700 | Fase 3 balanced |
|---|---:|---:|---:|
| fire mAP50 | 0.680 | 0.468 | 0.623 |
| smoke mAP50 | 0.371 | 0.551 | 0.678 |
| media mAP50 | 0.525 | 0.509 | 0.650 |
| fire recall | 0.582 | 0.475 | 0.609 |
| smoke recall | 0.368 | 0.559 | 0.582 |
| media recall | 0.475 | 0.517 | 0.596 |
| media mAP50-95 | 0.240 | 0.241 | 0.300 |

### Interpretacion

La fase 3 corrige el problema principal de la fase 2. Al seleccionar D-Fire con orientacion a fuego, el modelo recupera rendimiento en `fire` sin perder la mejora de `smoke`. El mAP50 de humo sube incluso mas que en fase 2, de 0.551 a 0.678, y el mAP50 de fuego se recupera de 0.468 a 0.623.

La media mejora de forma clara: mAP50 pasa de 0.525 en fase 1 y 0.509 en fase 2 a 0.650 en fase 3. Tambien mejora mAP50-95, de aproximadamente 0.240 a 0.300, lo que indica no solo mas detecciones, sino cajas algo mejor ajustadas.

El resultado tiene sentido porque el dataset de entrenamiento queda mucho mas simetrico: 490 imagenes de fuego, 490 de humo y 210 negativas en train. Esto reduce el sesgo hacia humo observado en fase 2 y conserva suficientes negativos para no disparar falsos positivos.

### Mejoras propuestas tras la fase 3

1. Tomar `fire_smoke_v3_balanced` como mejor modelo actual.
2. Hacer hard-negative mining con cloud/fog/calima: pasar el modelo por imagenes negativas adicionales y anadir falsos positivos dificiles al entrenamiento.
3. Probar una fase 4 con `imgsz=768`, manteniendo exactamente el dataset de fase 3, para medir si mejora humo lejano y cajas pequenas.
4. Revisar ejemplos visuales de errores en `prediction_examples_4x4.png` y la matriz de confusion para decidir si conviene ajustar umbrales por clase en inferencia.

## Fase 4 - Pipeline territorial, API y dashboard

### Configuracion implementada

Se inicia la segunda parte del proyecto a partir de `agent_02_dashboard.md`, sin modificar `inference.py`.

Archivos creados:

- `geo_pipeline/`: carga FIRMS, ZARI, combustible, AEMET, calculo del indice y exportacion GeoJSON.
- `api/`: FastAPI con endpoints `/predict`, `/risk`, `/alerts`, `/images/{filename}`, `/geo/{filename}` y `/health`.
- `dashboard/`: dashboard Streamlit con mapa Folium, KPIs, meteorologia, contexto territorial y prueba manual de inferencia por imagen.
- `deploy/`: Dockerfile, dependencias de produccion, `.env.example` sin credenciales reales y guia de despliegue.
- `notebooks/03_analisis_territorial.ipynb`: analisis reproducible de FIRMS, ZARI, combustible e indice de riesgo.

### Adaptaciones por datos reales

ZARI no declara CRS, pero sus coordenadas corresponden a UTM Canarias, por lo que se asume `EPSG:32628` y se reproyecta a `EPSG:4326`. Los campos reales usados son `ZONA`, `ISLA` y `B__O__C_`.

FIRMS viene como shapefile `fire_archive_SV-C2_747852.shp` con 20.875 registros en `EPSG:4326`. Tras filtrar Gran Canaria y confianza VIIRS nominal/alta quedan 722 puntos, con rango temporal 2012-06-06 a 2025-11-17.

Combustible de Gran Canaria usa el campo real `mc`. Se selecciona `gc_mc_can_sieve.shp`, se conserva el codigo predominante y se usa un peso medio ponderado por superficie para el indice, porque el codigo `0` domina parte del radio como zona sin combustible/no clasificada y podia infravalorar el riesgo.

### Resultados territoriales iniciales

Para la camara simulada de Tejeda:

| Elemento | Resultado |
|---|---:|
| ZARI | Dentro, `SECTOR 5` |
| Focos FIRMS en 15 km | 552 |
| FRP maximo | 282.94 MW |
| Ano pico | 2019 |
| Mes pico | agosto |
| Peso combustible ponderado 5 km | 0.299 |
| Indice sin viento AEMET | 0.640 |
| Nivel | ALTO |

El nivel `ALTO` se explica principalmente por estar dentro de ZARI y por la alta densidad historica FIRMS alrededor del punto. El combustible no domina el indice porque una parte importante del buffer esta marcada como `0`, pero el peso ponderado evita ignorar los modelos peligrosos presentes en el radio.

### Mejoras sugeridas

1. Ajustar la tabla de pesos `mc` con una fuente documental oficial del modelo de combustible canario, si se incluye en la memoria.
2. Reducir o vector-tilear `combustible_gc.geojson`: actualmente queda en torno a 5.4 MB incluso simplificado.
3. Probar el dashboard con AEMET real configurando `AEMET_API_KEY` como variable de entorno, no dentro del repositorio.
4. Validar visualmente `/predict` con imagenes positivas y ajustar `CONF_THRESHOLD_FIRE` y `CONF_THRESHOLD_SMOKE` antes de activar Telegram.

### Observaciones de prueba en video/pantalla

Prueba manual con `inference.py --source screen` sobre videos de YouTube:

- El modelo tiende a clasificar muchas detecciones como `fire`, incluso cuando visualmente son humo. A veces detecta humo correctamente, pero la frontera entre clases no es estable.
- Aparecen falsos positivos de `fire` en elementos rojizos de baja resolucion, por ejemplo banderines o objetos rojos en cables entre balcones.
- Antes de reproducir el video, la captura de pantalla normal del escritorio no genero detecciones de humo ni fuego, lo cual es una senal positiva para falsos positivos fuera del dominio.

Estas observaciones apuntan a dos mejoras futuras: revisar umbrales por clase en inferencia y crear un set de hard negatives con objetos rojizos, baja resolucion, escenas urbanas y humo sin llama para reducir confusiones.

### Ajustes de flujo del aplicativo

Se configura `.env` local con AEMET y Telegram a partir del documento de trabajo, dejando `deploy/.env.example` solo con placeholders para no publicar credenciales. AEMET queda operativo y devuelve la estacion `TEJEDA-CRUZ DE TEJEDA`, a 1.48 km del punto de camara.

Se corrige el dashboard para que el uploader no vuelva a llamar a `/predict` en cada refresco de Streamlit. A partir de ahora la imagen se analiza solo al pulsar `Analizar imagen`; el refresco del dashboard ya no deberia registrar alertas duplicadas por la misma imagen.

Se implementa simulacion de foco: cuando `/predict` genera una deteccion, la alerta se registra en una coordenada aleatoria dentro de 5 km de la camara (`SIMULATE_RANDOM_ALERT_POINT=1`). El indice territorial se calcula para ese foco simulado y no siempre para la coordenada exacta de la camara.

Se anade `screen_to_api.py` para probar video o pantalla completa pasando frames a la API. Esto permite que un video de YouTube active el flujo completo: deteccion, calculo territorial, registro en SQLite y Telegram si las credenciales estan configuradas.

### Ajuste de UX para captura de pantalla

Se descarta como flujo de usuario la captura mediante comando PowerShell. La deteccion de pantalla/video pasa al frontend:

- El dashboard muestra el boton `Abrir detector de pantalla`.
- La API sirve `/screen-capture`, una pagina HTML que usa `navigator.mediaDevices.getDisplayMedia`.
- El usuario pulsa `Iniciar captura`, selecciona pantalla/ventana/pestana y el navegador envia frames a `/predict`.
- Se anade CORS para permitir integracion local entre Streamlit (`8501`) y API (`8000`).

`screen_to_api.py` queda como utilidad de desarrollo, no como flujo principal de usuario.

### Confirmacion temporal de alertas en video

Se separa el criterio de alerta por modo:

- Imagen estatica: una deteccion con confianza suficiente puede registrar alerta inmediatamente, porque el tiempo no aporta informacion.
- Video/pantalla: la deteccion debe persistir durante `ALERT_CONFIRM_SECONDS=5` segundos antes de registrar alerta y enviar Telegram.

Implementacion eficiente: la API mantiene en memoria un estado pequeno por `session_id` y por clase (`fire`/`smoke`), con primer instante visto, ultimo instante visto, mejor confianza y si ya se alerto. Si pasan mas de `TEMPORAL_MAX_GAP_SECONDS=4` segundos sin ver la clase, se reinicia el contador. Esto evita escribir en SQLite y mandar Telegram por cada frame, y filtra videos con cambios rapidos o falsos positivos puntuales.

El endpoint `/predict` conserva compatibilidad: por defecto funciona como imagen estatica; el frontend de `/screen-capture` envia `temporal_confirm=true` y un `session_id` unico.

### Analisis preliminar de despliegue

Se prepara `deploy/docker-compose.yml` con dos servicios, `api` y `dashboard`, construidos desde el mismo Dockerfile y comandos distintos.

Ruta preferida para IsardVDI: clonar desde GitHub, configurar `deploy/.env` y ejecutar `docker compose up -d --build`. Es la opcion mas reproducible y evita depender del Python global del servidor.

Para Hugging Face se recomienda Space Docker, no Space Streamlit simple, porque el aplicativo necesita FastAPI, endpoints auxiliares, dashboard y captura `/screen-capture`.

Para nube academica, Azure Container Apps parece una opcion sencilla para contenedores CPU. En AWS se debe tener cuidado con App Runner porque la documentacion oficial indica cambio de disponibilidad para nuevos clientes desde 2026-04-30; si la cuenta no lo permite, ECS/Fargate o una VM son alternativas mas controlables.

### Ajuste de mapa y gestion de historial

Se implementa limpieza del historial desde el dashboard:

- Nuevo endpoint `DELETE /alerts`.
- Borra registros SQLite y las imagenes `api/alert_images/alert_*.jpg`.
- Reinicia cooldown y sesiones temporales.
- En el dashboard se exige marcar `Confirmar limpieza` antes de pulsar `Reiniciar historial`.

Se rediseña la logica de los anillos de riesgo:

- Los anillos dejan de estar fijos sobre la camara.
- El usuario selecciona un foco haciendo click en el mapa.
- El dashboard recalcula `/risk` para la latitud/longitud del foco.
- Los anillos se dibujan alrededor del foco seleccionado.
- Los labels son `Riesgo inmediato` (1 km), `Riesgo alto` (2.5 km) y `Riesgo potencial` (5 km).
- La opacidad se reduce con la distancia al foco y se acentua suavemente con el peso de combustible ponderado en 5 km.

Esto convierte el mapa en una herramienta de analisis territorial local, no solo en una visualizacion estatica de la camara.

### Ajuste de indice, combustible y viento

Tras probar focos cercanos se observa que el indice quedaba casi siempre en `ALTO` con valores 0.62-0.64. La causa era doble:

- `ZARI` tenia demasiado peso para una zona donde muchos puntos cercanos caen dentro de ZARI.
- `FIRMS` saturaba el factor historico porque la referencia maxima era 50 hotspots y alrededor de Tejeda hay mas de 500.

Se recalibra el indice:

- ZARI baja a 0.15 como contexto estructural.
- Combustible sube a 0.35.
- FIRMS queda en 0.20 con referencia 700 hotspots para evitar saturacion constante.
- Viento queda en 0.15.
- Temperatura se incorpora con peso 0.15; empieza a contar por encima de 25 C y aumenta claramente a partir de 30 C.

Tambien se evita presentar `0 - Sin combustible o no clasificado` como dato principal del panel. Ahora se muestra una tabla de combustibles presentes en el radio, excluyendo `0` y `11`, ordenada por porcentaje de superficie y con su peso de combustibilidad.

Se anade flecha de viento desde el foco seleccionado. AEMET da direccion de procedencia, asi que la flecha se dibuja hacia donde empuja el viento. El tooltip incluye velocidad, temperatura, factor viento y factor temperatura.

Para reducir lentitud y evitar errores `429 Too Many Requests` de AEMET, la meteorologia se cachea durante 10 minutos para la zona de trabajo. Cambiar el foco recalcula ZARI, combustible y FIRMS, pero no golpea AEMET en cada click.

Las capas del mapa dejan de depender de los checks internos de Leaflet y se pasan al sidebar de Streamlit, guardadas en `session_state`, para que no se reactiven solas al seleccionar otro foco o refrescar la pagina.

## Fase 5 - Propuesta de mejora del modelo pendiente de aprobacion

Estado: ejecutada tras recibir visto bueno el 2026-05-28.

### Problemas observados

- El modelo tiende a clasificar como `fire` elementos que visualmente son `smoke`.
- Aparecen falsos positivos de `fire` en objetos rojizos de baja resolucion, como adornos o banderines en videos urbanos.
- Las llamas suelen detectarse, pero la precision de `fire` no es suficientemente robusta para despliegue sin supervision.
- El humo mejora respecto a fases iniciales, pero sigue quedando cojo en recall y separacion semantica frente a fuego.

### Objetivo de la fase

Mejorar robustez sin alargar el entrenamiento mas de 1.5-2 horas. La prioridad no es solo subir mAP medio, sino reducir confusiones `smoke -> fire` y falsos positivos rojizos.

### Propuesta tecnica

1. Conservar intacto el modelo actual:
   - `exports/best_fire_smoke.pt`
   - `exports/best_fire_smoke.onnx`
   - `models/runs/fire_smoke_v3_balanced`
2. Crear una nueva version `fire_smoke_v4_hardneg_smoke`.
3. Mantener YOLOv8s e `imgsz=640` para controlar duracion.
4. Partir de `exports/best_fire_smoke.pt` como pesos iniciales, no desde COCO, para hacer fine-tuning corto.
5. Usar un dataset ampliado con:
   - base de fase 3;
   - mas ejemplos de humo puro o predominante;
   - hard negatives: objetos rojos, baja resolucion, escenas urbanas, banderines/adornos, luces calidas, atardeceres, nubes/calima;
   - si es posible, capturas propias de los videos donde fallo.
6. Entrenar con menos epocas y early stopping:
   - `epochs=50`
   - `patience=10`
   - `batch=16`
   - `imgsz=640`
   - `lr0=0.0003`
   - `optimizer=AdamW`
   - `cos_lr=True`
7. Hacer checks cada 10 minutos:
   - revisar si el usuario pidio parar;
   - comprobar `val/box_loss`, `val/cls_loss`, precision, recall y mAP;
   - si train mejora pero validacion se estanca o empeora durante varias epocas, considerar parada temprana manual para evitar overfitting.

### Criterio de aceptacion

Aceptar la nueva version solo si mejora de forma clara la utilidad practica:

- no empeora mucho `fire` frente a v3;
- mejora separacion entre `fire` y `smoke`;
- reduce falsos positivos rojizos en pruebas manuales;
- mantiene o mejora mAP50 medio en test;
- no sustituye el modelo actual hasta validar visualmente dashboard, `inference.py` y `screen_to_api.py`.

### Dataset v4 generado

Se preparo `data/processed_v4_hardneg_smoke` sin reutilizar imagenes presentes en los manifests anteriores. La comprobacion de solape por nombre original dio:

```text
overlap = 0
```

Composicion:

| Bloque | Imagenes | Criterio |
|---|---:|---|
| D-Fire | 500 | Imagenes no vistas, priorizando fuego y fuego+humo. |
| Wildfire Smoke | 700 | Humo no visto por el modelo actual. |
| Cloud/Fog | 400 | Negativos no vistos; se priorizan falsos positivos del modelo v3. |

Division:

| Split | D-Fire | Wildfire Smoke | Cloud/Fog | Total |
|---|---:|---:|---:|---:|
| Train | 350 | 490 | 280 | 1120 |
| Val | 75 | 105 | 60 | 240 |
| Test | 75 | 105 | 60 | 240 |

Conteo de cajas en todo el dataset:

| Clase | Cajas |
|---|---:|
| fire | 987 |
| smoke | 927 |

Hard-negative mining: de los negativos no vistos, 18 imagenes dieron alguna deteccion con `conf >= 0.10` usando el modelo v3. Esas imagenes se priorizaron como negativos dificiles.

### Entrenamiento v4

Run:

```text
models/runs/fire_smoke_v4_hardneg_smoke
```

Pesos iniciales:

```text
exports/best_fire_smoke.pt
```

Configuracion:

| Parametro | Valor |
|---|---:|
| epochs | 50 |
| patience | 10 |
| batch | 16 |
| imgsz | 640 |
| optimizer | AdamW |
| lr0 | 0.0003 |
| cos_lr | True |
| device | 0 |

El entrenamiento paro por early stopping en la epoca 28. La mejor epoca fue la 18. Duracion aproximada: 0.124 horas.

Validacion en mejor epoca:

| Clase | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| fire | 0.657 | 0.594 | 0.682 | 0.349 |
| smoke | 0.715 | 0.475 | 0.551 | 0.253 |
| media | 0.686 | 0.534 | 0.617 | 0.301 |

### Comparacion en test v4 no visto

| Modelo | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| v3 actual sobre test v4 | 0.613 | 0.457 | 0.459 | 0.223 |
| v4 candidato sobre test v4 | 0.603 | 0.586 | 0.582 | 0.288 |

Por clase en test v4:

| Modelo | fire mAP50 | fire mAP50-95 | smoke mAP50 | smoke mAP50-95 |
|---|---:|---:|---:|---:|
| v3 actual | 0.522 | 0.260 | 0.397 | 0.187 |
| v4 candidato | 0.657 | 0.349 | 0.507 | 0.226 |

El candidato v4 mejora claramente sobre el conjunto nuevo no visto. Esto indica que el fine-tuning ha aprendido parte de la nueva distribucion.

### Comprobacion de regresion sobre test anterior

Evaluando v4 sobre el test original de fase 3:

| Modelo | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| v3 actual sobre test fase 3 | 0.725 | 0.596 | 0.650 | 0.300 |
| v4 candidato sobre test fase 3 | 0.655 | 0.557 | 0.580 | 0.286 |

El candidato v4 no debe sustituir automaticamente al modelo actual porque pierde rendimiento en el test historico, especialmente en mAP50 medio.

### Falsos positivos y humo

Negativos Cloud/Fog v4:

| Modelo | Imagenes con falso positivo | Predicciones falsas | FP fire | FP smoke |
|---|---:|---:|---:|---:|
| v3 actual | 11 | 13 | 7 | 6 |
| v4 candidato | 5 | 5 | 2 | 3 |

El candidato reduce de forma clara los falsos positivos en negativos cloud/fog no vistos.

Wildfire Smoke test v4:

| Modelo | Imagenes | Con prediccion fire | Con prediccion smoke | Sin deteccion |
|---|---:|---:|---:|---:|
| v3 actual | 105 | 0 | 85 | 20 |
| v4 candidato | 105 | 0 | 82 | 23 |

No aparece confusion `smoke -> fire` en este subconjunto, pero v4 pierde ligeramente sensibilidad a humo frente a v3.

### Decision

Se conserva el modelo actual como modelo de produccion/demo:

```text
exports/best_fire_smoke.pt
exports/best_fire_smoke.onnx
```

Se guarda v4 como candidato experimental:

```text
exports/best_fire_smoke_v4_hardneg_smoke.pt
exports/best_fire_smoke_v4_hardneg_smoke.onnx
models/runs/fire_smoke_v4_hardneg_smoke
```

La conclusion es que v4 mejora robustez sobre datos nuevos y reduce falsos positivos en negativos, pero no supera al modelo actual como sustituto general. La siguiente mejora deberia incorporar negativos rojizos reales capturados de los videos donde fallo, porque el dataset actual solo aporto cloud/fog como hard negatives y no cubre suficientemente banderines/adornos urbanos.

## Fase 5 - Todo Wildfire Smoke disponible no visto por v3

### Objetivo

La fase 5 se planteo para atacar directamente la debilidad observada en demo: el modelo tiende a confundir algunos casos de humo con fuego y todavia puede reaccionar a elementos visuales rojizos o de bajo detalle. Como no se pueden incorporar imagenes nuevas fuera del proyecto, la mejora se limito a reutilizar material ya presente, excluyendo las imagenes que el modelo de produccion v3 habia visto en fases anteriores.

### Preparacion del dataset

Script:

```text
scripts/prepare_v5_dataset.py
```

Salida:

```text
data/processed_v5_all_wildfire
data/dataset_v5_all_wildfire.yaml
```

Se excluyeron las imagenes presentes en los manifests v1-v3. El solape final con esos manifests fue 0.

Seleccion:

| Bloque | Imagenes |
|---|---:|
| D-Fire | 540 |
| Wildfire Smoke | 882 |
| Cloud/Fog negativo | 513 |
| Total | 1935 |

Division:

| Split | Cloud/Fog | D-Fire fire | D-Fire both | D-Fire smoke | Wildfire Smoke | Total |
|---|---:|---:|---:|---:|---:|---:|
| Train | 359 | 238 | 119 | 21 | 617 | 1354 |
| Val | 77 | 51 | 26 | 4 | 132 | 290 |
| Test | 77 | 51 | 25 | 5 | 133 | 291 |

Conteo de cajas en todo el dataset:

| Clase | Cajas |
|---|---:|
| fire | 1087 |
| smoke | 1165 |

La intencion era meter todo el `wildfire_smoke` no visto por v3 y reforzar con negativos cloud/fog tambien no vistos. D-Fire quedo por debajo del objetivo inicial porque, aplicando los filtros conservadores de no solape y calidad de etiquetas, habia menos imagenes elegibles en los estratos prioritarios.

### Entrenamiento v5

Run:

```text
models/runs/fire_smoke_v5_all_wildfire
```

Pesos iniciales:

```text
exports/best_fire_smoke.pt
```

Configuracion:

| Parametro | Valor |
|---|---:|
| epochs | 60 |
| patience | 12 |
| batch | 16 |
| imgsz | 640 |
| optimizer | AdamW |
| lr0 | 0.00025 |
| cos_lr | True |
| device | 0 |

El entrenamiento paro por early stopping en la epoca 22. La mejor epoca fue la 10. Duracion: 1.042 horas.

Validacion en mejor epoca:

| Clase | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| fire | 0.671 | 0.632 | 0.702 | 0.377 |
| smoke | 0.771 | 0.529 | 0.615 | 0.245 |
| media | 0.721 | 0.580 | 0.658 | 0.311 |

La curva mejoro pronto y despues se estanco. El early stopping fue correcto: tras la epoca 10 no hubo mejora real sostenida en mAP50-95, aunque algunas epocas rozaron el maximo. No se observo una mejora suficiente como para justificar alargar el entrenamiento.

### Comparacion en test v5 no visto por v3

| Modelo | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| v3 actual sobre test v5 | 0.694 | 0.532 | 0.554 | 0.261 |
| v5 candidato sobre test v5 | 0.707 | 0.583 | 0.641 | 0.305 |

Por clase en test v5:

| Modelo | fire mAP50 | fire mAP50-95 | smoke mAP50 | smoke mAP50-95 |
|---|---:|---:|---:|---:|
| v3 actual | 0.632 | 0.323 | 0.475 | 0.198 |
| v5 candidato | 0.684 | 0.370 | 0.598 | 0.240 |

En el conjunto nuevo, v5 mejora de forma clara. Esto confirma que el fine-tuning si aprende parte de la distribucion adicional, especialmente el humo de Wildfire Smoke.

### Comprobacion de regresion sobre test fase 3

| Modelo | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| v3 actual sobre test fase 3 | 0.725 | 0.596 | 0.650 | 0.300 |
| v5 candidato sobre test fase 3 | 0.694 | 0.508 | 0.600 | 0.296 |

Por clase en test fase 3:

| Modelo | fire mAP50 | fire mAP50-95 | smoke mAP50 | smoke mAP50-95 |
|---|---:|---:|---:|---:|
| v3 actual | 0.623 | 0.311 | 0.678 | 0.289 |
| v5 candidato | 0.586 | 0.302 | 0.615 | 0.289 |

El candidato v5 no debe sustituir al modelo actual: mejora en datos nuevos, pero pierde generalizacion sobre el test historico, sobre todo en recall y mAP50.

### Falsos positivos y confusion humo/fuego

Diagnostico con `conf=0.15` sobre test v5:

| Bloque | Modelo | Imagenes | Con deteccion | Pred fire | Pred smoke | Sin deteccion |
|---|---|---:|---:|---:|---:|---:|
| Cloud/Fog | v3 actual | 77 | 3 | 2 | 1 | 74 |
| Cloud/Fog | v5 candidato | 77 | 1 | 1 | 0 | 76 |
| Wildfire Smoke | v3 actual | 133 | 119 | 1 | 119 | 14 |
| Wildfire Smoke | v5 candidato | 133 | 108 | 0 | 108 | 25 |
| D-Fire | v3 actual | 81 | 80 | 79 | 3 | 1 |
| D-Fire | v5 candidato | 81 | 76 | 73 | 19 | 5 |

Lectura:

- v5 reduce falsos positivos en Cloud/Fog.
- v5 elimina la unica confusion `smoke -> fire` observada en Wildfire Smoke test.
- v5 pierde sensibilidad: deja mas imagenes de humo sin deteccion y tambien baja en D-Fire.
- En D-Fire aumenta la presencia de predicciones `smoke`, lo que sugiere que el refuerzo de humo desplaza el equilibrio del modelo y puede penalizar fuego.

### Artefactos guardados

Se conserva el modelo actual de produccion/demo:

```text
exports/best_fire_smoke.pt
exports/best_fire_smoke.onnx
```

Se guarda v5 como candidato experimental, sin promoverlo:

```text
exports/best_fire_smoke_v5_all_wildfire.pt
exports/best_fire_smoke_v5_all_wildfire.onnx
models/runs/fire_smoke_v5_all_wildfire
models/runs_eval/v5_comparison_metrics.json
models/runs_eval/v5_behavior_diagnostics_conf015.json
```

### Decision y siguientes mejoras

No se sustituye v3 por v5. El resultado es util como experimento porque demuestra que meter todo Wildfire Smoke no visto mejora el nuevo dominio y reduce algunos falsos positivos, pero tambien demuestra que solo anadir mas humo no basta: el modelo pierde equilibrio y baja sobre el test que ya validaba la version actual.

Siguiente mejora recomendable:

1. Mantener v3 como base de produccion.
2. Crear un dataset mixto que combine parte del dataset v3 original con una seleccion del nuevo material, en lugar de entrenar solo con imagenes no vistas por v3. Esto puede reducir catastrophic forgetting.
3. Ajustar el muestreo para que fuego no quede penalizado: usar mas D-Fire con fuego claro, pero controlando las imagenes mixtas fuego+humo para no reforzar etiquetas ambiguas.
4. Si no se pueden anadir imagenes nuevas, extraer frames de los videos de prueba solo si esos videos forman parte permitida del proyecto. Si no se permite, documentar la limitacion y no usarlos.
5. Evaluar siempre con dos tests: test historico fase 3 y test nuevo v5. Solo promover un modelo si mejora o mantiene ambos.

## Fase 6 - Replay mix v3 + v5 sin duplicados internos

### Correccion de criterio

Se corrigio la interpretacion del requisito: no habia que entrenar exclusivamente con imagenes nuevas no vistas por el modelo, sino evitar duplicar imagenes dentro del conjunto de entrenamiento. Por eso se preparo una fase 6 con replay: se conserva el dataset base v3 que ya funcionaba y se anade el material nuevo preparado en v5, evitando colisiones internas.

### Preparacion del dataset

Scripts:

```text
scripts/prepare_v6_replay_dataset.py
scripts/train_v6.py
```

Salida:

```text
data/processed_v6_replay_mix
data/dataset_v6_replay_mix.yaml
```

Composicion:

| Origen | Train | Val | Test | Total |
|---|---:|---:|---:|---:|
| v3 historico | 1190 | 255 | 255 | 1700 |
| v5 nuevo | 1354 | 290 | 291 | 1935 |
| Total | 2544 | 545 | 546 | 3635 |

Validaciones:

| Check | Resultado |
|---|---:|
| Imagenes totales | 3635 |
| Claves unicas de deduplicacion | 3635 |
| Duplicados internos | 0 |
| Imagenes sin fichero | 0 |
| Labels sin fichero | 0 |

Conteo de cajas:

| Clase | Cajas |
|---|---:|
| fire | 2468 |
| smoke | 1905 |

El dataset queda algo inclinado hacia `fire`, pero mucho menos sesgado que un entrenamiento solo con D-Fire. La mezcla permite reforzar humo sin olvidar el dominio historico.

### Entrenamiento v6

Run:

```text
models/runs/fire_smoke_v6_replay_mix
```

Pesos iniciales:

```text
exports/best_fire_smoke.pt
```

Configuracion:

| Parametro | Valor |
|---|---:|
| epochs | 40 |
| patience | 8 |
| batch | 16 |
| imgsz | 640 |
| optimizer | AdamW |
| lr0 | 0.00018 |
| cos_lr | True |
| device | 0 |

El entrenamiento paro por early stopping en la epoca 38. La mejor epoca fue la 30. Duracion: 0.839 horas.

Validacion mixta en mejor epoca:

| Clase | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| fire | 0.713 | 0.735 | 0.746 | 0.428 |
| smoke | 0.698 | 0.595 | 0.596 | 0.256 |
| media | 0.706 | 0.665 | 0.671 | 0.342 |

La curva mejora mas tarde que v5 y no muestra una caida clara por overfitting. El mejor punto queda en epoca 30 y despues no se supera, por lo que el early stopping es razonable.

### Comparacion con modelo actual

Test historico fase 3:

| Modelo | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| v3 actual | 0.725 | 0.596 | 0.650 | 0.300 |
| v6 candidato | 0.650 | 0.662 | 0.638 | 0.309 |

Test v5 nuevo:

| Modelo | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| v3 actual | 0.694 | 0.532 | 0.554 | 0.261 |
| v6 candidato | 0.733 | 0.608 | 0.656 | 0.315 |

Test mixto v6:

| Modelo | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| v3 actual | 0.706 | 0.552 | 0.588 | 0.274 |
| v6 candidato | 0.676 | 0.640 | 0.640 | 0.307 |

Lectura:

- v6 mejora mucho el conjunto nuevo y el conjunto mixto.
- En el test historico mantiene mAP50 cerca de v3, sube mAP50-95 y sube recall, pero baja precision.
- El cambio de perfil es claro: v6 detecta mas, especialmente humo, pero acepta mas riesgo de falsos positivos o cajas secundarias.

### Diagnostico de comportamiento con conf=0.15

Wildfire Smoke:

| Test | Modelo | Imagenes | Pred fire | Pred smoke | Sin deteccion |
|---|---|---:|---:|---:|---:|
| v3 historico | v3 actual | 105 | 1 | 94 | 11 |
| v3 historico | v6 candidato | 105 | 0 | 95 | 10 |
| v5 nuevo | v3 actual | 133 | 1 | 119 | 14 |
| v5 nuevo | v6 candidato | 133 | 0 | 122 | 11 |
| v6 mixto | v3 actual | 238 | 2 | 213 | 25 |
| v6 mixto | v6 candidato | 238 | 0 | 217 | 21 |

Cloud/Fog:

| Test | Modelo | Imagenes | Con deteccion | Pred fire | Pred smoke |
|---|---|---:|---:|---:|---:|
| v3 historico | v3 actual | 45 | 0 | 0 | 0 |
| v3 historico | v6 candidato | 45 | 0 | 0 | 0 |
| v5 nuevo | v3 actual | 77 | 3 | 2 | 1 |
| v5 nuevo | v6 candidato | 77 | 2 | 2 | 0 |
| v6 mixto | v3 actual | 122 | 3 | 2 | 1 |
| v6 mixto | v6 candidato | 122 | 2 | 2 | 0 |

D-Fire:

| Test | Modelo | Imagenes | Pred fire | Pred smoke | Sin deteccion |
|---|---|---:|---:|---:|---:|
| v3 historico | v3 actual | 105 | 103 | 1 | 1 |
| v3 historico | v6 candidato | 105 | 103 | 20 | 1 |
| v5 nuevo | v3 actual | 81 | 79 | 3 | 1 |
| v5 nuevo | v6 candidato | 81 | 73 | 22 | 2 |
| v6 mixto | v3 actual | 186 | 182 | 4 | 2 |
| v6 mixto | v6 candidato | 186 | 176 | 42 | 3 |

Interpretacion:

- v6 elimina la confusion `smoke -> fire` observada en Wildfire Smoke.
- v6 detecta mas humo y deja menos imagenes de humo sin deteccion.
- v6 mantiene o reduce falsos positivos en Cloud/Fog.
- v6 empieza a marcar mas cajas `smoke` en imagenes D-Fire, probablemente por presencia visual de humo real o ambiguo en algunas imagenes etiquetadas principalmente como fuego. Este punto debe revisarse visualmente antes de promocionar.

### Artefactos guardados

Modelo actual, intacto:

```text
exports/best_fire_smoke.pt
exports/best_fire_smoke.onnx
```

Candidato v6:

```text
exports/best_fire_smoke_v6_replay_mix.pt
exports/best_fire_smoke_v6_replay_mix.onnx
models/runs/fire_smoke_v6_replay_mix
models/runs_eval/v6_comparison_metrics.json
models/runs_eval/v6_behavior_diagnostics_conf015.json
```

### Decision provisional

v6 es el primer candidato realmente serio para sustituir al modelo actual, pero no se promociona automaticamente. La mejora en humo y recall es clara, y el test nuevo mejora mucho, pero la bajada de precision y el aumento de predicciones `smoke` en D-Fire requieren una prueba visual con el flujo del dashboard y videos antes de cambiar `exports/best_fire_smoke.pt`.

Siguiente paso recomendado: probar el dashboard con v6 como modelo temporal, sin sobrescribir v3. Si en video reduce humo marcado como fuego y no aumenta demasiado falsas alarmas, entonces se puede promocionar v6 como nuevo modelo de produccion.

## Fase 7 - Publicacion en GitHub y preparacion de despliegue

Fecha: 2026-05-28

Objetivo: publicar una version desplegable del proyecto sin secretos ni datos pesados reproducibles.

Acciones:

- Inicializado repositorio Git local y remoto `https://github.com/LHdezLP/sistema_alerta_forestal_petproject.git`.
- Creado `.gitignore` para excluir `.env`, `.venv`, datasets crudos, datasets procesados, runs de entrenamiento, alertas generadas y modelos candidatos.
- Sustituidas credenciales reales detectadas en `agent_02_dashboard.md` por placeholders antes del commit.
- Subido commit inicial `2a3166d` a la rama `main`.
- Incluido el modelo activo actual (`exports/best_fire_smoke.pt` y `.onnx`) para que el aplicativo sea ejecutable tras clonar.
- Incluidos datos territoriales necesarios para la demo de Gran Canaria: ZARI, NASA FIRMS y combustible de Gran Canaria. Se dejan fuera capas de combustible de otras islas para reducir peso.
- Preparado Docker Compose para Isard/servidor Linux con API y dashboard separados.
- Preparado `Dockerfile` raiz para Hugging Face Spaces Docker, sirviendo API + Streamlit a traves de Nginx en el puerto `7860`.

Validacion:

- `python -m compileall api dashboard geo_pipeline scripts -q`: correcto.
- `docker compose -f deploy/docker-compose.yml config` usando un `.env` temporal basado en `.env.example`: correcto.
- `git grep` sobre el commit para patrones de token/API: sin credenciales reales tras la sanitizacion.
- API local `http://127.0.0.1:8000/health`: `status=ok`, modelo cargado.
- Dashboard local `http://127.0.0.1:8501/_stcore/health`: `ok`.

Limitacion:

- No se pudo construir la imagen Docker localmente porque Docker Desktop no estaba levantado en Windows. La prueba real de contenedor queda pendiente en Isard o al iniciar Docker Desktop.
