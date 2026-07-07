import pytest

from bio_bim_agent.executors.mcp_client import (
    MockRevitExecutor,
    RevitConnectionError,
    RevitMCPExecutor,
)


def test_mock_create_wall_returns_id(mock_executor):
    result = mock_executor.create_wall(
        level="Level 1", start=(0, 0), end=(5, 0), height=3.0, material_name="bacterial_cement"
    )
    assert "id" in result
    assert result["status"] == "created"
    assert result["id"] in mock_executor.elements


def test_mock_create_bioreactor_panel_sets_bio_parameters(mock_executor):
    panel = mock_executor.create_bioreactor_panel(
        location=(0, 0),
        size=(10, 3),
        material="mycelium_composite",
        growth_rate=0.03,
        regeneration_cycle_days=90,
    )
    element = mock_executor.elements[panel["id"]]
    assert element["parameters"]["Bio_Growth_Rate"] == 0.03
    assert element["parameters"]["Bio_Regeneration_Cycle"] == 90


def test_mock_set_parameter_on_unknown_element_raises(mock_executor):
    with pytest.raises(RevitConnectionError):
        mock_executor.execute_command(
            "set_parameter",
            {"element_id": "does-not-exist", "parameter": "X", "value": 1},
        )


def test_mock_unsupported_command_raises(mock_executor):
    with pytest.raises(RevitConnectionError):
        mock_executor.execute_command("delete_everything", {})


def test_real_executor_does_not_connect_at_construction():
    """Bug del original: `websocket.create_connection` se llamaba en
    `__init__`, así que solo importar/instanciar el ejecutor ya requería
    tener Revit corriendo. Ahora la conexión es perezosa."""
    executor = RevitMCPExecutor(ws_url="ws://localhost:9999")
    assert executor._ws is None  # aún no se ha conectado


def test_real_executor_raises_clear_error_when_revit_unreachable():
    executor = RevitMCPExecutor(ws_url="ws://localhost:9", timeout=0.2)
    with pytest.raises(RevitConnectionError):
        executor.execute_command("create_wall", {})
