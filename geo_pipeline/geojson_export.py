"""Exportacion de capas estaticas para el dashboard."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from geo_pipeline import CAMERA, CRS_CANARIAS_UTM, CRS_WGS84, GC_BBOX, PROJECT_ROOT, RADIO_ANILLOS_KM
from geo_pipeline.combustible_loader import cargar_combustible_gc
from geo_pipeline.firms_loader import cargar_firms
from geo_pipeline.zari_loader import cargar_zari


def _write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, driver="GeoJSON")
    mb = path.stat().st_size / (1024 * 1024)
    aviso = " ADVERTENCIA: supera 5 MB; conviene simplificar mas." if mb > 5 else ""
    print(f"{path}: {mb:.2f} MB.{aviso}")


def _rings() -> gpd.GeoDataFrame:
    punto = gpd.GeoSeries([Point(CAMERA["lon"], CAMERA["lat"])], crs=CRS_WGS84).to_crs(CRS_CANARIAS_UTM).iloc[0]
    rows = []
    for radio in RADIO_ANILLOS_KM:
        rows.append({"radio_km": radio, "geometry": punto.buffer(radio * 1000)})
    return gpd.GeoDataFrame(rows, crs=CRS_CANARIAS_UTM).to_crs(CRS_WGS84)


def exportar_geojsons(ruta_base: str | Path = PROJECT_ROOT) -> None:
    base = Path(ruta_base)
    out = base / "dashboard" / "static" / "geo"
    territoriales = base / "Datasets Territoriales"

    zari = cargar_zari(territoriales / "ZARI")
    if "ISLA" in zari.columns:
        zari = zari[zari["ISLA"].astype(str).str.upper().str.contains("GRAN CANARIA", na=False)]
    zari = zari.copy()
    zari["geometry"] = zari.geometry.simplify(0.001, preserve_topology=True)
    _write_geojson(zari[["ZONA", "B__O__C_", "geometry"]], out / "zari_gc.geojson")

    comb = cargar_combustible_gc(territoriales / "Modelos de Combustible por Isla" / "GRAN CANARIA")
    comb = comb.copy()
    comb = comb[~comb["codigo"].isin(["0", "11"])]
    comb["geometry"] = comb.geometry.simplify(0.005, preserve_topology=True)
    _write_geojson(comb[["codigo", "descripcion", "peso", "geometry"]], out / "combustible_gc.geojson")

    firms = cargar_firms(territoriales / "NASA Firms", GC_BBOX)
    firms = firms.copy()
    firms["anio"] = firms["acq_date"].dt.year
    cols = [c for c in ["latitude", "longitude", "frp", "anio", "geometry"] if c in firms.columns]
    _write_geojson(firms[cols], out / "firms_heatmap_gc.geojson")

    cam = gpd.GeoDataFrame([{**CAMERA, "geometry": Point(CAMERA["lon"], CAMERA["lat"])}], crs=CRS_WGS84)
    _write_geojson(cam, out / "camara.geojson")
    _write_geojson(_rings(), out / "anillos_riesgo.geojson")


if __name__ == "__main__":
    exportar_geojsons(PROJECT_ROOT)
