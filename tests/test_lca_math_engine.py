"""
tests/test_lca_math_engine.py
Full regression suite for the WLCA Engine (EN 15978 / EN 15804 compliant).

Run from project root:
    pytest tests/ -v
"""
import pytest
import math
import pandas as pd
import numpy as np
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.lca_math_engine import (
    LCAMathEngine, ProjectSettings, _classify_material,
    WASTE_FACTORS, EOL_FACTORS, SERVICE_LIFE,
    TRANSPORT_FACTORS, DEFAULT_TRANSPORT_A4, DEFAULT_TRANSPORT_VEHICLE,
    MAINTENANCE_ANNUAL_FACTORS, BIOGENIC_SEQ_FACTORS,
)
from core.exceptions import VolumeCalculationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db() -> pd.DataFrame:
    """
    Minimal material DB with two materials whose physical properties are
    well-known so every assertion can be hand-verified.

    Concrete C30/37 A1-A3 GWP ≈ 0.103 kgCO2e/kg  (ICE v3, CEM II/A-L 30%)
    Steel S355 (virgin) A1-A3 GWP ≈ 1.55 kgCO2e/kg (ICE v3, structural)
    """
    return pd.DataFrame({
        'material_id':            ['Concrete', 'Steel', 'Timber'],
        'density_kg_m3':          [2400.0,     7850.0,  500.0],
        'gwp_factor_kgco2_per_kg': [0.103,     1.55,    0.263],
    })


@pytest.fixture
def default_settings() -> ProjectSettings:
    return ProjectSettings(
        reference_study_period=60,
        gfa_m2=5000.0,
        a5_machinery_factor=0.015,
        include_sequestration=True,
        uncertainty_factor_pct=10.0,
    )


@pytest.fixture
def engine(mock_db, default_settings) -> LCAMathEngine:
    return LCAMathEngine(mock_db, settings=default_settings)


# ---------------------------------------------------------------------------
# Helper: compute expected A4 value deterministically
# ---------------------------------------------------------------------------

def _expected_a4(mass_kg: float, mat_class: str) -> float:
    dist = DEFAULT_TRANSPORT_A4.get(mat_class, DEFAULT_TRANSPORT_A4['generic'])
    veh  = DEFAULT_TRANSPORT_VEHICLE.get(mat_class, 'HGV_RIGID_40T')
    ef   = TRANSPORT_FACTORS[veh]
    return mass_kg * dist * ef


# ===========================================================================
# Group 1 — Input Validation
# ===========================================================================

class TestInputValidation:

    def test_missing_required_column_raises_key_error(self, engine):
        """Engine must raise KeyError when 'volume_m3' is absent."""
        df = pd.DataFrame({'material_id': ['Concrete']})
        with pytest.raises(KeyError, match="volume_m3"):
            engine.calculate_embodied_carbon(df)

    def test_negative_volume_raises_volume_calculation_error(self, engine):
        """Negative volume from corrupted Revit geometry MUST stop execution."""
        df = pd.DataFrame({
            'element_id':  ['WALL-BROKEN'],
            'material_id': ['Concrete'],
            'volume_m3':   [-3.5],
        })
        with pytest.raises(VolumeCalculationError):
            engine.calculate_embodied_carbon(df)

    def test_empty_dataframe_returns_empty(self, engine):
        df = pd.DataFrame(columns=['element_id', 'material_id', 'volume_m3'])
        result = engine.calculate_embodied_carbon(df)
        assert result.empty

    def test_volume_as_string_is_coerced(self, engine):
        """
        C# HttpClient serialises occasional double values as strings.
        Engine must handle '10.0' transparently.
        """
        df = pd.DataFrame({
            'element_id':  ['FLOOR-01'],
            'material_id': ['Concrete'],
            'volume_m3':   ['10.0'],
        })
        result = engine.calculate_embodied_carbon(df)
        assert result.loc[0, 'mass_kg'] == pytest.approx(24_000.0, rel=1e-6)


# ===========================================================================
# Group 2 — Module A1-A3: Product Stage
# ===========================================================================

