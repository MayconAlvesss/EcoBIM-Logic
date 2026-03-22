import pandas as pd
import logging

logger = logging.getLogger(__name__)

class ESGReportingEngine:
    @staticmethod
    def generate_executive_summary(df):
        logger.info('generating esg summary')
        
        # using float() because pandas types sometimes mess up the json serialization
        vol_total = float(df['volume_m3'].sum())
        a1_a3 = float(df['embodied_carbon_kgco2e'].sum())
        
        # TODO: phase a4 and c are mocked right now. 
        # frontend breaks if these are missing so using get() with 0.0 as a fallback
        a4 = float(df.get('transport_a4_kgco2e', pd.Series([0.0])).sum())
        c = float(df.get('end_of_life_c_kgco2e', pd.Series([0.0])).sum())

        grand_total = a1_a3 + a4 + c
        
        cat_group = df.groupby("category")['embodied_carbon_kgco2e'].sum().to_dict()

        # management wants the top 3 worst elements for the dashboard
        top_3 = df.nlargest(3, 'embodied_carbon_kgco2e')
        emitters = [
            {
                "element_id": r.element_id, 
                'material': getattr(r, 'name', r.material_id), 
                "carbon_impact": round(r.embodied_carbon_kgco2e, 2)
            } 
            for r in top_3.itertuples()
        ]

        return {
            'metrics': {
                "total_volume_m3": round(vol_total, 2),
                "grand_total_kgco2e": round(grand_total, 2),
                'phases_breakdown': {
                    "A1-A3_Manufacturing": round(a1_a3, 2),
                    "A4_Transport": round(a4, 2),
                    "C1-C4_EndOfLife": round(c, 2)
                }
            },
            "carbon_by_category": {k: round(v, 2) for k, v in cat_group.items()},
            'top_polluting_elements': emitters,
            "compliance_status": "PENDING_REVIEW" # hardcoded for now until legal approves
        }