"""Catálogo de materiales biológicos/biomiméticos de referencia.

Centraliza los materiales para que agentes y tests compartan la misma
fuente de verdad (evita 'materiales mágicos' definidos inline en cada
script, como ocurría en el esbozo original).
"""

from __future__ import annotations

from typing import Dict

from bio_bim_agent.models import BioMaterial

MATERIAL_CATALOG: Dict[str, BioMaterial] = {
    "mycelium_composite": BioMaterial(
        name="mycelium_composite",
        growth_rate=0.03,
        regeneration_cycle_days=90,
        carbon_sequestration=4.5,
        structural_strength=2.8,
        energy_production=0.0,
        degradation_rate=0.05,
    ),
    "bacterial_cement": BioMaterial(
        name="bacterial_cement",
        growth_rate=0.0,
        regeneration_cycle_days=180,
        carbon_sequestration=1.2,
        structural_strength=25.0,
        energy_production=0.0,
        degradation_rate=0.02,
    ),
    "organic_photovoltaic": BioMaterial(
        name="organic_photovoltaic",
        growth_rate=0.0,
        regeneration_cycle_days=90,
        carbon_sequestration=0.0,
        structural_strength=1.5,
        energy_production=0.18,
        degradation_rate=0.08,
    ),
    "piezoelectric_flooring": BioMaterial(
        name="piezoelectric_flooring",
        growth_rate=0.0,
        regeneration_cycle_days=365,
        carbon_sequestration=0.0,
        structural_strength=10.0,
        energy_production=0.02,
        degradation_rate=0.03,
    ),
}


def get_material(name: str) -> BioMaterial:
    """Devuelve un material del catálogo por nombre.

    Lanza `KeyError` con un mensaje claro si el material no existe,
    en lugar de fallar silenciosamente más adelante en la simulación.
    """
    try:
        return MATERIAL_CATALOG[name]
    except KeyError as exc:
        disponibles = ", ".join(sorted(MATERIAL_CATALOG))
        raise KeyError(
            f"Material '{name}' no encontrado. Disponibles: {disponibles}"
        ) from exc
