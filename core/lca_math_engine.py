"""
WLCA Phase Engine — ISO 21930 / EN 15978 / EN 15804 compliant
==============================================================
This module implements a rigorous Whole Life Carbon Assessment (WLCA) for
building elements extracted from Revit, covering modules A1–D as defined
by the following standards:

    EN 15978:2011  — Sustainability of construction works
    EN 15804:2012+A2:2019 — Core PCR for construction products
    ISO 21930:2017  — Sustainability in building construction

The engine is driven by ProjectConfig (core/project_config.py).
All transport distances, vehicle types, waste fractions, GIA and assessment
boundary declarations come from ProjectConfig — NOT from hardcoded tables.
The tables below serve as FALLBACK DEFAULTS ONLY when ProjectConfig is absent.

Lifecycle modules implemented:
    A1-A3  Product stage          (raw material, transport, manufacturing)
    A4     Transport to site       (distance × load factor by vehicle type)
    A5     Construction/Waste     (waste factor + machinery carbon)
    B1-B5  Use stage              (maintenance, replacement, refurbishment)
    C1-C4  End of life            (deconstruction, transport, waste processing, disposal)
    D      Beyond system boundary (net reuse/recycle credit — informational only)

Key references for default factors:
    - RICS Whole Life Carbon Assessment, 2nd ed. (2023)
    - ICE Database v3.0 (Bath, 2019) — GWP A1-A3 benchmarks
    - DEFRA transport emission factors (UK BEIS, 2023) — tCO2e/tonne.km
    - IPCC AR6 GWP100 characterisation factors
"""

import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Optional

from .exceptions import VolumeCalculationError
from .project_config import ProjectConfig, VEHICLE_OPTIONS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EN 15804 Transport Emission Factors (kgCO2e per tonne·km)
# Source: DEFRA/BEIS UK GHG Conversion Factors 2023, Table 10
# ---------------------------------------------------------------------------
TRANSPORT_FACTORS = {
    "HGV_RIGID_40T":   0.0603 / 1000,   # 40t rigid HGV (most common for ready-mix)
    "HGV_ARTIC_40T":   0.0490 / 1000,   # articulated 40t — steel / prefab
    "RAIL_FREIGHT":    0.0280 / 1000,    # rail — timber / stone over long distances
    "BARGE":           0.0312 / 1000,    # inland waterway barge
}

# ---------------------------------------------------------------------------
# EN 15804 Waste Factors per material class (fraction of purchased quantity
# that ends up as construction waste, based on WRAP BRE research, 2014)
# ---------------------------------------------------------------------------
WASTE_FACTORS = {
    "concrete":   0.05,   # 5 %  — typical for cast in-situ structures
    "steel":      0.02,   # 2 %  — prefab steel, very low waste generation
    "timber":     0.10,   # 10 % — high cut waste from framing + formwork
    "aluminium":  0.02,   # 2 %  — curtain wall systems mostly prefab
    "masonry":    0.07,   # 7 %  — brick/block laying mortar losses
    "glass":      0.03,   # 3 %  — curtain wall panels
    "insulation": 0.04,   # 4 %  — mineral wool, PIR etc.
    "generic":    0.05,   # 5 %  — fallback for unmapped materials
}

# ---------------------------------------------------------------------------
# EN 15804 C1-C4 End of Life Emission Factors (kgCO2e / kg material)
# Covers: C1 deconstruction energy, C2 transport, C3 waste processing,
# C4 landfill/incineration. Negative values = net benefit from recycling.
# Source: ICE Database v3.0 / BRE Green Guide Module C benchmarks.
# ---------------------------------------------------------------------------
EOL_FACTORS = {
    "concrete":    0.0088,   # C1 demolition fuel + C4 inert fill landfill
    "steel":      -0.410,    # net credit — high global scrap recovery rate ~86%
    "timber":      0.0150,   # biomass waste — partial incineration/landfill
    "aluminium":  -0.860,    # second highest recycling credit (>90% loop recovery)
    "masonry":     0.0050,   # crushed aggregate reuse, small landfill component
    "glass":       0.0120,   # limited recycling loop, mostly landfill
    "insulation":  0.0300,   # high-temperature incineration of non-recyclable foam
    "generic":     0.0200,   # conservative fallback
}

