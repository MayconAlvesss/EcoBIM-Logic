import requests
import json

# endpoint pointing to our local fastapi core
URL = "http://localhost:8000/api/v1/sync/process-model"

def run_simulation():
    print("--- Aura BIM Simulator Started ---")

    # payload mimicking a real Revit extraction
    # updated key to 'volume_m3' to match the engine's strict requirements
    payload = {
        "project_id": "SIM_PROJ_001",
        "elements": [
            {"id": 202101, "category": "Walls", "material_name": "Concrete", "volume_m3": 15.5},
            {"id": 202102, "category": "Floors", "material_name": "Timber", "volume_m3": 8.2},
            {"id": 202103, "category": "Beams", "material_name": "Steel", "volume_m3": 1.5}
        ]
    }

    print(f"Step 1: Sending {len(payload['elements'])} elements to API...")

    try:
        # standard POST request to the local engine
        response = requests.post(URL, json=payload)
        response.raise_for_status() # trigger error if status is 4xx or 5xx

        data = response.json()

        print("\nStep 2: API Response Received!")
        print(json.dumps(data, indent=4))

        # summary for the user
        print("\n--- Simulation Success ---")
        print(f"Status: {data.get('status')}")

    except requests.exceptions.RequestException as e:
        print(f"Simulator failed: {e}")
        if hasattr(e.response, 'text'):
            print(f"API Error Detail: {e.response.text}")

if __name__ == "__main__":
    run_simulation()
