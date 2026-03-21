import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer

# import logging
# logger = logging.getLogger(__name__)

class EcoFeatureEngineer:
    def __init__(self):
        self.preprocessor = ColumnTransformer(
            transformers=[
                ('num', StandardScaler(), ['density_kg_m3', 'gwp_factor_kgco2_per_kg']),
                ('cat', OneHotEncoder(handle_unknown='ignore'), ['structural_class'])
            ])
        self.is_fitted = False

    def fit_transform(self, df):
        data = self.preprocessor.fit_transform(df)
        self.is_fitted = True
        return data

    def transform_query(self, query):
        if not self.is_fitted:
            raise RuntimeError("you need to run fit_transform first!")
        return self.preprocessor.transform(query)