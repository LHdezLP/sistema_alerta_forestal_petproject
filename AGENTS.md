# AGENTS.md - PlantVision AI adaptado a deteccion de incendios forestales

## Contexto del proyecto

Este proyecto es el Trabajo Final del Master de Especializacion en Inteligencia Artificial y Big Data (IES El Rincon, Las Palmas de Gran Canaria). El objetivo es entrenar un modelo de deteccion de objetos basado en YOLOv8 para identificar `fire` y `smoke` en imagenes, videos, GIFs y capturas de pantalla, con foco en vigilancia forestal.

Entorno previsto:

- Desarrollo local, no cloud.
- GPU NVIDIA RTX 4070, 12 GB VRAM.
- CUDA habilitado.
- Python 3.10+.
- Jupyter Notebook / VS Code.

## Regla 0 - Analisis previo obligatorio

Antes de generar o modificar codigo, revisa:

1. `LuisHernandezRodriguez_Datasets_Elegidos.pdf` o su equivalente en texto, si existe.
2. La estructura real de la raiz del proyecto.
3. Las subcarpetas y formatos de anotacion presentes en `data/raw/`: YOLO `.txt`, COCO `.json`, Pascal VOC `.xml` u otros.

Si el PDF o algun dataset no esta todavia en local, continua creando notebooks y scripts, pero incluye avisos claros al inicio de cada notebook explicando que descargar y donde colocarlo. No inventes rutas de datos: usa busqueda recursiva y documenta cualquier adaptacion con `# ADAPTADO:`.

Estado observado el 2026-05-23: se encontro el PDF `LuisHernandezRodriguez_Datasets Elegidos.docx.pdf` y tres comprimidos en `Images/`:

- `D-Fire.zip`: 21.527 imagenes `.jpg`, 21.527 etiquetas YOLO `.txt` y `data.yaml`. El `data.yaml` local declara `names: ['smoke', 'fire']`, por lo que hay que remapear D-Fire a `0=fire`, `1=smoke` al preparar el dataset final.
- `day_time_wildfire_v2.tar.gz`: 2.191 imagenes `.jpeg` y 2.191 anotaciones Pascal VOC `.xml`.
- `cloud.tar.gz`: 1.296 imagenes `.jpg` sin anotacion.

No extraigas datos automaticamente salvo peticion expresa. Los notebooks deben indicar que esos archivos se extraen a `data/raw/dfire/`, `data/raw/wildfire_smoke/` y `data/raw/cloud_fog/`.

## Estructura objetivo

```text
.
├── data/
│   ├── raw/
│   │   ├── dfire/
│   │   ├── wildfire_smoke/
│   │   └── cloud_fog/
│   ├── processed/
│   │   ├── images/
│   │   │   ├── train/
│   │   │   ├── val/
│   │   │   └── test/
│   │   └── labels/
│   │       ├── train/
│   │       ├── val/
│   │       └── test/
│   └── dataset.yaml
├── notebooks/
│   ├── 00_exploracion_dataset.ipynb
│   ├── 01_preparacion_dataset.ipynb
│   └── 02_entrenamiento_evaluacion.ipynb
├── models/
│   └── runs/
├── exports/
├── inference.py
├── requirements.txt
└── README.md
```

## Seleccion de datos

Construir un dataset procesado activo de 1.700 imagenes para la fase 3:

- D-Fire: 700 imagenes con anotacion YOLO valida y presencia de `fire`, priorizando imagenes exclusivas de fuego para compensar el refuerzo de humo.
- Wildfire Smoke: 700 imagenes con anotaciones de humo. Convertir Pascal VOC o COCO a YOLO si hace falta. Clase YOLO: `1 = smoke`.
- Cloud/Fog: 300 imagenes negativas sin fuego ni humo. Crear `.txt` vacio para cada imagen.

Division final:

- Train: 70%, 1190 imagenes.
- Val: 15%, 255 imagenes.
- Test: 15%, 255 imagenes.

Usar division estratificada con etiqueta temporal `background` para negativos. Semilla fija: `42`.

## Dataset YOLO

`data/dataset.yaml` debe ser compatible con Ultralytics:

```yaml
path: <ruta absoluta o relativa valida a data/processed>
train: images/train
val: images/val
test: images/test

nc: 2
names:
  0: fire
  1: smoke
```

## Notebooks

Los notebooks deben poder ejecutarse de arriba a abajo cuando los datos esten presentes:

- `00_exploracion_dataset.ipynb`: entorno, conteo, formatos, ejemplos con bounding boxes, clases, resoluciones, tamanos relativos de bbox y resumen.
- `01_preparacion_dataset.ipynb`: seleccion reproducible, conversion de anotaciones, copia a `data/processed`, generacion de YAML y validacion final.
- `02_entrenamiento_evaluacion.ipynb`: entrenamiento YOLOv8s, curvas, evaluacion en test, matriz de confusion, ejemplos visuales, tabla final y exportacion.

No uses `!pip install` dentro de notebooks. Las dependencias van en `requirements.txt`.

## Entrenamiento

Modelo elegido: YOLOv8s (`yolov8s.pt`). Justificacion: mejor capacidad que YOLOv8n para patrones de humo/fuego con 1.700 imagenes, sin llegar al riesgo y coste de modelos medianos o grandes.

Hiperparametros base:

- `epochs=100`
- `patience=20`
- `batch=16`
- `imgsz=640`
- `optimizer="AdamW"`
- `lr0=0.001`
- `cos_lr=True`
- `device=0`
- `project="../models/runs"`
- `name="fire_smoke_v3_balanced"` para la fase 3. Mantener `fire_smoke_v1` y `fire_smoke_v2_smoke700` como historico.

No introducir dropout explicito salvo que haya una razon experimental clara. En este proyecto, la regularizacion principal es `weight_decay`, augmentacion, early stopping y transfer learning.

Durante ejecuciones largas de entrenamiento o evaluacion, hacer chequeos temporales cada 10 minutos aproximadamente para comprobar si el usuario ha escrito algo nuevo, si el proceso sigue avanzando y si conviene parar o ajustar. En cada chequeo, dejar un comentario breve de una o dos lineas con lo que se esta ejecutando y el estado observado.

## Inferencia

`inference.py` debe funcionar con solo:

- `inference.py`
- `exports/best_fire_smoke.pt`
- dependencias instaladas

Debe soportar imagen, carpeta, video, GIF y `--source screen`, con cajas `fire` en rojo `#FF4500`, `smoke` en gris `#A0A0A0`, texto `No detections` cuando no haya detecciones y resumen final de tiempos/detecciones.

## Criterios de calidad

- Priorizar legibilidad academica: celdas cortas, Markdown explicativo y funciones con nombres claros.
- No modificar datos originales en `data/raw/`.
- Validar que cada imagen procesada tiene etiqueta correspondiente, aunque sea vacia.
- Guardar graficas personalizadas en `models/runs/<run>/plots_custom/`.
- Mantener scripts autocontenidos y rutas resueltas desde la raiz del proyecto.
