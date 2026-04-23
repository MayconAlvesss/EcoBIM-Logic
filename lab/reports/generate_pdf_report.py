"""
lab/reports/generate_pdf_report.py
====================================
Generates a professional WLCA PDF report from the audit engine output.

Dependencies:
    pip install reportlab matplotlib

Run from project root:
    python lab/reports/generate_pdf_report.py
"""
import sys
import os
import io
import datetime

# Force UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

import pandas as pd

from core.lca_math_engine import LCAMathEngine
from core.project_config import ProjectConfig

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Sample BIM dataset
# ---------------------------------------------------------------------------
BIM_ELEMENTS = [
    {"element_id": "WALL-C01",  "material_id": "Concrete",   "volume_m3": 42.77, "category": "Walls"},
    {"element_id": "FLOOR-C01", "material_id": "Concrete",   "volume_m3": 10.69, "category": "Floors"},
    {"element_id": "FOUND-C01", "material_id": "Concrete",   "volume_m3": 22.51, "category": "Structural Foundations"},
    {"element_id": "COL-S01",   "material_id": "Steel",      "volume_m3":  0.22, "category": "Structural Columns"},
    {"element_id": "BEAM-S01",  "material_id": "Steel",      "volume_m3":  1.60, "category": "Structural Framing"},
    {"element_id": "RBAR-S01",  "material_id": "Steel",      "volume_m3":  0.85, "category": "Structural Framing"},
    {"element_id": "ROOF-T01",  "material_id": "Timber",     "volume_m3":  3.20, "category": "Roofs"},
    {"element_id": "INSUL-01",  "material_id": "Insulation", "volume_m3":  5.50, "category": "Walls"},
    {"element_id": "GLAZ-01",   "material_id": "Glass",      "volume_m3":  1.80, "category": "Walls"},
]

MATERIAL_DB = pd.DataFrame({
    "material_id":             ["Concrete", "Steel",  "Timber", "Insulation", "Glass"],
    "density_kg_m3":           [2400.0,     7850.0,   500.0,    35.0,         2500.0],
    "gwp_factor_kgco2_per_kg": [0.103,      1.55,     0.263,    1.86,         1.35],
})


def run_engine() -> tuple[pd.DataFrame, ProjectConfig]:
    config = ProjectConfig.default_template()
    engine = LCAMathEngine(MATERIAL_DB, config=config)
    df     = engine.calculate_embodied_carbon(pd.DataFrame(BIM_ELEMENTS))
    return df, config


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    buf.seek(0)
    return buf.read()


def make_donut_chart(labels, values, colors, title) -> bytes:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    # Filter out zero / negative for pie
    pairs = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not pairs:
        pairs = [("No Data", 1, "#555")]
    labs, vals, cols = zip(*pairs)

    fig, ax = plt.subplots(figsize=(4.5, 3.5), facecolor='#1a1a2e')
    wedges, texts, autotexts = ax.pie(
        vals, labels=None, colors=cols,
        autopct='%1.1f%%', startangle=90,
        pctdistance=0.75, wedgeprops=dict(width=0.55, edgecolor='#1a1a2e')
    )
    for t in autotexts:
        t.set_color('white')
        t.set_fontsize(7)
    ax.legend(wedges, labs, loc='lower center', bbox_to_anchor=(0.5, -0.18),
              ncol=3, fontsize=7, frameon=False, labelcolor='white')
    ax.set_title(title, color='white', fontsize=9, pad=4)
    plt.tight_layout()
    data = _fig_to_bytes(fig)
    plt.close(fig)
    return data


