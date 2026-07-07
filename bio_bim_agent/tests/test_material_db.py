"""Tests para el catálogo de materiales."""

import pytest

from bio_bim_agent.simulation.material_db import get_material, MATERIAL_CATALOG


def test_get_material_returns_biomaterial():
    material = get_material("mycelium_composite")
    assert material.name == "mycelium_composite"
    assert material.growth_rate == 0.03
    assert material.regeneration_cycle_days == 90


def test_get_material_unknown_raises_keyerror_with_clear_message():
    """KeyError debe incluir los materiales disponibles para facilitar debugging."""
    with pytest.raises(KeyError) as exc_info:
        get_material("material_inexistente")
    
    # Verificar que el mensaje incluye los materiales disponibles
    error_message = str(exc_info.value)
    assert "material_inexistente" in error_message
    assert "mycelium_composite" in error_message


def test_material_catalog_has_all_expected_materials():
    """Verifica que el catálogo contenga los 4 materiales base."""
    expected_materials = {
        "mycelium_composite",
        "bacterial_cement",
        "organic_photovoltaic",
        "piezoelectric_flooring",
    }
    assert set(MATERIAL_CATALOG.keys()) == expected_materials


def test_material_properties_are_reasonable():
    """Verifica que los materiales del catálogo tengan propiedades coherentes."""
    for name, material in MATERIAL_CATALOG.items():
        assert material.name == name
        assert material.structural_strength > 0
        assert 0 <= material.degradation_rate <= 1
