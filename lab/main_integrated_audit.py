import os
import sys
import sqlite3
import pandas as pd

# Resolve absolute paths to import modules from the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from core.lca_math_engine import LCAMathEngine
from ml.material_recommender import EcoMaterialRecommender

DB_PATH = os.path.join(BASE_DIR, "ecobim_materials.db")

def gerar_relatorio_pdf(results_df, total_carbon, recommender):
    """
    Generates a PDF report with the audit results.
    Requires the fpdf library (pip install fpdf).
    """
    try:
        from fpdf import FPDF
    except ImportError:
        print("\n⚠️ [WARNING] The 'fpdf' library is not installed. PDF was not generated.")
        print("💡 Hint: Run 'pip install fpdf' in the terminal and run the script again.")
        return

    # Create output directory if it does not exist
    output_dir = os.path.join(BASE_DIR, "lab", "outputs")
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, "Aura_Integrated_Audit_Report.pdf")

    pdf = FPDF()
    pdf.add_page()

    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "AURA CORE - INTEGRATED CARBON REPORT", ln=True, align='C')
    pdf.ln(10)

    # Element Details
    pdf.set_font("Arial", size=11)
    for index, row in results_df.iterrows():
        elem_id = row['element_id']
        mat_id = row['material_id']
        carbon = row['embodied_carbon_kgco2e']
        mass = row['mass_kg']

        status = "ALERT (High Impact)" if carbon > 500 else "OPTIMIZED"

        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, f"Element: {elem_id} | Material: {mat_id}", ln=True)

        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 8, f"Mass: {mass:,.2f} kg | Emission: {carbon:,.2f} kgCO2e [{status}]", ln=True)

        # AI Suggestion
        if carbon > 500:
            suggs = recommender.suggest_alternatives(mat_id)
            if not suggs.empty:
                best = suggs.iloc[0]
                reduction = best['carbon_reduction_pct']
                # Use red color to highlight the recommendation
                pdf.set_text_color(200, 50, 50)
                pdf.cell(0, 8, f"   > AI Suggestion: Replace with '{best['name']}'", ln=True)
                pdf.cell(0, 8, f"   > Impact: Reduces CO2e emissions by {reduction:.1f}%", ln=True)
                pdf.set_text_color(0, 0, 0) # Back to black

        pdf.ln(5)

    # Footer with total
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"TOTAL CARBON FOOTPRINT: {total_carbon:,.2f} kgCO2e", ln=True)

    pdf.output(pdf_path)
    print(f"\n📄 [SUCCESS] PDF Report generated and saved at:\n -> {pdf_path}")


def run_audit():
    """
    Executes a full audit in the terminal, uniting the mathematical engine (LCA)
    with the artificial intelligence (ML) recommendations.
    """
    print("\n" + "="*60)
    print(" 🚀 AURA CORE - INTEGRATED CARBON AUDIT (TERMINAL) ")
    print("="*60)

    # 1. Verify and Load Database
    if not os.path.exists(DB_PATH):
        print("❌ Critical Error: Database not found.")
        print("💡 Solution: Run 'python lab/setup_db.py' first.")
        return

    conn = sqlite3.connect(DB_PATH)
    db_df = pd.read_sql_query("SELECT * FROM materials", conn)
    conn.close()

    # 2. Revit Data Extraction Simulation (Mock Payload)
    bim_data = [
        {"element_id": "W-001", "material_id": "Steel", "volume_m3": 15.5},
        {"element_id": "F-002", "material_id": "Concrete", "volume_m3": 40.0},
        {"element_id": "R-003", "material_id": "Timber", "volume_m3": 10.0}
    ]
    df_input = pd.DataFrame(bim_data)

    print(f"\n[INFO] Loaded {len(db_df)} materials from the library.")
    print(f"[INFO] Auditing {len(df_input)} BIM elements...")

    # 3. Initialize Engines (Core + AI)
    try:
        engine = LCAMathEngine(db_df)
        recommender = EcoMaterialRecommender(db_df)
    except Exception as e:
        print(f"❌ Error initializing engines: {e}")
        return

    # 4. Vectorized Embodied Carbon Calculation
    print("\n[1/2] Processing Environmental Calculations (LCA)...")
    try:
        results_df = engine.calculate_embodied_carbon(df_input)
    except Exception as e:
        print(f"❌ Calculation error: {e}")
        return

    # 5. Report Generation with Recommendations
    print("[2/2] Consulting AI for Optimizations...")
    print("\n" + "-"*60)
    print(" 📊 FINAL ELEMENT REPORT ")
    print("-"*60)

    total_carbon = 0.0

    for index, row in results_df.iterrows():
        elem_id = row['element_id']
        mat_id = row['material_id']
        carbon = row['embodied_carbon_kgco2e']
        mass = row['mass_kg']
        total_carbon += carbon

        # Classification Logic
        if carbon > 500:
            status = "⚠️ ALERT (High Impact)"
        else:
            status = "✅ OPTIMIZED"

        print(f"🔸 Element: {elem_id} | Material: {mat_id}")
        print(f"   Mass: {mass:,.2f} kg | Emission: {carbon:,.2f} kgCO2e [{status}]")

        # Artificial Intelligence Intervention
        if carbon > 500:
            suggs = recommender.suggest_alternatives(mat_id)
            if not suggs.empty:
                best = suggs.iloc[0]
                reduction = best['carbon_reduction_pct']
                print(f"   💡 AI Suggestion: Replace with '{best['name']}'")
                print(f"      -> Impact: Reduces CO2e emissions by {reduction:.1f}%!")
        print("-" * 60)

    print(f"\n🌍 TOTAL PROJECT CARBON FOOTPRINT: {total_carbon:,.2f} kgCO2e")
    print("="*60)

    # 6. Export to PDF
    gerar_relatorio_pdf(results_df, total_carbon, recommender)

if __name__ == "__main__":
    run_audit()