def make_phase_bar_chart(phase_names, phase_values) -> bytes:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    colors = []
    for v in phase_values:
        colors.append('#E84040' if v > 0 else '#4CAF50')

    fig, ax = plt.subplots(figsize=(6.5, 3.0), facecolor='#1a1a2e')
    ax.set_facecolor('#16213e')
    bars = ax.bar(phase_names, phase_values, color=colors, edgecolor='none', width=0.55)
    ax.axhline(0, color='#888', linewidth=0.6)
    for bar, val in zip(bars, phase_values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                val + (max(phase_values) * 0.02 if val >= 0 else min(phase_values) * 0.05),
                f'{val:,.0f}', ha='center', va='bottom', fontsize=7, color='white')
    ax.set_ylabel('kgCO\u2082e', color='#aaa', fontsize=8)
    ax.tick_params(colors='#aaa', labelsize=8)
    ax.spines[:].set_color('#334')
    ax.set_title('Embodied Carbon by Lifecycle Phase', color='white', fontsize=9, pad=6)
    plt.tight_layout()
    data = _fig_to_bytes(fig)
    plt.close(fig)
    return data


def make_rating_bar(current_score, scores_dict) -> bytes:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    grades   = ["A++", "A+", "A", "B", "C", "D", "E", "F", "G"]
    grade_colors = ['#00820F', '#1DA41E', '#56B430', '#ADC62B',
                    '#F7E916', '#F5B500', '#F47920', '#E83D06', '#C8000B']
    thresholds = [scores_dict.get(g, 0) for g in grades]

    fig, ax = plt.subplots(figsize=(4.5, 3.0), facecolor='#1a1a2e')
    ax.set_facecolor('#1a1a2e')
    y = list(range(len(grades)))
    for i, (grade, col, thr) in enumerate(zip(grades, grade_colors, thresholds)):
        width = max(thr, 30)
        ax.barh(i, width, color=col, height=0.7, edgecolor='none')
        ax.text(-5, i, grade, ha='right', va='center', color='white', fontsize=9, fontweight='bold')
        ax.text(width + 5, i, f'{thr}', ha='left', va='center', color='#aaa', fontsize=7)

    # Plot current score marker
    ax.axvline(current_score, color='white', linewidth=2, linestyle='--')
    ax.text(current_score, len(grades) - 0.3,
            f'  {current_score:.0f}\nkgCO\u2082e/m\u00b2', color='white', fontsize=8, fontweight='bold')

    ax.set_yticks([])
    ax.set_xlabel('A1-A5 carbon intensity (kgCO\u2082e/m\u00b2)', color='#aaa', fontsize=8)
    ax.tick_params(axis='x', colors='#aaa', labelsize=7)
    ax.spines[:].set_color('#334')
    ax.set_title('Target Alignment (IStructE)', color='white', fontsize=9, pad=4)
    plt.tight_layout()
    data = _fig_to_bytes(fig)
    plt.close(fig)
    return data


# ---------------------------------------------------------------------------
# PDF builder
# ---------------------------------------------------------------------------

