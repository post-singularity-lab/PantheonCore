"""Agente que traduce decisiones de diseño / estados de simulación en
comandos concretos sobre el modelo BIM (vía un `RevitExecutorBase`).

Bugs corregidos respecto al esbozo original:

1. `apply_simulation_to_bim` comprobaba `props.get('volume_changed')` y
   `props.get('strength_changed')`, pero ningún componente del sistema
   escribía nunca esas claves -> la condición era siempre falsa y el
   modelo BIM jamás se actualizaba con los resultados de la simulación.
   Ahora se comparan los valores actuales contra el último snapshot
   sincronizado (`self._last_synced`) para decidir qué actualizar.
2. `execute_design_intent` llamaba a `self.llm.generate_code(...)` y
   `self._load_revit_api_docs()` sin que existieran en ningún lado
   (el esbozo nunca definía `_init_llm`). Ahora el generador de código
   se inyecta como una función (`code_generator`), con un generador por
   defecto que no depende de ningún servicio externo y es 100% testeable.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from bio_bim_agent.executors.mcp_client import RevitExecutorBase
from bio_bim_agent.models import BioBuildingState

CodeGenerator = Callable[[str, Dict[str, Any]], str]


def default_code_generator(intent: str, context: Dict[str, Any]) -> str:
    """Generador de código por defecto: no llama a ningún LLM externo.

    Sirve como placeholder determinista para tests y para uso sin API
    keys configuradas. En producción se sustituye por una llamada real
    a Ollama/Claude/etc. inyectando otro `code_generator`.
    """
    return (
        "# Script generado automáticamente (placeholder determinista)\n"
        f"# Intención: {intent}\n"
        f"# Contexto: {context}\n"
    )


class BIMExecutionAgent:
    """Aplica intenciones de diseño y estados de simulación sobre Revit."""

    def __init__(
        self,
        executor: RevitExecutorBase,
        code_generator: Optional[CodeGenerator] = None,
    ):
        self.executor = executor
        self.code_generator = code_generator or default_code_generator
        # Guarda el último valor sincronizado por elemento para poder
        # detectar cambios reales (fix del bug #1).
        self._last_synced: Dict[str, Dict[str, float]] = {}

    def execute_design_intent(self, intent: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Traduce una intención de diseño en lenguaje natural a un script,
        y lo despacha al ejecutor de Revit (vía `run_python_script`)."""
        code = self.code_generator(intent, context)
        return self.executor.execute_command(
            "run_python_script", {"script": code, "context": context}
        )

    def apply_simulation_to_bim(self, sim_state: BioBuildingState) -> Dict[str, Any]:
        """Sincroniza un estado de simulación con el modelo BIM actual,
        actualizando solo los elementos cuyo volumen o resistencia
        estructural cambiaron desde la última sincronización."""
        results = []
        for element_id, props in sim_state.elements.items():
            previous = self._last_synced.get(element_id, {})
            current_volume = props.get("volume")
            current_strength = props.get("structural_strength")

            volume_changed = previous.get("volume") != current_volume
            strength_changed = previous.get("structural_strength") != current_strength

            if not (volume_changed or strength_changed):
                continue

            self.executor.update_material_properties(
                element_id,
                new_strength=current_strength,
                new_volume=current_volume,
            )
            self.executor.execute_command(
                "set_parameter",
                {
                    "element_id": element_id,
                    "parameter": "Bio_Last_Simulation_Timestamp",
                    "value": sim_state.timestamp.isoformat(),
                },
            )
            self._last_synced[element_id] = {
                "volume": current_volume,
                "structural_strength": current_strength,
            }
            results.append({"element": element_id, "updated": True})

        return {"updated_elements": results}
