-- ==============================================================================
-- 🏥 Pharmacy DWH Verification Queries — RSUD Ir. Soekarno Sukoharjo
-- ==============================================================================
-- This file contains the PostgreSQL queries to compute all 6 KPIs across the
-- 4 metric categories defined in Bab III of the revised DWH report.
--
-- Since the staging data spans Jan 2025 to Sep 2025, these queries use relative
-- date lookups (e.g., SELECT MAX(full_date) FROM dim_time) instead of
-- CURRENT_DATE to ensure they always return data regardless of run time.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- CATEGORY 1: Performa Ketersediaan Stok
-- ------------------------------------------------------------------------------

-- KPI 1: Persentase Ketersediaan Stok Obat
-- Formula: ((opening_qty + received_qty - issued_qty) / (opening_qty + received_qty)) * 100%
-- Reference: Permenkes 72/2016 + Rofiq (2020) Customer Service Level
SELECT
    m.medicine_name,
    m.type_description,
    ROUND(
        ((SUM(COALESCE(f.opening_qty, 0)) + SUM(COALESCE(f.received_qty, 0))
          - SUM(COALESCE(f.issued_qty, 0))) * 100.0)
        / NULLIF(SUM(COALESCE(f.opening_qty, 0)) + SUM(COALESCE(f.received_qty, 0)), 0),
        2
    ) AS stock_availability_pct
FROM fact_pharmacy_inventory f
JOIN dim_medicine m ON f.medicine_id_fk = m.medicine_id_pk
JOIN dim_time     t ON f.date_id_fk     = t.date_id_pk
WHERE t.full_date = (SELECT MAX(full_date) FROM dim_time)
GROUP BY m.medicine_name, m.type_description
ORDER BY stock_availability_pct ASC
LIMIT 10;


-- KPI 2: Valuasi Aset Farmasi (IDR)
-- Formula: SUM((opening_qty + received_qty - issued_qty) * unit_cost * 15000)
-- Note: unit_cost is stored in USD in dim_medicine; we convert to IDR using the 15,000 multiplier.
-- Reference: Indarti et al. (2019) + Rofiq (2020) Inventory Value
SELECT
    m.type_description,
    SUM(
        (COALESCE(f.opening_qty, 0) + COALESCE(f.received_qty, 0)
         - COALESCE(f.issued_qty, 0))
    ) AS current_stock_qty,
    ROUND(
        SUM(
            (COALESCE(f.opening_qty, 0) + COALESCE(f.received_qty, 0)
             - COALESCE(f.issued_qty, 0)) * m.unit_cost * 15000
        ),
        2
    ) AS total_valuasi_idr
FROM fact_pharmacy_inventory f
JOIN dim_medicine m ON f.medicine_id_fk = m.medicine_id_pk
JOIN dim_time     t ON f.date_id_fk     = t.date_id_pk
WHERE t.full_date = (SELECT MAX(full_date) FROM dim_time)
GROUP BY m.type_description
ORDER BY total_valuasi_idr DESC;


-- ------------------------------------------------------------------------------
-- CATEGORY 2: Tren Pengeluaran Historis
-- ------------------------------------------------------------------------------

-- KPI 3: Total Pengeluaran Obat (Monthly Trend per Therapeutic Category)
-- Formula: SUM(issued_qty)
-- Reference: Permenkes 72/2016 + Quick et al. (2012)
SELECT
    t.year,
    t.month,
    t.month_name,
    m.type_description,
    SUM(COALESCE(f.issued_qty, 0)) AS total_qty_issued
FROM fact_pharmacy_inventory f
JOIN dim_medicine m ON f.medicine_id_fk = m.medicine_id_pk
JOIN dim_time     t ON f.date_id_fk     = t.date_id_pk
GROUP BY t.year, t.month, t.month_name, m.type_description
ORDER BY t.year, t.month, total_qty_issued DESC
LIMIT 20;


-- ------------------------------------------------------------------------------
-- CATEGORY 3: Efisiensi Pengelolaan Stok
-- ------------------------------------------------------------------------------