# ---------------------------------------------------------------------------
# Biogenic Carbon Sequestration (kgCO2 fixed per kg of dry material)
# Timber sequesters atmospheric CO2 during growth; values use EN 16485 method.
# Only applied to bio-based materials; concrete/steel always = 0.
# ---------------------------------------------------------------------------
BIOGENIC_SEQ_FACTORS = {
    "timber":       -1.83,   # kgCO2/kg — softwood average (ICE v3)
    "bamboo":       -1.10,
    "hemp":         -1.50,
}

# ---------------------------------------------------------------------------
# Default transport distances by structural element class (km, one-way)
# Based on typical UK/EU supply chains; configurable at project level.
# ---------------------------------------------------------------------------
DEFAULT_TRANSPORT_A4 = {
    "concrete":   30.0,    # km — ready-mix plant is usually local
    "steel":     150.0,    # km — steel mills are regional/national
    "timber":     80.0,    # km — sawmill is regional but timber imports add more
    "aluminium": 300.0,    # km — generally imported profiles
    "masonry":    50.0,    # km — brick/block factories are regional
    "glass":     200.0,    # km — float glass from large mills
    "insulation":100.0,
    "generic":    75.0,
}

DEFAULT_TRANSPORT_VEHICLE = {
    "concrete":   "HGV_RIGID_40T",
    "steel":      "HGV_ARTIC_40T",
    "timber":     "HGV_ARTIC_40T",
    "aluminium":  "HGV_ARTIC_40T",
    "masonry":    "HGV_RIGID_40T",
    "glass":      "HGV_ARTIC_40T",
    "insulation": "HGV_ARTIC_40T",
    "generic":    "HGV_RIGID_40T",
}

# ---------------------------------------------------------------------------
# Service Life data (years) — EN 15978 Annex A / ISO 15686-8
# Reference Study Period (RSP) = 60 years (IStructE default for structures)
# ---------------------------------------------------------------------------
RSP_YEARS = 60

SERVICE_LIFE = {
    "concrete":    120,   # structural concrete, self-compacting
    "steel":       120,   # structural steel with coating maintenance
    "timber":       60,   # structural timber (with moisture protection)
    "aluminium":    60,   # curtain wall / cladding
    "masonry":     120,   # load-bearing masonry
    "glass":        40,   # double-glazed units
    "insulation":   40,   # PIR/EPS built-in insulation
    "generic":      60,
}

# ---------------------------------------------------------------------------
# B2 Maintenance factors (kgCO2e per kg of material, per year of maintenance)
# e.g. repainting structural steel requires solvents and energy
# Source: RICS 2nd ed. WLCA Appendix C, typical maintenance intensities
# ---------------------------------------------------------------------------
MAINTENANCE_ANNUAL_FACTORS = {
    "concrete":    0.0000,   # no ongoing maintenance emissions for bare concrete
    "steel":       0.0012,   # solvent-based coating refresh every 10-15y
    "timber":      0.0020,   # wood preservative re-treatment + staining
    "aluminium":   0.0003,   # minimal coating refresh
    "masonry":     0.0002,   # re-pointing every 30y
    "glass":       0.0000,
    "insulation":  0.0000,
    "generic":     0.0005,
}


@dataclass
class ProjectSettings:
    """
    Project-level configuration that overrides generic defaults.
    Designed to be serialised to/from JSON so the Revit UI can expose
    these as editable fields in the Project Settings tab.
    """
    reference_study_period: int = RSP_YEARS
    gfa_m2: float = 0.0                    # Gross Floor Area (m²) for intensity calcs
    custom_transport_km: Optional[float] = None   # overrides all DEFAULT_TRANSPORT_A4
    a5_machinery_factor: float = 0.015     # site machinery carbon as % of A1-A3 total
    include_sequestration: bool = True
    include_module_d: bool = False          # D is informational per EN 15978
    uncertainty_factor_pct: float = 10.0   # ±% uncertainty band (RICS guidance)


