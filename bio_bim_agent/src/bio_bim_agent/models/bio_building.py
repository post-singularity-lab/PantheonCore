"""Modelos de datos para el estado de un 'edificio vivo' (biociborg).

Mejoras respecto a la versión original:
- Validación de rangos en `BioMaterial` (evita tasas negativas o absurdas).
- `BioBuildingState.copy()` implementado explícitamente con `copy.deepcopy`,
  ya que los `dataclass` normales NO tienen `.copy()` por defecto (bug del
  esbozo original que rompía `BioGrowthSimulator.step`).
- Métodos de serialización (`to_dict` / `from_dict`) para poder persistir
  el histórico de simulación en PostgreSQL/JSON sin perder tipos.
- Tipado estricto y docstrings para facilitar el trabajo de los agentes.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any


@dataclass(frozen=True)
class BioMaterial:
    """Propiedades de un material biológico/biomimético.

    Todas las tasas se expresan como fracciones (0.03 == 3%), no como
    porcentajes enteros, para evitar errores de unidades en el motor
    de simulación.
    """

    name: str
    growth_rate: float  # fracción por mes, ej. 0.03 == 3%/mes
    regeneration_cycle_days: int  # días para autoregeneración completa
    carbon_sequestration: float = 0.0  # kg CO2 / m3 / año
    structural_strength: float = 1.0  # MPa (resistencia nominal, 100%)
    energy_production: float = 0.0  # kWh / m3 / día (0 si no es fotovoltaico)
    degradation_rate: float = 0.0  # fracción por año

    def __post_init__(self) -> None:
        if self.growth_rate < 0:
            raise ValueError(f"growth_rate no puede ser negativo: {self.growth_rate}")
        if self.regeneration_cycle_days < 0:
            raise ValueError(
                f"regeneration_cycle_days no puede ser negativo: {self.regeneration_cycle_days}"
            )
        if self.structural_strength <= 0:
            raise ValueError("structural_strength debe ser > 0")
        if not (0 <= self.degradation_rate <= 1):
            raise ValueError("degradation_rate debe estar entre 0 y 1")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BioBuildingState:
    """Snapshot del estado de un edificio biociborg en un instante dado."""

    timestamp: datetime
    elements: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    energy_balance: float = 0.0  # kWh acumulados (positivo = excedente)
    biomass_growth: float = 0.0  # kg de material biológico acumulado
    carbon_captured: float = 0.0  # kg CO2 acumulados (el original lo calculaba y lo descartaba)
    regeneration_progress: Dict[str, float] = field(default_factory=dict)

    def copy(self) -> "BioBuildingState":
        """Copia profunda del estado, necesaria porque los dataclasses no
        implementan `.copy()` automáticamente (bug corregido de la v0)."""
        return copy.deepcopy(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "elements": self.elements,
            "energy_balance": self.energy_balance,
            "biomass_growth": self.biomass_growth,
            "carbon_captured": self.carbon_captured,
            "regeneration_progress": self.regeneration_progress,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BioBuildingState":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            elements=data.get("elements", {}),
            energy_balance=data.get("energy_balance", 0.0),
            biomass_growth=data.get("biomass_growth", 0.0),
            carbon_captured=data.get("carbon_captured", 0.0),
            regeneration_progress=data.get("regeneration_progress", {}),
        )