def generate_pdf(result_df: pd.DataFrame, config: ProjectConfig, output_path: str):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm, cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, Image, PageBreak, KeepTogether
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    except ImportError:
        print("\n[ERROR] reportlab not installed. Run: pip install reportlab matplotlib")
        return None

    # ── Colours ──────────────────────────────────────────────────────────────
    C_BG      = colors.HexColor('#1A1A2E')
    C_PANEL   = colors.HexColor('#16213E')
    C_ACCENT  = colors.HexColor('#00D4FF')
    C_WHITE   = colors.white
    C_GREY    = colors.HexColor('#A0AEC0')
    C_GREEN   = colors.HexColor('#2ECC71')
    C_ORANGE  = colors.HexColor('#F39C12')
    C_RED     = colors.HexColor('#E74C3C')

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )

    def _on_page(canvas, doc):
        """Dark background + footer on every page."""
        canvas.saveState()
        canvas.setFillColor(C_BG)
        canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
        # Footer
        canvas.setFillColor(C_GREY)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(15*mm, 8*mm, "EcoBIM WLCA Report  |  EN 15978 / EN 15804 / ISO 21930")
        canvas.drawRightString(A4[0]-15*mm, 8*mm, f"Page {doc.page}")
        canvas.restoreState()

    # ── Styles ───────────────────────────────────────────────────────────────
    S = getSampleStyleSheet()

    def ps(name, **kw) -> ParagraphStyle:
        base = kw.pop('parent', 'Normal')
        style = ParagraphStyle(name, parent=S[base], **kw)
        return style

    sTitle   = ps('sTitle',   fontSize=22, textColor=C_ACCENT,  alignment=TA_LEFT,  fontName='Helvetica-Bold', spaceAfter=2)
    sSub     = ps('sSub',     fontSize=11, textColor=C_GREY,    alignment=TA_LEFT,  fontName='Helvetica', spaceAfter=8)
    sH1      = ps('sH1',      fontSize=13, textColor=C_ACCENT,  alignment=TA_LEFT,  fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=4)
    sH2      = ps('sH2',      fontSize=10, textColor=C_WHITE,   alignment=TA_LEFT,  fontName='Helvetica-Bold', spaceBefore=6, spaceAfter=3)
    sBody    = ps('sBody',    fontSize=8,  textColor=C_GREY,    alignment=TA_LEFT,  fontName='Helvetica',  leading=12)
    sBodyW   = ps('sBodyW',   fontSize=8,  textColor=C_WHITE,   alignment=TA_LEFT,  fontName='Helvetica',  leading=12)
    sNote    = ps('sNote',    fontSize=7,  textColor=C_GREY,    alignment=TA_LEFT,  fontName='Helvetica-Oblique', leading=10)
    sBig     = ps('sBig',     fontSize=28, textColor=C_ACCENT,  alignment=TA_CENTER,fontName='Helvetica-Bold')
    sBigLbl  = ps('sBigLbl',  fontSize=8,  textColor=C_GREY,    alignment=TA_CENTER,fontName='Helvetica')
    sWarning = ps('sWarning', fontSize=8,  textColor=C_ORANGE,  alignment=TA_LEFT,  fontName='Helvetica-Oblique')

    def two_col_table(rows, col_widths=None):
        tbl = Table(rows, colWidths=col_widths or [90*mm, 80*mm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), C_PANEL),
            ('TEXTCOLOR',  (0,0), (-1,-1), C_GREY),
            ('FONTNAME',   (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE',   (0,0), (-1,-1), 8),
            ('GRID',       (0,0), (-1,-1), 0.3, colors.HexColor('#334455')),
            ('ROWBACKGROUNDS', (0,0), (-1,-1), [C_BG, C_PANEL]),
            ('LEFTPADDING',  (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING',   (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ]))
        return tbl

    story = []

    # ===========================================================================
    # Page 1 — Cover & Project Identity
    # ===========================================================================
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("EcoBIM", sTitle))
    story.append(Paragraph("Whole Life Carbon Assessment Report", sSub))
    story.append(HRFlowable(width='100%', thickness=1, color=C_ACCENT, spaceAfter=8))

    meta_rows = [
        [Paragraph('<b>Project Number</b>', sBodyW), Paragraph(config.project_number or '—', sBodyW)],
        [Paragraph('<b>Project Name</b>',   sBodyW), Paragraph(config.project_name, sBodyW)],
        [Paragraph('<b>Location</b>',       sBodyW), Paragraph(config.location or '—', sBodyW)],
        [Paragraph('<b>Assessor</b>',       sBodyW), Paragraph(config.assessor_name or '—', sBodyW)],
        [Paragraph('<b>Date</b>',           sBodyW), Paragraph(config.assessment_date or datetime.date.today().isoformat(), sBodyW)],
        [Paragraph('<b>Standard</b>',       sBodyW), Paragraph('EN 15978:2011 / EN 15804+A2 / ISO 21930', sBodyW)],
        [Paragraph('<b>RSP</b>',            sBodyW), Paragraph(f'{config.reference_study_period} years', sBodyW)],
        [Paragraph('<b>GIA</b>',            sBodyW), Paragraph(f'{config.gross_internal_area_m2:,.0f} m\u00b2', sBodyW)],
        [Paragraph('<b>Building Type</b>',  sBodyW), Paragraph(config.building_type_key, sBodyW)],
    ]
    story.append(two_col_table(meta_rows))
    story.append(Spacer(1, 6*mm))

    # ── Compliance flags ──────────────────────────────────────────────────────
    gaps = config.list_undeclared_assumptions()
    if gaps:
        story.append(Paragraph('<b>Compliance Notices — Undeclared Assumptions</b>', sH2))
        for g in gaps[:8]:
            story.append(Paragraph(f'  \u2022 {g}', sWarning))
        story.append(Spacer(1, 3*mm))

    story.append(PageBreak())

    # ===========================================================================
    # Page 2 — Summary KPIs + Phase Chart
    # ===========================================================================
    story.append(Paragraph('Carbon Summary', sH1))
    story.append(HRFlowable(width='100%', thickness=0.5, color=C_ACCENT, spaceAfter=6))

    # KPI cards via a table
    total_wlc     = result_df['embodied_carbon_kgco2e'].sum() / 1000.0
    upfront       = result_df['upfront_carbon_kgco2e'].sum() / 1000.0
    gia           = config.gross_internal_area_m2
    intensity     = (upfront * 1000 / gia) if gia > 0 else 0.0
    equiv_trees   = int((total_wlc * 1000) / 0.025)
    equiv_flights = int((total_wlc * 1000) / 900)

    kpi_rows = [
        [Paragraph('<b>TOTAL WHOLE LIFE CARBON</b>', sBigLbl), Paragraph(f'{total_wlc:,.2f} tCO\u2082e', sBig),
         Paragraph('<b>UPFRONT CARBON (A1-A5)</b>', sBigLbl),  Paragraph(f'{upfront:,.2f} tCO\u2082e', sBig)],
        [Paragraph('Intensity (kgCO\u2082e/m\u00b2)', sBigLbl), Paragraph(f'{intensity:,.1f}', sBig),
         Paragraph('Equiv. flights LHR\u2192JFK', sBigLbl),    Paragraph(f'{equiv_flights:,}', sBig)],
    ]
    kpi_tbl = Table(kpi_rows, colWidths=[45*mm, 45*mm, 45*mm, 45*mm])
    kpi_tbl.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), C_PANEL),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('GRID',        (0,0), (-1,-1), 0.3, colors.HexColor('#334455')),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [C_PANEL, C_BG]),
        ('TOPPADDING',   (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0), (-1,-1), 6),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Phase bar chart ───────────────────────────────────────────────────────
    phases = {
        'A1-A3': result_df['co2_a1_a3'].sum(),
        'A4':    result_df['co2_a4'].sum(),
        'A5':    result_df['co2_a5'].sum() if 'co2_a5' in result_df.columns else 0,
        'B':     (result_df['co2_b1'] + result_df['co2_b2'] + result_df['co2_b4']).sum(),
        'C1-C4': (result_df['co2_c1'] + result_df['co2_c2'] + result_df['co2_c3'] + result_df['co2_c4']).sum(),
        'D':     result_df['co2_d'].sum(),
        'Seq':   result_df['co2_seq'].sum(),
    }
    phase_img = make_phase_bar_chart(list(phases.keys()), [v for v in phases.values()])
    story.append(Image(io.BytesIO(phase_img), width=160*mm, height=75*mm))
    story.append(Spacer(1, 3*mm))

    # ── Phase table ───────────────────────────────────────────────────────────
    phase_rows = [[Paragraph('<b>Module</b>', sBodyW), Paragraph('<b>Description</b>', sBodyW),
                   Paragraph('<b>kgCO\u2082e</b>', sBodyW), Paragraph('<b>tCO\u2082e</b>', sBodyW)]]
    PHASE_DESC = {
        'A1-A3': 'Raw materials, manufacturing', 'A4': 'Transport to site',
        'A5':    'Construction / site waste',    'B':  'Use stage (maint. + replacement)',
        'C1-C4': 'End of life',                  'D':  'Recycling credit (informational)',
        'Seq':   'Biogenic sequestration (info)',
    }
    for ph, val in phases.items():
        phase_rows.append([
            Paragraph(ph, sBodyW), Paragraph(PHASE_DESC.get(ph,''), sBody),
            Paragraph(f'{val:,.2f}', sBodyW), Paragraph(f'{val/1000:,.3f}', sBodyW),
        ])
    p_tbl = Table(phase_rows, colWidths=[20*mm, 85*mm, 30*mm, 30*mm])
    p_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), C_ACCENT),
        ('TEXTCOLOR',     (0,0), (-1,0), C_BG),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_BG, C_PANEL]),
        ('TEXTCOLOR',     (0,1), (-1,-1), C_GREY),
        ('FONTNAME',      (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#334455')),
        ('LEFTPADDING',   (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING',    (0,0), (-1,-1), 3), ('BOTTOMPADDING',(0,0), (-1,-1), 3),
    ]))
    story.append(p_tbl)
    story.append(PageBreak())

    # ===========================================================================
    # Page 3 — Charts: By Category + Target Alignment
    # ===========================================================================
    story.append(Paragraph('Category Analysis & Target Alignment', sH1))
    story.append(HRFlowable(width='100%', thickness=0.5, color=C_ACCENT, spaceAfter=6))

    # Pie by category
    df_bim = pd.DataFrame(BIM_ELEMENTS)
    cat_sum = (
        df_bim.merge(result_df[['element_id', 'embodied_carbon_kgco2e']], on='element_id')
        .groupby('category')['embodied_carbon_kgco2e'].sum()
        .sort_values(ascending=False)
    )
    PIE_COLORS = ['#9F7A7A','#6AA8A4','#D1D343','#5F9EA0','#90EE90','#ADD8E6','#FFA07A']
    cat_img = make_donut_chart(
        list(cat_sum.index), list(cat_sum.values),
        PIE_COLORS[:len(cat_sum)], 'Whole Life Carbon by Category'
    )

    # Target alignment chart
    _, scores = config.get_target_score()
    rating_img = make_rating_bar(intensity, scores)

    chart_tbl = Table(
        [[Image(io.BytesIO(cat_img), width=85*mm, height=68*mm),
          Image(io.BytesIO(rating_img), width=85*mm, height=68*mm)]],
        colWidths=[90*mm, 90*mm]
    )
    story.append(chart_tbl)
    story.append(Spacer(1, 4*mm))

    # Category table
    story.append(Paragraph('Emissions by Revit Category', sH2))
    cat_rows = [[Paragraph(h, sBodyW) for h in ['Category', 'kgCO2e', 'tCO2e', '% of Total']]]
    total_cat = cat_sum.sum()
    for cat, val in cat_sum.items():
        cat_rows.append([
            Paragraph(cat, sBody), Paragraph(f'{val:,.2f}', sBodyW),
            Paragraph(f'{val/1000:,.3f}', sBodyW), Paragraph(f'{100*val/total_cat:.1f}%', sBodyW),
        ])
    c_tbl = Table(cat_rows, colWidths=[70*mm, 35*mm, 30*mm, 30*mm])
    c_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), C_ACCENT), ('TEXTCOLOR', (0,0), (-1,0), C_BG),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_BG, C_PANEL]),
        ('TEXTCOLOR',     (0,1), (-1,-1), C_GREY),
        ('FONTNAME',      (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#334455')),
        ('LEFTPADDING',   (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING',    (0,0), (-1,-1), 3), ('BOTTOMPADDING',(0,0), (-1,-1), 3),
    ]))
    story.append(c_tbl)
    story.append(PageBreak())

    # ===========================================================================
    # Page 4 — Element-Level Table
    # ===========================================================================
    story.append(Paragraph('Element Calculation Detail', sH1))
    story.append(HRFlowable(width='100%', thickness=0.5, color=C_ACCENT, spaceAfter=6))
    story.append(Paragraph(
        'All values in kgCO\u2082e. Upfront = A1-A5. Whole Life = A1-C4. '
        'Recycling credit (D) and sequestration are informational and excluded from totals.',
        sNote))
    story.append(Spacer(1, 3*mm))

    headers = ['Element', 'Material', 'Vol\n(m\u00b3)', 'Mass\n(kg)', 'A1-A3', 'A4', 'A5',
               'B', 'C1-C4', 'D', 'Seq', 'WHOLE\nLIFE']
    elem_rows = [[Paragraph(h, sBodyW) for h in headers]]

    # Drop columns that already exist in df_bim to avoid merge ambiguity (_x/_y suffixes)
    bim_cols_to_drop = [c for c in ['material_id', 'volume_m3', 'category'] if c in result_df.columns]
    df_merged = pd.DataFrame(BIM_ELEMENTS).merge(
        result_df.drop(columns=bim_cols_to_drop, errors='ignore'),
        on='element_id'
    )
    for _, row in df_merged.iterrows():
        b = (row.get('co2_b1',0) + row.get('co2_b2',0) + row.get('co2_b4',0))
        c = (row.get('co2_c1',0) + row.get('co2_c2',0) + row.get('co2_c3',0) + row.get('co2_c4',0))
        wlc = row.get('embodied_carbon_kgco2e', 0)
        color = C_RED if wlc > 10000 else (C_ORANGE if wlc > 3000 else C_GREY)
        ps_cell = ParagraphStyle('cell', fontSize=7, textColor=color, fontName='Helvetica')
        elem_rows.append([
            Paragraph(str(row['element_id']), sNote),
            Paragraph(str(row['material_id']), sNote),
            Paragraph(f"{row['volume_m3']:.2f}", sNote),
            Paragraph(f"{row.get('mass_kg',0):,.0f}", sNote),
            Paragraph(f"{row.get('co2_a1_a3',0):,.0f}", ps_cell),
            Paragraph(f"{row.get('co2_a4',0):,.1f}", sNote),
            Paragraph(f"{row.get('co2_a5',0):,.1f}", sNote),
            Paragraph(f"{b:,.1f}", sNote),
            Paragraph(f"{c:,.1f}", sNote),
            Paragraph(f"{row.get('co2_d',0):,.1f}", sNote),
            Paragraph(f"{row.get('co2_seq',0):,.1f}", sNote),
            Paragraph(f"{wlc:,.0f}", ps_cell),
        ])

    e_tbl = Table(elem_rows, colWidths=[22*mm,18*mm,12*mm,16*mm,16*mm,12*mm,12*mm,12*mm,12*mm,12*mm,12*mm,17*mm])
    e_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), C_ACCENT), ('TEXTCOLOR', (0,0), (-1,0), C_BG),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_BG, C_PANEL]),
        ('FONTNAME',      (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 7),
        ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#334455')),
        ('TOPPADDING',    (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING',   (0,0), (-1,-1), 3), ('RIGHTPADDING',  (0,0), (-1,-1), 3),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(e_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Totals row ─────────────────────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5, color=C_ACCENT, spaceAfter=3))
    tot_rows = [
        [Paragraph('TOTAL A1-A3 (kgCO2e)', sBodyW), Paragraph(f"{result_df['co2_a1_a3'].sum():,.2f}", sBodyW)],
        [Paragraph('TOTAL UPFRONT A1-A5 (kgCO2e)', sBodyW), Paragraph(f"{result_df['upfront_carbon_kgco2e'].sum():,.2f}", sBodyW)],
        [Paragraph('TOTAL WHOLE LIFE A1-C4 (kgCO2e)', sBodyW), Paragraph(f"{result_df['embodied_carbon_kgco2e'].sum():,.2f}", sBodyW)],
        [Paragraph(f'Uncertainty Upper (+{config.uncertainty_factor_pct:.0f}%)', sBodyW), Paragraph(f"{result_df['embodied_carbon_upper'].sum():,.2f}", sBodyW)],
        [Paragraph(f'Uncertainty Lower (-{config.uncertainty_factor_pct:.0f}%)', sBodyW), Paragraph(f"{result_df['embodied_carbon_lower'].sum():,.2f}", sBodyW)],
    ]
    story.append(two_col_table(tot_rows, col_widths=[100*mm, 70*mm]))
    story.append(PageBreak())

    # ===========================================================================
    # Page 5 — Transport Declarations
    # ===========================================================================
    story.append(Paragraph('Transport Declarations (Module A4)', sH1))
    story.append(HRFlowable(width='100%', thickness=0.5, color=C_ACCENT, spaceAfter=4))
    story.append(Paragraph(
        'The following transport scenarios were declared by the assessor and used in calculation. '
        'Entries marked [DEFAULT] were not declared and used national benchmark assumptions (non-compliant for formal submissions).',
        sNote))
    story.append(Spacer(1, 3*mm))

    t_headers = ['Material', 'Supplier', 'Distance (km)', 'Vehicle', 'Origin', 'Source']
    t_rows = [[Paragraph(h, sBodyW) for h in t_headers]]
    all_classes = ['concrete','steel','timber','aluminium','masonry','glass','insulation']
    for cls in all_classes:
        dist, ef, label = config.get_transport_ef(cls)
        is_default = '[DEFAULT]' in label
        row_color = sWarning if is_default else sBody
        if cls in config.transport:
            cfg = config.transport[cls]
            t_rows.append([
                Paragraph(cls, sBodyW),
                Paragraph(cfg.supplier_name or '—', row_color),
                Paragraph(f'{cfg.distance_km:.0f}', sBodyW),
                Paragraph(label.replace(' [DEFAULT]',''), row_color),
                Paragraph(cfg.country_of_origin or '—', sBody),
                Paragraph('Declared', sBodyW),
            ])
        else:
            t_rows.append([
                Paragraph(cls, sBodyW), Paragraph('—', sWarning),
                Paragraph(f'{dist:.0f}', sWarning), Paragraph(label, sWarning),
                Paragraph('—', sWarning), Paragraph('DEFAULT', sWarning),
            ])
    t_tbl = Table(t_rows, colWidths=[22*mm, 40*mm, 25*mm, 55*mm, 18*mm, 17*mm])
    t_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), C_ACCENT), ('TEXTCOLOR', (0,0), (-1,0), C_BG),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_BG, C_PANEL]),
        ('FONTNAME',      (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#334455')),
        ('TOPPADDING',    (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING',   (0,0), (-1,-1), 4), ('RIGHTPADDING',  (0,0), (-1,-1), 4),
    ]))
    story.append(t_tbl)
    story.append(Spacer(1, 6*mm))

    # ── Waste declarations ────────────────────────────────────────────────────
    story.append(Paragraph('Site Waste Declarations (Module A5)', sH2))
    w_headers = ['Material', 'Waste Fraction', 'Source']
    w_rows = [[Paragraph(h, sBodyW) for h in w_headers]]
    for cls in all_classes:
        wf, src = config.get_waste_fraction(cls)
        is_def = 'WRAP BRE 2014' in src
        w_rows.append([
            Paragraph(cls, sBodyW),
            Paragraph(f'{wf*100:.1f}%', sWarning if is_def else sBodyW),
            Paragraph(src, sWarning if is_def else sBody),
        ])
    w_tbl = Table(w_rows, colWidths=[35*mm, 35*mm, 107*mm])
    w_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), C_ACCENT), ('TEXTCOLOR', (0,0), (-1,0), C_BG),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_BG, C_PANEL]),
        ('FONTNAME',      (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#334455')),
        ('TOPPADDING',    (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING',   (0,0), (-1,-1), 4), ('RIGHTPADDING',  (0,0), (-1,-1), 4),
    ]))
    story.append(w_tbl)
    story.append(PageBreak())

    # ===========================================================================
    # Page 6 — Compliance Statement & Math Notes
    # ===========================================================================
    story.append(Paragraph('Compliance Statement & Methodology', sH1))
    story.append(HRFlowable(width='100%', thickness=0.5, color=C_ACCENT, spaceAfter=6))

    compliance_text = (
        f'This report was produced by EcoBIM in accordance with EN 15978:2011, '
        f'EN 15804:2012+A2:2019, and ISO 21930:2017. The declared system boundary '
        f'covers modules A1\u2013A3 (Product), A4 (Transport), A5 (Construction), '
        f'B1\u2013B5 (Use), and C1\u2013C4 (End of Life). Module D (recycling credit) '
        f'is reported as informational and excluded from the Whole Life Carbon total.\n\n'
        f'The Reference Study Period (RSP) is {config.reference_study_period} years. '
        f'Uncertainty is reported at \u00b1{config.uncertainty_factor_pct:.0f}% '
        f'(RICS WLCA 2nd Edition, 2023). GWP100 characterisation factors from IPCC AR6 '
        f'are used throughout.'
    )
    for para in compliance_text.split('\n\n'):
        story.append(Paragraph(para, sBody))
        story.append(Spacer(1, 3*mm))

    story.append(Paragraph('Mathematical Methodology', sH2))
    math_rows = [
        ['Module', 'Formula'],
        ['A1-A3', 'mass (kg) \u00d7 GWP_A1A3 (kgCO2e/kg)'],
        ['A4',    'mass (kg) \u00d7 distance (km) \u00d7 EF_vehicle (kgCO2e/kg\u00b7km)'],
        ['A5_waste', 'waste_mass = mass \u00d7 wf/(1\u2212wf); A5w = waste_mass \u00d7 (GWP_A1A3 + A4/kg)'],
        ['A5_mach',  'A1\u2013A3 \u00d7 site_machinery_factor (1.5%)'],
        ['B1',    '\u22121.5% \u00d7 A1-A3 (concrete carbonation CO2 uptake, EN 16757)'],
        ['B2',    'mass \u00d7 maintenance_factor (kgCO2e/kg\u00b7yr) \u00d7 RSP'],
        ['B4',    '(floor(RSP/SL)\u22121) \u00d7 A1\u2013A5 where SL = service life'],
        ['C1',    'mass \u00d7 demolition_EF (kgCO2e/kg) \u2014 ICE v3 benchmarks'],
        ['C2',    'mass \u00d7 30 km \u00d7 EF_HGV_rigid'],
        ['C3+C4', 'mass \u00d7 EoL_factor(material); negative = recycling credit'],
        ['D',     'mass \u00d7 D_factor (informational, EN 15978 \u00a76.4.4.1)'],
        ['UC',    'embodied_carbon \u00d7 (1 \u00b1 uncertainty_pct/100)'],
    ]
    m_tbl = Table(math_rows, colWidths=[28*mm, 142*mm])
    m_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), C_ACCENT), ('TEXTCOLOR', (0,0), (-1,0), C_BG),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_BG, C_PANEL]),
        ('TEXTCOLOR',     (0,1), (-1,-1), C_GREY),
        ('FONTNAME',      (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#334455')),
        ('TOPPADDING',    (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING',   (0,0), (-1,-1), 5), ('RIGHTPADDING',  (0,0), (-1,-1), 5),
    ]))
    story.append(m_tbl)
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph('References', sH2))
    refs = [
        'EN 15978:2011 — Sustainability of construction works — Assessment of environmental performance of buildings',
        'EN 15804:2012+A2:2019 — Core PCR for construction products',
        'ISO 21930:2017 — Sustainability in building and civil engineering works',
        'ICE Database v3.0, University of Bath (2019) — Inventory of Carbon & Energy',
        'DEFRA/BEIS UK GHG Conversion Factors 2023, Table 10 (transport)',
        'RICS Professional Standard: Whole Life Carbon Assessment, 2nd Edition (2023)',
        'EN 16757:2017 — Concrete and concrete elements (carbonation B1)',
        'EN 16485:2014 — Round and sawn timber (biogenic carbon, sequestration)',
        'WRAP/BRE Site Waste Management Plans: Benchmark Waste Fractions (2014)',
    ]
    for r in refs:
        story.append(Paragraph(f'  \u2022 {r}', sNote))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return output_path


def main():
    print("Running WLCA engine...")
    result_df, config = run_engine()
    print(f"Processed {len(result_df)} elements.")

    ts   = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    path = os.path.join(OUTPUT_DIR, f'WLCA_Report_{ts}.pdf')

    print("Generating PDF report...")
    out = generate_pdf(result_df, config, path)

    if out:
        print(f"\nPDF saved: {out}")
    else:
        print("PDF generation failed. See error above.")


if __name__ == '__main__':
    main()
