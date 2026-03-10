"""
Pharmacy Inventory Intelligence — RSUD Ir. Soekarno Sukoharjo
Streamlit BI Dashboard (mockup with realistic dummy data)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ───────────────────────────── page config ──────────────────────────────

st.set_page_config(
    page_title="Pharmacy Inventory Intelligence",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────── custom CSS ───────────────────────────────

st.markdown(
    """
    <style>
    /* ---------- global ---------- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="st-"] {
        font-family: 'Inter', sans-serif;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1rem;
    }

    /* ---------- header ---------- */
    .main-header {
        background: linear-gradient(135deg, #1A5276 0%, #2E86C1 60%, #3498DB 100%);
        padding: 1.8rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 4px 20px rgba(26, 82, 118, 0.30);
    }
    .main-header h1 {
        margin: 0; font-size: 1.65rem; font-weight: 700; letter-spacing: .3px;
    }
    .main-header p {
        margin: .35rem 0 0 0; font-size: 1rem; opacity: .88; font-weight: 400;
    }

    /* ---------- KPI cards ---------- */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #D6EAF8;
        border-radius: 12px;
        padding: 1.3rem 1.5rem;
        box-shadow: 0 2px 12px rgba(46, 134, 193, .08);
        text-align: center;
    }
    .kpi-card .kpi-label {
        font-size: .82rem; font-weight: 600; color: #5D6D7E;
        text-transform: uppercase; letter-spacing: .6px; margin-bottom: .45rem;
    }
    .kpi-card .kpi-value {
        font-size: 1.75rem; font-weight: 700; color: #1A5276;
    }
    .kpi-card .kpi-delta {
        font-size: .82rem; margin-top: .3rem;
    }
    .kpi-delta.positive { color: #27AE60; }
    .kpi-delta.negative { color: #E74C3C; }

    /* ---------- chart containers ---------- */
    .chart-container {
        background: #ffffff;
        border: 1px solid #D6EAF8;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        box-shadow: 0 2px 12px rgba(46, 134, 193, .06);
        margin-bottom: 1rem;
    }
    .chart-container h3 {
        font-size: .95rem; font-weight: 600; color: #1A5276; margin-bottom: .6rem;
    }

    /* ---------- sidebar ---------- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1A5276 0%, #154360 100%);
    }
    [data-testid="stSidebar"] * {
        color: #EBF5FB !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label,
    [data-testid="stSidebar"] .stDateInput label {
        font-weight: 600 !important;
    }

    /* Hide default Streamlit metric styling to use custom KPI cards */
    div[data-testid="stMetricValue"] { font-size: 1.7rem !important; color: #1A5276 !important; }
    div[data-testid="stMetricLabel"] { font-size: .82rem !important; color: #5D6D7E !important; text-transform: uppercase; }

    /* ---------- footer ---------- */
    .footer {
        text-align: center; padding: 1rem 0; font-size: .75rem;
        color: #85929E; border-top: 1px solid #D6EAF8; margin-top: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════
# DATA GENERATION  — Star Schema with realistic dummy data
# ═══════════════════════════════════════════════════════════════════════

SEED = 42
rng = np.random.default_rng(SEED)


@st.cache_data
def generate_data():
    """Generate all dimension and fact tables."""

    # ── Dim: Medicine ──────────────────────────────────────────────────
    medicine_names = {
        "Antibiotics": [
            "Amoxicillin 500 mg", "Ciprofloxacin 500 mg", "Azithromycin 250 mg",
            "Cefixime 200 mg", "Metronidazole 500 mg", "Levofloxacin 500 mg",
        ],
        "Analgesics": [
            "Paracetamol 500 mg", "Ibuprofen 400 mg", "Ketorolac 30 mg",
            "Mefenamic Acid 500 mg", "Tramadol 50 mg", "Aspirin 100 mg",
        ],
        "Vaccines": [
            "Sinovac COVID-19", "Hepatitis B Vaccine", "BCG Vaccine",
            "Tetanus Toxoid", "MMR Vaccine", "Influenza Vaccine",
        ],
        "Antihypertensives": [
            "Amlodipine 5 mg", "Captopril 25 mg", "Losartan 50 mg",
            "Bisoprolol 5 mg", "Valsartan 80 mg", "Ramipril 5 mg",
        ],
        "Antidiabetics": [
            "Metformin 500 mg", "Glimepiride 2 mg", "Insulin Glargine",
            "Acarbose 50 mg", "Pioglitazone 15 mg", "Gliclazide 80 mg",
        ],
    }
    rows = []
    mid = 1
    for med_type, names in medicine_names.items():
        for name in names:
            rows.append({"Medicine_ID": mid, "Medicine_Name": name, "Medicine_Type": med_type})
            mid += 1
    dim_medicine = pd.DataFrame(rows)

    # ── Dim: Staff ─────────────────────────────────────────────────────
    staff_names = [
        "Apt. Siti Nurhaliza", "Apt. Budi Santoso", "Apt. Dewi Lestari",
        "Apt. Agus Prasetyo", "Apt. Rina Wulandari", "Apt. Hendra Gunawan",
        "Apt. Mega Putri", "Apt. Fajar Nugroho", "Apt. Yuni Astuti",
        "Apt. Dian Permata",
    ]
    dim_staff = pd.DataFrame({
        "Staff_ID": range(1, len(staff_names) + 1),
        "Staff_Name": staff_names,
    })

    # ── Dim: Vendor ────────────────────────────────────────────────────
    vendor_names = [
        "PT Kimia Farma Tbk", "PT Kalbe Farma Tbk", "PT Biofarma",
        "PT Sanbe Farma", "PT Dexa Medica", "PT Phapros Tbk",
        "PT Indofarma Tbk", "PT Tempo Scan Pacific",
    ]
    dim_vendor = pd.DataFrame({
        "Vendor_ID": range(1, len(vendor_names) + 1),
        "Vendor_Name": vendor_names,
    })

    # ── Dim: Patient ───────────────────────────────────────────────────
    n_patients = 500
    age_groups = ["0-17", "18-30", "31-45", "46-60", "60+"]
    dim_patient = pd.DataFrame({
        "Patient_ID": range(1, n_patients + 1),
        "Gender": rng.choice(["Male", "Female"], n_patients),
        "Age_Group": rng.choice(age_groups, n_patients, p=[0.12, 0.22, 0.28, 0.23, 0.15]),
    })

    # ── Dim: Time ──────────────────────────────────────────────────────
    today = pd.Timestamp("2026-03-10")
    dates = pd.date_range(end=today, periods=90, freq="D")
    dim_time = pd.DataFrame({
        "Date": dates,
        "Day": dates.day,
        "Month": dates.month_name(),
        "Year": dates.year,
        "Day_of_Week": dates.day_name(),
    })

    # ── Fact: Pharmacy Inventory ───────────────────────────────────────
    n_rows = 5000
    fact = pd.DataFrame({
        "Date": rng.choice(dates, n_rows),
        "Medicine_ID": rng.choice(dim_medicine["Medicine_ID"].values, n_rows),
        "Staff_ID": rng.choice(dim_staff["Staff_ID"].values, n_rows),
        "Vendor_ID": rng.choice(dim_vendor["Vendor_ID"].values, n_rows),
        "Patient_ID": rng.choice(dim_patient["Patient_ID"].values, n_rows),
        "Opening_Qty": rng.integers(50, 500, n_rows),
        "Received_Qty": rng.integers(0, 200, n_rows),
        "Issued_Qty": rng.integers(5, 150, n_rows),
    })
    fact["Remaining_Qty"] = fact["Opening_Qty"] + fact["Received_Qty"] - fact["Issued_Qty"]
    fact["Unit_Cost"] = rng.integers(500, 150_000, n_rows)  # IDR per unit
    fact["Total_Value"] = fact["Remaining_Qty"] * fact["Unit_Cost"]

    # Merge dimension attributes onto fact
    fact = (
        fact
        .merge(dim_medicine, on="Medicine_ID")
        .merge(dim_staff, on="Staff_ID")
        .merge(dim_vendor, on="Vendor_ID")
        .merge(dim_patient, on="Patient_ID")
    )

    return fact, dim_medicine, dim_vendor, today


fact_df, dim_medicine, dim_vendor, TODAY = generate_data()

# ═══════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <div class="main-header">
        <h1>🏥 RSUD Ir. Soekarno Sukoharjo</h1>
        <p>💊 Pharmacy Analytical Dashboard &mdash; Inventory Intelligence</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR FILTERS
# ═══════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 🔍 Dashboard Filters")
    st.markdown("---")

    # Date range
    default_start = TODAY - pd.Timedelta(days=30)
    date_start = st.date_input("📅 Start Date", value=default_start.date())
    date_end = st.date_input("📅 End Date", value=TODAY.date())

    st.markdown("---")

    # Medicine Type
    all_types = sorted(dim_medicine["Medicine_Type"].unique())
    selected_types = st.multiselect(
        "💉 Medicine Type",
        options=all_types,
        default=all_types,
    )

    st.markdown("---")

    # Vendor
    all_vendors = sorted(dim_vendor["Vendor_Name"].unique())
    selected_vendors = st.multiselect(
        "🏭 Vendor Name",
        options=all_vendors,
        default=all_vendors,
    )

    st.markdown("---")
    st.caption("© 2026 RSUD Ir. Soekarno Sukoharjo")

# ── Apply filters ──────────────────────────────────────────────────────

mask = (
    (fact_df["Date"] >= pd.Timestamp(date_start))
    & (fact_df["Date"] <= pd.Timestamp(date_end))
    & (fact_df["Medicine_Type"].isin(selected_types))
    & (fact_df["Vendor_Name"].isin(selected_vendors))
)
filtered = fact_df.loc[mask].copy()

# ═══════════════════════════════════════════════════════════════════════
# KPI CARDS
# ═══════════════════════════════════════════════════════════════════════

total_inventory_value = filtered["Total_Value"].sum()

today_issued = filtered.loc[filtered["Date"] == TODAY, "Issued_Qty"].sum()
yesterday = TODAY - pd.Timedelta(days=1)
yesterday_issued = filtered.loc[filtered["Date"] == yesterday, "Issued_Qty"].sum()
issued_delta = int(today_issued - yesterday_issued)

critical_stock = filtered.loc[filtered["Issued_Qty"] > filtered["Remaining_Qty"]]
n_critical = critical_stock["Medicine_Name"].nunique()

kpi1, kpi2, kpi3 = st.columns(3)

with kpi1:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Total Inventory Value</div>
            <div class="kpi-value">IDR {total_inventory_value:,.0f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi2:
    delta_class = "positive" if issued_delta >= 0 else "negative"
    delta_icon = "▲" if issued_delta >= 0 else "▼"
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Medicines Issued Today</div>
            <div class="kpi-value">{int(today_issued):,}</div>
            <div class="kpi-delta {delta_class}">{delta_icon} {abs(issued_delta):,} vs yesterday</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi3:
    alert_color = "negative" if n_critical > 0 else "positive"
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Critical Stock Alerts</div>
            <div class="kpi-value" style="color: {'#E74C3C' if n_critical > 0 else '#27AE60'};">
                ⚠️ {n_critical}
            </div>
            <div class="kpi-delta {alert_color}">Items where Issued &gt; Remaining</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# VISUALIZATIONS — Row 1
# ═══════════════════════════════════════════════════════════════════════

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#1A5276"),
    margin=dict(l=20, r=20, t=40, b=20),
    height=370,
)

col_left, col_right = st.columns(2)

# ── Top 10 Medicines by Current Stock ─────────────────────────────────

with col_left:
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.markdown("#### 📦 Top 10 Medicines by Current Stock")

    stock_by_med = (
        filtered.groupby("Medicine_Name", as_index=False)["Remaining_Qty"]
        .sum()
        .nlargest(10, "Remaining_Qty")
        .sort_values("Remaining_Qty")
    )

    fig_stock = px.bar(
        stock_by_med,
        x="Remaining_Qty",
        y="Medicine_Name",
        orientation="h",
        color="Remaining_Qty",
        color_continuous_scale=["#AED6F1", "#2E86C1", "#1A5276"],
        labels={"Remaining_Qty": "Current Stock (units)", "Medicine_Name": ""},
    )
    fig_stock.update_layout(**PLOTLY_LAYOUT, showlegend=False, coloraxis_showscale=False)
    fig_stock.update_traces(
        hovertemplate="<b>%{y}</b><br>Stock: %{x:,.0f} units<extra></extra>"
    )
    st.plotly_chart(fig_stock, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── Demand Trend (Issued Qty over time) ───────────────────────────────

with col_right:
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.markdown("#### 📈 Demand Trend — Daily Medicines Issued")

    demand = (
        filtered.groupby("Date", as_index=False)["Issued_Qty"]
        .sum()
        .sort_values("Date")
    )

    fig_demand = go.Figure()
    fig_demand.add_trace(
        go.Scatter(
            x=demand["Date"],
            y=demand["Issued_Qty"],
            mode="lines+markers",
            line=dict(color="#2E86C1", width=2.5, shape="spline"),
            marker=dict(size=4, color="#1A5276"),
            fill="tozeroy",
            fillcolor="rgba(46,134,193,0.10)",
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Issued: %{y:,.0f}<extra></extra>",
        )
    )
    fig_demand.update_layout(
        **PLOTLY_LAYOUT,
        xaxis_title="",
        yaxis_title="Issued Qty",
        xaxis=dict(gridcolor="#EAF2F8"),
        yaxis=dict(gridcolor="#EAF2F8"),
    )
    st.plotly_chart(fig_demand, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# VISUALIZATIONS — Row 2
# ═══════════════════════════════════════════════════════════════════════

col_left2, col_right2 = st.columns(2)

# ── Patient Demographics (Pie) ────────────────────────────────────────

with col_left2:
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.markdown("#### 👥 Patient Demographics — Usage by Age Group")

    demo = (
        filtered.groupby("Age_Group", as_index=False)["Issued_Qty"]
        .sum()
    )

    age_order = ["0-17", "18-30", "31-45", "46-60", "60+"]
    demo["Age_Group"] = pd.Categorical(demo["Age_Group"], categories=age_order, ordered=True)
    demo = demo.sort_values("Age_Group")

    fig_demo = px.pie(
        demo,
        names="Age_Group",
        values="Issued_Qty",
        hole=0.45,
        color_discrete_sequence=["#AED6F1", "#85C1E9", "#5DADE2", "#2E86C1", "#1A5276"],
    )
    fig_demo.update_layout(**PLOTLY_LAYOUT)
    fig_demo.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Issued: %{value:,.0f}<br>%{percent}<extra></extra>",
    )
    st.plotly_chart(fig_demo, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── Vendor Performance (Horizontal Bar) ───────────────────────────────

with col_right2:
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.markdown("#### 🏭 Vendor Performance — Total Supply Received")

    vendor_perf = (
        filtered.groupby("Vendor_Name", as_index=False)["Received_Qty"]
        .sum()
        .sort_values("Received_Qty")
    )

    fig_vendor = px.bar(
        vendor_perf,
        x="Received_Qty",
        y="Vendor_Name",
        orientation="h",
        color="Received_Qty",
        color_continuous_scale=["#D4E6F1", "#2E86C1", "#154360"],
        labels={"Received_Qty": "Total Received (units)", "Vendor_Name": ""},
    )
    fig_vendor.update_layout(**PLOTLY_LAYOUT, showlegend=False, coloraxis_showscale=False)
    fig_vendor.update_traces(
        hovertemplate="<b>%{y}</b><br>Received: %{x:,.0f} units<extra></extra>"
    )
    st.plotly_chart(fig_vendor, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <div class="footer">
        Pharmacy Inventory Intelligence v1.0 · RSUD Ir. Soekarno Sukoharjo · Data Warehouse & BI Layer · 2026
    </div>
    """,
    unsafe_allow_html=True,
)
