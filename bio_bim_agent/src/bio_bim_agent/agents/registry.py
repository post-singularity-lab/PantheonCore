"""Definición de los agentes especializados del sistema.

Problema del esbozo original: `from autogen import AssistantAgent, ...` se
ejecutaba a nivel de módulo, así que **cualquier** import de este paquete
(incluso solo para leer los `system_message` en un test) requería tener
`pyautogen` instalado y un `llm_config` válido apuntando a un modelo real.
Eso hace imposible correr tests unitarios rápidos en CI.

Solución: los mensajes de sistema (el conocimiento de dominio de cada
agente) se definen como datos puros en `AGENT_SYSTEM_MESSAGES`, testeables
sin ninguna dependencia. La construcción real de agentes AutoGen se aísla
en `build_agents()`, que importa `autogen` de forma perezosa y solo falla
si de verdad se necesita instanciar agentes conversacionales.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

AGENT_SYSTEM_MESSAGES: Dict[str, str] = {
    "structural": (
        "Eres un ingeniero estructural experto en geometrías bio-inspiradas. "
        "Puedes generar estructuras de celosía orgánica, optimizar para carga "
        "viva y muerta, y sugerir espesores de elementos basados en principios "
        "de crecimiento biológico."
    ),
    "bio_material": (
        "Eres un especialista en materiales biológicos y biomiméticos. Conoces "
        "propiedades de micelio, bacterias cementantes, madera tratada, "
        "bioplásticos, y materiales con capacidad de auto-reparación. Puedes "
        "sugerir combinaciones y tasas de crecimiento/regeneración."
    ),
    "energy_metabolism": (
        "Eres un ingeniero energético especializado en edificios autosuficientes. "
        "Modelas flujos de energía: fotovoltaica orgánica, piezoelectricidad en "
        "pisos, captura de CO2 para biocombustibles, y sistemas de almacenamiento "
        "regenerativo."
    ),
    "regeneration_cycle": (
        "Eres un experto en ciclo de vida y economía circular. Modelas la "
        "degradación de materiales, programas de reemplazo, tasas de reciclaje, "
        "y diseñas edificios como 'bancos de materiales' para desmontaje y reuso."
    ),
    "bim_executor": (
        "Eres el agente que traduce decisiones de diseño en comandos Revit. "
        "Generas código Python que llama a la API de Revit (vía MCP) para "
        "crear, modificar o eliminar elementos."
    ),
}


def build_agents(
    llm_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construye agentes conversacionales reales usando AutoGen.

    Requiere `pyautogen` instalado. Se importa de forma perezosa para que
    el resto del paquete (incluidos los tests) funcione sin esa dependencia.
    """
    try:
        from autogen import AssistantAgent
    except ImportError as exc:
        raise ImportError(
            "pyautogen no está instalado. Instálalo con `pip install pyautogen` "
            "para construir agentes conversacionales reales, o usa "
            "AGENT_SYSTEM_MESSAGES directamente en tus propios tests/orquestación."
        ) from exc

    llm_config = llm_config or {"model": "deepseek-coder"}
    agent_names = {
        "structural": "StructuralEngineer",
        "bio_material": "BioMaterialSpecialist",
        "energy_metabolism": "EnergyMetabolismAgent",
        "regeneration_cycle": "RegenerationCycleAgent",
        "bim_executor": "BIMExecutor",
    }

    return {
        key: AssistantAgent(
            name=agent_names[key],
            system_message=message,
            llm_config=llm_config,
        )
        for key, message in AGENT_SYSTEM_MESSAGES.items()
    }
