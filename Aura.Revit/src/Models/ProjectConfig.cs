using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Aura.Revit.Models
{
    /// <summary>
    /// Full project configuration declared by the structural engineer / assessor.
    /// This is serialised to JSON and sent alongside the BIM payload to the Python API
    /// so the engine can use project-specific transport, waste, and boundary data
    /// instead of generic national defaults.
    ///
    /// Maps 1:1 to core/project_config.py → ProjectConfig dataclass.
    /// </summary>
    public class ProjectConfig
    {
        // ── Project Identity ─────────────────────────────────────────────────
        [JsonPropertyName("project_number")]
        public string ProjectNumber { get; set; } = "";

        [JsonPropertyName("project_name")]
        public string ProjectName { get; set; } = "";

        [JsonPropertyName("location")]
        public string Location { get; set; } = "";

        [JsonPropertyName("structural_engineer")]
        public string StructuralEngineer { get; set; } = "";

        [JsonPropertyName("assessor_name")]
        public string AssessorName { get; set; } = "";

        [JsonPropertyName("assessment_date")]
        public string AssessmentDate { get; set; } = "";

        // ── System Boundary ──────────────────────────────────────────────────
        [JsonPropertyName("include_module_a4")]
        public bool IncludeModuleA4 { get; set; } = true;

        [JsonPropertyName("include_module_a5")]
        public bool IncludeModuleA5 { get; set; } = true;

        [JsonPropertyName("include_module_b")]
        public bool IncludeModuleB { get; set; } = true;

        [JsonPropertyName("include_module_c")]
        public bool IncludeModuleC { get; set; } = true;

        [JsonPropertyName("include_module_d")]
        public bool IncludeModuleD { get; set; } = false;

        [JsonPropertyName("include_sequestration")]
        public bool IncludeSequestration { get; set; } = true;

        // ── Metrics ───────────────────────────────────────────────────────────
        [JsonPropertyName("reference_study_period")]
        public int ReferenceStudyPeriod { get; set; } = 60;

        [JsonPropertyName("gross_internal_area_m2")]
        public double GrossInternalAreaM2 { get; set; } = 0.0;

        [JsonPropertyName("new_gia_m2")]
        public double NewGiaM2 { get; set; } = 0.0;

        [JsonPropertyName("building_type_key")]
        public string BuildingTypeKey { get; set; } = "IStructE";

        // ── A5 Machinery ──────────────────────────────────────────────────────
        [JsonPropertyName("a5_machinery_factor_pct")]
        public double A5MachineryFactorPct { get; set; } = 1.5;

        [JsonPropertyName("uncertainty_factor_pct")]
        public double UncertaintyFactorPct { get; set; } = 10.0;

        // ── Transport Declarations (A4) ────────────────────────────────────────
        [JsonPropertyName("transport")]
        public Dictionary<string, MaterialTransportConfig> Transport { get; set; } = new();

        // ── Waste Declarations (A5) ────────────────────────────────────────────
        [JsonPropertyName("waste")]
        public Dictionary<string, MaterialWasteConfig> Waste { get; set; } = new();
    }

    /// <summary>
    /// Transport scenario for a single material class.
    /// The professional fills this from actual supplier delivery data or
    /// uses the vehicle type lookup to match their supply chain.
    /// </summary>
    public class MaterialTransportConfig
    {
        [JsonPropertyName("material_class")]
        public string MaterialClass { get; set; } = "";

        /// <summary>
        /// One-way delivery distance from factory/batching plant to construction site.
        /// </summary>
        [JsonPropertyName("distance_km")]
        public double DistanceKm { get; set; }

        /// <summary>
        /// Vehicle type key. Valid values:
        ///   HGV_RIGID_40T, HGV_ARTIC_40T, HGV_RIGID_7p5T,
        ///   RAIL_FREIGHT, BARGE, SEA_FREIGHT
        /// </summary>
        [JsonPropertyName("vehicle_type")]
        public string VehicleType { get; set; } = "HGV_RIGID_40T";

        [JsonPropertyName("supplier_name")]
        public string SupplierName { get; set; } = "";

        [JsonPropertyName("country_of_origin")]
        public string CountryOfOrigin { get; set; } = "";

        [JsonPropertyName("notes")]
        public string Notes { get; set; } = "";
    }

    /// <summary>
    /// Site waste fraction declaration for a material class.
    /// Sources: Site Waste Management Plan, or WRAP BRE 2014 benchmarks.
    /// </summary>
    public class MaterialWasteConfig
    {
        [JsonPropertyName("material_class")]
        public string MaterialClass { get; set; } = "";

        /// <summary>
        /// Fraction of purchased material wasted on site (0.0–0.5).
        /// Example: 0.05 = 5% of concrete ordered ends up as waste.
        /// </summary>
        [JsonPropertyName("waste_fraction")]
        public double WasteFraction { get; set; }

        [JsonPropertyName("source")]
        public string Source { get; set; } = "WRAP BRE 2014 (default)";
    }
}
