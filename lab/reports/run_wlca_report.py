"""
lab/reports/run_wlca_report.py
==============================
Standalone audit script that:
  1. Runs the WLCA engine against a realistic BIM-like dataset.
  2. Validates each phase independently against expected reference values.
  3. Computes pass/fail rates per test group.
  4. Writes a JSON + Markdown report to lab/reports/outputs/.

Run from project root:
    python lab/reports/run_wlca_report.py
"""
import os
import sys
import json
import datetime
import traceback

# Force UTF-8 output on Windows PowerShell / cmd to avoid charmap encoding errors
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from core.lca_math_engine import (
    LCAMathEngine, ProjectSettings, TRANSPORT_FACTORS, DEFAULT_TRANSPORT_A4, DEFAULT_TRANSPORT_VEHICLE,
    WASTE_FACTORS, MAINTENANCE_ANNUAL_FACTORS,
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# ===========================================================================
# Reference BIM Dataset (simulates typical IStructE multi-storey RC building)
# ===========================================================================

BIM_ELEMENTS = [
    {"element_id": "WALL-C01",  "material_id": "Concrete",   "volume_m3": 42.77, "category": "Walls"},
    {"element_id": "FLOOR-C01", "material_id": "Concrete",   "volume_m3": 10.69, "category": "Floors"},
    {"element_id": "FOUND-C01", "material_id": "Concrete",   "volume_m3": 22.51, "category": "Structural Foundations"},
    {"element_id": "COL-S01",   "material_id": "Steel",      "volume_m3": 0.22,  "category": "Structural Columns"},
    {"element_id": "BEAM-S01",  "material_id": "Steel",      "volume_m3": 1.60,  "category": "Structural Framing"},
    {"element_id": "RBAR-S01",  "material_id": "Steel",      "volume_m3": 0.85,  "category": "Structural Framing"},
    {"element_id": "ROOF-T01",  "material_id": "Timber",     "volume_m3": 3.20,  "category": "Roofs"},
    {"element_id": "INSUL-01",  "material_id": "Insulation", "volume_m3": 5.50,  "category": "Walls"},
    {"element_id": "GLAZ-01",   "material_id": "Glass",      "volume_m3": 1.80,  "category": "Walls"},
]

MATERIAL_DB = pd.DataFrame({
    "material_id":            ["Concrete", "Steel",  "Timber", "Insulation", "Glass"],
    "density_kg_m3":          [2400.0,     7850.0,   500.0,    35.0,         2500.0],
    "gwp_factor_kgco2_per_kg": [0.103,     1.55,     0.263,    1.86,         1.35],
})

SETTINGS = ProjectSettings(
    reference_study_period=60,
    gfa_m2=6400.0,
    a5_machinery_factor=0.015,
    include_sequestration=True,
    uncertainty_factor_pct=10.0,
)


# ===========================================================================
# Test Case Definitions
# ===========================================================================

def _a4_ref(mass_kg: float, mat_class: str) -> float:
    dist = DEFAULT_TRANSPORT_A4.get(mat_class, DEFAULT_TRANSPORT_A4["generic"])
    veh  = DEFAULT_TRANSPORT_VEHICLE.get(mat_class, "HGV_RIGID_40T")
    return mass_kg * dist * TRANSPORT_FACTORS[veh]


TEST_CASES = []


def define_tests(result_df: pd.DataFrame):
    """Build all test cases after engine has run."""
    cases = []

    for _, row in result_df.iterrows():
        eid   = row["element_id"]
        mat   = row["material_id"]
        cls   = row["material_class"]
        mass  = row["mass_kg"]

        # ── A1-A3 ────────────────────────────────────────────────────────────
        gwp_from_db = MATERIAL_DB.loc[MATERIAL_DB["material_id"] == mat, "gwp_factor_kgco2_per_kg"]
        gwp = float(gwp_from_db.values[0]) if not gwp_from_db.empty else 0.130
        expected_a1a3 = mass * gwp
        cases.append({
            "group": "A1-A3 Product Stage",
            "element": eid,
            "check": "co2_a1_a3",
            "expected": round(expected_a1a3, 4),
            "actual":   round(float(row["co2_a1_a3"]), 4),
            "tol_pct":  0.001,
        })

        # ── A4 Transport ─────────────────────────────────────────────────────
        expected_a4 = _a4_ref(mass, cls)
        cases.append({
            "group": "A4 Transport to Site",
            "element": eid,
            "check": "co2_a4",
            "expected": round(expected_a4, 6),
            "actual":   round(float(row["co2_a4"]), 6),
            "tol_pct":  0.001,
        })

        # ── A5 Waste ─────────────────────────────────────────────────────────
        wf = WASTE_FACTORS.get(cls, WASTE_FACTORS["generic"])
        waste_mass = mass * wf / (1.0 - wf)
        a4_per_kg = expected_a4 / max(mass, 1e-9)
        expected_a5w = waste_mass * (gwp + a4_per_kg)
        cases.append({
            "group": "A5 Construction Waste",
            "element": eid,
            "check": "co2_a5_waste",
            "expected": round(expected_a5w, 6),
            "actual":   round(float(row["co2_a5_waste"]), 6),
            "tol_pct":  0.001,
        })

        # ── B2 Maintenance ───────────────────────────────────────────────────
        mf = MAINTENANCE_ANNUAL_FACTORS.get(cls, 0.0005)
        expected_b2 = mass * mf * SETTINGS.reference_study_period
        cases.append({
            "group": "B2 Maintenance",
            "element": eid,
            "check": "co2_b2",
            "expected": round(expected_b2, 6),
            "actual":   round(float(row["co2_b2"]), 6),
            "tol_pct":  0.001,
        })

        # ── C2 EoL Transport ─────────────────────────────────────────────────
        expected_c2 = mass * 30.0 * TRANSPORT_FACTORS["HGV_RIGID_40T"]
        cases.append({
            "group": "C2 EoL Transport",
            "element": eid,
            "check": "co2_c2",
            "expected": round(expected_c2, 6),
            "actual":   round(float(row["co2_c2"]), 6),
            "tol_pct":  0.001,
        })

        # ── Upfront Carbon Summation ─────────────────────────────────────────
        expected_upfront = (
            float(row["co2_a1_a3"])
            + float(row["co2_a4"])
            + float(row["co2_a5_waste"])
            + float(row["co2_a5_machinery"])
        )
        cases.append({
            "group": "Upfront Carbon A1-A5",
            "element": eid,
            "check": "upfront_carbon_kgco2e",
            "expected": round(expected_upfront, 6),
            "actual":   round(float(row["upfront_carbon_kgco2e"]), 6),
            "tol_pct":  0.001,
        })

        # ── Uncertainty Bounds ───────────────────────────────────────────────
        ec = float(row["embodied_carbon_kgco2e"])
        cases.append({
            "group": "Uncertainty ±10%",
            "element": eid,
            "check": "embodied_carbon_upper",
            "expected": round(ec * 1.10, 4),
            "actual":   round(float(row["embodied_carbon_upper"]), 4),
            "tol_pct":  0.001,
        })

    # ── Steel EoL Sign (aggregate check) ─────────────────────────────────────
    steel_rows = result_df[result_df["material_id"] == "Steel"]
    if not steel_rows.empty:
        steel_eol = (
            steel_rows["co2_c1"] + steel_rows["co2_c2"]
            + steel_rows["co2_c3"] + steel_rows["co2_c4"]
        ).sum()
        cases.append({
            "group": "C1-C4 Steel Credit Sign",
            "element": "ALL_STEEL",
            "check": "eol_sum < 0",
            "expected": "< 0",
            "actual":   round(float(steel_eol), 4),
            "force_pass": float(steel_eol) < 0,
        })

    # ── Timber Sequestration Sign ─────────────────────────────────────────────
    timber_rows = result_df[result_df["material_id"] == "Timber"]
    if not timber_rows.empty:
        seq = float(timber_rows["co2_seq"].sum())
        cases.append({
            "group": "Sequestration (Biogenic)",
            "element": "ALL_TIMBER",
            "check": "co2_seq < 0",
            "expected": "< 0",
            "actual":   round(seq, 4),
            "force_pass": seq < 0,
        })

    return cases


# ===========================================================================
# Evaluator
# ===========================================================================

def evaluate(cases):
    results = []
    for tc in cases:
        # Forced pass/fail (non-numeric checks)
        if "force_pass" in tc:
            passed = tc["force_pass"]
        else:
            exp = tc["expected"]
            act = tc["actual"]
            tol = tc.get("tol_pct", 0.001)
            if exp == 0.0:
                passed = abs(act) < 1e-6
            else:
                passed = abs((act - exp) / exp) <= tol

        results.append({**tc, "PASS": passed})
    return results


# ===========================================================================
# Project-level aggregation checks
# ===========================================================================

def aggregation_checks(result_df: pd.DataFrame):
    total_ec_tco2e = result_df["embodied_carbon_kgco2e"].sum() / 1000.0
    upfront_tco2e  = result_df["upfront_carbon_kgco2e"].sum() / 1000.0
    intensity      = total_ec_tco2e * 1000.0 / SETTINGS.gfa_m2  # kgCO2e/m²

    category_summary = (
        pd.DataFrame(BIM_ELEMENTS)
        .merge(result_df[["element_id", "embodied_carbon_kgco2e"]], on="element_id")
        .groupby("category")["embodied_carbon_kgco2e"]
        .sum()
        .sort_values(ascending=False)
        .to_dict()
    )

    phase_totals = {
        "A1-A3 (kgCO2e)": round(result_df["co2_a1_a3"].sum(), 2),
        "A4    (kgCO2e)": round(result_df["co2_a4"].sum(), 2),
        "A5    (kgCO2e)": round(result_df["co2_a5"].sum(), 2) if "co2_a5" in result_df.columns else 0,
        "B1-B5 (kgCO2e)": round((result_df["co2_b1"] + result_df["co2_b2"] + result_df["co2_b4"]).sum(), 2),
        "C1-C4 (kgCO2e)": round((result_df["co2_c1"] + result_df["co2_c2"] + result_df["co2_c3"] + result_df["co2_c4"]).sum(), 2),
        "D     (kgCO2e)": round(result_df["co2_d"].sum(), 2),
        "Seq   (kgCO2e)": round(result_df["co2_seq"].sum(), 2),
    }

    return {
        "total_embodied_carbon_tCO2e": round(total_ec_tco2e, 3),
        "upfront_carbon_A1_A5_tCO2e":  round(upfront_tco2e, 3),
        "carbon_intensity_kgCO2e_m2":  round(intensity, 2),
        "GIA_m2": SETTINGS.gfa_m2,
        "RSP_years": SETTINGS.reference_study_period,
        "element_count": len(result_df),
        "phase_totals_kgCO2e": phase_totals,
        "by_category_kgCO2e": {k: round(v, 2) for k, v in category_summary.items()},
    }


# ===========================================================================
# Writers
# ===========================================================================

def write_json(report_data: dict, test_results: list):
    path = os.path.join(OUTPUT_DIR, f"wlca_report_{TIMESTAMP}.json")
    payload = {
        "generated_at": TIMESTAMP,
        "project": report_data,
        "test_results": test_results,
        "summary": {
            "total_checks": len(test_results),
            "passed": sum(1 for t in test_results if t["PASS"]),
            "failed": sum(1 for t in test_results if not t["PASS"]),
            "pass_rate_pct": round(100.0 * sum(1 for t in test_results if t["PASS"]) / max(len(test_results), 1), 1),
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def write_markdown(report_data: dict, test_results: list, md_path: str):
    passed = [t for t in test_results if t["PASS"]]
    failed = [t for t in test_results if not t["PASS"]]
    total  = len(test_results)
    rate   = round(100.0 * len(passed) / max(total, 1), 1)

    # group failures
    fail_by_group: dict = {}
    for t in failed:
        fail_by_group.setdefault(t["group"], []).append(t)

    proj = report_data

    lines = [
        "# EcoBIM — WLCA Engine Audit Report",
        f"**Generated:** {TIMESTAMP}  ",
        "**Standard compliance:** EN 15978:2011 / EN 15804:2012+A2 / ISO 21930:2017  ",
        "",
        "---",
        "",
        "## Project Overview",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Elements analysed | {proj['element_count']} |",
        f"| GIA | {proj['GIA_m2']:,.0f} m² |",
        f"| Reference Study Period | {proj['RSP_years']} years |",
        f"| **Total Whole Life Carbon** | **{proj['total_embodied_carbon_tCO2e']:,.3f} tCO₂e** |",
        f"| Upfront Carbon (A1–A5) | {proj['upfront_carbon_A1_A5_tCO2e']:,.3f} tCO₂e |",
        f"| Carbon Intensity | {proj['carbon_intensity_kgCO2e_m2']:,.1f} kgCO₂e/m² |",
        "",
        "### Phase Breakdown",
        "",
        "| Phase | kgCO₂e |",
        "|-------|--------|",
    ]
    for ph, val in proj["phase_totals_kgCO2e"].items():
        lines.append(f"| {ph} | {val:,.2f} |")

    lines += [
        "",
        "### Emissions by Revit Category",
        "",
        "| Category | kgCO₂e | % of Total |",
        "|----------|--------|------------|",
    ]
    total_cat = sum(proj["by_category_kgCO2e"].values())
    for cat, val in proj["by_category_kgCO2e"].items():
        pct = round(100.0 * val / max(total_cat, 1e-9), 1)
        lines.append(f"| {cat} | {val:,.2f} | {pct} % |")

    lines += [
        "",
        "---",
        "",
        "## Test Summary",
        "",
        "| Total Checks | ✅ Passed | ❌ Failed | Pass Rate |",
        "|---|---|---|---|",
        f"| {total} | {len(passed)} | {len(failed)} | **{rate} %** |",
        "",
    ]

    if failed:
        lines += ["## ❌ Failed Checks", ""]
        for grp, items in fail_by_group.items():
            lines.append(f"### {grp}")
            lines.append("| Element | Check | Expected | Actual |")
            lines.append("|---------|-------|----------|--------|")
            for t in items:
                lines.append(f"| {t['element']} | {t['check']} | {t['expected']} | {t['actual']} |")
            lines.append("")

    lines += [
        "## ✅ Passed Checks",
        "",
        "| Element | Group | Check | Expected | Actual |",
        "|---------|-------|-------|----------|--------|",
    ]
    for t in passed:
        lines.append(f"| {t['element']} | {t['group']} | {t['check']} | {t['expected']} | {t['actual']} |")

    lines += [
        "",
        "---",
        "",
        "## Mathematical Notes",
        "",
        "### A4 Transport Emission Factors (DEFRA/BEIS 2023)",
        "| Vehicle | kgCO₂e / (tonne · km) |",
        "|---------|----------------------|",
        "| HGV Rigid 40t | 0.0603 |",
        "| HGV Artic 40t | 0.0490 |",
        "| Rail Freight | 0.0280 |",
        "| Barge | 0.0312 |",
        "",
        "### A5 Waste Calculation",
        "Waste mass = purchased_mass × waste_fraction / (1 − waste_fraction)  ",
        "A5_waste = waste_mass × (GWP_A1A3 + A4_per_kg_of_main_material)",
        "",
        "### B4 Replacement",
        "replacements = floor(RSP / SL) − 1, where SL = material service life  ",
        "B4 = replacements × (A1–A5)",
        "",
        "### Uncertainty",
        "Upper = EC × (1 + σ/100), Lower = EC × (1 − σ/100)  ",
        "Default σ = 10 % (RICS WLCA 2nd edition guidance)",
    ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ===========================================================================
# Main
# ===========================================================================

def main():
    print("=" * 65)
    print("  EcoBIM WLCA Audit — EN 15978 / EN 15804 / ISO 21930")
    print("=" * 65)

    # 1. Run engine
    engine = LCAMathEngine(MATERIAL_DB, settings=SETTINGS)
    df_input = pd.DataFrame(BIM_ELEMENTS)

    try:
        result_df = engine.calculate_embodied_carbon(df_input)
    except Exception as exc:
        print(f"\n❌ ENGINE FAULT — {exc}")
        traceback.print_exc()
        return

    print(f"\n✅ Engine completed — {len(result_df)} elements processed.\n")

    # 2. Aggregation
    agg = aggregation_checks(result_df)
    print(f"  Total Whole Life Carbon : {agg['total_embodied_carbon_tCO2e']:>10.3f} tCO₂e")
    print(f"  Upfront Carbon (A1-A5)  : {agg['upfront_carbon_A1_A5_tCO2e']:>10.3f} tCO₂e")
    print(f"  Carbon Intensity        : {agg['carbon_intensity_kgCO2e_m2']:>10.1f} kgCO₂e/m²")
    print(f"  GIA                     : {agg['GIA_m2']:>10,.0f} m²")

    # 3. Define and evaluate test cases
    cases   = define_tests(result_df)
    results = evaluate(cases)
    passed  = sum(1 for r in results if r["PASS"])
    total   = len(results)
    rate    = round(100 * passed / max(total, 1), 1)

    print(f"\n{'─'*65}")
    print(f"  Test Results: {passed}/{total} passed  ({rate} %)")

    failures = [r for r in results if not r["PASS"]]
    if failures:
        print("\n  ❌ Failures:")
        for f in failures:
            print(f"     [{f['group']}] {f['element']}.{f['check']}: "
                  f"expected={f['expected']}  got={f['actual']}")
    else:
        print("  ✅ All checks passed.")

    # 4. Write outputs
    json_path = write_json(agg, results)
    md_path   = os.path.join(OUTPUT_DIR, f"wlca_report_{TIMESTAMP}.md")
    write_markdown(agg, results, md_path)

    print("\n📄 Reports saved to:")
    print(f"   JSON → {json_path}")
    print(f"   MD   → {md_path}")
    print("=" * 65)

    # 5. Print per-element phase detail
    print("\n  Per-element phase summary (kgCO₂e):\n")
    cols_show = ["element_id", "material_id", "mass_kg",
                 "co2_a1_a3", "co2_a4", "co2_a5_waste",
                 "co2_b2", "co2_c1", "co2_c2", "co2_c3", "co2_c4",
                 "co2_d", "co2_seq", "embodied_carbon_kgco2e"]
    with pd.option_context("display.float_format", "{:,.2f}".format,
                           "display.max_columns", None,
                           "display.width", 220):
        print(result_df[cols_show].to_string(index=False))


if __name__ == "__main__":
    main()
