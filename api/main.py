from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import sqlite3
import pandas as pd
from typing import List, Dict, Optional
import os
import sys
import logging
from config.settings import settings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from core.lca_math_engine import LCAMathEngine
from ml.material_recommender import EcoMaterialRecommender
from security.auth import verify_api_key
from api.middleware import PerformanceTrackingMiddleware

logger = logging.getLogger(__name__)

CARBON_THRESHOLD_KG = settings.AURA_CARBON_THRESHOLD_KG

app = FastAPI(
    title="Aura CORE - Detailed LCA Support System",
    description="Whole Life Carbon Assessment (WLCA) engine.",
    version="3.0.0"
)

ALLOWED_ORIGINS = settings.allowed_origins_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Aura-API-Key"],
)

app.add_middleware(PerformanceTrackingMiddleware)

DB_PATH = os.path.join(BASE_DIR, "ecobim_materials.db")

sync_router = APIRouter(prefix="/api/v1/sync", tags=["BIM Sync"])

def load_db_to_dataframe() -> pd.DataFrame:
    try:
        if not os.path.exists(DB_PATH):
            return pd.DataFrame(columns=['material_id', 'name', 'category', 'density_kg_m3', 'gwp_factor_kgco2_per_kg', 'structural_class'])
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM materials", conn)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"CRITICAL DB ERROR: {e}")
        return pd.DataFrame()

@sync_router.post("/process-model", dependencies=[Depends(verify_api_key)])
async def process_model(payload: Dict):
    elements = payload.get("elements", [])
    if not elements:
        return {"status": "warning", "message": "Empty element array in payload."}

    df_input = pd.DataFrame(elements)
    if 'material_name' in df_input.columns:
        df_input.rename(columns={'material_name': 'material_id'}, inplace=True)
    if 'id' in df_input.columns:
        df_input['element_id'] = df_input['id']

    db_df = load_db_to_dataframe()
    engine = LCAMathEngine(db_df)
    
    # Optional Recommender
    recommender = EcoMaterialRecommender(db_df)

    try:
        df_results = engine.calculate_embodied_carbon(df_input)

        results = []
        for _, row in df_results.iterrows():
            total_embodied = float(row.get('embodied_carbon_kgco2e', 0.0))
            mat_id = row.get('material_id')
            status = "Optimized" if total_embodied < CARBON_THRESHOLD_KG else "Warning"

            recommendation = None
            if status == "Warning":
                suggs = recommender.suggest_alternatives(mat_id)
                if not suggs.empty:
                    best = suggs.iloc[0]
                    recommendation = {
                        "alternative_name": str(best['name']),
                        "reduction_pct": float(round(best['carbon_reduction_pct'], 1)),
                        "reasoning": (
                            f"Suggested alternative reduces CO₂e by "
                            f"{round(best['carbon_reduction_pct'], 1)}% while maintaining structural integrity."
                        ),
                    }

            # Expose every phase the WLCA engine calculated — matched to new column names.
            # All values in kgCO₂e; tCO₂e conversion is done in the aggregator / UI.
            results.append({
                "id": int(row.get('element_id', 0)),
                "status": status,
                "metrics": {
                    "material":       mat_id,
                    "material_class": str(row.get('material_class', 'generic')),
                    "mass_kg":        round(float(row.get('mass_kg', 0.0)), 2),
                    "volume_m3":      round(float(row.get('volume_m3', 0.0)), 4),
                    # Product stage
                    "co2_a1_a3":      round(float(row.get('co2_a1_a3', 0.0)), 3),
                    "co2_a4":         round(float(row.get('co2_a4', 0.0)), 4),
                    "co2_a5_waste":   round(float(row.get('co2_a5_waste', 0.0)), 4),
                    "co2_a5_mach":    round(float(row.get('co2_a5_machinery', 0.0)), 4),
                    # Use stage
                    "co2_b1":         round(float(row.get('co2_b1', 0.0)), 4),
                    "co2_b2":         round(float(row.get('co2_b2', 0.0)), 4),
                    "co2_b4":         round(float(row.get('co2_b4', 0.0)), 4),
                    # End of life
                    "co2_c1":         round(float(row.get('co2_c1', 0.0)), 4),
                    "co2_c2":         round(float(row.get('co2_c2', 0.0)), 4),
                    "co2_c3":         round(float(row.get('co2_c3', 0.0)), 4),
                    "co2_c4":         round(float(row.get('co2_c4', 0.0)), 4),
                    # Informational
                    "co2_d":          round(float(row.get('co2_d', 0.0)), 4),
                    "co2_seq":        round(float(row.get('co2_seq', 0.0)), 4),
                    # Aggregated summaries
                    "total_upfront_kg":    round(float(row.get('upfront_carbon_kgco2e', 0.0)), 3),
                    "total_embodied_kg":   round(total_embodied, 3),
                    "carbon_intensity_m3": round(float(row.get('carbon_intensity_per_m3', 0.0)), 4),
                    "uncertainty_upper":   round(float(row.get('embodied_carbon_upper', 0.0)), 3),
                    "uncertainty_lower":   round(float(row.get('embodied_carbon_lower', 0.0)), 3),
                },
                "recommendation": recommendation,
            })

        return {"status": "success", "elements": results}

    except Exception as e:
        import traceback
        logger.error(f"Engine Fault: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Engine Fault: {str(e)}")

app.include_router(sync_router)

@app.get("/")
async def health():
    return {"status": "Aura DSS Online", "module": "WLCA Phase Supported"}

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)