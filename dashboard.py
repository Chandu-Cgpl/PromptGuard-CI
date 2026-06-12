import streamlit as st
import pandas as pd
import sqlite3
import os
import json
import altair as alt
from datetime import datetime

from src.database import DB_PATH, get_run_history, get_results_for_run, set_baseline_run, get_baseline_run
from src.drift import check_performance_drift

st.set_page_config(
    page_title="LLM Regression Diagnostics Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom styles for a premium design
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    .metric-card {
        background-color: #1e293b;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #334155;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🎯 Model Regression Detection System")
st.markdown("Monitor LLM prompt configurations, evaluate model performance, detect regressions, and analyze quality drift.")

# Check if SQLite DB exists and has data
if not os.path.exists(DB_PATH):
    st.warning("⚠️ No database found. Please run the evaluation pipeline first to log history.")
    st.info("Run `python -m src.run --prompt prompts/v1.yaml --baseline` to seed the first run.")
    st.stop()

# Load history
conn = sqlite3.connect(DB_PATH)
df_runs = pd.read_sql_query("SELECT * FROM eval_runs ORDER BY timestamp DESC", conn)
conn.close()

if df_runs.empty:
    st.warning("⚠️ Database is empty. No runs logged yet.")
    st.stop()

# Sidebar Setup
st.sidebar.header("📊 History & Config")
run_options = [f"{row['id']} - v{row['prompt_version']} ({row['timestamp'][:16]})" for idx, row in df_runs.iterrows()]
selected_run_str = st.sidebar.selectbox("Select Evaluation Run", run_options)
selected_run_id = selected_run_str.split(" - ")[0]
selected_run = df_runs[df_runs["id"] == selected_run_id].iloc[0]

# Load active baseline
baseline = get_baseline_run()

# Set current run as baseline action
if st.sidebar.button("⭐ Mark Selected Run as Baseline"):
    set_baseline_run(selected_run_id)
    st.sidebar.success(f"Run {selected_run_id} is now the active baseline!")
    st.rerun()

# ----------------- MAIN LAYOUT -----------------
col1, col2, col3, col4 = st.columns(4)

# KPI Metric 1: Accuracy
with col1:
    acc_val = f"{selected_run['pass_rate']:.1f}%"
    acc_delta = None
    if baseline is not None:
        delta = selected_run['pass_rate'] - baseline.pass_rate
        acc_delta = f"{delta:+.1f}% vs baseline" if selected_run_id != baseline.id else "Active Baseline"
    st.metric(label="Category Accuracy", value=acc_val, delta=acc_delta)

# KPI Metric 2: Relevance
with col2:
    rel_val = f"{selected_run['avg_relevance']:.2f}/5"
    rel_delta = None
    if baseline is not None:
        delta = selected_run['avg_relevance'] - baseline.avg_relevance
        rel_delta = f"{delta:+.2f} vs baseline" if selected_run_id != baseline.id else "Active Baseline"
    st.metric(label="Summary Relevance", value=rel_val, delta=rel_delta)

# KPI Metric 3: Latency
with col3:
    lat_val = f"{selected_run['avg_latency']:.2f}s"
    lat_delta = None
    if baseline is not None:
        delta = selected_run['avg_latency'] - baseline.avg_latency
        lat_delta = f"{delta:+.2f}s vs baseline" if selected_run_id != baseline.id else "Active Baseline"
    st.metric(label="Avg Latency", value=lat_val, delta=lat_delta, delta_color="inverse")

# KPI Metric 4: Token cost
with col4:
    cost_val = f"${selected_run['total_cost']:.4f}"
    st.metric(label="Est. Execution Cost", value=cost_val, delta=f"{selected_run['total_tokens']} tokens")

# Drift Check Banner
drift_results = check_performance_drift(rolling_window=7)
if drift_results["drift_detected"]:
    st.warning(f"🚨 **Slow Drift Alert:** {drift_results['message']}")
else:
    st.success(f"📈 **Drift Monitor Status:** {drift_results['message']}")

st.divider()

# Get results for current and baseline
current_results = get_results_for_run(selected_run_id)
baseline_results = get_results_for_run(baseline.id) if baseline else []

# Split analysis layout
tab_results, tab_trends, tab_config = st.tabs(["🔍 Diagnostics & Case Logs", "📈 Performance Trends", "⚙️ Run Configuration"])

with tab_results:
    st.header("Detailed Case Diagnostics")
    
    # Check if this selected run has regressions vs baseline
    has_diff = len(baseline_results) > 0 and selected_run_id != baseline.id
    
    # Formatting results as DataFrame
    res_list = []
    regressions_ids = []
    
    if has_diff:
        baseline_map = {r.case_id: r for r in baseline_results}
        for current in current_results:
            b_res = baseline_map.get(current.case_id)
            if b_res:
                b_passed = b_res.category_passed and b_res.relevance_score >= 3.5
                c_passed = current.category_passed and current.relevance_score >= 3.5
                if b_passed and not c_passed:
                    regressions_ids.append(current.case_id)

    for r in current_results:
        status_label = "PASS" if (r.category_passed and r.relevance_score >= 3.5) else "FAIL"
        if r.case_id in regressions_ids:
            status_label = "REGRESSED 🔴"
            
        res_list.append({
            "Case ID": r.case_id,
            "Input text": r.input_text,
            "Expected Cat": r.expected_category,
            "Actual Cat": r.actual_category,
            "Cat Match": "✅ Match" if r.category_passed else "❌ Mismatch",
            "Summary Relevance": r.relevance_score,
            "Actual Summary": r.actual_summary,
            "Expected Summary": r.expected_summary,
            "Status": status_label,
            "Latency (s)": round(r.latency, 3),
            "Tokens": r.input_tokens + r.output_tokens
        })
    df_results_tab = pd.DataFrame(res_list)
    
    # Filter selection
    filter_option = st.selectbox("Filter Results", ["All Cases", "Regressions Only 🔴", "Failures Only (Current Run)", "Successes Only"])
    
    filtered_df = df_results_tab
    if filter_option == "Regressions Only 🔴":
        filtered_df = df_results_tab[df_results_tab["Status"] == "REGRESSED 🔴"]
    elif filter_option == "Failures Only (Current Run)":
        filtered_df = df_results_tab[df_results_tab["Status"].str.contains("FAIL|REGRESSED")]
    elif filter_option == "Successes Only":
        filtered_df = df_results_tab[df_results_tab["Status"] == "PASS"]
        
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    # Detailed Side-by-Side inspector
    st.subheader("🔎 Case Inspector")
    inspected_case_id = st.selectbox("Select Case ID to inspect detailed outputs:", filtered_df["Case ID"].tolist() if not filtered_df.empty else ["None"])
    
    if inspected_case_id != "None":
        case_data = next(c for c in current_results if c.case_id == inspected_case_id)
        
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            st.markdown(f"**Customer Input Email:**")
            st.info(case_data.input_text)
            st.write(f"**Expected Category:** `{case_data.expected_category}`")
            st.write(f"**Expected Summary:** _{case_data.expected_summary}_")
            
        with c_col2:
            st.markdown(f"**Model Response Predictions:**")
            is_good_cat = "✅ Category Correct" if case_data.category_passed else "❌ Category Misclassified"
            st.markdown(f"**Category:** `{case_data.actual_category}` ({is_good_cat})")
            st.markdown(f"**Summary:** _{case_data.actual_summary}_")
            st.markdown(f"**LLM-as-Judge Relevance Score:** `{case_data.relevance_score}/5.0`")
            
            if has_diff:
                b_case = next((b for b in baseline_results if b.case_id == inspected_case_id), None)
                if b_case:
                    st.divider()
                    st.markdown("**Comparison vs Baseline Output:**")
                    st.write(f"Baseline Category: `{b_case.actual_category}`")
                    st.write(f"Baseline Summary: _{b_case.actual_summary}_")
                    st.write(f"Baseline Relevance Score: `{b_case.relevance_score}/5.0`")

with tab_trends:
    st.header("Performance History Charts")
    
    # Process history data for plotting
    df_history = df_runs.copy()
    df_history["timestamp"] = pd.to_datetime(df_history["timestamp"])
    df_history = df_history.sort_values("timestamp")
    
    # Plot 1: Category Accuracy Trend
    st.subheader("Category Accuracy Over Time (%)")
    chart_acc = alt.Chart(df_history).mark_line(point=True, color="#8b5cf6").encode(
        x=alt.X("timestamp:T", title="Date Run"),
        y=alt.Y("pass_rate:Q", scale=alt.Scale(domain=[0, 100]), title="Accuracy (%)"),
        tooltip=["id", "prompt_version", "pass_rate", "timestamp"]
    ).properties(height=300, use_container_width=True)
    st.altair_chart(chart_acc, use_container_width=True)
    
    # Plot 2: Average Relevance Trend
    st.subheader("Average Summary Relevance Score Over Time (1-5)")
    chart_rel = alt.Chart(df_history).mark_line(point=True, color="#10b981").encode(
        x=alt.X("timestamp:T", title="Date Run"),
        y=alt.Y("avg_relevance:Q", scale=alt.Scale(domain=[1, 5]), title="Relevance Score"),
        tooltip=["id", "prompt_version", "avg_relevance", "timestamp"]
    ).properties(height=300, use_container_width=True)
    st.altair_chart(chart_rel, use_container_width=True)

with tab_config:
    st.header("Run Context Metadata")
    
    st.write(f"**Run Identifier:** `{selected_run['id']}`")
    st.write(f"**Evaluation Timestamp:** `{selected_run['timestamp']}`")
    st.write(f"**Prompt Version:** `{selected_run['prompt_version']}`")
    st.write(f"**Config Hash (MD5):** `{selected_run['config_hash']}`")
    st.write(f"**Model Name:** `{selected_run['model']}`")
    
    st.divider()
    st.subheader("Active Prompt System Config Settings")
    
    # We could show active prompt instructions if we extract them, but for now we read the run config or details
    st.info("Ensure prompts are kept in the `/prompts` folder to run them against the evaluation pipeline.")
