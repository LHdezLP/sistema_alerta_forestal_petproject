"""Carga de modelos de combustible para Gran Canaria."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from geo_pipeline import CRS_CANARIAS_UTM, CRS_WGS84, PROJECT_ROOT

PESOS_COMBUSTIBLE = {
    "GR1": 0.40, "GR2": 0.55, "GR3": 0.65, "GR4": 0.75, "GR5": 0.70, "GR6": 0.80, "GR7": 0.85, "GR8": 0.80, "GR9": 0.85,
    "SH1": 0.55, "SH2": 0.65, "SH3": 0.70, "SH4": 0.75, "SH5": 0.80, "SH6": 0.85, "SH7": 0.90, "SH8": 0.85, "SH9": 0.90,
    "TU1": 0.45, "TU2": 0.50, "TU3": 0.60, "TU4": 0.65, "TU5": 0.70,
    "TL1": 0.30, "TL2": 0.35, "TL3": 0.40, "TL4": 0.45, "TL5": 0.50, "TL6": 0.45, "TL7": 0.55, "TL8": 0.50, "TL9": 0.60,
    "NB1": 0.00, "NB2": 0.00, "NB3": 0.00, "NB8": 0.00, "NB9": 0.00,
}
PESO_COMBUSTIBLE_DESCONOCIDO = 0.30

# ADAPTADO: campo real = mc. El fichero gc_mc_can_sieve.shp usa codigos numericos
# de modelos canarios; se asignan pesos ordinales conservadores para el indice.
PESOS_MC_NUMERICOS = {
    0: 0.00, 1: 0.35, 2: 0.45, 3: 0.55,
    11: 0.00, 42: 0.65, 43: 0.70, 52: 0.72, 53: 0.78, 54: 0.82,
    61: 0.70, 62: 0.75, 63: 0.82, 71: 0.78, 72: 0.82, 75: 0.86, 77: 0.90,
    91: 0.10, 92: 0.15, 731: 0.85, 741: 0.88, 762: 0.92,
}
DESCRIPCIONES_MC_NUMERICOS = {
    0: "Sin combustible o no clasificado",
    11: "Urbano, agua o superficie no combustible",
    42: "Matorral/pastizal de carga media",
    43: "Matorral/pastizal de carga alta",
    63: "Arbolado con sotobosque combustible",
    77: "Matorral denso de alta peligrosidad",
    92: "Agricola o baja combustibilidad",
    731: "Matorral-arbolado de alta continuidad",
    741: "Arbolado con combustible elevado",
    762: "Modelo local de peligrosidad muy alta",
}


def _peso(codigo) -> float:
    if pd.isna(codigo):
        return PESO_COMBUSTIBLE_DESCONOCIDO
    if isinstance(codigo, str):
        return PESOS_COMBUSTIBLE.get(codigo.upper(), PESO_COMBUSTIBLE_DESCONOCIDO)
    return PESOS_MC_NUMERICOS.get(int(codigo), PESO_COMBUSTIBLE_DESCONOCIDO)


def _descripcion(codigo) -> str:
    if pd.isna(codigo):
        return "Modelo desconocido"
    if isinstance(codigo, str):
        return f"Modelo Scott & Burgan {codigo.upper()}"
    return DESCRIPCIONES_MC_NUMERICOS.get(int(codigo), f"Modelo combustible canario {int(codigo)}")


def cargar_combustible_gc(ruta_gc_dir: str | Path) -> gpd.GeoDataFrame:
    ruta = Path(ruta_gc_dir)
    preferido = list(ruta.rglob("gc_mc_can_sieve.shp"))
    shp_files = preferido or sorted(ruta.rglob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"No se encontro SHP de combustible en {ruta_gc_dir}")

    gdf = gpd.read_file(shp_files[0])
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_CANARIAS_UTM)
    if "mc" not in gdf.columns:
        candidatos = [c for c in gdf.columns if c.lower() in {"mod_comb", "modelo", "fuel_model"}]
        if not candidatos:
            raise ValueError("No se detecto campo de modelo de combustible")
        gdf = gdf.rename(columns={candidatos[0]: "mc"})

    gdf = gdf.to_crs(CRS_WGS84)
    gdf["codigo"] = gdf["mc"].astype(str)
    gdf["peso"] = gdf["mc"].map(_peso)
    gdf["descripcion"] = gdf["mc"].map(_descripcion)
    return gdf


def combustible_en_punto(gdf_comb: gpd.GeoDataFrame, lat: float, lon: float, radio_km: float) -> dict:
    punto = gpd.GeoSeries([Point(lon, lat)], crs=CRS_WGS84).to_crs(CRS_CANARIAS_UTM).iloc[0]
    buffer_gdf = gpd.GeoDataFrame(geometry=[punto.buffer(radio_km * 1000)], crs=CRS_CANARIAS_UTM)
    comb_utm = gdf_comb.to_crs(CRS_CANARIAS_UTM)
    zona = gpd.overlay(comb_utm, buffer_gdf, how="intersection")
    if zona.empty:
        return {"codigo_predominante": None, "descripcion": None, "peso": 0.0, "distribucion": {}}

    zona["area_m2"] = zona.geometry.area
    areas = zona.groupby("codigo")["area_m2"].sum().sort_values(ascending=False)
    total = float(areas.sum())
    codigo = str(areas.index[0])
    row = zona[zona["codigo"] == codigo].iloc[0]
    areas_combustibles = areas[~areas.index.astype(str).isin(["0", "11"])]
    codigo_combustible = str(areas_combustibles.index[0]) if not areas_combustibles.empty else None
    row_combustible = zona[zona["codigo"] == codigo_combustible].iloc[0] if codigo_combustible else None
    peso_medio = float((zona["peso"] * zona["area_m2"]).sum() / total)
    combustibles_presentes = []
    for codigo_item, area in areas_combustibles.items():
        porcentaje = float(area / total * 100)
        if porcentaje < 0.05:
            continue
        row_item = zona[zona["codigo"] == str(codigo_item)].iloc[0]
        combustibles_presentes.append(
            {
                "codigo": str(codigo_item),
                "descripcion": row_item.get("descripcion"),
                "porcentaje": round(porcentaje, 2),
                "peso": round(float(row_item.get("peso", 0.0)), 3),
            }
        )
    return {
        "codigo_predominante": codigo,
        "descripcion": row.get("descripcion"),
        "codigo_combustible_principal": codigo_combustible,
        "descripcion_combustible_principal": row_combustible.get("descripcion") if row_combustible is not None else None,
        "peso": round(peso_medio, 3),
        "peso_predominante": float(row.get("peso", 0.0)),
        "combustibles_presentes": combustibles_presentes,
        "distribucion": {str(k): round(float(v / total * 100), 2) for k, v in areas.items()},
    }


if __name__ == "__main__":
    comb = cargar_combustible_gc(PROJECT_ROOT / "Datasets Territoriales" / "Modelos de Combustible por Isla" / "GRAN CANARIA")
    print(comb[["mc", "peso", "descripcion"]].head())
    print(combustible_en_punto(comb, 27.9938, -15.5963, 5.0))
