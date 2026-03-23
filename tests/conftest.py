import pytest
from fastapi.testclient import TestClient
import pandas as pd

from api.main import app
from api.dependencies import get_lca_engine
from core.lca_math_engine import LCAMathEngine

# doing this globally because overriding depends per test was a pain
def override_get_lca_engine():
    mock_db = pd.DataFrame({
        'material_id': ['TEST-MAT-1'],
        'density_kg_m3': [1000.0],
        'gwp_factor_kgco2_per_kg': [1.0]
    })
    return LCAMathEngine(mock_db)

app.dependency_overrides[get_lca_engine] = override_get_lca_engine

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def auth_headers():
    # just a dummy key for testing routes
    return {"X-Aura-API-Key": "aura-dev-key-super-secret"}