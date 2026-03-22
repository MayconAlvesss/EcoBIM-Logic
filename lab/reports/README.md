# EcoBIM — Lab Reports

This directory contains the standalone audit runner and reference outputs for the WLCA Engine.

## Files

| File | Purpose |
|------|---------|
| `run_wlca_report.py` | Main audit runner — execute to generate reports |
| `outputs/wlca_report_<TIMESTAMP>.json` | Machine-readable structured results |
| `outputs/wlca_report_<TIMESTAMP>.md` | Human-readable audit report |

## How to Run

```bash
# From project root:
python lab/reports/run_wlca_report.py
```

## Standards References

| Standard | Scope |
|----------|-------|
| **EN 15978:2011** | WLCA system boundary (A-D modules) |
| **EN 15804:2012+A2:2019** | Core PCR — product stage & transport |
| **ISO 21930:2017** | Sustainability in building construction |
| **RICS WLCA 2nd Ed. (2023)** | Uncertainty factor (±10%), project settings |
| **ICE Database v3.0** | GWP A1-A3 reference values |
| **DEFRA/BEIS 2023** | Transport emission factors by vehicle type |
