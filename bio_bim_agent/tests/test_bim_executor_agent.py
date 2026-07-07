from datetime import datetime

from bio_bim_agent.executors.bim_executor_agent import BIMExecutionAgent
from bio_bim_agent.models import BioBuildingState
from bio_bim_agent.simulation.growth_engine import BioGrowthSimulator
from bio_bim_agent.simulation.material_db import get_material


def _state_with_element_registered_in_executor(mock_executor) -> BioBuildingState:
    """Crea el elemento en el executor primero (como haría el orquestador
    real vía `create_bioreactor_panel`) y luego construye el estado de
    simulación referenciando ese mismo id. Un `update_element` sobre un id
    que Revit nunca creó debe fallar (así lo hace también `MockRevitExecutor`),
    así que las fixtures deben reflejar ese orden real de operaciones."""
    material = get_material("mycelium_composite")
    wall = mock_executor.create_wall(
        level="Level 1", start=(0, 0), end=(10, 0), height=3.0, material_name=material.name
    )
    return BioBuildingState(
        timestamp=datetime(2026, 1, 1),
        elements={
            wall["id"]: {
                "material": material,
                "volume": 100.0,
                "structural_load": 100.0,
                "structural_strength": material.structural_strength,
            }
        },
    )


def test_apply_simulation_to_bim_updates_changed_elements(mock_executor):
    """Bug del original: la condición `props.get('volume_changed')` nunca
    era verdadera (nadie seteaba esa clave), así que el modelo BIM nunca
    se actualizaba con los resultados de la simulación. Verificamos que
    ahora sí se detecta el cambio y se llama a `update_element`."""
    state = _state_with_element_registered_in_executor(mock_executor)
    element_id = next(iter(state.elements))
    agent = BIMExecutionAgent(mock_executor)
    sim = BioGrowthSimulator(state)

    state_after_growth = sim.step(days=30)
    result = agent.apply_simulation_to_bim(state_after_growth)

    assert result["updated_elements"], "se esperaba al menos un elemento actualizado"
    update_calls = [c for c in mock_executor.calls if c["command"] == "update_element"]
    assert len(update_calls) == 1
    assert update_calls[0]["params"]["id"] == element_id


def test_apply_simulation_to_bim_is_idempotent_when_nothing_changed(mock_executor):
    """Sincronizar dos veces el mismo estado no debería generar llamadas
    duplicadas a Revit (evita tráfico/costo innecesario)."""
    state = _state_with_element_registered_in_executor(mock_executor)
    agent = BIMExecutionAgent(mock_executor)
    sim = BioGrowthSimulator(state)

    state_after_growth = sim.step(days=30)
    agent.apply_simulation_to_bim(state_after_growth)
    calls_after_first_sync = len(mock_executor.calls)

    # Sincronizar el mismo estado otra vez: no debería añadir llamadas nuevas.
    agent.apply_simulation_to_bim(state_after_growth)
    assert len(mock_executor.calls) == calls_after_first_sync


def test_execute_design_intent_uses_injected_code_generator(mock_executor):
    captured = {}

    def fake_generator(intent, context):
        captured["intent"] = intent
        captured["context"] = context
        return "print('hello')"

    agent = BIMExecutionAgent(mock_executor, code_generator=fake_generator)
    result = agent.execute_design_intent("crea una fachada de micelio", {"level": "Level 1"})

    assert captured["intent"] == "crea una fachada de micelio"
    assert result["status"] == "script_registered"