-- KPI 4: Inventory Turnover Ratio (ITOR)
-- Formula: SUM(issued_qty) / AVG(opening_qty)
-- Reference: Indarti et al. (2019) ITOR + Doso et al. (2018)
SELECT
    m.medicine_name,
    m.type_description,
    SUM(COALESCE(f.issued_qty, 0)) AS total_issued,
    ROUND(AVG(COALESCE(f.opening_qty, 0)), 2) AS avg_opening,
    ROUND(
        SUM(COALESCE(f.issued_qty, 0))
        / NULLIF(AVG(COALESCE(f.opening_qty, 0)), 0),
        2
    ) AS turnover_ratio
FROM fact_pharmacy_inventory f
JOIN dim_medicine m ON f.medicine_id_fk = m.medicine_id_pk
GROUP BY m.medicine_name, m.type_description
ORDER BY turnover_ratio DESC
LIMIT 10;


-- KPI 5: Stock Coverage Days (Days of Stock Availability)
-- Formula: current_stock / avg_daily_issued_last_30_days
-- Thresholds: Green (>30 days), Yellow (14-30 days), Red (<14 days)
-- Reference: Indarti et al. (2019) Month-Stock + CPCON Benchmark (30 to 45 days)
WITH avg_daily_usage AS (
    SELECT
        f.medicine_id_fk,
        AVG(COALESCE(f.issued_qty, 0)) AS avg_issued
    FROM fact_pharmacy_inventory f
    JOIN dim_time t ON f.date_id_fk = t.date_id_pk
    WHERE t.full_date >= (SELECT MAX(full_date) FROM dim_time) - INTERVAL '30 days'
    GROUP BY f.medicine_id_fk
)
SELECT
    m.medicine_name,
    m.type_description,
    ROUND(
        (SUM(COALESCE(f.opening_qty, 0)) + SUM(COALESCE(f.received_qty, 0))
         - SUM(COALESCE(f.issued_qty, 0)))
        / NULLIF(a.avg_issued, 0),
        2
    ) AS coverage_days,
    CASE
        WHEN (SUM(COALESCE(f.opening_qty, 0)) + SUM(COALESCE(f.received_qty, 0)) - SUM(COALESCE(f.issued_qty, 0))) / NULLIF(a.avg_issued, 0) > 30 THEN 'GREEN (Safe)'
        WHEN (SUM(COALESCE(f.opening_qty, 0)) + SUM(COALESCE(f.received_qty, 0)) - SUM(COALESCE(f.issued_qty, 0))) / NULLIF(a.avg_issued, 0) BETWEEN 14 AND 30 THEN 'YELLOW (Reorder Warning)'
        ELSE 'RED (Urgent Stockout Risk)'
    END AS status
FROM fact_pharmacy_inventory f
JOIN dim_medicine m ON f.medicine_id_fk = m.medicine_id_pk
JOIN dim_time     t ON f.date_id_fk     = t.date_id_pk
JOIN avg_daily_usage a ON f.medicine_id_fk = a.medicine_id_fk
WHERE t.full_date = (SELECT MAX(full_date) FROM dim_time)
GROUP BY m.medicine_name, m.type_description, a.avg_issued
ORDER BY coverage_days ASC
LIMIT 15;


-- ------------------------------------------------------------------------------
-- CATEGORY 4: Manajemen Wastage
-- ------------------------------------------------------------------------------

-- KPI 6: Rasio Inefisiensi per Kategori & Vendor (Wastage)
-- Formula: ((SUM(received_qty) - SUM(issued_qty)) * 100.0) / NULLIF(SUM(received_qty), 0)
-- Reference: ASHP benchmark (2-7% waste limit) + Permenkes 72/2016
SELECT
    m.type_description,
    v.vendor_name,
    SUM(COALESCE(f.received_qty, 0)) AS total_received,
    SUM(COALESCE(f.issued_qty, 0)) AS total_issued,
    ROUND(
        ((SUM(COALESCE(f.received_qty, 0)) - SUM(COALESCE(f.issued_qty, 0))) * 100.0)
        / NULLIF(SUM(COALESCE(f.received_qty, 0)), 0),
        2
    ) AS wastage_ratio_pct
FROM fact_pharmacy_inventory f
JOIN dim_medicine m ON f.medicine_id_fk = m.medicine_id_pk
JOIN dim_vendor   v ON f.vendor_id_fk   = v.vendor_id_pk
GROUP BY m.type_description, v.vendor_name
ORDER BY wastage_ratio_pct DESC
LIMIT 15;
