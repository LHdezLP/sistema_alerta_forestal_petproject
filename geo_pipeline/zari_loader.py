"""Carga de Zonas de Alto Riesgo de Incendio (ZARI)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from geo_pipeline import CRS_CANARIAS_UTM, CRS_WGS84, PROJECT_ROOT


def cargar_zari(ruta_zari_dir: str | Path) -> gpd.GeoDataFrame:
    shp_files = sorted(Path(ruta_zari_dir).rglob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"No se encontro SHP ZARI en {ruta_zari_dir}")

    gdf = gpd.read_file(shp_files[0])
    if gdf.crs is None:
        # ADAPTADO: el SHP local no declara CRS; sus coordenadas encajan con EPSG:32628.
        gdf = gdf.set_crs(CRS_CANARIAS_UTM)
    gdf = gdf.to_crs(CRS_WGS84)
    return gdf


def punto_en_zari(gdf_zari: gpd.GeoDataFrame, lat: float, lon: float) -> dict:
    punto = Point(lon, lat)
    hits = gdf_zari[gdf_zari.geometry.intersects(punto)]
    if hits.empty:
        return {"dentro": False, "zona": None, "boc": None}
    row = hits.iloc[0]
    # ADAPTADO: campos reales del DBF = ZONA y B__O__C_.
    return {
        "dentro": True,
        "zona": row.get("ZONA"),
        "boc": row.get("B__O__C_"),
    }


if __name__ == "__main__":
    zari = cargar_zari(PROJECT_ROOT / "Datasets Territoriales" / "ZARI")
    print(zari[["ZONA", "ISLA", "B__O__C_"]].head())
    print(punto_en_zari(zari, 27.9938, -15.5963))
