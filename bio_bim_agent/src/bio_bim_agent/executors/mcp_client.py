"""Cliente MCP para Revit + una implementación mock para tests/CI.

Problemas del esbozo original:
- `RevitMCPExecutor.__init__` abría la conexión websocket inmediatamente y
  sin manejo de errores: si Revit no estaba corriendo, cualquier import del
  módulo (incluso en tests) reventaba con una excepción de red.
- No existía forma de probar `BIMExecutionAgent`/`BioBuildingOrchestrator`
  sin un Revit real corriendo con el add-in instalado, lo cual hace
  imposible correr tests en CI (GitHub Actions no tiene Revit).
- `create_bioreactor_panel` asumía una forma de respuesta (`wall['id']`)
  que nunca se validaba.

Solución: una interfaz común `RevitExecutorBase` con dos implementaciones:
  * `RevitMCPExecutor`: la real, conecta por websocket de forma perezosa
    (lazy) y solo cuando se usa, con manejo de errores explícito.
  * `MockRevitExecutor`: in-memory, determinista, usada por los tests y
    por CI. Permite validar toda la lógica de agentes/orquestación sin
    depender de Revit ni de red.
"""

from __future__ import annotations

import itertools
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple


class RevitConnectionError(RuntimeError):
    """Se lanza cuando no se puede establecer o usar la conexión con Revit."""


class RevitExecutorBase(ABC):
    """Interfaz común que deben implementar los ejecutores de Revit."""

    @abstractmethod
    def execute_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def create_wall(
        self,
        level: str,
        start: Tuple[float, float],
        end: Tuple[float, float],
        height: float,
        material_name: str,
    ) -> Dict[str, Any]:
        return self.execute_command(
            "create_wall",
            {
                "level": level,
                "start_x": start[0],
                "start_y": start[1],
                "end_x": end[0],
                "end_y": end[1],
                "height": height,
                "material": material_name,
            },
        )

    def create_bioreactor_panel(
        self,
        location: Tuple[float, float],
        size: Tuple[float, float],
        material: str,
        growth_rate: float,
        regeneration_cycle_days: int = 90,
    ) -> Dict[str, Any]:
        wall = self.create_wall(
            "Level 1",
            location,
            (location[0] + size[0], location[1] + size[1]),
            size[1],
            material,
        )
        if "id" not in wall:
            raise RevitConnectionError(
                f"Respuesta de create_wall sin 'id': {wall!r}"
            )
        self.execute_command(
            "set_parameter",
            {
                "element_id": wall["id"],
                "parameter": "Bio_Growth_Rate",
                "value": growth_rate,
            },
        )
        self.execute_command(
            "set_parameter",
            {
                "element_id": wall["id"],
                "parameter": "Bio_Regeneration_Cycle",
                "value": regeneration_cycle_days,
            },
        )
        return wall

    def update_material_properties(
        self, element_id: str, new_strength: float, new_volume: float
    ) -> Dict[str, Any]:
        return self.execute_command(
            "update_element",
            {
                "id": element_id,
                "structural_load": new_strength,
                "volume": new_volume,
            },
        )


class RevitMCPExecutor(RevitExecutorBase):
    """Ejecutor real: habla con el MCP server de Revit vía WebSocket.

    La conexión es perezosa (no se abre en `__init__`) para poder importar
    y construir este objeto sin que Revit esté corriendo (por ejemplo en
    scripts de configuración o al arrancar un orquestador que aún no ha
    recibido ninguna petición).
    """

    def __init__(self, ws_url: str = "ws://localhost:8080", timeout: float = 5.0):
        self.ws_url = ws_url
        self.timeout = timeout
        self._ws = None

    def _ensure_connection(self):
        if self._ws is not None:
            return self._ws
        try:
            import websocket  # import perezoso: dependencia opcional en CI
        except ImportError as exc:
            raise RevitConnectionError(
                "El paquete 'websocket-client' no está instalado. "
                "Instálalo con `pip install websocket-client` para usar "
                "RevitMCPExecutor, o usa MockRevitExecutor en tests."
            ) from exc
        try:
            self._ws = websocket.create_connection(self.ws_url, timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001 - queremos envolver cualquier error de red
            raise RevitConnectionError(
                f"No se pudo conectar al MCP server de Revit en {self.ws_url}: {exc}"
            ) from exc
        return self._ws

    def execute_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        ws = self._ensure_connection()
        message = json.dumps({"command": command, "params": params})
        try:
            ws.send(message)
            raw_response = ws.recv()
        except Exception as exc:  # noqa: BLE001
            raise RevitConnectionError(
                f"Fallo comunicándose con Revit durante '{command}': {exc}"
            ) from exc
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise RevitConnectionError(
                f"Respuesta no-JSON del MCP server: {raw_response!r}"
            ) from exc

    def close(self) -> None:
        if self._ws is not None:
            self._ws.close()
            self._ws = None


class MockRevitExecutor(RevitExecutorBase):
    """Ejecutor en memoria para tests y demos sin Revit instalado.

    Simula el comportamiento del add-in: guarda un diccionario de
    "elementos" y responde de forma determinista, permitiendo probar toda
    la cadena de agentes/orquestación en CI (GitHub Actions, por ejemplo).
    """

    def __init__(self):
        self._id_counter = itertools.count(1)
        self.elements: Dict[str, Dict[str, Any]] = {}
        self.calls: list = []  # historial de comandos, útil para aserciones en tests

    def execute_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append({"command": command, "params": params})

        if command == "create_wall":
            element_id = f"wall-{next(self._id_counter)}"
            self.elements[element_id] = {
                "id": element_id,
                "type": "wall",
                "parameters": {},
                **params,
            }
            return {"id": element_id, "status": "created"}

        if command == "set_parameter":
            element_id = params["element_id"]
            if element_id not in self.elements:
                raise RevitConnectionError(f"Elemento inexistente: {element_id}")
            self.elements[element_id]["parameters"][params["parameter"]] = params["value"]
            return {"id": element_id, "status": "updated"}

        if command == "update_element":
            element_id = params["id"]
            if element_id not in self.elements:
                raise RevitConnectionError(f"Elemento inexistente: {element_id}")
            self.elements[element_id].update(params)
            return {"id": element_id, "status": "updated"}

        if command == "run_python_script":
            # En el mock simplemente registramos que se pidió ejecutar
            # el script; no lo interpretamos (evita ejecutar código
            # arbitrario generado por un LLM dentro de los tests).
            return {"status": "script_registered", "script_len": len(params.get("script", ""))}

        raise RevitConnectionError(f"Comando MCP no soportado por el mock: {command}")
