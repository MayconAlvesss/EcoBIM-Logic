import pandas as pd
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class BIMDataPipeline:
    def __init__(self):
        # standard mapping for incoming revit geometry
        self.category_map = {
            "Walls": "Concrete",
            "Floors": "Concrete",
            "Columns": "Concrete",
            "Structural Framing": "Steel",
            "Windows": "Glass",
            "Doors": "Timber"
        }

    def process_raw_json(self, json_data):
        try:
            if isinstance(json_data, str):
                if Path(json_data).exists():
                    with open(json_data, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                else:
                    data = json.loads(json_data)
            else:
                data = json_data

            if not data:
                logger.warning("Empty JSON payload received")
                return pd.DataFrame()

            df = pd.DataFrame(data)
            
            req_cols = ['element_id', 'revit_category', 'volume_m3']
            missing = [c for c in req_cols if c not in df.columns]
            if missing:
                logger.error(f"Bad payload shape. Missing: {missing}")
                raise ValueError(f"Payload missing columns: {missing}")

            # cleanup and map categories
            df['volume_m3'] = pd.to_numeric(df['volume_m3'], errors='coerce').fillna(0)
            df = df[df['volume_m3'] > 0].copy()
            
            df['category'] = df['revit_category'].map(self.category_map).fillna("Unresolved")
            
            # generic fallback
            df['material_id'] = df['category'] + "_Standard"

            logger.info(f"Pipeline processed {len(df)} elements.")
            return df

        except Exception as e:
            logger.error(f"Pipeline failure: {str(e)}")
            raise