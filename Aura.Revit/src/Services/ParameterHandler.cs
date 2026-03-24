using System.Text.Json;
using System.Collections.Generic;
using System.Text.Json.Serialization;
using System.Linq;
using Autodesk.Revit.DB;
using System.Diagnostics;

namespace Aura.Revit.Services
{
    // The enriched API Response from the new WLCA calculation
    public class AuraApiResponse
    {
        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("elements")]
        public List<AuraElementResult> Elements { get; set; } = new();
    }

    public class AuraElementResult
    {
        [JsonPropertyName("id")]
        public long Id { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("metrics")]
        public AuraMetrics? Metrics { get; set; }

        [JsonPropertyName("recommendation")]
        public AuraRecommendation? Recommendation { get; set; }
    }

    public class AuraMetrics
    {
        [JsonPropertyName("material")]
        public string Material { get; set; } = string.Empty;

        [JsonPropertyName("mass_kg")]
        public double MassKg { get; set; }

        [JsonPropertyName("volume_m3")]
        public double VolumeM3 { get; set; }

        [JsonPropertyName("co2_a1_a3")]
        public double Co2A1A3 { get; set; }

        [JsonPropertyName("co2_a4")]
        public double Co2A4 { get; set; }

        [JsonPropertyName("co2_a5")]
        public double Co2A5 { get; set; }

        [JsonPropertyName("co2_b1_b5")]
        public double Co2B1B5 { get; set; }

        [JsonPropertyName("co2_c1_c4")]
        public double Co2C1C4 { get; set; }

        [JsonPropertyName("co2_seq")]
        public double Co2Seq { get; set; }

        [JsonPropertyName("total_embodied_kg")]
        public double TotalEmbodiedKg { get; set; }

        [JsonPropertyName("total_upfront_kg")]
        public double TotalUpfrontKg { get; set; }
    }

    public class AuraRecommendation
    {
        [JsonPropertyName("alternative_name")]
        public string AlternativeName { get; set; } = string.Empty;

        [JsonPropertyName("reduction_pct")]
        public double ReductionPct { get; set; }

        [JsonPropertyName("reasoning")]
        public string Reasoning { get; set; } = string.Empty;
    }

    public static class ParameterHandler
    {
        private const string PARAM_CARBON_SCORE = "Aura_CarbonScore";
        private const string PARAM_MATERIAL_STATUS = "Aura_MaterialStatus";

        public static (int UpdatedCount, AuraApiResponse? ParsedData) UpdateParametersFromJson(Document doc, string apiResponseJson)
        {
            if (string.IsNullOrWhiteSpace(apiResponseJson) || apiResponseJson.StartsWith("Error"))
                return (0, null);

            AuraApiResponse? apiResponse;
            try
            {
                apiResponse = JsonSerializer.Deserialize<AuraApiResponse>(apiResponseJson);
            }
            catch (JsonException ex)
            {
                Debug.WriteLine($"[Aura] Failed to deserialize API response: {ex.Message}");
                return (0, null);
            }

            if (apiResponse?.Elements == null || apiResponse.Elements.Count == 0)
                return (0, apiResponse);

            int updatedCount = 0;

            foreach (AuraElementResult result in apiResponse.Elements)
            {
                ElementId elementId = new ElementId(result.Id);
                Element? element = doc.GetElement(elementId);

                if (element == null)
                {
                    Debug.WriteLine($"[Aura] Element {result.Id} not found in active document. Skipping.");
                    continue;
                }

                double carbonScore = result.Metrics?.TotalEmbodiedKg ?? 0.0;
                string materialStatus = result.Status;

                bool scoreSaved = TrySetParameter(element, PARAM_CARBON_SCORE, carbonScore);
                bool statusSaved = TrySetParameter(element, PARAM_MATERIAL_STATUS, materialStatus);

                if (scoreSaved && statusSaved)
                    updatedCount++;
            }

            Debug.WriteLine($"[Aura] ParameterHandler: {updatedCount}/{apiResponse.Elements.Count} elements updated.");
            return (updatedCount, apiResponse);
        }

        private static bool TrySetParameter(Element element, string paramName, double value)
        {
            Parameter? param = element.LookupParameter(paramName);
            if (param == null || param.IsReadOnly)
                return false;
            
            param.Set(value);
            return true;
        }

        private static bool TrySetParameter(Element element, string paramName, string value)
        {
            Parameter? param = element.LookupParameter(paramName);
            if (param == null || param.IsReadOnly)
                return false;
            
            param.Set(value);
            return true;
        }
    }
}