@dataclass
class PhaseResult:
    """Container for all LCA phase results for a single element (kgCO2e)."""
    element_id: str
    material_id: str
    material_class: str
    mass_kg: float
    volume_m3: float

    co2_a1_a3: float = 0.0
    co2_a4: float = 0.0
    co2_a5_waste: float = 0.0
    co2_a5_machinery: float = 0.0
    co2_b1: float = 0.0       # use — carbonation in concrete (negative for CO2 uptake)
    co2_b2: float = 0.0       # maintenance
    co2_b3: float = 0.0       # repair
    co2_b4: float = 0.0       # replacement (if service life < RSP)
    co2_b5: float = 0.0       # refurbishment — not element-level, zeroed here
    co2_c1: float = 0.0       # deconstruction / demolition fuel
    co2_c2: float = 0.0       # transport to waste facility
    co2_c3: float = 0.0       # waste processing
    co2_c4: float = 0.0       # landfill / disposal
    co2_d: float = 0.0        # net recycling benefit (informational)
    co2_seq: float = 0.0      # biogenic sequestration (informational)
    _fallback: bool = False

    @property
    def upfront_carbon(self) -> float:
        """A1-A5 — Upfront / Embodied Carbon (pre-occupancy)."""
        return self.co2_a1_a3 + self.co2_a4 + self.co2_a5_waste + self.co2_a5_machinery

    @property
    def use_stage_carbon(self) -> float:
        """B1-B5 — In-use carbon."""
        return self.co2_b1 + self.co2_b2 + self.co2_b3 + self.co2_b4 + self.co2_b5

    @property
    def end_of_life_carbon(self) -> float:
        """C1-C4 — End of life carbon."""
        return self.co2_c1 + self.co2_c2 + self.co2_c3 + self.co2_c4

    @property
    def whole_life_carbon(self) -> float:
        """A1-C4 — Whole Life Carbon (standard reporting boundary)."""
        return self.upfront_carbon + self.use_stage_carbon + self.end_of_life_carbon

    @property
    def total_inc_d(self) -> float:
        """A1–D including informational module D."""
        return self.whole_life_carbon + self.co2_d + self.co2_seq


def _classify_material(material_id: str) -> str:
    """
    Maps a Revit material name string to an internal material class key.
    Uses substring matching with a priority order to handle compound names
    like 'Concrete - Reinforced C30/37' → 'concrete'.
    """
    mid = material_id.lower()
    # Priority order matters — check more specific names first
    for kw, cls in [
        ("aluminium", "aluminium"), ("aluminum", "aluminium"),
        ("steel", "steel"), ("rebar", "steel"), ("reinforcement", "steel"),
        ("timber", "timber"), ("wood", "timber"), ("plywood", "timber"),
        ("bamboo", "bamboo"),
        ("glass", "glass"),
        ("insulation", "insulation"), ("rockwool", "insulation"), ("pir", "insulation"),
        ("masonry", "masonry"), ("brick", "masonry"), ("block", "masonry"),
        ("concrete", "concrete"),
    ]:
        if kw in mid:
            return cls
    return "generic"


