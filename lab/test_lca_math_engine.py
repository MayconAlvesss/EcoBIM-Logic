"""
lab/test_lca_math_engine.py — Updated for WLCA Engine (EN 15978 / EN 15804)
Legacy lab test file — kept for standalone execution without pytest infrastructure.
For CI/CD, use tests/test_lca_math_engine.py instead.
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.lca_math_engine import LCAMathEngine, ProjectSettings, _classify_material
from core.exceptions import VolumeCalculationError

@pytest.fixture
def mock_db():
    return pd.DataFrame({
        'material_id':            ['Concrete', 'Steel'],
        'density_kg_m3':          [2400.0,     7850.0],
        'gwp_factor_kgco2_per_kg': [0.103,     1.55],
    })

@pytest.fixture
def engine(mock_db):
    return LCAMathEngine(mock_db, settings=ProjectSettings())

def test_embodied_carbon_columns_present(engine):
    """All mandatory output columns from the WLCA engine must exist."""
    df = pd.DataFrame({'element_id': ['W', 'B'], 'material_id': ['Concrete', 'Steel'], 'volume_m3': [10.0, 2.0]})
    result = engine.calculate_embodied_carbon(df)
    required_cols = [
        'mass_kg', 'co2_a1_a3', 'co2_a4', 'co2_a5_waste', 'co2_a5_machinery',
        'co2_b1', 'co2_b2', 'co2_b4', 'co2_c1', 'co2_c2', 'co2_c3', 'co2_c4',
        'co2_d', 'co2_seq', 'upfront_carbon_kgco2e', 'embodied_carbon_kgco2e',
        'embodied_carbon_upper', 'embodied_carbon_lower', 'carbon_intensity_per_m3',
    ]
    for col in required_cols:
        assert col in result.columns, f"Missing column: {col}"

def test_embodied_carbon_success(engine):
    """Concrete: 10m³ × 2400 kg/m³ = 24,000 kg; A1-A3 = 24,000 × 0.103 = 2,472 kgCO2e."""
    df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
    result = engine.calculate_embodied_carbon(df)
    assert result.loc[0, 'mass_kg'] == pytest.approx(24_000.0)
    assert result.loc[0, 'co2_a1_a3'] == pytest.approx(2_472.0)

def test_negative_volume_raises(engine):
    """Corrupted Revit geometry must stop execution immediately."""
    with pytest.raises(VolumeCalculationError):
        engine.calculate_embodied_carbon(
            pd.DataFrame({'element_id': ['BAD'], 'material_id': ['Concrete'], 'volume_m3': [-5.0]})
        )

def test_missing_material_uses_fallback_not_exception(engine):
    """Unknown material should apply fallback (no exception), _fallback=True."""
    df = pd.DataFrame({'element_id': ['X'], 'material_id': ['Unregistered_Gypsum'], 'volume_m3': [1.0]})
    result = engine.calculate_embodied_carbon(df)
    # Fallback ρ=2200, so mass = 2200, GWP=0.13 → A1-A3=286
    assert result.loc[0, '_fallback'] is True
    assert result.loc[0, 'mass_kg'] == pytest.approx(2200.0)
    assert result.loc[0, 'co2_a1_a3'] == pytest.approx(2200.0 * 0.130)

def test_volume_string_coercion(engine):
    """String volume '10.0' must be coerced to float without error."""
    df = pd.DataFrame({'element_id': ['F'], 'material_id': ['Concrete'], 'volume_m3': ['10.0']})
    result = engine.calculate_embodied_carbon(df)
    assert result.loc[0, 'mass_kg'] == pytest.approx(24_000.0)

def test_steel_eol_net_negative(engine):
    """
    Steel has ~86% global circularity rate. Net C1-C4 credit MUST be negative.
    This test guards against accidental sign flip in EOL_FACTORS.
    """
    df = pd.DataFrame({'element_id': ['B'], 'material_id': ['Steel'], 'volume_m3': [1.0]})
    result = engine.calculate_embodied_carbon(df)
    eol_total = result.loc[0, 'co2_c1'] + result.loc[0, 'co2_c2'] + result.loc[0, 'co2_c3'] + result.loc[0, 'co2_c4']
    assert eol_total < 0

def test_timber_biogenic_sequestration_negative(engine):
    """Timber sequesters atmospheric CO2 during growth. co2_seq must be < 0."""
    db = pd.DataFrame({'material_id': ['Timber'], 'density_kg_m3': [500.0], 'gwp_factor_kgco2_per_kg': [0.263]})
    eng = LCAMathEngine(db)
    df = pd.DataFrame({'element_id': ['T'], 'material_id': ['Timber'], 'volume_m3': [5.0]})
    result = eng.calculate_embodied_carbon(df)
    assert result.loc[0, 'co2_seq'] < 0

def test_uncertainty_bounds(engine):
    """Upper / lower bounds must be ±10% of the central estimate."""
    df = pd.DataFrame({'element_id': ['W'], 'material_id': ['Concrete'], 'volume_m3': [10.0]})
    res = engine.calculate_embodied_carbon(df).iloc[0]
    ec = res['embodied_carbon_kgco2e']
    assert res['embodied_carbon_upper'] == pytest.approx(ec * 1.10, rel=1e-6)
    assert res['embodied_carbon_lower'] == pytest.approx(ec * 0.90, rel=1e-6)