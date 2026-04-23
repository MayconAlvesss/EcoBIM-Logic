import pytest
import pandas as pd

from core.lca_math_engine import LCAMathEngine
from core.exceptions import VolumeCalculationError
from ml.material_recommender import EcoMaterialRecommender
from ingestion.data_pipeline import BIMDataPipeline


# ---------------------------------------------------------------------------
# Shared Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_db() -> pd.DataFrame:
    """
    Minimal in-memory material library used across all tests.
    Covers two categories so the KNN recommender can be trained per-category.
    """
    return pd.DataFrame([
        {"material_id": "Concrete",       "name": "Standard Concrete", "category": "Concrete", "density_kg_m3": 2400.0, "gwp_factor_kgco2_per_kg": 0.15, "structural_class": "A"},
        {"material_id": "Eco_Concrete",   "name": "Eco Concrete",      "category": "Concrete", "density_kg_m3": 2350.0, "gwp_factor_kgco2_per_kg": 0.07, "structural_class": "A"},
        {"material_id": "Steel",          "name": "Structural Steel",  "category": "Metal",    "density_kg_m3": 7850.0, "gwp_factor_kgco2_per_kg": 1.80, "structural_class": "A"},
        {"material_id": "Recycled_Steel", "name": "Recycled Steel",    "category": "Metal",    "density_kg_m3": 7850.0, "gwp_factor_kgco2_per_kg": 0.45, "structural_class": "A"},
    ])


# ---------------------------------------------------------------------------
# API Health Check
# ---------------------------------------------------------------------------

def test_api_health(client):
    """Health endpoint must return 200 and the expected status key."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "Aura DSS Online"


# ---------------------------------------------------------------------------
# LCA Math Engine
# ---------------------------------------------------------------------------

class TestLCAMathEngine:

    def test_carbon_calculation_is_correct(self, sample_db):
        """Embodied carbon = volume * density * GWP factor."""
        engine = LCAMathEngine(sample_db)
        df_input = pd.DataFrame([
            {"element_id": "W-001", "material_id": "Concrete", "volume_m3": 10.0}
        ])
        result = engine.calculate_embodied_carbon(df_input)

        expected_mass = 10.0 * 2400.0          # 24,000 kg
        expected_carbon = 24000.0 * 0.15       # 3,600 kgCO2e
        assert result.iloc[0]["mass_kg"] == pytest.approx(expected_mass)
        assert result.iloc[0]["co2_a1_a3"] == pytest.approx(expected_carbon)
        # Total whole life will be higher, just verify it runs
        assert result.iloc[0]["embodied_carbon_kgco2e"] >= expected_carbon

    def test_negative_volume_raises_error(self, sample_db):
        """VolumeCalculationError must be raised for elements with negative volume."""
        engine = LCAMathEngine(sample_db)
        df_bad = pd.DataFrame([
            {"element_id": "BAD-001", "material_id": "Concrete", "volume_m3": -5.0}
        ])
        with pytest.raises(VolumeCalculationError):
            engine.calculate_embodied_carbon(df_bad)

    def test_unknown_material_uses_fallback(self, sample_db):
        """The engine must gracefully handle unmapped materials using fallback factors instead of crashing."""
        engine = LCAMathEngine(sample_db)
        df_unknown = pd.DataFrame([
            {"element_id": "W-999", "material_id": "UnknownMaterial_XYZ", "volume_m3": 5.0}
        ])
        result = engine.calculate_embodied_carbon(df_unknown)
        # Should get generic density and GWP fallback instead of crashing
        assert result.iloc[0]["mass_kg"] > 0
        assert result.iloc[0]["embodied_carbon_kgco2e"] > 0


# ---------------------------------------------------------------------------
# ML Material Recommender
# ---------------------------------------------------------------------------

class TestEcoMaterialRecommender:

    def test_recommender_returns_lower_gwp_alternative(self, sample_db):
        """
        When asked for alternatives to 'Concrete', the recommender must return
        'Eco_Concrete' which has a lower GWP.
        """
        rec = EcoMaterialRecommender(sample_db)
        result = rec.suggest_alternatives("Concrete")
        assert not result.empty, "Expected at least one alternative for Concrete"
        assert result.iloc[0]["material_id"] == "Eco_Concrete"

    def test_scaler_isolation_per_category(self, sample_db):
        """
        Regression test for the shared-scaler bug:
        After training, each category must have a separate scaler instance
        so that calling suggest_alternatives on 'Metal' does not use
        parameters calibrated on 'Concrete' data.
        """
        rec = EcoMaterialRecommender(sample_db)
        # If scalers are shared, one transform() overwrites the other and the
        # KNN distances are meaningless. Verifying both categories are trained.
        assert "Concrete" in rec.models, "Concrete model must be trained"
        assert "Metal" in rec.models, "Metal model must be trained"
        # Verify each category holds a distinct scaler object
        assert rec.models["Concrete"]["scaler"] is not rec.models["Metal"]["scaler"], \
            "Scalers must be separate instances per category (shared scaler bug regression)"

    def test_unknown_material_returns_empty(self, sample_db):
        """Asking for alternatives to a non-existent material must return an empty DataFrame."""
        rec = EcoMaterialRecommender(sample_db)
        result = rec.suggest_alternatives("UnknownMaterial_XYZ")
        assert result.empty

    def test_carbon_reduction_pct_is_positive(self, sample_db):
        """The reduction percentage must be > 0 for any valid suggestion."""
        rec = EcoMaterialRecommender(sample_db)
        result = rec.suggest_alternatives("Steel")
        if not result.empty:
            assert all(result["carbon_reduction_pct"] > 0)


# ---------------------------------------------------------------------------
# BIM Data Pipeline
# ---------------------------------------------------------------------------

class TestBIMDataPipeline:

    def test_category_mapping_works(self):
        """Revit categories must be mapped to material categories correctly."""
        pipeline = BIMDataPipeline()
        raw = [
            {"element_id": "W-1", "revit_category": "Walls",    "volume_m3": 10.0},
            {"element_id": "F-1", "revit_category": "Floors",   "volume_m3": 5.0},
            {"element_id": "C-1", "revit_category": "Columns",  "volume_m3": 2.0},
        ]
        result = pipeline.process_raw_json(raw)
        assert all(result["category"] == "Concrete")

    def test_zero_volume_elements_are_filtered_out(self):
        """Elements with zero volume must be dropped before LCA calculation."""
        pipeline = BIMDataPipeline()
        raw = [
            {"element_id": "V-0", "revit_category": "Walls", "volume_m3": 0.0},
            {"element_id": "V-1", "revit_category": "Walls", "volume_m3": 5.0},
        ]
        result = pipeline.process_raw_json(raw)
        assert len(result) == 1
        assert result.iloc[0]["element_id"] == "V-1"

    def test_missing_columns_raise_value_error(self):
        """Payloads that are missing required columns must raise ValueError."""
        pipeline = BIMDataPipeline()
        bad_payload = [{"element_id": "X-1"}]  # missing revit_category and volume_m3
        with pytest.raises(ValueError, match="Payload missing columns"):
            pipeline.process_raw_json(bad_payload)
