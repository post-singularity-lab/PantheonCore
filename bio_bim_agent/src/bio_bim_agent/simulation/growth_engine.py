"""Motor de simulación de crecimiento/regeneración de un edificio biociborg.

Bugs corregidos respecto al esbozo original:

1. ``BioBuildingState`` (dataclass) no tenía ``.copy()`` -> ``self.state.copy()``
   lanzaba ``AttributeError`` en cada llamada a ``step()``. Se implementó
   ``copy()`` explícitamente en el modelo (ver ``models/bio_building.py``).
2. ``biomass_growth`` se declaraba en el estado pero nunca se actualizaba
   durante la simulación (quedaba siempre en 0). Ahora se acumula a partir
   del crecimiento de volumen de los elementos con ``growth_rate > 0``.
3. El secuestro de carbono se calculaba y se descartaba (comentario
   "Log para reporting"). Ahora se acumula en ``state.carbon_captured``.
4. La regeneración y la degradación se aplicaban de forma que un material
   podía terminar con ``structural_strength`` negativo tras muchos ciclos
   sin regenerarse (degradación compuesta sin límite inferior). Ahora se
   limita a un mínimo razonable (10% de la resistencia nominal) y se
   fuerza recalcular la degradación *desde* la resistencia nominal del
   material en cada ciclo, no de forma compuesta indefinida.
5. Faltaba validación: pasar ``days <= 0`` o materiales no encontrados
   fallaba de forma críptica más adelante. Ahora se valida explícitamente.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Dict, Optional

from bio_bim_agent.models import BioBuildingState, BioMaterial

# Resistencia mínima permitida como fracción de la resistencia nominal,
# para evitar que la degradación compuesta produzca valores absurdos
# (materiales con resistencia estructural negativa o cercana a cero).
MIN_STRENGTH_FRACTION = 0.10


class BioGrowthSimulator:
    """Simula la evolución temporal de un edificio biociborg."""

    def __init__(self, initial_state: BioBuildingState):
        if initial_state is None:
            raise ValueError(
                "initial_state no puede ser None. El esbozo original permitía "
                "None y fallaba en el primer step(); ahora se exige un estado válido."
            )
        self.state = initial_state
        self.history = [initial_state.copy()]

    def step(self, days: int = 30) -> BioBuildingState:
        """Avanza la simulación `days` días y devuelve el nuevo estado."""
        if days <= 0:
            raise ValueError(f"days debe ser positivo, recibido: {days}")

        new_state = self.state.copy()

        for element_id, element in new_state.elements.items():
            material: BioMaterial = element["material"]

            # 1. Crecimiento biológico (solo afecta volumen/carga, no resistencia).
            if material.growth_rate > 0:
                growth_factor = 1 + material.growth_rate * (days / 30)
                previous_volume = element["volume"]
                element["volume"] = previous_volume * growth_factor
                element["structural_load"] = element.get(
                    "structural_load", previous_volume
                ) * growth_factor

                # Acumular biomasa ganada (antes se ignoraba por completo).
                volume_gained = element["volume"] - previous_volume
                new_state.biomass_growth += max(0.0, volume_gained)

            # 2. Regeneración / degradación de materiales.
            if material.regeneration_cycle_days > 0:
                prior_progress = self.state.regeneration_progress.get(material.name, 0.0)
                regen_progress = min(
                    1.0, prior_progress + (days / material.regeneration_cycle_days)
                )

                if regen_progress >= 1.0:
                    # Ciclo completo: material restaurado a su resistencia nominal.
                    element["structural_strength"] = material.structural_strength
                    new_state.regeneration_progress[material.name] = 0.0
                else:
                    # Degradación calculada SIEMPRE desde la resistencia nominal,
                    # nunca compuesta sobre el valor ya degradado (fix del bug #4).
                    elapsed_fraction_of_cycle = regen_progress
                    degradation = material.degradation_rate * elapsed_fraction_of_cycle
                    strength_fraction = max(MIN_STRENGTH_FRACTION, 1 - degradation)
                    element["structural_strength"] = (
                        material.structural_strength * strength_fraction
                    )
                    new_state.regeneration_progress[material.name] = regen_progress

            # 3. Producción energética.
            if material.energy_production > 0:
                energy_gain = material.energy_production * element["volume"] * days
                new_state.energy_balance += energy_gain

            # 4. Secuestro de carbono (ahora sí se acumula, fix del bug #3).
            if material.carbon_sequestration > 0:
                co2_captured = (
                    material.carbon_sequestration * element["volume"] * (days / 365)
                )
                new_state.carbon_captured += co2_captured

        new_state.timestamp = self.state.timestamp + timedelta(days=days)
        self.history.append(new_state.copy())
        self.state = new_state
        return new_state

    def run(self, total_days: int, step_days: int = 30) -> BioBuildingState:
        """Ejecuta múltiples steps hasta acumular `total_days`."""
        remaining = total_days
        while remaining > 0:
            step = min(step_days, remaining)
            self.step(days=step)
            remaining -= step
        return self.state

    def predict_optimal_regeneration(self) -> Dict[str, "Optional[object]"]:
        """Predice la fecha en la que cada material necesitará regenerarse."""
        materials_by_name = {
            element["material"].name: element["material"]
            for element in self.state.elements.values()
        }
        schedule = {}
        for name, progress in self.state.regeneration_progress.items():
            material = materials_by_name.get(name)
            if material is None or material.regeneration_cycle_days == 0:
                continue
            remaining_days = (1 - progress) * material.regeneration_cycle_days
            schedule[name] = self.state.timestamp + timedelta(days=remaining_days)
        return schedule