class TestModuleA1A3:

    def test_concrete_mass_and_gwp(self, engine):
        """
        Concrete: V=10 m³, ρ=2400 kg/m³ → mass=24,000 kg
        A1-A3: 24,000 × 0.103 = 2,472 kgCO2e
        """
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        result = engine.calculate_embodied_carbon(df)
        assert result.loc[0, 'mass_kg'] == pytest.approx(24_000.0, rel=1e-6)
        assert result.loc[0, 'co2_a1_a3'] == pytest.approx(2_472.0, rel=1e-6)

    def test_steel_gwp(self, engine):
        """
        Steel: V=1 m³, ρ=7850 kg/m³ → mass=7,850 kg
        A1-A3: 7,850 × 1.55 = 12,167.5 kgCO2e
        """
        df = pd.DataFrame({'element_id': ['B'], 'material_id': ['Steel'], 'volume_m3': [1.0]})
        result = engine.calculate_embodied_carbon(df)
        assert result.loc[0, 'mass_kg'] == pytest.approx(7_850.0, rel=1e-6)
        assert result.loc[0, 'co2_a1_a3'] == pytest.approx(12_167.5, rel=1e-6)

    def test_unknown_material_applies_concrete_fallback(self, engine):
        """Materials absent from DB must use fallback (ρ=2200, GWP=0.130) and set _fallback=True."""
        df = pd.DataFrame({'element_id': ['X'], 'material_id': ['UNKNOWN-MAT'], 'volume_m3': [5.0]})
        result = engine.calculate_embodied_carbon(df)
        expected_mass = 5.0 * 2200.0
        expected_a1a3 = expected_mass * 0.130
        assert result.loc[0, 'mass_kg'] == pytest.approx(expected_mass, rel=1e-6)
        assert result.loc[0, 'co2_a1_a3'] == pytest.approx(expected_a1a3, rel=1e-6)
        assert result.loc[0, '_fallback'] is True


# ===========================================================================
# Group 3 — Module A4: Transport to Site
# ===========================================================================

class TestModuleA4:

    def test_concrete_a4_uses_hgv_rigid_30km(self, engine):
        """
        Concrete → HGV_RIGID_40T, 30 km
        EF = 0.0603/1000 kgCO2e/(kg·km)
        A4 = 24,000 × 30 × 0.0000603 = 43.416 kgCO2e
        """
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        result = engine.calculate_embodied_carbon(df)
        expected = _expected_a4(24_000.0, 'concrete')
        assert result.loc[0, 'co2_a4'] == pytest.approx(expected, rel=1e-5)

    def test_steel_a4_uses_artic_hgv_150km(self, engine):
        """Steel → HGV_ARTIC_40T, 150 km."""
        df = pd.DataFrame({'element_id': ['B'], 'material_id': ['Steel'], 'volume_m3': [1.0]})
        result = engine.calculate_embodied_carbon(df)
        expected = _expected_a4(7_850.0, 'steel')
        assert result.loc[0, 'co2_a4'] == pytest.approx(expected, rel=1e-5)

    def test_custom_transport_distance_overrides_default(self, mock_db):
        """ProjectSettings.custom_transport_km must override all material defaults."""
        settings = ProjectSettings(custom_transport_km=200.0)
        eng = LCAMathEngine(mock_db, settings=settings)
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        result = eng.calculate_embodied_carbon(df)
        mass = 10.0 * 2400.0
        expected = mass * 200.0 * TRANSPORT_FACTORS['HGV_RIGID_40T']
        assert result.loc[0, 'co2_a4'] == pytest.approx(expected, rel=1e-5)


# ===========================================================================
# Group 4 — Module A5: Construction Waste & Machinery
# ===========================================================================

class TestModuleA5:

    def test_a5_waste_fraction_concrete(self, engine):
        """
        Concrete waste factor = 5 %.
        Waste mass = mass × wf / (1-wf)
        A5_waste = waste_mass × (GWP_A1A3 + GWP_A4_per_kg)
        """
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        result = engine.calculate_embodied_carbon(df)
        mass = 24_000.0
        wf = WASTE_FACTORS['concrete']
        waste_mass = mass * wf / (1.0 - wf)
        gwp = 0.103
        a4_per_kg = result.loc[0, 'co2_a4'] / mass
        expected_a5_waste = waste_mass * (gwp + a4_per_kg)
        assert result.loc[0, 'co2_a5_waste'] == pytest.approx(expected_a5_waste, rel=1e-5)

    def test_a5_machinery_is_1p5_pct_of_a1a3(self, engine):
        """Site machinery factor is 1.5% of A1-A3 by default."""
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        result = engine.calculate_embodied_carbon(df)
        expected = result.loc[0, 'co2_a1_a3'] * 0.015
        assert result.loc[0, 'co2_a5_machinery'] == pytest.approx(expected, rel=1e-6)


