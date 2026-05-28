"""Indice compuesto de riesgo territorial."""


def calcular_indice_riesgo(
    dentro_zari: bool,
    peso_combustible: float,
    densidad_firms: dict,
    datos_meteo: dict,
    n_hotspots_max_referencia: int = 700,
) -> dict:
    """Combina ZARI, combustible, FIRMS, viento y temperatura en un indice 0-1."""
    # Logica de negocio: ZARI es contexto estructural, pero no debe dominar por si sola.
    # Combustible y meteorologia ganan peso para que el indice varie entre focos cercanos.
    factor_zari = 1.0 if dentro_zari else 0.0
    factor_combustible = max(0.0, min(float(peso_combustible or 0.0), 1.0))
    factor_firms = min(float(densidad_firms.get("n_hotspots", 0)) / n_hotspots_max_referencia, 1.0)
    viento_vel = datos_meteo.get("viento_vel") or 0.0
    factor_viento = min(float(viento_vel) / 80.0, 1.0)
    temperatura = datos_meteo.get("temperatura")
    factor_temperatura = 0.0 if temperatura is None else min(max((float(temperatura) - 25.0) / 15.0, 0.0), 1.0)

    indice = (
        0.15 * factor_zari
        + 0.35 * factor_combustible
        + 0.20 * factor_firms
        + 0.15 * factor_viento
        + 0.15 * factor_temperatura
    )
    if indice < 0.30:
        nivel, color = "BAJO", "#2ecc71"
    elif indice < 0.55:
        nivel, color = "MODERADO", "#f39c12"
    elif indice < 0.75:
        nivel, color = "ALTO", "#e67e22"
    else:
        nivel, color = "EXTREMO", "#c0392b"

    return {
        "indice": round(float(indice), 3),
        "nivel": nivel,
        "color_hex": color,
        "componentes": {
            "zari": round(factor_zari, 3),
            "combustible": round(factor_combustible, 3),
            "firms": round(factor_firms, 3),
            "viento": round(factor_viento, 3),
            "temperatura": round(factor_temperatura, 3),
        },
    }
