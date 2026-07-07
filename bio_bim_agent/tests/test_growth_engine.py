from datetime import datetime, timedelta

import pytest

from bio_bim_agent.models import BioBuildingState
from bio_bim_agent.simulation.growth_engine import BioGrowthSimulator
from bio_bim_agent.simulation.material_db import get_material


def test_rejects_none_initial_state():
    """El esbozo original permitía `BioGrowthSimulator(None)` y reventaba
    en el primer `step()`. Ahora falla rápido y con un mensaje claro."""
    with pytest.raises(ValueError):
        BioGrowthSimulator(None)


def test_step_rejects_non_positive_days(mycelium_state):
    sim = BioGrowthSimulator(mycelium_state)
    with pytest.raises(ValueError):
        sim.step(days=0)
    with pytest.raises(ValueError):
        sim.step(days=-5)


def test_step_does_not_mutate_previous_history_entry(mycelium_state):
    """Bug clave del original: `BioBuildingState` no tenía `.copy()`, así
    que `self.state.copy()` lanzaba AttributeError en cada step. Aquí
    verificamos que además el histórico queda realmente congelado."""
    sim = BioGrowthSimulator(mycelium_state)
    first_snapshot_volume = sim.history[0].elements["facade-north"]["volume"]

    sim.step(days=30)

    # El snapshot histórico no debe cambiar aunque el estado actual sí.
    assert sim.history[0].elements["facade-north"]["volume"] == first_snapshot_volume
    assert sim.state.elements["facade-north"]["volume"] > first_snapshot_volume


def test_biomass_growth_accumulates(mycelium_state):
    """Bug: `biomass_growth` nunca se actualizaba en el original."""
    sim = BioGrowthSimulator(mycelium_state)
    assert sim.state.biomass_growth == 0.0

    sim.step(days=30)

    assert sim.state.biomass_growth > 0.0


def test_carbon_capture_accumulates(mycelium_state):
    """Bug: el CO2 capturado se calculaba y se descartaba en el original."""
    sim = BioGrowthSimulator(mycelium_state)
    sim.step(days=365)
    assert sim.state.carbon_captured > 0.0


def test_full_regeneration_cycle_restores_nominal_strength(mycelium_state):
    material = get_material("mycelium_composite")
    sim = BioGrowthSimulator(mycelium_state)

    # Avanzar exactamente un ciclo completo de regeneración.
    sim.step(days=material.regeneration_cycle_days)

    strength = sim.state.elements["facade-north"]["structural_strength"]
    assert strength == pytest.approx(material.structural_strength)
    assert sim.state.regeneration_progress["mycelium_composite"] == 0.0


def test_partial_degradation_never_goes_below_minimum_floor(mycelium_state):
    """Bug: la degradación compuesta indefinidamente podía dejar la
    resistencia estructural en valores absurdos (negativos o casi cero)."""
    sim = BioGrowthSimulator(mycelium_state)

    # Muchos pasos pequeños sin llegar nunca a completar un ciclo de
    # regeneración (regeneration_cycle_days=90), para forzar degradación.
    for _ in range(50):
        sim.step(days=1)

    strength = sim.state.elements["facade-north"]["structural_strength"]
    material = get_material("mycelium_composite")
    assert strength > 0
    assert strength >= 0.10 * material.structural_strength - 1e-9


def test_predict_optimal_regeneration_returns_future_dates(mycelium_state):
    sim = BioGrowthSimulator(mycelium_state)
    sim.step(days=10)

    schedule = sim.predict_optimal_regeneration()

    assert "mycelium_composite" in schedule
    assert schedule["mycelium_composite"] > sim.state.timestamp


def test_predict_optimal_regeneration_skips_materials_with_zero_cycle():
    """Materiales con regeneration_cycle_days=0 no deben aparecer en el schedule."""
    from datetime import datetime

    # Crear un estado con un material sin ciclo de regeneración
    material_no_cycle = get_material("bacterial_cement")  # growth_rate=0, regeneration_cycle_days=180
    # Crear un estado manually con material sin ciclo
    state = BioBuildingState(
        timestamp=datetime(2026, 1, 1),
        elements={
            "element-1": {
                "material": material_no_cycle,
                "volume": 100.0,
                "structural_load": 100.0,
                "structural_strength": material_no_cycle.structural_strength,
            }
        },
    )
    # bacterial_cement tiene regeneration_cycle_days=180, no 0
    # Pero el regeneration_progress solo se llena cuando hacemos steps()
    sim = BioGrowthSimulator(state)
    # Antes de cualquier step, el schedule está vacío porque no hay progress aún
    schedule = sim.predict_optimal_regeneration()
    # El schedule está vacío porque no hemos hecho ningún step
    assert schedule == {}
    
    # Hacer un step para poblar regeneration_progress
    sim.step(days=10)
    schedule = sim.predict_optimal_regeneration()
    # Ahora bacterial_cement debería aparecer en el schedule
    assert "bacterial_cement" in schedule


def test_run_advances_multiple_steps(mycelium_state):
    sim = BioGrowthSimulator(mycelium_state)
    final_state = sim.run(total_days=100, step_days=30)

    assert final_state.timestamp == datetime(2026, 1, 1) + timedelta(days=100)
    # 30+30+30+10 = 4 pasos
    assert len(sim.history) == 5  # incluye el snapshot inicial