class LCAMathEngine:
    """
    Whole Life Carbon Assessment engine.

    Implements EN 15978/EN 15804 module calculations for any set of BIM elements
    represented as a Pandas DataFrame. All intermediate values are preserved in
    the output for full audit-trail compliance.

    Usage (with full project config):
        from core.project_config import ProjectConfig
        config = ProjectConfig.load('project_config.json')
        engine = LCAMathEngine(db_df, config=config)
        result_df = engine.calculate_embodied_carbon(bim_df)

    Usage (legacy — uses hardcoded defaults):
        engine = LCAMathEngine(db_df, settings=ProjectSettings(gfa_m2=5400))
        result_df = engine.calculate_embodied_carbon(bim_df)
    """

    def __init__(
        self,
        db_df: pd.DataFrame,
        settings: Optional[ProjectSettings] = None,    # legacy
        config: Optional[ProjectConfig] = None,        # preferred
    ):
        # ProjectConfig takes priority over the legacy ProjectSettings shim.
        self.config   = config
        self.settings = settings or ProjectSettings()

        # Sync ProjectConfig → ProjectSettings for fields that still use the legacy path
        if config:
            self.settings.reference_study_period  = config.reference_study_period
            self.settings.gfa_m2                  = config.gross_internal_area_m2
            self.settings.a5_machinery_factor      = config.a5_machinery_factor_pct / 100.0
            self.settings.include_sequestration    = config.include_sequestration
            self.settings.uncertainty_factor_pct   = config.uncertainty_factor_pct

        columns_to_keep = ['material_id', 'density_kg_m3', 'gwp_factor_kgco2_per_kg']
        existing = [c for c in columns_to_keep if c in db_df.columns]
        self.db = db_df[existing].copy()

        if 'gwp_factor_kgco2_per_kg' in self.db.columns:
            self.db.rename(columns={'gwp_factor_kgco2_per_kg': 'gwp_a1_a3'}, inplace=True)
        elif 'gwp_a1_a3' not in self.db.columns:
            self.db['gwp_a1_a3'] = 0.10

        if 'material_id' in self.db.columns:
            self.db.set_index('material_id', inplace=True)

        src = 'ProjectConfig' if config else 'ProjectSettings (defaults)'
        logger.info(f"LCAMathEngine initialised — {len(self.db)} materials, config={src}.")

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def calculate_embodied_carbon(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Entry point. Accepts a BIM payload DataFrame and returns it enriched
        with all LCA phase columns plus summary properties.

        Required columns in df:
            material_id (str), volume_m3 (numeric)
        Optional columns:
            element_id (str), category (str)
        """
        if df.empty:
            return df

        self._validate_input(df)

        df = df.copy()
        df['volume_m3'] = pd.to_numeric(df['volume_m3'], errors='coerce').fillna(0.0)
        df['material_class'] = df['material_id'].apply(_classify_material)

        # Join DB properties (density + GWP A1-A3)
        enriched = df.join(self.db, on='material_id', how='left')
        enriched = self._apply_fallback(enriched)

        # --- Phase calculations ---
        enriched = self._calc_mass(enriched)
        enriched = self._calc_a1_a3(enriched)
        enriched = self._calc_a4(enriched)
        enriched = self._calc_a5(enriched)
        enriched = self._calc_b_modules(enriched)
        enriched = self._calc_c_modules(enriched)
        enriched = self._calc_d_and_sequestration(enriched)
        enriched = self._calc_summaries(enriched)

        return enriched

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def _validate_input(self, df: pd.DataFrame) -> None:
        required = ['material_id', 'volume_m3']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise KeyError(f"Input DataFrame missing required columns: {missing}")

        df_tmp = df.copy()
        df_tmp['volume_m3'] = pd.to_numeric(df_tmp['volume_m3'], errors='coerce').fillna(0)
        negatives = df_tmp[df_tmp['volume_m3'] < 0]
        if not negatives.empty:
            row = negatives.iloc[0]
            raise VolumeCalculationError(
                element_id=str(row.get('element_id', 'Unknown')),
                volume=float(row['volume_m3'])
            )

    # -----------------------------------------------------------------------
    # Fallback for materials missing from DB
    # -----------------------------------------------------------------------

    def _apply_fallback(self, df: pd.DataFrame) -> pd.DataFrame:
        missing_mask = df['gwp_a1_a3'].isna()
        if missing_mask.any():
            missing_mats = df.loc[missing_mask, 'material_id'].unique().tolist()
            logger.warning(
                f"[A1-A3 Fallback] {missing_mask.sum()} element(s) used generic concrete "
                f"values (density=2200 kg/m³, GWP=0.13 kgCO₂e/kg). "
                f"Unmapped materials: {missing_mats}"
            )
            df.loc[missing_mask, 'density_kg_m3'] = 2200.0
            df.loc[missing_mask, 'gwp_a1_a3'] = 0.130
            df.loc[missing_mask, '_fallback'] = True
        else:
            df['_fallback'] = False
        return df

    # -----------------------------------------------------------------------
    # Module A1-A3: Product Stage
    # -----------------------------------------------------------------------

    def _calc_mass(self, df: pd.DataFrame) -> pd.DataFrame:
        df['mass_kg'] = df['volume_m3'] * df['density_kg_m3']
        return df

    def _calc_a1_a3(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        A1-A3: Raw material extraction + transport to factory + manufacturing.
        Uses EPD GWP100 factor (kgCO2e/kg) from material DB.
        """
        df['co2_a1_a3'] = df['mass_kg'] * df['gwp_a1_a3']
        return df

    # -----------------------------------------------------------------------
    # Module A4: Transport to Site
    # EN 15804 formula: EC_A4 = mass_t × distance_km × EF_vehicle (kgCO2e/t·km)
    # -----------------------------------------------------------------------

    def _calc_a4(self, df: pd.DataFrame) -> pd.DataFrame:
        def _a4_for_row(row):
            mat_cls = row['material_class']
            if self.config:
                # Use declared project transport data (auditable)
                dist_km, ef, veh_label = self.config.get_transport_ef(mat_cls)
                row['_a4_vehicle']  = veh_label
                row['_a4_dist_km']  = dist_km
            else:
                # Legacy fallback
                dist_km = (
                    self.settings.custom_transport_km
                    or DEFAULT_TRANSPORT_A4.get(mat_cls, DEFAULT_TRANSPORT_A4["generic"])
                )
                vehicle = DEFAULT_TRANSPORT_VEHICLE.get(mat_cls, "HGV_RIGID_40T")
                ef      = TRANSPORT_FACTORS[vehicle]
            return row['mass_kg'] * dist_km * ef

        df['co2_a4'] = df.apply(_a4_for_row, axis=1)
        # Populate audit columns if config was used
        if self.config:
            def _audit(row):
                d, ef, label = self.config.get_transport_ef(row['material_class'])
                return pd.Series({'_a4_vehicle': label, '_a4_dist_km': d})
            df[['_a4_vehicle', '_a4_dist_km']] = df.apply(_audit, axis=1)
        return df

    # -----------------------------------------------------------------------
    # Module A5: Construction-Installation Process
    # A5 = A5_waste + A5_machinery
    # A5_waste = waste_fraction × (mass/(1-waste_fraction)) × (GWP_A1A3 + GWP_A4)
    # This accounts for material over-order to cover losses on site.
    # -----------------------------------------------------------------------

    def _calc_a5(self, df: pd.DataFrame) -> pd.DataFrame:
        def _a5_for_row(row):
            mat_cls = row['material_class']
            if self.config:
                wf, wf_source = self.config.get_waste_fraction(mat_cls)
            else:
                wf = WASTE_FACTORS.get(mat_cls, WASTE_FACTORS["generic"])
            waste_mass_kg  = row['mass_kg'] * wf / (1.0 - wf)
            gwp_per_kg     = row['gwp_a1_a3']
            a4_per_kg      = row['co2_a4'] / max(row['mass_kg'], 1e-9)
            return waste_mass_kg * (gwp_per_kg + a4_per_kg)

        df['co2_a5_waste']     = df.apply(_a5_for_row, axis=1)
        df['co2_a5_machinery'] = df['co2_a1_a3'] * self.settings.a5_machinery_factor
        df['co2_a5']           = df['co2_a5_waste'] + df['co2_a5_machinery']
        return df

    # -----------------------------------------------------------------------
    # Modules B1–B5: Use Stage
    # B1 = carbonation CO2 uptake by concrete (negative, EN 16757 method)
    # B2 = maintenance (annual coating/treatment factor × mass × RSP)
    # B4 = replacement carbon = (RSP/SL - 1) × (A1-A5) if SL < RSP, else 0
    # -----------------------------------------------------------------------

    def _calc_b_modules(self, df: pd.DataFrame) -> pd.DataFrame:
        rsp = self.settings.reference_study_period

        def _b_for_row(row):
            mat_cls = row['material_class']
            mass = row['mass_kg']

            # B1: Concrete carbonation recaptures ~1-3% of manufacturing CO2 over RSP
            # EN 16757:2017 simplified method — 1.5% uptake factor for ordinary concrete
            b1 = -row['co2_a1_a3'] * 0.015 if mat_cls == 'concrete' else 0.0

            # B2: Maintenance — annual maintenance emission × RSP years
            maint_factor = MAINTENANCE_ANNUAL_FACTORS.get(mat_cls, 0.0005)
            b2 = mass * maint_factor * rsp

            # B3: Repair (distinct from maintenance) — set to zero for structural elements
            b3 = 0.0

            # B4: Replacement — if service life < RSP, element must be replaced
            sl = SERVICE_LIFE.get(mat_cls, 60)
            replacements = max(0, int(rsp / sl) - 1) if sl < rsp else 0
            a1_a5 = row['co2_a1_a3'] + row.get('co2_a4', 0) + row.get('co2_a5', 0)
            b4 = replacements * a1_a5

            # B5: Refurbishment — building-level, not element-level → zero
            b5 = 0.0

            return b1, b2, b3, b4, b5

        df[['co2_b1', 'co2_b2', 'co2_b3', 'co2_b4', 'co2_b5']] = (
            df.apply(lambda r: pd.Series(_b_for_row(r)), axis=1)
        )
        return df

    # -----------------------------------------------------------------------
    # Modules C1–C4: End of Life
    # C1: Deconstruction fuel (ICE benchmark: 0.0083 kgCO2e/kg for concrete demolition)
    # C2: Transport of debris (mass × avg EoL transport distance × HGV factor)
    # C3+C4: Combined — from material-specific EoL factors in EOL_FACTORS
    # -----------------------------------------------------------------------

    def _calc_c_modules(self, df: pd.DataFrame) -> pd.DataFrame:
        # C1 deconstruction energy benchmarks (kgCO2e/kg)
        C1_FACTORS = {
            "concrete":    0.0083,   # mechanical demolition + crushing
            "steel":       0.0010,   # cutting — very low energy vs concrete
            "timber":      0.0020,
            "generic":     0.0050,
        }
        EOL_TRANSPORT_KM = 30.0   # typical skip/debris lorry distance to waste facility

        def _c_for_row(row):
            mat_cls = row['material_class']
            mass = row['mass_kg']

            c1 = mass * C1_FACTORS.get(mat_cls, C1_FACTORS['generic'])
            c2 = mass * EOL_TRANSPORT_KM * TRANSPORT_FACTORS['HGV_RIGID_40T']
            eol_combined = mass * EOL_FACTORS.get(mat_cls, EOL_FACTORS['generic'])
            # Split C3+C4 allocation: 30% processing, 70% disposal (WRAP data)
            c3 = eol_combined * 0.30
            c4 = eol_combined * 0.70
            return c1, c2, c3, c4

        df[['co2_c1', 'co2_c2', 'co2_c3', 'co2_c4']] = (
            df.apply(lambda r: pd.Series(_c_for_row(r)), axis=1)
        )
        return df

    # -----------------------------------------------------------------------
    # Module D: Beyond System Boundary (informational)
    # Net benefit from reuse, recovery, and recycling potential.
    # EN 15978 requires this to be reported separately and never summed into A-C.
    # -----------------------------------------------------------------------

    def _calc_d_and_sequestration(self, df: pd.DataFrame) -> pd.DataFrame:
        # D: material-specific recycling credit at EoL
        D_FACTORS = {
            "steel":       -0.450,   # kgCO2e/kg credit (virgin steel avoided)
            "aluminium":   -0.900,
            "timber":      -0.050,   # biomass energy recovery credit
            "concrete":     0.000,
            "generic":     -0.020,
        }

        def _d_for_row(row):
            mat_cls = row['material_class']
            d = row['mass_kg'] * D_FACTORS.get(mat_cls, D_FACTORS['generic'])
            seq = row['mass_kg'] * BIOGENIC_SEQ_FACTORS.get(mat_cls, 0.0) if self.settings.include_sequestration else 0.0
            return d, seq

        df[['co2_d', 'co2_seq']] = df.apply(lambda r: pd.Series(_d_for_row(r)), axis=1)
        return df

    # -----------------------------------------------------------------------
    # Summary Columns (used by API response and aggregator)
    # -----------------------------------------------------------------------

    def _calc_summaries(self, df: pd.DataFrame) -> pd.DataFrame:
        df['upfront_carbon_kgco2e'] = (
            df['co2_a1_a3'] + df['co2_a4'] + df['co2_a5_waste'] + df['co2_a5_machinery']
        )
        df['use_stage_carbon_kgco2e'] = (
            df['co2_b1'] + df['co2_b2'] + df['co2_b3'] + df['co2_b4'] + df['co2_b5']
        )
        df['end_of_life_carbon_kgco2e'] = (
            df['co2_c1'] + df['co2_c2'] + df['co2_c3'] + df['co2_c4']
        )
        df['embodied_carbon_kgco2e'] = (
            df['upfront_carbon_kgco2e']
            + df['use_stage_carbon_kgco2e']
            + df['end_of_life_carbon_kgco2e']
        )
        # GWP intensity per unit volume — useful for heatmap colour-mapping
        df['carbon_intensity_per_m3'] = np.where(
            df['volume_m3'] > 0,
            df['embodied_carbon_kgco2e'] / df['volume_m3'],
            0.0
        )
        # Uncertainty bounds (±%)
        unc = self.settings.uncertainty_factor_pct / 100.0
        df['embodied_carbon_upper'] = df['embodied_carbon_kgco2e'] * (1.0 + unc)
        df['embodied_carbon_lower'] = df['embodied_carbon_kgco2e'] * (1.0 - unc)

        return df