from datetime import datetime

import pytest

from bio_bim_agent.executors.mcp_client import MockRevitExecutor
from bio_bim_agent.models import BioBuildingState
from bio_bim_agent.simulation.material_db import get_material


@pytest.fixture
def mock_executor() -> MockRevitExecutor:
    return MockRevitExecutor()


@pytest.fixture
def mycelium_state() -> BioBuildingState:
    material = get_material("mycelium_composite")
    return BioBuildingState(
        timestamp=datetime(2026, 1, 1),
        elements={
            "facade-north": {
                "material": material,
                "volume": 100.0,
                "structural_load": 100.0,
                "structural_strength": material.structural_strength,
            }
        },
    )
