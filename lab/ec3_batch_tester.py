import sys
import os
import json
import asyncio
from datetime import datetime

# Path configuration to ensure Python finds the ECOBIM package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports from the Professional Backend Structure
try:
    from ECOBIM.core.lca_math_engine import LCAMathEngine
    from ECOBIM.core.lca_lifecycle_engine import LifecycleEngine
    from ECOBIM.ml.material_recommender import MaterialRecommender
    from ECOBIM.reporting.carbon_report import CarbonReport
    from ECOBIM.bim_connectors.revit_injector_payload import RevitInjector
    from ECOBIM.utils.logger import setup_custom_logger
except ImportError as e:
    print(f"Import Error: Ensure you are running the script at the project root. {e}")
    sys.exit(1)

# Initialize Professional Logger
logger = setup_custom_logger("Aura_Integrator")

async def run_decarbonization_pipeline():
    """
    Orchestrates the complete flow:
    Data Ingestion -> LCA Processing -> ML Optimization -> Reporting -> BIM Sync
    """
    logger.info("--- Starting Aura EcoBIM Integrated Pipeline ---")

    # 1. DATA LOADING (Ingestion)
    input_file = "outputs/bim_extraction.json"
    if not os.path.exists(input_file):
        logger.error(f"File {input_file} not found. Run the scanner first.")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        bim_elements = json.load(f)

    # 2. INSTANTIATION OF BACKEND ENGINES
    lca_math = LCAMathEngine()
    lifecycle = LifecycleEngine()
    ai_recommender = MaterialRecommender()
    report_engine = CarbonReport()
    revit_sync = RevitInjector()

    processed_results = []

    logger.info(f"Processing {len(bim_elements)} elements using the complete structure...")

    # 3. PROCESSING LOOP (Core + ML)
    for element in bim_elements:
        # Impact Calculation via Core Engine
        # We pass the raw data to the engine which decides the A1-A3 logic
        impact_data = lca_math.calculate_impact(
            volume=element['volume_m3'],
            material_cat=element['category']
        )

        # Lifecycle Analysis (A4 + Biogenic Sequestration)
        lifecycle_data = lifecycle.analyze_stages(element, impact_data)

        # Artificial Intelligence Recommendation
        suggestion = ai_recommender.predict_optimized_material(element['category'])

        # Data consolidation for the report and Revit
        final_entry = {
            "element_id": element['element_id'],
            "original_name": element['original_name'],
            "category": element['category'],
            "current_gwp": impact_data['total_gwp'],
            "suggested_material": suggestion['name'],
            "potential_reduction": suggestion['reduction_factor'],
            "status": "OPTIMIZED" if suggestion['reduction_factor'] > 0.2 else "EFFICIENT"
        }
        processed_results.append(final_entry)

    # 4. PROFESSIONAL OUTPUTS GENERATION
    # Generates PDF using the actual Reporting module
    logger.info("Generating Executive PDF Report...")
    report_engine.generate_professional_audit(processed_results)

    # Generates the JSON Payload for injection into Revit via Connector
    logger.info("Generating Sync Payload for Revit...")
    revit_sync.export_payload(processed_results, "outputs/revit_sync_payload.json")

    logger.info(f"--- Pipeline Completed Successfully [{datetime.now().strftime('%H:%M:%S')}] ---")

if __name__ == "__main__":
    try:
        asyncio.run(run_decarbonization_pipeline())
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user.")
