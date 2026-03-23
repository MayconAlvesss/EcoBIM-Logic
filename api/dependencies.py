from fastapi import Request
from database.materials_db import MaterialDatabaseManager
from core.lca_math_engine import LCAMathEngine
from ml.material_recommender import EcoMaterialRecommender
import logging

logger = logging.getLogger(__name__)

# in-memory globals
db_mgr = None
lca_eng = None
rec_eng = None

def init_services():
    global db_mgr, lca_eng, rec_eng
    
    logger.info("Initializing DB cache and ML models...")
    
    db_mgr = MaterialDatabaseManager()
    df_mat = db_mgr.get_all_materials_as_dataframe()
    
    lca_eng = LCAMathEngine(df_mat)
    rec_eng = EcoMaterialRecommender(df_mat)

async def get_db_manager():
    if not db_mgr:
        raise RuntimeError("DB Manager not initialized (services offline?)")
    return db_mgr

async def get_lca_engine():
    if not lca_eng:
        raise RuntimeError('LCA Engine offline.')
    return lca_eng

async def get_ml_recommender():
    if not rec_eng:
        raise RuntimeError("ML Recommendation Engine offline.")
    return rec_eng