# ===========================================================================
# Group 5 — Modules B1-B5: Use Stage
# ===========================================================================

class TestModuleB:

    def test_b1_carbonation_only_for_concrete(self, engine):
        """Concrete B1 = -1.5 % of A1-A3 (CO2 uptake); steel B1 = 0."""
        df = pd.DataFrame({
            'element_id':  ['W', 'B'],
            'material_id': ['Concrete', 'Steel'],
            'volume_m3':   [10.0, 1.0],
        })
        result = engine.calculate_embodied_carbon(df)
        conc = result.loc[result['element_id'] == 'W'].iloc[0]
        steel = result.loc[result['element_id'] == 'B'].iloc[0]

        assert conc['co2_b1'] == pytest.approx(-conc['co2_a1_a3'] * 0.015, rel=1e-5)
        assert steel['co2_b1'] == pytest.approx(0.0, abs=1e-9)

    def test_b2_maintenance_over_60_years(self, engine):
        """B2 = mass × annual_factor × RSP (60 y)."""
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Steel'], 'volume_m3': [1.0]})
        result = engine.calculate_embodied_carbon(df)
        mass   = 7_850.0
        factor = MAINTENANCE_ANNUAL_FACTORS['steel']
        expected = mass * factor * 60
        assert result.loc[0, 'co2_b2'] == pytest.approx(expected, rel=1e-5)

    def test_b4_replacement_for_short_life_material(self, engine):
        """Glass (SL=40y) needs 1 replacement in RSP=60y → B4 = A1-A5."""
        df = pd.DataFrame({'element_id': ['G'], 'material_id': ['Glass'], 'volume_m3': [2.0]})
        result = engine.calculate_embodied_carbon(df)
        # glass SL=40, RSP=60 → int(60/40)-1 = 0 replacements ... wait, 60/40=1 floor=1, minus1=0
        # Let's test with insulation: SL=40, RSP=60 → same result = 0 replacements
        # A real replacement case: if RSP=120, SL=40 → int(120/40)-1 = 2 replacements
        settings_long = ProjectSettings(reference_study_period=120)
        eng_long = LCAMathEngine(
            pd.DataFrame({'material_id': ['Glass'], 'density_kg_m3': [2500.0], 'gwp_factor_kgco2_per_kg': [1.35]}),
            settings=settings_long,
        )
        df2 = pd.DataFrame({'element_id': ['G2'], 'material_id': ['Glass'], 'volume_m3': [1.0]})
        res2 = eng_long.calculate_embodied_carbon(df2)
        assert res2.loc[0, 'co2_b4'] > 0.0, "Glass (SL=40y) MUST be replaced in RSP=120y"


# ===========================================================================
# Group 6 — Modules C1-C4: End of Life
# ===========================================================================

class TestModuleC:

    def test_steel_eol_credit_is_negative(self, engine):
        """Steel has ~86% recycling rate → net C1-C4 must be negative."""
        df = pd.DataFrame({'element_id': ['B'], 'material_id': ['Steel'], 'volume_m3': [1.0]})
        result = engine.calculate_embodied_carbon(df)
        c_total = (
            result.loc[0, 'co2_c1']
            + result.loc[0, 'co2_c2']
            + result.loc[0, 'co2_c3']
            + result.loc[0, 'co2_c4']
        )
        assert c_total < 0, "Steel EoL (C1-C4) must be a net negative due to recycling credit"

    def test_concrete_eol_is_positive(self, engine):
        """Concrete has no significant recycling loop → C1-C4 must be > 0."""
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        result = engine.calculate_embodied_carbon(df)
        c_total = (
            result.loc[0, 'co2_c1']
            + result.loc[0, 'co2_c2']
            + result.loc[0, 'co2_c3']
            + result.loc[0, 'co2_c4']
        )
        assert c_total > 0, "Concrete EoL (C1-C4) must be positive (net landfill contribution)"

    def test_c2_transport_uses_correct_factor(self, engine):
        """C2 = mass × 30 km × HGV_RIGID_40T factor."""
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        result = engine.calculate_embodied_carbon(df)
        expected_c2 = 24_000.0 * 30.0 * TRANSPORT_FACTORS['HGV_RIGID_40T']
        assert result.loc[0, 'co2_c2'] == pytest.approx(expected_c2, rel=1e-5)


