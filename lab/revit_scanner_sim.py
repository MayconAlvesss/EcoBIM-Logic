import json
import random
import uuid
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def scan_revit_project(num_elements=1000):
    logger.info("Initiating geometric sweep on Revit model: 'Global_Project_v01.rvt'...")

    bim_data = []

    # mock revit categories mapping
    categories = {
        "Walls": ["Cast-in-Place Concrete", "Drywall Partition", "Brick Wall", "Generic - 200mm"],
        "Columns": ["C30/37", "Steel Column - HEB 300", "Unknown Column"],
        "Floors": ["Solid Slab - 15cm", "Steel Deck", "Floor Generic"],
        "Windows": ["Double Glazing - Aluminum Frame", "Single Glass"],
        "Structural Framing": ["W200x22.5", "Structural Timber", "Beam - Unknown"]
    }

    aura_map = {
        "Walls": "Concrete",
        "Columns": "Concrete",
        "Floors": "Concrete",
        "Windows": "Glass",
        "Structural Framing": "Steel"
    }

    for _ in range(num_elements):
        revit_cat = random.choice(list(categories.keys()))
        mat_name = random.choice(categories[revit_cat])

        # randomize dims
        width = round(random.uniform(0.10, 0.40), 3)
        height = round(random.uniform(2.50, 4.00), 3)
        length = round(random.uniform(1.00, 10.00), 3)

        volume = round(width * height * length, 3)
        area = round(length * height, 2)

        element = {
            "element_id": str(uuid.uuid4()),
            "revit_category": revit_cat,
            "category": aura_map.get(revit_cat, "Unresolved"),
            "original_name": mat_name,
            "dimensions": {
                "width_m": width,
                "height_m": height,
                "length_m": length,
                "area_m2": area
            },
            "volume_m3": volume,
            # dummy financial/lca data
            "current_gwp_total": random.uniform(450, 1500),
            "current_cost": random.uniform(800, 4500),
            "is_poorly_defined": any(k in mat_name for k in ["Generic", "Unknown", "Generico"])
        }
        bim_data.append(element)

    output_file = os.path.join(OUTPUT_DIR, "bim_extraction.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(bim_data, f, indent=4, ensure_ascii=False)

    logger.info(f"Saved {num_elements} mock elements to '{output_file}'")

if __name__ == "__main__":
    scan_revit_project(1000)
