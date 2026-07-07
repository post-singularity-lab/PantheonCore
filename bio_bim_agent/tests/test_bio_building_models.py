from datetime import datetime

import pytest

from bio_bim_agent.models import BioBuildingState, BioMaterial


def test_bio_material_rejects_negative_growth_rate():
    with pytest.raises(ValueError):
        BioMaterial(name="bad", growth_rate=-0.1, regeneration_cycle_days=30)


def test_bio_material_rejects_negative_regeneration_cycle_days():
    """Bug original: no había validación para regeneration_cycle_days negativo."""
    with pytest.raises(ValueError) as exc_info:
        BioMaterial(name="bad", growth_rate=0.0, regeneration_cycle_days=-1)
    assert "regeneration_cycle_days" in str(exc_info.value)


def test_bio_material_rejects_zero_structural_strength():
    """Bug original: no había validación para structural_strength <= 0."""
    with pytest.raises(ValueError) as exc_info:
        BioMaterial(name="bad", growth_rate=0.0, regeneration_cycle_days=30, structural_strength=0)
    assert "structural_strength" in str(exc_info.value)


def test_bio_material_rejects_negative_structural_strength():
    with pytest.raises(ValueError) as exc_info:
        BioMaterial(name="bad", growth_rate=0.0, regeneration_cycle_days=30, structural_strength=-1)
    assert "structural_strength" in str(exc_info.value)


def test_bio_material_rejects_invalid_degradation_rate():
    with pytest.raises(ValueError):
        BioMaterial(
            name="bad",
            growth_rate=0.0,
            regeneration_cycle_days=30,
            degradation_rate=1.5,
        )


def test_bio_material_to_dict_returns_dict():
    """BioMaterial.to_dict() debe funcionar correctamente."""
    material = BioMaterial(
        name="mycelium",
        growth_rate=0.03,
        regeneration_cycle_days=90,
        carbon_sequestration=4.5,
        structural_strength=2.8,
    )
    data = material.to_dict()
    assert isinstance(data, dict)
    assert data["name"] == "mycelium"
    assert data["growth_rate"] == 0.03
    assert data["structural_strength"] == 2.8


def test_state_copy_is_a_deep_copy_not_the_same_object():
    state = BioBuildingState(
        timestamp=datetime(2026, 1, 1),
        elements={"a": {"volume": 1.0}},
    )
    copy = state.copy()

    assert copy is not state
    assert copy.elements is not state.elements
    copy.elements["a"]["volume"] = 999.0
    assert state.elements["a"]["volume"] == 1.0


def test_state_roundtrip_to_dict_from_dict():
    state = BioBuildingState(
        timestamp=datetime(2026, 1, 1),
        energy_balance=42.0,
        biomass_growth=5.0,
        carbon_captured=3.0,
        regeneration_progress={"mycelium_composite": 0.5},
    )
    restored = BioBuildingState.from_dict(state.to_dict())

    assert restored.timestamp == state.timestamp
    assert restored.energy_balance == state.energy_balance
    assert restored.biomass_growth == state.biomass_growth
    assert restored.carbon_captured == state.carbon_captured
    assert restored.regeneration_progress == state.regeneration_progress
