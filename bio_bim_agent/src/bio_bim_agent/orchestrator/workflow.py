"""Orquestador principal: coordina agentes, simulación y ejecución BIM.

El esbozo original encadenaba varios métodos que nunca se implementaban
(`_extract_design_params`, `_generate_initial_bim`, `_bim_to_state`,
`_generate_health_report`, `_export_bim`) y usaba una API de AutoGen
(`manager.run()`) que no existe en `pyautogen`. El resultado era un
pipeline que ni siquiera se podía importar sin `NameError`, y mucho menos
correr en un test.

Este módulo separa dos responsabilidades:

1. **`DesignParams`**: una estructura explícita y validable con las
   decisiones de diseño (qué material va en qué elemento, tasas de
   crecimiento, ciclo de regeneración, etc.). Puede construirse a mano,
   o —cuando `pyautogen` esté disponible y configurado— derivarse de una
   conversación multi-agente real (fuera del alcance de este módulo, para
   no acoplar la lógica de simulación a un LLM concreto).
2. **`BioBuildingOrchestrator`**: dado un `DesignParams` y un
   `RevitExecutorBase` (real o mock), genera la geometría inicial, corre
   la simulación de crecimiento/regeneración, sincroniza periódicamente
   con el modelo BIM, y devuelve un reporte final. Esta parte es 100%
   determinista y testeable sin red ni LLMs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bio_bim_agent.executors.bim_executor_agent import BIMExecutionAgent
from bio_bim_agent.executors.mcp_client import RevitExecutorBase
from bio_bim_agent.models import BioBuildingState
from bio_bim_agent.simulation.growth_engine import BioGrowthSimulator
from bio_bim_agent.simulation.material_db import get_material


@dataclass
class ElementSpec:
    """Especificación de un elemento inicial del edificio."""

    element_id: str
    material_name: str
    location: tuple
    size: tuple
    volume: float
    structural_load: float


@dataclass
class DesignParams:
    """Parámetros de diseño de un edificio biociborg.

    En el esbozo original esto era un comentario ("params = {...}") nunca
    materializado como estructura real; aquí se define explícitamente.
    """

    elements: List[ElementSpec] = field(default_factory=list)
    simulation_days: int = 30 * 60  # 5 años por defecto
    sync_every_days: int = 30 * 6  # sincronizar BIM cada 6 meses
    step_days: int = 30


class BioBuildingOrchestrator:
    """Coordina la generación inicial, la simulación y la sincronización BIM."""

    def __init__(self, executor: RevitExecutorBase):
        self.executor = executor
        self.bim_agent = BIMExecutionAgent(executor)
        self.simulator: Optional[BioGrowthSimulator] = None

    def design_bio_building(self, params: DesignParams) -> Dict[str, Any]:
        """Ejecuta el pipeline completo: geometría inicial -> simulación -> sync BIM."""
        initial_state = self._generate_initial_bim(params)
        self.simulator = BioGrowthSimulator(initial_state)

        remaining = params.simulation_days
        elapsed_since_sync = 0
        while remaining > 0:
            step = min(params.step_days, remaining)
            state = self.simulator.step(days=step)
            remaining -= step
            elapsed_since_sync += step

            if elapsed_since_sync >= params.sync_every_days:
                self.bim_agent.apply_simulation_to_bim(state)
                elapsed_since_sync = 0

        # Sincronización final para no perder el último tramo simulado.
        self.bim_agent.apply_simulation_to_bim(self.simulator.state)

        return {
            "final_state": self.simulator.state.to_dict(),
            "simulation_steps": len(self.simulator.history),
            "regeneration_schedule": {
                name: date.isoformat()
                for name, date in self.simulator.predict_optimal_regeneration().items()
            },
            "energy_balance": self.simulator.state.energy_balance,
            "biomass_grown": self.simulator.state.biomass_growth,
            "carbon_captured": self.simulator.state.carbon_captured,
        }

    def _generate_initial_bim(self, params: DesignParams) -> BioBuildingState:
        """Crea los elementos en Revit (vía el executor) y construye el
        estado inicial de simulación a partir de las respuestas reales del
        modelo BIM (en vez de asumir su forma, como hacía el esbozo original)."""
        elements: Dict[str, Dict[str, Any]] = {}

        for spec in params.elements:
            material = get_material(spec.material_name)
            bim_response = self.executor.create_bioreactor_panel(
                location=spec.location,
                size=spec.size,
                material=spec.material_name,
                growth_rate=material.growth_rate,
                regeneration_cycle_days=material.regeneration_cycle_days,
            )
            element_id = bim_response.get("id", spec.element_id)
            elements[element_id] = {
                "material": material,
                "volume": spec.volume,
                "structural_load": spec.structural_load,
                "structural_strength": material.structural_strength,
            }

        return BioBuildingState(timestamp=datetime.now(timezone.utc), elements=elements)
