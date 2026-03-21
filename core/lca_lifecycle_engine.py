import pandas as pd
import numpy as np
import logging

from .exceptions import VolumeCalculationError

logger = logging.getLogger(__name__)


class LCALifecycleEngine:
    """
    Legacy thin wrapper kept for backwards compatibility.
    New code should use LCAMathEngine directly, which now handles all modules
    A1-D in a single pipeline per EN 15978/EN 15804.
    """

    def __init__(self, transport_factor: float = 0.0603e-3):
        # Default: HGV 40t rigid factor (DEFRA 2023), kgCO2e / (kg · km)
        self.transport_factor = transport_factor

    def calculate_transport_emissions(self, df: pd.DataFrame, dist_km: float) -> pd.DataFrame:
        if 'mass_kg' not in df.columns:
            raise ValueError("Call calculate_embodied_carbon first — 'mass_kg' column is missing.")
        df = df.copy()
        df['transport_a4_kgco2e'] = df['mass_kg'] * dist_km * self.transport_factor
        return df

    def calculate_end_of_life_emissions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Per-material C1-C4 EoL factors (kgCO2e/kg).
        Negative values = net credit from recycling (steel, aluminium).
        Source: ICE Database v3.0 / BRE Green Guide Module C benchmarks.
        """
        EOL_MAP = {
            "Concrete": 0.0088,
            "Steel":   -0.410,
            "Timber":   0.015,
            "Aluminium": -0.860,
        }

        df = df.copy()
        df['eol_kgco2e_per_kg'] = df['material_class'].map(EOL_MAP).fillna(0.020)
        df['end_of_life_c_kgco2e'] = df['mass_kg'] * df['eol_kgco2e_per_kg']
        df.drop(columns=['eol_kgco2e_per_kg'], inplace=True)
        return df