from __future__ import annotations
import hashlib
import math
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sklearn.ensemble import RandomForestRegressor

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from rtl_analysis import FEATURE_LABELS, extract_features, strip_comments
from synthesis_engine import parse_rtl_modules

DATASET = ROOT / "dataset" / "final_merged_dataset.csv"
MODEL_FEATURE_MAP = {
    "modules": "RTL_Modules", "registers": "RTL_Register_Declarations", "wires": "RTL_Wire_Declarations",
    "multipliers": "RTL_Multiplication_Operators", "adders": "RTL_Addition_Operators", "subtractors": "RTL_Subtraction_Operators",
    "always_blocks": "RTL_Always_Blocks", "assign_statements": "RTL_Assign_Statements", "if_statements": "RTL_If_Statements",
    "case_blocks": "RTL_Case_Blocks", "else_statements": "RTL_Else_Statements", "data_width": "RTL_Data_Width",
    "output_width": "RTL_Output_Width", "has_clock": "RTL_Has_Clock", "has_reset": "RTL_Has_Reset", "has_enable": "RTL_Has_Enable",
}

st.set_page_config(page_title="PPA-Insight | Intelligent RTL Analysis", page_icon="🧪", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
:root { color-scheme: light; }
html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
.block-container { max-width: 1500px; padding-top: 1.65rem; padding-bottom: 3rem; }
[data-testid="stSidebar"] { background: #f7f8fa; border-right: 1px solid #e3e7ed; }
[data-testid="stSidebar"] > div { padding-top: 1.4rem; }
h1,h2,h3 { letter-spacing: -0.035em; color: #15243a; }
h1 { font-weight: 800 !important; font-size: 2.15rem !important; }
h2 { font-weight: 750 !important; }
h3 { font-weight: 700 !important; }
.eyebrow { text-transform: uppercase; letter-spacing: .15em; font-size: .72rem; font-weight: 800; color: #65758b; }
.subhead { color: #65758b; font-size: .98rem; line-height: 1.65; max-width: 1000px; }
.brand { font-size: 1.12rem; font-weight: 800; letter-spacing: .06em; color: #14263d; }
.brand-mark { display: inline-block; border-radius: 8px; padding: .45rem .55rem; background: #dff4f4; color: #007d82; margin-right: .55rem; }
div[data-testid="stMetric"] { background: #fff; border: 1px solid #e2e7ed; border-radius: 12px; padding: .95rem 1rem; box-shadow: 0 1px 2px #14263d08; }
[data-testid="stMetricLabel"] { color: #69798c; font-size: .82rem; }
[data-testid="stMetricValue"] { color: #15243a; font-weight: 800; }
[data-testid="stDataFrame"] { border: 1px solid #e2e7ed; border-radius: 10px; overflow: hidden; }
.stTabs [data-baseweb="tab-list"] { gap: .6rem; border-bottom: 1px solid #e2e7ed; }
.stTabs [data-baseweb="tab"] { padding: .7rem .9rem; height: auto; }
.stTabs [aria-selected="true"] { color: #007d82; border-bottom-color: #007d82; }
code, pre { font-family: 'DM Mono', monospace !important; }
footer { visibility: hidden; }
@keyframes ppaFadeUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes ppaSoftPulse { 0%,100% { box-shadow: 0 5px 18px rgba(0,125,130,.05); } 50% { box-shadow: 0 8px 24px rgba(0,125,130,.12); } }
.block-container { animation: ppaFadeUp .55s ease-out both; }
[data-testid="stVerticalBlock"] > div { animation: ppaFadeUp .45s ease-out both; }
.stButton > button, .stDownloadButton > button { transition: transform .18s ease, box-shadow .18s ease; }
.stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,125,130,.14); }
.ppa-team { margin: 1rem 0 1.35rem; padding: 1rem 1.1rem; border: 1px solid #dce6ec; border-radius: 14px; background: linear-gradient(115deg,#f5fafb,#fff 55%,#f5f8fc); animation: ppaFadeUp .7s ease-out both; }
.ppa-team-label { font-size: .68rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; color: #65758b; margin-bottom: .65rem; }
.ppa-team-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.7rem; }
.ppa-member { background:#fff; border:1px solid #e4ebef; border-radius:10px; padding:.72rem .8rem; animation:ppaSoftPulse 5s ease-in-out infinite; }
.ppa-member:nth-child(2){animation-delay:.4s}.ppa-member:nth-child(3){animation-delay:.8s}
.ppa-member strong { display:block; color:#172b43; font-size:.92rem; }
.ppa-member span { color:#718096; font-family:'DM Mono',monospace; font-size:.75rem; }
.ppa-evidence { animation: ppaFadeUp .7s ease-out both; }
@media(max-width:720px){.ppa-team-grid{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}

</style>
""", unsafe_allow_html=True)


def train_experimental_model(path: Path):
    """Fit an explicitly experimental LUT regressor; never describe in-sample fit as validation."""
    if not path.exists(): return None, "Bundled dataset not found."
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig")
        if "LUTs" not in frame.columns: return None, "No LUT target column is present."
        cols = [c for c in MODEL_FEATURE_MAP.values() if c in frame.columns]
        if not cols: return None, "No compatible RTL feature columns are present."
        work = frame[cols + ["LUTs"]].apply(pd.to_numeric, errors="coerce").dropna(subset=["LUTs"])
        work = work[work["LUTs"] >= 0]
        if len(work) < 3: return None, f"Only {len(work)} labelled rows; at least three are needed to fit a demonstration model."
        medians = work[cols].median().fillna(0)
        model = RandomForestRegressor(n_estimators=200, random_state=42, max_depth=4, min_samples_leaf=1)
        model.fit(work[cols].fillna(medians), work["LUTs"])
        return {"model": model, "columns": cols, "medians": medians, "rows": len(work), "frame": frame}, None
    except Exception as exc:
        return None, str(exc)


def predict_luts(features, bundle):
    reverse = {v: k for k, v in MODEL_FEATURE_MAP.items()}
    row = {c: features.get(reverse[c], 0) for c in bundle["columns"]}
    return float(bundle["model"].predict(pd.DataFrame([row]).fillna(bundle["medians"]))[0])


def make_recommendations(f):
    rows = []
    def add(priority, domain, evidence, action):
        rows.append({"Priority": priority, "Review area": domain, "Source evidence": evidence, "Engineering investigation": action})
    if f["multipliers"]:
        add("High", "Arithmetic mapping", f"{f['multipliers']} multiplication operator(s) detected.", "Check operand widths, signedness and DSP inference. Compare target-specific utilization before and after any rewrite.")
    if f["adders"] + f["subtractors"] >= 2:
        add("Medium", "Arithmetic datapath", f"{f['adders']} addition and {f['subtractors']} subtraction operator(s).", "Inspect widths, sharing opportunities and critical paths. Avoid manual sharing unless area/timing results support it.")
    if f["always_blocks"] and f["if_statements"] >= 3:
        add("Medium", "Control logic", f"{f['always_blocks']} procedural block(s), {f['if_statements']} if statement(s).", "Review priority chains and nesting. Check inferred mux depth and timing after synthesis.")
    if f["registers"] or f["has_clock"]:
        add("Medium", "Sequential logic", f"{f['registers']} declared names counted; clock-like identifier: {'yes' if f['has_clock'] else 'no'}.", "Review reset/enable behavior, state width and register inference. Confirm with elaboration and synthesis reports.")
    if f["wires"] > 8:
        add("Low", "Intermediate nets", f"{f['wires']} wire declarations detected.", "Inspect fanout and netlist; source wire count alone does not imply excess area.")
    if not rows:
        add("Low", "Evidence-led review", "No high-confidence source-pattern trigger.", "Use synthesis utilization, timing paths and functional verification to identify any worthwhile change.")
    order = {"High": 0, "Medium": 1, "Low": 2}
    return sorted(rows, key=lambda r: order[r["Priority"]])


def decode_upload(upload):
    return upload.getvalue().decode("utf-8", errors="replace") if upload else ""


def number(v):
    try:
        if pd.isna(v) or str(v).strip() == "": return None
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def read_metrics_csv(upload):
    if not upload: return {}
    try:
        df = pd.read_csv(upload)
        if df.empty: return {}
        return {str(k): number(v) for k, v in df.iloc[0].to_dict().items() if number(v) is not None}
    except Exception:
        return {}


def report_markdown(design, top, source, features, recs, prediction, model_rows):
    lines = [
        "# PPA-Insight: Intelligent Pre-Synthesis PPA Analysis and Optimization Framework",
        "", f"- Design: `{design}`", f"- Top module: `{top or 'not selected'}`",
        f"- Generated: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
        "", "## RTL Feature Profile", "", "| Feature | Count |", "|---|---:|"
    ]
    lines += [f"| {FEATURE_LABELS.get(k,k)} | {v} |" for k, v in features.items()]
    lines += ["", "## Machine Learning PPA Estimate", "",
              f"Estimated LUT resources: {prediction:.2f}" if prediction is not None else "Estimate unavailable.",
              f"Training design samples: {model_rows}",
              "", "## Optimization Insights", ""]
    lines += [f"- **{x['Priority']} — {x['Review area']}:** {x['Source evidence']} {x['Engineering investigation']}" for x in recs]
    lines += ["", "## RTL Source", "", "```systemverilog", source, "```"]
    return "\\n".join(lines)


with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-mark">PPA</span>INSIGHT</div>', unsafe_allow_html=True)
    st.caption("Intelligent RTL analysis and optimization")
    st.divider()
    st.markdown('<div class="eyebrow">Design input</div>', unsafe_allow_html=True)
    rtl_upload = st.file_uploader("Upload RTL source", type=["v", "sv", "vh"])
    pasted = st.text_area("Or paste a module", height=155, placeholder="module counter8 (...);\\n  ...\\nendmodule")
    rtl_text = rtl_upload.getvalue().decode("utf-8", errors="replace") if rtl_upload else pasted
    design_name = Path(rtl_upload.name).stem if rtl_upload else "pasted_design"
    modules = parse_rtl_modules(rtl_text) if rtl_text.strip() else []
    if not rtl_upload and modules:
        design_name = modules[0]
    top = st.selectbox("Top module", modules, index=0, disabled=False) if modules else ""

model_bundle, model_error = train_experimental_model(DATASET)
st.markdown('<div class="eyebrow">INTELLIGENT RTL ANALYSIS PLATFORM</div>', unsafe_allow_html=True)
st.title("PPA-Insight: Intelligent Pre-Synthesis PPA Analysis and Optimization Framework")
st.markdown('<p class="subhead">An intelligent ECE/VLSI framework for Verilog RTL feature extraction, machine-learning-based PPA estimation, design analysis and optimization recommendations.</p>', unsafe_allow_html=True)

st.markdown("""
<div class="ppa-team">
  <div class="ppa-team-label">Project team · Electronics and Communication Engineering</div>
  <div class="ppa-team-grid">
    <div class="ppa-member"><strong>Amulya Reddy</strong><span>23R21A04D9</span></div>
    <div class="ppa-member"><strong>G. Aravind</strong><span>23R21A04E4</span></div>
    <div class="ppa-member"><strong>G. Ajay</strong><span>23R21A04E7</span></div>
  </div>
</div>
""", unsafe_allow_html=True)

st.write("")

try:
    benchmark = pd.read_csv(DATASET, encoding="utf-8-sig") if DATASET.exists() else pd.DataFrame()
except Exception:
    benchmark = pd.DataFrame()

if benchmark.empty:
    labelled_luts = timing_rows = power_rows = 0
else:
    labelled_luts = int(pd.to_numeric(benchmark.get("LUTs", pd.Series(dtype=float)), errors="coerce").notna().sum())
    timing_rows = int(pd.to_numeric(benchmark.get("WNS_ns", pd.Series(dtype=float)), errors="coerce").notna().sum())
    power_rows = int(pd.to_numeric(benchmark.get("Estimated_Total_Power_W", pd.Series(dtype=float)), errors="coerce").notna().sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("Benchmark designs", len(benchmark))
k2.metric("Rows with LUT labels", labelled_luts)
k3.metric("Rows with timing labels", timing_rows)
k4.metric("Rows with power labels", power_rows)
st.caption("Six benchmark designs included in the project dataset")

if not rtl_text.strip():
    st.divider()
    st.subheader("Start a design assessment")
    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("#### Recommended workflow")
        st.markdown("1. Upload a Verilog/SystemVerilog module or paste RTL.\n2. Extract RTL design features automatically.\n3. Generate machine-learning-based PPA estimates.\n4. Review design characteristics and optimization recommendations.\n5. Explore benchmark results and export the analysis report.")
    with right:
        st.markdown("#### Benchmark designs")
        if not benchmark.empty:
            cols = [c for c in ["Design", "Tool", "LUTs", "Registers", "DSPs", "WNS_ns", "Estimated_Total_Power_W"] if c in benchmark.columns]
            st.dataframe(benchmark[cols], use_container_width=True, hide_index=True)
        else:
            st.info("No bundled benchmark data found.")
else:
    clean = strip_comments(rtl_text)
    features = extract_features(rtl_text)
    recs = make_recommendations(features)
    prediction = predict_luts(features, model_bundle) if model_bundle else None

    st.divider()
    st.markdown(f"### Design overview · `{design_name}`")
    st.caption(f"Top module: {top or 'not detected'}  ·  {len(rtl_text):,} source characters  ·  {len(rtl_text.splitlines()):,} lines")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Modules detected", features["modules"])
    c2.metric("Arithmetic operators", features["multipliers"] + features["adders"] + features["subtractors"])
    c3.metric("Procedural blocks", features["always_blocks"])
    c4.metric("Detected data width", f'{features.get("data_width", 0)} bits')

    tabs = st.tabs(["Design Overview", "RTL Structure", "ML PPA Estimate", "Optimization Insights", "Benchmark Results"])
    with tabs[0]:
        st.subheader("RTL design overview")
        col_a, col_b = st.columns([1.15, 1])
        with col_a:
            st.markdown("#### Extracted design characteristics")
            summary = pd.DataFrame([
                {"Parameter": "RTL modules", "Value": features["modules"]},
                {"Parameter": "Arithmetic operators", "Value": features["multipliers"] + features["adders"] + features["subtractors"]},
                {"Parameter": "Procedural blocks", "Value": features["always_blocks"]},
                {"Parameter": "Detected data width", "Value": f'{features.get("data_width", 0)} bits'},
            ])
            st.dataframe(summary, use_container_width=True, hide_index=True)
        with col_b:
            st.markdown("#### RTL feature profile")
            feature_frame = pd.DataFrame([{"Feature": FEATURE_LABELS[k], "Count": v} for k, v in features.items()])
            st.bar_chart(feature_frame.set_index("Feature"), horizontal=True, height=420)

    with tabs[1]:
        left, right = st.columns([1, 1.15])
        with left:
            st.subheader("RTL feature inventory")
            st.dataframe(pd.DataFrame([{"Feature": FEATURE_LABELS[k], "Value": v} for k, v in features.items()]), use_container_width=True, hide_index=True, height=460)
        with right:
            st.subheader("Source snapshot")
            st.code(rtl_text, language="verilog", line_numbers=True)


    with tabs[2]:
        st.subheader("Machine Learning PPA Estimation")
        if model_bundle:
            x, y = st.columns([.8, 1.2])
            with x:
                st.metric("Estimated LUT resources", f"{prediction:.1f} LUTs" if prediction is not None else "Unavailable")
                st.metric("Training design samples", model_bundle["rows"])
            with y:
                importance = pd.DataFrame({"Feature": [next((k for k, v in MODEL_FEATURE_MAP.items() if v == c), c) for c in model_bundle["columns"]], "Random forest importance": model_bundle["model"].feature_importances_}).sort_values("Random forest importance", ascending=False)
                st.bar_chart(importance.head(12).set_index("Feature"), horizontal=True, height=390)
                st.dataframe(importance, use_container_width=True, hide_index=True)
        else:
            st.error(model_error or "No experimental model available.")


    with tabs[3]:
        st.subheader("RTL Optimization Insights")
        st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)

    with tabs[4]:
        st.subheader("Benchmark Results")
        if not benchmark.empty:
            display_cols = [c for c in ["Design", "LUTs", "Registers", "DSPs", "WNS_ns", "TNS_ns", "Estimated_Total_Power_W"] if c in benchmark.columns]
            st.dataframe(benchmark[display_cols], use_container_width=True, hide_index=True)
            plot_df = benchmark.copy()
            for col in ["LUTs", "WNS_ns", "Estimated_Total_Power_W"]:
                if col in plot_df: plot_df[col] = pd.to_numeric(plot_df[col], errors="coerce")
            area_timing = plot_df.dropna(subset=[c for c in ["LUTs", "WNS_ns"] if c in plot_df.columns]) if {"LUTs", "WNS_ns"}.issubset(plot_df.columns) else pd.DataFrame()
            if not area_timing.empty:
                st.markdown("#### Area–timing sample view")
                st.scatter_chart(area_timing, x="LUTs", y="WNS_ns", color="Tool" if "Tool" in area_timing.columns else None, size=None)
                st.caption("Benchmark design-space overview")
        else:
            st.info("Bundled benchmark dataset is unavailable.")
        report = report_markdown(design_name, top, rtl_text, features, recs, prediction, model_bundle["rows"] if model_bundle else 0)
        st.divider()
        st.subheader("Assessment report export")
        st.download_button("Download complete Markdown report", report, file_name=f"{design_name}_ppa_insight_report.md", mime="text/markdown", type="primary")
        st.download_button("Download extracted RTL feature CSV", pd.DataFrame([{"Design": design_name, "Top_Module": top, **features}]).to_csv(index=False), file_name=f"{design_name}_rtl_features.csv", mime="text/csv")
st.divider()
st.markdown('<p class="subhead">PPA-Insight · Intelligent RTL analysis, machine-learning-based PPA estimation and optimization insights.</p>', unsafe_allow_html=True)
