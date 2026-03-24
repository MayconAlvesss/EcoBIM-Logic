using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Aura.Revit.Models
{
    public class SyncPayload
    {
        [JsonPropertyName("project_id")]
        public string ProjectId { get; set; } = string.Empty;

        [JsonPropertyName("timestamp")]
        public string Timestamp { get; set; } = string.Empty;

        [JsonPropertyName("elements")]
        public List<ElementData> Elements { get; set; } = new List<ElementData>();
    }

    public class ElementData
    {
        // Revit 2024+ changed ElementId from int to long internally.
        [JsonPropertyName("id")]
        public long Id { get; set; }

        [JsonPropertyName("category")]
        public string Category { get; set; } = string.Empty;

        // Volume in cubic meters (converted from Revit's internal cubic-foot units on extraction).
        [JsonPropertyName("volume_m3")]
        public double Volume { get; set; }

        [JsonPropertyName("material_name")]
        public string MaterialName { get; set; } = string.Empty;
    }
}