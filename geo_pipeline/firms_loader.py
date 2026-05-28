"""Carga y analisis de puntos historicos NASA FIRMS."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from geo_pipeline import CRS_CANARIAS_UTM, CRS_WGS84, GC_BBOX, PROJECT_ROOT

MESES_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    if "latitude" not in out.columns and "lat" in out.columns:
        out = out.rename(columns={"lat": "latitude"})
    if "longitude" not in out.columns and "lon" in out.columns:
        out = out.rename(columns={"lon": "longitude"})
    if "bright_ti4" not in out.columns and "brightness" in out.columns:
        out["bright_ti4"] = out["brightness"]
    return out


def _leer_firms(ruta_firms_dir: str | Path) -> gpd.GeoDataFrame:
    ruta = Path(ruta_firms_dir)
    shp_files = sorted(ruta.rglob("*.shp"))
    csv_files = sorted(ruta.rglob("*.csv"))
    frames: list[gpd.GeoDataFrame] = []

    for shp in shp_files:
        gdf = gpd.read_file(shp)
        gdf = _normalizar_columnas(gdf)
        if gdf.crs is None:
            gdf = gdf.set_crs(CRS_WGS84)
        frames.append(gdf.to_crs(CRS_WGS84))

    for csv in csv_files:
        df = _normalizar_columnas(pd.read_csv(csv))
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
            crs=CRS_WGS84,
        )
        frames.append(gdf)

    if not frames:
        raise FileNotFoundError(f"No se encontraron ficheros FIRMS CSV/SHP en {ruta}")
    return pd.concat(frames, ignore_index=True)


def _filtrar_confianza(df: pd.DataFrame, confianza_minima: str) -> pd.DataFrame:
    if "confidence" not in df.columns:
        return df
    conf = df["confidence"]
    numeric = pd.to_numeric(conf, errors="coerce")
    if numeric.notna().sum() > len(df) * 0.8:
        return df[numeric >= 30].copy()

    min_conf = confianza_minima.strip().lower()
    aceptadas = {"nominal": {"n", "nominal", "h", "high"}, "high": {"h", "high"}}
    valores = aceptadas.get(min_conf, aceptadas["nominal"])
    return df[conf.astype(str).str.lower().isin(valores)].copy()


def cargar_firms(
    ruta_firms_dir: str | Path,
    bbox: dict = GC_BBOX,
    confianza_minima: str = "nominal",
) -> gpd.GeoDataFrame:
    """Carga FIRMS, filtra Gran Canaria y devuelve puntos limpios en EPSG:4326."""
    bruto = _leer_firms(ruta_firms_dir)
    total = len(bruto)

    # ADAPTADO: el SHP local usa LATITUDE/LONGITUDE y CONFIDENCE con letras VIIRS n/h/l.
    df = _normalizar_columnas(bruto)
    df = df[
        df["longitude"].between(bbox["lon_min"], bbox["lon_max"])
        & df["latitude"].between(bbox["lat_min"], bbox["lat_max"])
    ].copy()
    df = _filtrar_confianza(df, confianza_minima)
    cols = [
        c
        for c in [
            "latitude",
            "longitude",
            "acq_date",
            "acq_time",
            "confidence",
            "frp",
            "bright_ti4",
            "brightness",
            "instrument",
            "satellite",
        ]
        if c in df.columns
    ]
    df = df[cols].copy()
    df["acq_date"] = pd.to_datetime(df.get("acq_date"), errors="coerce")
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs=CRS_WGS84,
    )

    fechas = gdf["acq_date"].dropna()
    rango = "sin fechas" if fechas.empty else f"{fechas.min().date()} - {fechas.max().date()}"
    distribucion = gdf["confidence"].value_counts(dropna=False).to_dict() if "confidence" in gdf else {}
    print(f"FIRMS: {total} registros totales; {len(gdf)} tras filtros; fechas {rango}")
    print(f"Confianza: {distribucion}")
    return gdf


def densidad_hotspots(
    gdf_firms: gpd.GeoDataFrame,
    punto_lat: float,
    punto_lon: float,
    radio_km: float,
) -> dict:
    """Resume la actividad historica FIRMS dentro de un radio en kilometros."""
    if gdf_firms.empty:
        return {"n_hotspots": 0, "frp_max": 0.0, "frp_medio": 0.0, "anio_pico": None, "mes_pico": None, "n_por_anio": {}}

    punto = gpd.GeoSeries([Point(punto_lon, punto_lat)], crs=CRS_WGS84).to_crs(CRS_CANARIAS_UTM).iloc[0]
    firms_utm = gdf_firms.to_crs(CRS_CANARIAS_UTM)
    zona = firms_utm[firms_utm.geometry.within(punto.buffer(radio_km * 1000))]
    if zona.empty:
        return {"n_hotspots": 0, "frp_max": 0.0, "frp_medio": 0.0, "anio_pico": None, "mes_pico": None, "n_por_anio": {}}

    fechas = pd.to_datetime(zona.get("acq_date"), errors="coerce")
    anios = fechas.dt.year.dropna().astype(int)
    meses = fechas.dt.month.dropna().astype(int)
    n_por_anio = anios.value_counts().sort_index().to_dict()
    frp = pd.to_numeric(zona.get("frp", pd.Series(dtype=float)), errors="coerce")
    return {
        "n_hotspots": int(len(zona)),
        "frp_max": float(frp.max()) if frp.notna().any() else 0.0,
        "frp_medio": float(frp.mean()) if frp.notna().any() else 0.0,
        "anio_pico": int(anios.value_counts().idxmax()) if not anios.empty else None,
        "mes_pico": MESES_ES.get(int(meses.value_counts().idxmax())) if not meses.empty else None,
        "n_por_anio": {int(k): int(v) for k, v in n_por_anio.items()},
    }


if __name__ == "__main__":
    firms = cargar_firms(PROJECT_ROOT / "Datasets Territoriales" / "NASA Firms")
    print(densidad_hotspots(firms, 27.9938, -15.5963, 15.0))
