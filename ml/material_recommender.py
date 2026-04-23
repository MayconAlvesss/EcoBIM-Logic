import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger(__name__)

FEATURES = ['density_kg_m3', 'gwp_factor_kgco2_per_kg']

class EcoMaterialRecommender:
    def __init__(self, db_df):
        self.db = db_df.copy()
        self.models = {}
        self._train()

    def _train(self):
        cats = self.db['category'].unique()

        for c in cats:
            data = self.db[self.db['category'] == c].copy()
            if len(data) < 2:
                # KNN needs at least 2 samples to be meaningful
                continue

            feats = data[FEATURES]

            # Each category gets its own scaler instance so that fit_transform()
            # for one category does not overwrite the parameters of another.
            scaler = StandardScaler()
            scaled = scaler.fit_transform(feats)

            knn = NearestNeighbors(n_neighbors=min(5, len(data)), algorithm='auto')
            knn.fit(scaled)

            self.models[c] = {
                'model': knn,
                'data': data,
                'scaler': scaler
            }

        logger.info(f"Recommender trained for categories: {list(self.models.keys())}")

    def suggest_alternatives(self, mat_id, req_class=None):
        try:
            if mat_id not in self.db['material_id'].values:
                logger.warning(f"material {mat_id} not found in training set — skipping recommendation")
                return pd.DataFrame()

            target = self.db[self.db['material_id'] == mat_id].iloc[0]
            cat = target['category']
            curr_gwp = target['gwp_factor_kgco2_per_kg']

            if cat not in self.models:
                return pd.DataFrame()

            minfo = self.models[cat]

            # Pass a single-row DataFrame with column names so sklearn does not
            # raise a UserWarning about missing feature names.
            q = pd.DataFrame([[target['density_kg_m3'], curr_gwp]], columns=FEATURES)
            q_scaled = minfo['scaler'].transform(q)

            _, idxs = minfo['model'].kneighbors(q_scaled)

            suggs = minfo['data'].iloc[idxs[0]].copy()

            # only keep materials that actually improve gwp
            suggs = suggs[suggs['gwp_factor_kgco2_per_kg'] < curr_gwp].copy()

            if req_class and req_class != 'N/A':
                suggs = suggs[suggs['structural_class'] == req_class].copy()

            if suggs.empty:
                return pd.DataFrame()

            suggs['carbon_reduction_pct'] = ((curr_gwp - suggs['gwp_factor_kgco2_per_kg']) / curr_gwp) * 100
            suggs.sort_values(by='carbon_reduction_pct', ascending=False, inplace=True)

            return suggs[['material_id', 'name', 'structural_class', 'gwp_factor_kgco2_per_kg', 'carbon_reduction_pct']]

        except Exception as e:
            logger.warning(f"Recommender failed for material '{mat_id}': {e}")
            return pd.DataFrame()
