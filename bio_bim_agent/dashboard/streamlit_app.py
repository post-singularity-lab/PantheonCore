"""Dashboard de Streamlit para visualizar la evolución de un edificio biociborg.

Uso:
    streamlit run dashboard/streamlit_app.py
"""

import plotly.graph_objects as go
import streamlit as st

from bio_bim_agent.executors.mcp_client import MockRevitExecutor
from bio_bim_agent.orchestrator.workflow import BioBuildingOrchestrator, DesignParams, ElementSpec
from bio_bim_agent.simulation.growth_engine import BioGrowthSimulator


def build_demo_simulator() -> BioGrowthSimulator:
    """Construye una simulación de demostración usando el executor mock,
    para poder abrir el dashboard sin depender de Revit."""
    executor = MockRevitExecutor()
    orchestrator = BioBuildingOrchestrator(executor)
    params = DesignParams(
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
        simulation_days=365 * 3,
        sync_every_days=90,
    )
    orchestrator.design_bio_building(params)
    return orchestrator.simulator


def render_bio_dashboard(simulator: BioGrowthSimulator) -> None:
    st.title("🧬 Edificio Biociborg - Dashboard de Vida")

    fig_biomass = go.Figure()
    fig_biomass.add_trace(
        go.Scatter(
            x=[s.timestamp for s in simulator.history],
            y=[s.biomass_growth for s in simulator.history],
            mode="lines",
            name="Biomasa Acumulada (m3)",
        )
    )
    st.plotly_chart(fig_biomass)

    fig_energy = go.Figure()
    fig_energy.add_trace(
        go.Scatter(
            x=[s.timestamp for s in simulator.history],
            y=[s.energy_balance for s in simulator.history],
            mode="lines",
            name="Balance Energético (kWh)",
            fill="tozeroy",
        )
    )
    st.plotly_chart(fig_energy)

    st.subheader("🔄 Estado de Regeneración")
    for material, progress in simulator.state.regeneration_progress.items():
        st.progress(progress, text=f"{material}: {progress * 100:.1f}%")

    st.subheader("📅 Próximas Regeneraciones Programadas")
    schedule = simulator.predict_optimal_regeneration()
    for material, date in schedule.items():
        st.write(f"- {material}: {date.strftime('%Y-%m-%d')}")

    st.subheader("🌍 Carbono Capturado")
    st.metric("kg CO2 acumulados", f"{simulator.state.carbon_captured:.1f}")


if __name__ == "__main__":
    demo_simulator = build_demo_simulator()
    render_bio_dashboard(demo_simulator)
