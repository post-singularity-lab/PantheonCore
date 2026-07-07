from bio_bim_agent.executors.mcp_client import MockRevitExecutor
from bio_bim_agent.orchestrator.workflow import (
    BioBuildingOrchestrator,
    DesignParams,
    ElementSpec,
)


def _sample_params(simulation_days=180, sync_every_days=90) -> DesignParams:
    return DesignParams(
        elements=[
            ElementSpec(
                element_id="facade-north",
                material_name="mycelium_composite",
                location=(0.0, 0.0),
                size=(10.0, 3.0),
                volume=30.0,
                structural_load=30.0,
            ),
            ElementSpec(
                element_id="roof-pv",
                material_name="organic_photovoltaic",
                location=(0.0, 3.0),
                size=(10.0, 1.0),
                volume=10.0,
                structural_load=10.0,
            ),
        ],
        simulation_days=simulation_days,
        sync_every_days=sync_every_days,
    )


def test_orchestrator_runs_full_pipeline_end_to_end():
    """El esbozo original no podía ni importarse de punta a punta:
    llamaba a métodos nunca definidos (`_extract_design_params`,
    `_bim_to_state`, `_export_bim`, etc.) y a una API de AutoGen
    inexistente. Este test corre el pipeline completo con un executor
    mock, sin red ni LLMs."""
    executor = MockRevitExecutor()
    orchestrator = BioBuildingOrchestrator(executor)

    report = orchestrator.design_bio_building(_sample_params())

    assert report["energy_balance"] > 0  # el panel fotovoltaico generó energía
    assert report["biomass_grown"] > 0  # el micelio creció
    assert report["carbon_captured"] > 0
    assert report["simulation_steps"] > 1
    assert "mycelium_composite" in report["regeneration_schedule"]


def test_orchestrator_creates_real_bim_elements_via_executor():
    executor = MockRevitExecutor()
    orchestrator = BioBuildingOrchestrator(executor)

    orchestrator.design_bio_building(_sample_params())

    create_wall_calls = [c for c in executor.calls if c["command"] == "create_wall"]
    assert len(create_wall_calls) == 2  # una por cada ElementSpec


def test_orchestrator_syncs_bim_at_least_once():
    executor = MockRevitExecutor()
    orchestrator = BioBuildingOrchestrator(executor)

    orchestrator.design_bio_building(_sample_params(simulation_days=60, sync_every_days=30))

    update_calls = [c for c in executor.calls if c["command"] == "update_element"]
    assert len(update_calls) >= 1