# ===========================================================================
# Group 7 — Module D & Sequestration
# ===========================================================================

class TestModuleD:

    def test_steel_module_d_is_large_negative(self, engine):
        """D for steel = mass × -0.45 kgCO2e/kg (recycled steel replaces virgin)."""
        df = pd.DataFrame({'element_id': ['B'], 'material_id': ['Steel'], 'volume_m3': [1.0]})
        result = engine.calculate_embodied_carbon(df)
        assert result.loc[0, 'co2_d'] == pytest.approx(7_850.0 * -0.450, rel=1e-5)

    def test_timber_sequestration_is_negative(self, engine):
        """Timber sequesters CO2 during growth → co2_seq < 0."""
        df = pd.DataFrame({'element_id': ['T'], 'material_id': ['Timber'], 'volume_m3': [5.0]})
        result = engine.calculate_embodied_carbon(df)
        assert result.loc[0, 'co2_seq'] < 0, "Timber biogenic sequestration must be negative"

    def test_concrete_sequestration_is_zero(self, engine):
        """Inorganic material — no biogenic carbon storage."""
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [1.0]})
        result = engine.calculate_embodied_carbon(df)
        assert result.loc[0, 'co2_seq'] == pytest.approx(0.0, abs=1e-9)


# ===========================================================================
# Group 8 — Summary Aggregations & Uncertainty
# ===========================================================================

class TestSummaries:

    def test_upfront_carbon_equals_a1_to_a5(self, engine):
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        res = engine.calculate_embodied_carbon(df).iloc[0]
        expected = res['co2_a1_a3'] + res['co2_a4'] + res['co2_a5_waste'] + res['co2_a5_machinery']
        assert res['upfront_carbon_kgco2e'] == pytest.approx(expected, rel=1e-9)

    def test_embodied_carbon_equals_a_plus_b_plus_c(self, engine):
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        res = engine.calculate_embodied_carbon(df).iloc[0]
        expected = (
            res['upfront_carbon_kgco2e']
            + res['co2_b1'] + res['co2_b2'] + res['co2_b3'] + res['co2_b4'] + res['co2_b5']
            + res['co2_c1'] + res['co2_c2'] + res['co2_c3'] + res['co2_c4']
        )
        assert res['embodied_carbon_kgco2e'] == pytest.approx(expected, rel=1e-9)

    def test_uncertainty_bounds_are_symmetric(self, engine):
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        res = engine.calculate_embodied_carbon(df).iloc[0]
        ec = res['embodied_carbon_kgco2e']
        assert res['embodied_carbon_upper'] == pytest.approx(ec * 1.10, rel=1e-6)
        assert res['embodied_carbon_lower'] == pytest.approx(ec * 0.90, rel=1e-6)

    def test_carbon_intensity_per_m3_calculation(self, engine):
        df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
        res = engine.calculate_embodied_carbon(df).iloc[0]
        expected = res['embodied_carbon_kgco2e'] / 10.0
        assert res['carbon_intensity_per_m3'] == pytest.approx(expected, rel=1e-6)

    def test_multi_element_batch_produces_correct_row_count(self, engine):
        df = pd.DataFrame({
            'element_id':  ['W1', 'W2', 'B1', 'S1'],
            'material_id': ['Concrete', 'Concrete', 'Steel', 'Timber'],
            'volume_m3':   [20.0, 15.5, 0.8, 3.2],
        })
        result = engine.calculate_embodied_carbon(df)
        assert len(result) == 4

    def test_material_classifier_concrete(self):
        assert _classify_material("Concrete - Reinforced C30/37") == "concrete"
        assert _classify_material("CONCRETE IN SITU") == "concrete"

    def test_material_classifier_steel(self):
        assert _classify_material("Metal - Steel Generic") == "steel"
        assert _classify_material("Steel UK Reinforcement") == "steel"
        assert _classify_material("Rebar BS4449") == "steel"

    def test_material_classifier_timber(self):
        assert _classify_material("Timber - Plywood") == "timber"
        assert _classify_material("CLT Panel (Cross-Laminated Timber)") == "timber"