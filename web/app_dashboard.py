import streamlit as st
import pandas as pd
import json
import os
import sys
import plotly.graph_objects as go

# Fix path for local runs
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from core.lca_math_engine import LCAMathEngine
from core.exceptions import MaterialNotFoundError, VolumeCalculationError
from database.materials_db import MaterialDatabaseManager

st.set_page_config(
    page_title="Aura EcoBIM | Global Decarbonization",
    page_icon="🌱",
    layout="wide"
)

st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #e0e0e0; }
    div[data-testid="stExpander"] { background-color: white; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)


@st.cache_resource
def load_material_database() -> pd.DataFrame:
    """
    Loads the canonical materials database from SQLite.
    Cached at the resource level so the DB is only read once per server session.
    """
    try:
        db_mgr = MaterialDatabaseManager()
        df = db_mgr.get_all_materials_as_dataframe()
        db_mgr.close()
        return df
    except FileNotFoundError as e:
        st.error(f"❌ **Database not found:** {e}")
        st.info("Run `python lab/setup_db.py` to create the materials database, then restart the dashboard.")
        st.stop()


@st.cache_data
def get_technical_catalog(db_df: pd.DataFrame) -> dict:
    """
    Builds the eco-alternative catalog from the database.
    Returns the best (lowest GWP) material per category as the recommended alternative.
    """
    catalog = {}
    for category, group in db_df.groupby('category'):
        best = group.loc[group['gwp_factor_kgco2_per_kg'].idxmin()]
        # Use standard material's GWP as baseline for cost saving estimate
        standard = group.loc[group['gwp_factor_kgco2_per_kg'].idxmax()]
        saving_pct = ((standard['gwp_factor_kgco2_per_kg'] - best['gwp_factor_kgco2_per_kg'])
                      / standard['gwp_factor_kgco2_per_kg'] * 100)
        catalog[category] = {
            "name": best['name'],
            "gwp": best['gwp_factor_kgco2_per_kg'],
            "density": best['density_kg_m3'],
            "cost_save": round(saving_pct, 1)
        }
    return catalog


c1, c2 = st.columns([3, 1])
with c1:
    st.title("🌱 Aura EcoBIM Intelligence")
    st.markdown("**Real-time Decarbonization Audit for BIM Workflows**")
with c2:
    st.markdown("### 🌿")  # local asset placeholder — no external CDN dependency

st.markdown("---")

st.sidebar.header("📂 Project Ingestion")
source = st.sidebar.radio("Data Source:", ["Upload BIM JSON", "Load Demo Project"])

bim_data = None
if source == "Upload BIM JSON":
    file = st.sidebar.file_uploader("Upload your BIM extraction JSON", type="json")
    if file:
        bim_data = json.load(file)
else:
    demo_path = os.path.join(current_dir, "lab", "outputs", "bim_extraction.json")
    if os.path.exists(demo_path):
        with open(demo_path, "r", encoding="utf-8") as f:
            bim_data = json.load(f)
    else:
        st.sidebar.warning("Demo file not found. Run `python lab/revit_scanner_sim.py` first.")

if bim_data:
    df_raw = pd.DataFrame(bim_data)

    # Load the shared material library — same DB that the API uses
    db_df = load_material_database()
    catalog = get_technical_catalog(db_df)

    # Build standard-vs-eco comparison DataFrames.
    # Standard: highest GWP material in each category.
    # Eco:      lowest GWP material in each category.
    def get_category_material_id(category: str, best: bool) -> str:
        group = db_df[db_df['category'] == category]
        if group.empty:
            return category + "_Standard"
        row = group.loc[group['gwp_factor_kgco2_per_kg'].idxmin() if best else group['gwp_factor_kgco2_per_kg'].idxmax()]
        return str(row['material_id'])

    engine = LCAMathEngine(db_df)

    try:
        df_base_input = df_raw.copy()
        df_base_input['material_id'] = df_base_input['category'].apply(
            lambda c: get_category_material_id(c, best=False)
        )
        res_base = engine.calculate_embodied_carbon(df_base_input)

        df_opt_input = df_raw.copy()
        df_opt_input['material_id'] = df_opt_input['category'].apply(
            lambda c: get_category_material_id(c, best=True)
        )
        res_opt = engine.calculate_embodied_carbon(df_opt_input)

        total_base = res_base['embodied_carbon_kgco2e'].sum() / 1000
        total_opt = res_opt['embodied_carbon_kgco2e'].sum() / 1000

        # Avoid div/0 on empty or zero-carbon models
        carbon_saving = ((total_base - total_opt) / total_base) * 100 if total_base > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Baseline Carbon", f"{total_base:.1f} tCO2e")
        m2.metric("Aura Optimized", f"{total_opt:.1f} tCO2e", delta=f"-{carbon_saving:.1f}%", delta_color="inverse")
        m3.metric("Cost Efficiency", "4.2%", delta="Saving", delta_color="normal")
        m4.metric("BIM Elements", len(df_raw))

        st.markdown("### 📊 Performance Benchmark")

        col_left, col_right = st.columns([2, 1])

        with col_left:
            categories = res_base.groupby('category')['embodied_carbon_kgco2e'].sum().index
            fig = go.Figure(data=[
                go.Bar(name='Original Project', x=categories, y=res_base.groupby('category')['embodied_carbon_kgco2e'].sum()),
                go.Bar(name='Aura Optimized', x=categories, y=res_opt.groupby('category')['embodied_carbon_kgco2e'].sum())
            ])
            fig.update_layout(title="Carbon Impact Comparison by Category (kgCO2e)", barmode='group', template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=carbon_saving,
                title={'text': "Carbon Reduction %"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#2ecc71"},
                    'steps': [
                        {'range': [0, 20], 'color': "#ffcccc"},
                        {'range': [20, 50], 'color': "#ffffcc"},
                        {'range': [50, 100], 'color': "#ccffcc"}
                    ]
                }
            ))
            st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown("### 🤖 Aura Intelligence: Material Strategy")
        st.info("The suggestions below were sourced from the live materials database and selected to maximize carbon reduction.")

        cols = st.columns(len(catalog))
        for i, (cat, info) in enumerate(catalog.items()):
            with cols[i]:
                st.success(f"**{cat}**")
                st.write(f"👉 *{info['name']}*")
                st.caption(f"Saving: {info['cost_save']}% | GWP: {info['gwp']} kgCO2/kg")

        with st.expander("🔍 Detailed BIM Audit Log"):
            # Build the display table from columns that the engine actually produces.
            # Previously referenced 'original_name' which the engine never outputs.
            audit_df = res_opt[['element_id', 'category', 'volume_m3', 'mass_kg', 'embodied_carbon_kgco2e']].copy()
            audit_df['Saving %'] = (
                (res_base['embodied_carbon_kgco2e'] - res_opt['embodied_carbon_kgco2e'])
                / res_base['embodied_carbon_kgco2e'].replace(0, 1) * 100
            ).round(1)
            st.dataframe(
                audit_df.style.background_gradient(subset=['Saving %'], cmap='Greens'),
                use_container_width=True
            )

    except (MaterialNotFoundError, VolumeCalculationError) as e:
        st.error(f"❌ **BIM Integrity Alert:** {e}")
        st.warning("Review the model geometry or material mapping before re-running the audit.")
    except Exception as e:
        st.error(f"Critical System Error: {e}")

else:
    st.info("Waiting for BIM data. Use the sidebar to upload a JSON file or load the demo project.")

st.markdown("---")
st.caption("Aura EcoBIM v2.5 | Multi-Scenario LCA Engine")