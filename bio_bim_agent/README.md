# Bio-BIM Agent 🧬🏗️

Sistema multi-agente que convierte **Revit** en una plataforma de diseño de
"edificios vivos": agentes especializados (estructura, materiales
biológicos, energía/metabolismo, ciclo de regeneración, ejecución BIM)
reciben instrucciones en lenguaje natural, simulan crecimiento biológico y
metabolismo energético, y sincronizan los resultados con el modelo BIM vía
el Protocolo MCP.

Este repo es una **refactorización probada** de un esbozo de arquitectura
inicial: el diseño conceptual se mantiene, pero el código ahora se importa,
se ejecuta y se testea de punta a punta sin depender de Revit ni de un LLM
externo (gracias a un ejecutor mock intercambiable).

## Qué cambió respecto al esbozo original

El esbozo original no era ejecutable tal cual — describía bien la
arquitectura pero tenía varios bugs que impedían correrlo o testearlo.
Esta versión los corrige explícitamente (cada uno documentado en el
docstring del módulo correspondiente):

| # | Bug en el esbozo original | Corrección |
|---|---|---|
| 1 | `BioBuildingState.copy()` no existía (los `dataclass` no lo generan solos) → `AttributeError` en el primer `step()` | `copy()` implementado con `copy.deepcopy` en `models/bio_building.py` |
| 2 | `biomass_growth` se declaraba pero nunca se actualizaba | Se acumula en cada `step()` a partir del crecimiento de volumen |
| 3 | El CO2 capturado se calculaba y se descartaba ("Log para reporting") | Se acumula en `state.carbon_captured` |
| 4 | La degradación estructural podía componerse indefinidamente hasta valores absurdos (negativos) | Se recalcula siempre desde la resistencia nominal, con un piso mínimo del 10% |
| 5 | `apply_simulation_to_bim` comprobaba flags (`volume_changed`, `strength_changed`) que nadie seteaba jamás → el modelo BIM **nunca** se sincronizaba | Se comparan valores actuales contra el último snapshot sincronizado |
| 6 | `RevitMCPExecutor.__init__` abría el WebSocket inmediatamente → importar el módulo sin Revit corriendo rompía todo, incluidos los tests | Conexión perezosa (`_ensure_connection`) + `MockRevitExecutor` para tests/CI |
| 7 | `execute_design_intent` llamaba a `self.llm.generate_code(...)` y `self._load_revit_api_docs()`, nunca definidos | Generador de código inyectable (`code_generator`), con un stub determinista por defecto |
| 8 | `BioBuildingOrchestrator.design_bio_building` llamaba a `manager.run()` (no existe en AutoGen) y a métodos nunca implementados (`_extract_design_params`, `_bim_to_state`, `_export_bim`, `_generate_health_report`) | Pipeline reescrito con `DesignParams` explícito y 100% ejecutable/testeable, sin acoplarse a una API de AutoGen concreta |
| 9 | `from autogen import ...` a nivel de módulo obligaba a tener `pyautogen` instalado solo para leer los `system_message` de los agentes | `AGENT_SYSTEM_MESSAGES` como datos puros; `build_agents()` importa AutoGen de forma perezosa |
| 10 | `datetime.utcnow()` deprecated warning en Python 3.12+ | Usar `datetime.now(timezone.utc)` en `workflow.py` |

## Estructura del proyecto

```
bio_bim_agent/
├── src/bio_bim_agent/
│   ├── models/           # BioMaterial, BioBuildingState (con validación y copy() real)
│   ├── simulation/        # Motor de crecimiento/regeneración + catálogo de materiales
│   ├── executors/         # Cliente MCP real (Revit) + mock para tests/CI
│   ├── agents/            # System messages de los agentes + construcción AutoGen (opcional)
│   └── orchestrator/      # Pipeline completo: diseño -> simulación -> sync BIM
├── dashboard/             # Dashboard Streamlit (usa el executor mock por defecto)
├── tests/                 # Suite pytest (34 tests, todos dirigidos a los bugs de la tabla)
├── config/                # Configuración de LLM local y del MCP server
└── .github/workflows/     # CI: pytest en Python 3.10/3.11/3.12/3.13 + lint ruff
```

## Instalación

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # núcleo + pytest
pip install -e ".[dev,revit]"    # + websocket-client, para conectar a Revit real
pip install -e ".[dashboard]"    # + streamlit/plotly, para el dashboard
```

## Correr los tests

```bash
pytest                                        # suite completa
pytest --cov=bio_bim_agent --cov-report=term-missing  # con cobertura
```

Los tests **no requieren Revit ni ningún LLM**: usan `MockRevitExecutor`
(un ejecutor en memoria que simula las respuestas del add-in de Revit) y un
generador de código inyectable en lugar de un LLM real. Esto es lo que
permite correrlos en GitHub Actions sin infraestructura adicional — la
carpeta `.github/workflows/tests.yml` ya está lista para eso.

> **Nota sobre "OpenHands" / agentes de test automatizados**: este sandbox
> no tiene acceso de red, así que no pude invocar herramientas externas
> (OpenHands, pip install de paquetes no cacheados, etc.) durante la
> generación de este entregable. En su lugar, escribí y corrí manualmente
> el equivalente exacto de cada test de la suite pytest (mismos asserts,
> mismos fixtures) para verificar que todo el pipeline importa y corre sin
> errores antes de empaquetarlo. Al clonar el repo con conexión a internet,
> `pytest` correrá esa misma suite tal cual, y el workflow de CI la
> ejecutará automáticamente en cada push/PR.

## Uso rápido (sin Revit, con el executor mock)

```python
from bio_bim_agent.executors.mcp_client import MockRevitExecutor
from bio_bim_agent.orchestrator.workflow import (
    BioBuildingOrchestrator, DesignParams, ElementSpec,
)

executor = MockRevitExecutor()
orchestrator = BioBuildingOrchestrator(executor)

params = DesignParams(
    elements=[
        ElementSpec("facade-north", "mycelium_composite", (0, 0), (10, 3), 30.0, 30.0),
        ElementSpec("roof-pv", "organic_photovoltaic", (0, 3), (10, 1), 10.0, 10.0),
    ],
    simulation_days=365 * 5,
    sync_every_days=180,
)

report = orchestrator.design_bio_building(params)
print(report["energy_balance"], report["biomass_grown"], report["regeneration_schedule"])
```

## Uso con Revit real

1. Instala el MCP server para Revit (add-in) siguiendo la documentación de
   tu servidor MCP (`mcp-server-for-revit`, `pyRevit Routes`, etc.).
2. Usa `RevitMCPExecutor` en vez de `MockRevitExecutor`:

```python
from bio_bim_agent.executors.mcp_client import RevitMCPExecutor

executor = RevitMCPExecutor(ws_url="ws://localhost:8080")
orchestrator = BioBuildingOrchestrator(executor)
# ... igual que arriba
```

## Dashboard

```bash
streamlit run dashboard/streamlit_app.py
```

## Roadmap (fuera del alcance de este entregable)

- Derivar `DesignParams` automáticamente a partir de una conversación
  multi-agente real (`agents.build_agents()` + AutoGen `GroupChat`), en
  vez de construirlos a mano.
- Persistencia del histórico de simulación en PostgreSQL/TimescaleDB.
- Generación real de código C#/Python vía un LLM (sustituyendo
  `default_code_generator` por una llamada a Ollama/Claude/etc.).

## Licencia

MIT. Ver [`LICENSE`](./LICENSE).
