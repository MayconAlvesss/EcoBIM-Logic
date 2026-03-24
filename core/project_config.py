"""
core/project_config.py — Project-Level WLCA Configuration Schema
=================================================================
This module defines the configuration that a professional engineer must fill in
before running a WLCA calculation. Without this data, the engine falls back to
conservative generic assumptions that may not reflect site reality.

The config is persisted as a JSON file alongside the Revit model and is passed
from the C# plugin to the Python API as part of every /process-model request.

Why this matters (professional traceability):
  EN 15978 §6.3 requires that the declared system boundary and all scenario
  assumptions be explicitly documented and justified in the assessment report.
  Using unverified defaults is non-compliant for formal WLCA submissions.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List
import json
import os

# ---------------------------------------------------------------------------
# Transport vehicle options - each maps to a DEFRA/BEIS 2023 emission factor
# ---------------------------------------------------------------------------
VEHICLE_OPTIONS = {
    "HGV_RIGID_40T":  {"label": "HGV Rigid 40t (Ready-mix, masonry)", "ef_kg_per_t_km": 0.0603},
    "HGV_ARTIC_40T":  {"label": "HGV Articulated 40t (Steel, timber prefab)", "ef_kg_per_t_km": 0.0490},
    "HGV_RIGID_7p5T": {"label": "HGV Rigid 7.5t (Small loads, insulation)", "ef_kg_per_t_km": 0.1633},
    "RAIL_FREIGHT":   {"label": "Rail Freight (Long-distance stone, aggregates)", "ef_kg_per_t_km": 0.0280},
    "BARGE":          {"label": "Inland Barge (Aggregates, heavy materials)", "ef_kg_per_t_km": 0.0312},
    "SEA_FREIGHT":    {"label": "Sea Freight (Imported aluminium, bamboo)", "ef_kg_per_t_km": 0.0115},
}

BUILDING_TYPE_OPTIONS = {
    "IStructE":  {"label": "IStructE Structure",  "scores": {"A++": 0,   "A+": 50,  "A": 100, "B": 150, "C": 200, "D": 250, "E": 300, "F": 350, "G": 450}},
    "RIBA_2030": {"label": "RIBA 2030 Upfront",   "scores": {"A++": 0,   "A+": 100, "A": 200, "B": 300, "C": 400, "D": 500, "E": 600, "F": 800, "G": 1000}},
    "LETI_2020": {"label": "LETI 2020 Whole Life", "scores": {"A++": 0,   "A+": 200, "A": 300, "B": 450, "C": 600, "D": 750, "E": 900, "F": 1050, "G": 1200}},
    "CUSTOM":    {"label": "Custom Targets",       "scores": {}},
}


@dataclass
class MaterialTransportConfig:
    """
    Transport declaration for a single material class.
    The professional fills this in from actual supplier delivery data.
    """
    material_class: str         # e.g. "concrete", "steel", "timber"
    distance_km: float          # one-way delivery distance from factory/plant to site
    vehicle_type: str           # key from VEHICLE_OPTIONS
    supplier_name: str = ""     # optional: for audit trail
    country_of_origin: str = "" # optional: flags for long-haul (sea freight)
    notes: str = ""

    def validate(self) -> List[str]:
        errors = []
        if self.distance_km <= 0:
            errors.append(f"{self.material_class}: distance_km must be > 0")
        if self.vehicle_type not in VEHICLE_OPTIONS:
            errors.append(f"{self.material_class}: unknown vehicle_type '{self.vehicle_type}'. Choose: {list(VEHICLE_OPTIONS.keys())}")
        return errors


@dataclass
class MaterialWasteConfig:
    """
    Site waste declaration for a material class.
    Sources: site waste management plans, or WRAP BRE benchmarks as defaults.
    """
    material_class: str
    waste_fraction: float   # 0.0 to 0.5 — fraction of purchased material wasted on site
    source: str = "WRAP BRE 2014 (default)"


@dataclass
class ProjectConfig:
    """
    Master configuration object that every professional must complete.
    This replaces all hardcoded defaults in the WLCA engine.

    Fields map directly to the 'Project Settings' tab in the Revit plugin.
    If a field is left at its default, the report will flag it as
    'ASSUMED — not verified for this project' in compliance notes.
    """
    # --- Identity ---
    project_number: str = ""
    project_name: str = "Unnamed Project"
    location: str = ""
    architect: str = ""
    structural_engineer: str = ""
    assessor_name: str = ""
    assessment_date: str = ""

    # --- System Boundary (EN 15978 §6.3) ---
    include_module_a0: bool = False   # A0: pre-construction (surveys, temp works)
    include_module_a1_a3: bool = True
    include_module_a4: bool = True
    include_module_a5: bool = True
    include_module_b: bool = True
    include_module_c: bool = True
    include_module_d: bool = False    # EN 15978: D is informational, reported separately
    include_sequestration: bool = True

    # --- Metrics ---
    reference_study_period: int = 60         # years — IStructE default
    gross_internal_area_m2: float = 0.0      # GIA — required for intensity (kgCO2e/m²)
    new_gia_m2: float = 0.0                  # for extensions/refurbs: new area only
    building_type_key: str = "IStructE"      # key from BUILDING_TYPE_OPTIONS

    # --- A5 Machinery ---
    # EN 15804 A5 site energy: % of A1-A3 carbon attributed to site plant/machinery
    a5_machinery_factor_pct: float = 1.5     # % — RICS 2023 typical range: 0.5–3.0%

    # --- Uncertainty ---
    uncertainty_factor_pct: float = 10.0    # ±% — RICS WLCA 2nd ed. default

    # --- Transport Declarations (A4) ---
    # Maps material_class → transport config.
    # If a class is absent, the motor uses conservative national defaults.
    transport: Dict[str, MaterialTransportConfig] = field(default_factory=dict)

    # --- Waste Declarations (A5) ---
    waste: Dict[str, MaterialWasteConfig] = field(default_factory=dict)

    # --- Custom Targets ---
    custom_a1_c_target_kg_m2: Optional[float] = None  # only used if building_type_key == "CUSTOM"

    def get_transport_ef(self, material_class: str) -> tuple[float, float, str]:
        """
        Returns (distance_km, ef_kg_per_t_km, vehicle_label) for a material class.
        Falls back to conservative defaults if not declared — and logs the assumption.
        """
        # Defaults matching lca_math_engine.py for auditable fallback
        DEFAULT_TRANSPORT = {
            "concrete":   ("HGV_RIGID_40T",  30.0),
            "steel":      ("HGV_ARTIC_40T", 150.0),
            "timber":     ("HGV_ARTIC_40T",  80.0),
            "aluminium":  ("HGV_ARTIC_40T", 300.0),
            "masonry":    ("HGV_RIGID_40T",  50.0),
            "glass":      ("HGV_ARTIC_40T", 200.0),
            "insulation": ("HGV_ARTIC_40T", 100.0),
            "generic":    ("HGV_RIGID_40T",  75.0),
        }
        if material_class in self.transport:
            cfg = self.transport[material_class]
            ef  = VEHICLE_OPTIONS[cfg.vehicle_type]["ef_kg_per_t_km"] / 1000.0
            return cfg.distance_km, ef, VEHICLE_OPTIONS[cfg.vehicle_type]["label"]
        veh, dist = DEFAULT_TRANSPORT.get(material_class, ("HGV_RIGID_40T", 75.0))
        return dist, VEHICLE_OPTIONS[veh]["ef_kg_per_t_km"] / 1000.0, f"{VEHICLE_OPTIONS[veh]['label']} [DEFAULT]"

    def get_waste_fraction(self, material_class: str) -> tuple[float, str]:
        """Returns (waste_fraction, source) — declared or benchmark default."""
        DEFAULTS = {
            "concrete": (0.05, "WRAP BRE 2014"),
            "steel":    (0.02, "WRAP BRE 2014"),
            "timber":   (0.10, "WRAP BRE 2014"),
            "aluminium":(0.02, "WRAP BRE 2014"),
            "masonry":  (0.07, "WRAP BRE 2014"),
            "glass":    (0.03, "WRAP BRE 2014"),
            "insulation":(0.04,"WRAP BRE 2014"),
            "generic":  (0.05, "WRAP BRE 2014"),
        }
        if material_class in self.waste:
            cfg = self.waste[material_class]
            return cfg.waste_fraction, cfg.source
        return DEFAULTS.get(material_class, (0.05, "WRAP BRE 2014 [DEFAULT]"))

    def get_target_score(self) -> tuple[float, Dict[str, float]]:
        """Returns the A1-A5 target score (kgCO2e/m²) for the chosen building type."""
        if self.building_type_key == "CUSTOM":
            return self.custom_a1_c_target_kg_m2 or 150.0, {}
        btype = BUILDING_TYPE_OPTIONS.get(self.building_type_key, BUILDING_TYPE_OPTIONS["IStructE"])
        target_a = btype["scores"].get("A", 150.0)
        return target_a, btype["scores"]

    def get_score_rating(self, intensity_kg_m2: float) -> str:
        """Maps a carbon intensity value to a letter rating for the target chart."""
        _, scores = self.get_target_score()
        if not scores:
            return "N/A"
        for grade in ["A++", "A+", "A", "B", "C", "D", "E", "F", "G"]:
            threshold = scores.get(grade, 9999)
            if intensity_kg_m2 <= threshold:
                return grade
        return "G"

    def list_undeclared_assumptions(self) -> List[str]:
        """
        Returns a list of assumptions that were NOT explicitly declared
        and therefore used engine defaults — important for WLCA compliance.
        """
        notes = []
        required_classes = ["concrete", "steel", "timber", "masonry", "aluminium", "glass", "insulation"]
        for cls in required_classes:
            if cls not in self.transport:
                notes.append(f"[A4] {cls}: transport distance and vehicle type not declared — using national defaults")
            if cls not in self.waste:
                notes.append(f"[A5] {cls}: site waste fraction not declared — using WRAP BRE 2014 benchmark")
        if self.gross_internal_area_m2 == 0:
            notes.append("[GIA] Gross Internal Area not set — carbon intensity (kgCO2e/m²) cannot be calculated")
        if not self.assessor_name:
            notes.append("[ID] Assessor name not declared — required for EN 15978 compliance statement")
        return notes

    def validate(self) -> List[str]:
        """Returns all validation errors. Empty list = config is valid."""
        errors = []
        for cls, cfg in self.transport.items():
            errors.extend(cfg.validate())
        for cls, cfg in self.waste.items():
            if not (0 < cfg.waste_fraction < 1):
                errors.append(f"[A5] {cls}: waste_fraction must be between 0 and 1, got {cfg.waste_fraction}")
        if self.gross_internal_area_m2 < 0:
            errors.append("gross_internal_area_m2 cannot be negative")
        if not (0 < self.uncertainty_factor_pct < 100):
            errors.append("uncertainty_factor_pct must be between 0 and 100")
        return errors

    # ---- Serialisation ----

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: str) -> "ProjectConfig":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Reconstruct nested dataclasses
        transport_raw = data.pop("transport", {})
        waste_raw     = data.pop("waste", {})
        cfg = cls(**data)
        cfg.transport = {k: MaterialTransportConfig(**v) for k, v in transport_raw.items()}
        cfg.waste     = {k: MaterialWasteConfig(**v) for k, v in waste_raw.items()}
        return cfg

    @classmethod
    def default_template(cls) -> "ProjectConfig":
        """
        Returns a fully declared example config for a typical UK RC-framed office.
        Used as a template for first-time users and for the test suite.
        """
        return cls(
            project_number="PROJ-001",
            project_name="Sample RC Office Building",
            location="London, UK",
            assessor_name="J. Smith (CEng MIStructE)",
            gross_internal_area_m2=6400.0,
            new_gia_m2=6400.0,
            reference_study_period=60,
            building_type_key="IStructE",
            a5_machinery_factor_pct=1.5,
            uncertainty_factor_pct=10.0,
            transport={
                "concrete":   MaterialTransportConfig("concrete",   15.0, "HGV_RIGID_40T",  "ABC Ready Mix Ltd",    "UK",   "Local batching plant"),
                "steel":      MaterialTransportConfig("steel",      180.0, "HGV_ARTIC_40T", "British Steel",        "UK",   "Scunthorpe mill"),
                "timber":     MaterialTransportConfig("timber",     250.0, "RAIL_FREIGHT",  "Sweden Timber AB",     "SE",   "Rail + road last mile"),
                "aluminium":  MaterialTransportConfig("aluminium",  500.0, "SEA_FREIGHT",   "Norsk Hydro",          "NO",   "Sea + road from port"),
                "masonry":    MaterialTransportConfig("masonry",     40.0, "HGV_RIGID_40T", "Ibstock Bricks",       "UK",   "Regional brick works"),
                "glass":      MaterialTransportConfig("glass",      300.0, "HGV_ARTIC_40T", "Pilkington UK",        "UK",   "St Helens factory"),
                "insulation": MaterialTransportConfig("insulation",  80.0, "HGV_ARTIC_40T", "Knauf Insulation Ltd", "UK",   ""),
            },
            waste={
                "concrete":    MaterialWasteConfig("concrete",    0.04, "Site Waste Management Plan Rev.2"),
                "steel":       MaterialWasteConfig("steel",       0.02, "Site Waste Management Plan Rev.2"),
                "timber":      MaterialWasteConfig("timber",      0.08, "Site Waste Management Plan Rev.2"),
                "aluminium":   MaterialWasteConfig("aluminium",   0.02, "WRAP BRE 2014"),
                "masonry":     MaterialWasteConfig("masonry",     0.06, "Site Waste Management Plan Rev.2"),
                "glass":       MaterialWasteConfig("glass",       0.03, "WRAP BRE 2014"),
                "insulation":  MaterialWasteConfig("insulation",  0.04, "WRAP BRE 2014"),
            },
        )
