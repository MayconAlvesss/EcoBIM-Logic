import json
import os

class RevitPayloadBuilder:
    """
    Utility class to format Machine Learning and LCA results into the strict 
    JSON schema expected by the C# Revit Add-in (ParameterHandler).
    """
    
    def __init__(self, project_id: str):
        """
        Initializes a new sync payload for a specific BIM project.
        """
        self.payload = {
            "project_id": project_id,
            "elements": []
        }

    def add_element_update(self, element_id: int, carbon_value: float, status: str):
        """
        Adds a parameter update instruction for a specific Revit element.
        
        Args:
            element_id (int): The UniqueID or ElementId from Revit.
            carbon_value (float): The calculated embodied carbon score.
            status (str): The material optimization status (e.g., 'Optimized', 'Warning').
        """
        element_entry = {
            "id": element_id,
            "parameters": {
                "Aura_CarbonScore": round(carbon_value, 2),
                "Aura_Material_Status": status
            }
        }
        self.payload["elements"].append(element_entry)

    def export_to_json(self, filepath: str) -> dict:
        """
        Exports the built payload to a local JSON file.
        Automatically creates the directory if it does not exist.
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.payload, f, indent=4)
        return self.payload

# Example of integrated use with your core LCA engine
if __name__ == "__main__":
    # Initialize the builder for a test project
    builder = RevitPayloadBuilder("AURA_TEST_01")
    
    # Simulating 5 elements processed by the AI/LCA engine
    for i in range(5):
        builder.add_element_update(5000 + i, 12.5 * i, "Optimized")
    
    print("Payload generated successfully for C# communication.")
    
    # Exporting the payload to the lab folder for inspection
    builder.export_to_json("lab/outputs/revit_sync_payload.json")