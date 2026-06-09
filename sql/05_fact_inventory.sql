CREATE TABLE IF NOT EXISTS fact_pharmacy_inventory (
    date_id_fk              BIGINT NOT NULL REFERENCES dim_time(date_id_pk),
    medicine_id_fk          BIGINT NOT NULL REFERENCES dim_medicine(medicine_id_pk),
    vendor_id_fk            BIGINT NOT NULL REFERENCES dim_vendor(vendor_id_pk),
    opening_qty             NUMERIC(18,2) NOT NULL DEFAULT 0,
    received_qty            NUMERIC(18,2) NOT NULL DEFAULT 0,
    issued_qty              NUMERIC(18,2) NOT NULL DEFAULT 0,
    closed_qty              NUMERIC(18,2) NOT NULL DEFAULT 0,
    stock_availability_pct  NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    valuasi                 NUMERIC(18,2) NOT NULL DEFAULT 0.00,
    pengeluaran             NUMERIC(18,2) NOT NULL DEFAULT 0.00,
    wastage_ratio_pct       NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    CONSTRAINT pk_fact_pharmacy_inventory
        PRIMARY KEY (date_id_fk, medicine_id_fk, vendor_id_fk)
);

CREATE INDEX IF NOT EXISTS ix_fact_date     ON fact_pharmacy_inventory(date_id_fk);
CREATE INDEX IF NOT EXISTS ix_fact_medicine ON fact_pharmacy_inventory(medicine_id_fk);
CREATE INDEX IF NOT EXISTS ix_fact_vendor   ON fact_pharmacy_inventory(vendor_id_fk);

