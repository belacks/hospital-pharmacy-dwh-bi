import sys
import time
from pathlib import Path
import click
import polars as pl
from rich.console import Console
from rich.table import Table
from sqlalchemy import text
from etl.config import get_engine, execute_upsert, read_query_to_df, execute_direct_copy

console = Console()
steps = {}

def step(name):
    """Simple decorator to register an ETL step."""
    def decorator(func):
        steps[name] = func
        return func
    return decorator

@step("load-dim-medicine")
def load_dim_medicine():
    """Populates dim_medicine with clean data from the master CSV."""
    console.print("[blue]Step: load-dim-medicine[/blue]")
    start_time = time.time()
    csv_path = Path("data/STG_EHP__MDCN.csv")
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing master file: {csv_path}")
        
    df = pl.read_csv(csv_path)
    
    # Cast, select, and rename columns to map to the target star schema
    df_clean = (
        df.select([
            pl.col("MED_ID").alias("medicine_sku").cast(pl.String),
            pl.col("MED_NAME").alias("medicine_name").cast(pl.String),
            pl.col("TYPE_DES").alias("type_description").cast(pl.String),
            pl.col("STRG_DES").alias("storage_type").cast(pl.String),
            pl.col("COST_UN").alias("unit_cost").cast(pl.Float64).fill_null(0.0),
            pl.col("EXP_MON").alias("expiration_months").cast(pl.Int32).fill_null(0),
        ])
        .unique(subset=["medicine_sku"])
    )
    
    execute_upsert(
        df=df_clean,
        target_table="dim_medicine",
        unique_key="medicine_sku",
        columns=["medicine_sku", "medicine_name", "type_description", "storage_type", "unit_cost", "expiration_months"],
        update_columns=["medicine_name", "type_description", "storage_type", "unit_cost", "expiration_months"],
    )
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    console.print(f"🎉 Ingesti dim_medicine selesai dalam: {minutes} menit {seconds} detik.")
    console.print(f"  [green]✅ Loaded {len(df_clean)} records into dim_medicine[/green]")

@step("load-dim-vendor")
def load_dim_vendor():
    """Populates dim_vendor with clean data from the vendor CSV."""
    console.print("[blue]Step: load-dim-vendor[/blue]")
    start_time = time.time()
    csv_path = Path("data/STG_EHP__VNDR.csv")
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing master file: {csv_path}")
        
    df = pl.read_csv(csv_path)
    
    # Select and rename attributes according to the Star Schema design
    df_clean = (
        df.select([
            pl.col("VEN_ACC").alias("vendor_account").cast(pl.String),
            pl.col("VEN_NAME").alias("vendor_name").cast(pl.String),
            pl.col("VEN_TYPE").alias("vendor_type").cast(pl.String),
            pl.col("CTRY_NAME").alias("country_name").cast(pl.String),
            pl.col("VSTAT_DES").alias("vendor_status").cast(pl.String),
        ])
        .unique(subset=["vendor_account"])
    )
    
    execute_upsert(
        df=df_clean,
        target_table="dim_vendor",
        unique_key="vendor_account",
        columns=["vendor_account", "vendor_name", "vendor_type", "country_name", "vendor_status"],
        update_columns=["vendor_name", "vendor_type", "country_name", "vendor_status"],
    )
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    console.print(f"🎉 Ingesti dim_vendor selesai dalam: {minutes} menit {seconds} detik.")
    console.print(f"  [green]✅ Loaded {len(df_clean)} records into dim_vendor[/green]")

@step("load-dim-time")
def load_dim_time():
    """Dynamically builds dim_time by scanning unique dates inside the inventory files."""
    console.print("[blue]Step: load-dim-time[/blue]")
    start_time = time.time()
    
    # 1. Scan unique dates from all files lazily to save memory
    df_raw = (
        pl.scan_csv("data/STG_EHP__INVN/*.csv")
        .select("INGTN_TS")
        .drop_nulls()
        .unique()
        .collect()
    )
    
    # 2. Convert to date format. Using strict=False converts anomalies (like single digit '2') to Null so we can drop them.
    df_dates = (
        df_raw.select([
            pl.col("INGTN_TS").str.to_date(format="%Y-%m-%d", strict=False).alias("full_date")
        ])
        .drop_nulls("full_date")
        .unique(subset=["full_date"])
    )
    
    # 3. Derive calendar dimensions for queries
    df_clean = df_dates.select([
        pl.col("full_date"),
        pl.col("full_date").dt.year().alias("year").cast(pl.Int32),
        pl.col("full_date").dt.quarter().alias("quarter").cast(pl.Int32),
        pl.col("full_date").dt.month().alias("month").cast(pl.Int32),
        pl.col("full_date").dt.strftime("%B").alias("month_name"),
        pl.col("full_date").dt.day().alias("day").cast(pl.Int32),
        pl.col("full_date").dt.strftime("%A").alias("day_of_week")
    ]).sort("full_date")
    
    execute_upsert(
        df=df_clean,
        target_table="dim_time",
        unique_key="full_date",
        columns=["full_date", "year", "quarter", "month", "month_name", "day", "day_of_week"],
        update_columns=[],  # If date already exists, do nothing
    )
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    console.print(f"🎉 Ingesti dim_time selesai dalam: {minutes} menit {seconds} detik.")
    console.print(f"  [green]✅ Loaded {len(df_clean)} records into dim_time[/green]")

@step("load-fact")
def load_fact_inventory():
    """
    Ingests and aggregates the 82M rows of movement transactions across 98 CSV files.
    Features:
      1. O(1) Memory footprint: Ingests chunk-by-chunk, immediately writing to database 
         to prevent WSL memory crashes (OOM).
      2. Vendor Batch Mapping: Uses join_asof to link every transaction date to the 
         closest preceding receipt date in supply records for precise vendor mapping.
      3. Metrics Materialization: Computes stock availability, valuation, spend, and 
         wastage in-memory using Polars before staged upsert loading.
      4. High-Performance Bulk COPY: Drops indexes and constraints before loading and
         rebuilds them after loading to achieve 100x faster ingestion.
    """
    console.print("[blue]Step: load-fact[/blue]")
    start_time = time.time()
    
    # 1. Start clean and disable constraints to bypass row-by-row index and FK checks
    engine = get_engine()
    console.print("  [yellow]⚡ Disabling indexes and foreign key constraints on fact table...[/yellow]")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE fact_pharmacy_inventory DROP CONSTRAINT IF EXISTS pk_fact_pharmacy_inventory CASCADE;"))
        conn.execute(text("ALTER TABLE fact_pharmacy_inventory DROP CONSTRAINT IF EXISTS fact_pharmacy_inventory_date_id_fk_fkey CASCADE;"))
        conn.execute(text("ALTER TABLE fact_pharmacy_inventory DROP CONSTRAINT IF EXISTS fact_pharmacy_inventory_medicine_id_fk_fkey CASCADE;"))
        conn.execute(text("ALTER TABLE fact_pharmacy_inventory DROP CONSTRAINT IF EXISTS fact_pharmacy_inventory_vendor_id_fk_fkey CASCADE;"))
        conn.execute(text("DROP INDEX IF EXISTS ix_fact_date;"))
        conn.execute(text("DROP INDEX IF EXISTS ix_fact_medicine;"))
        conn.execute(text("DROP INDEX IF EXISTS ix_fact_vendor;"))
        conn.execute(text("TRUNCATE TABLE fact_pharmacy_inventory;"))
        
    # 2. Get active lookups from the database to map IDs (and medicine unit_cost)
    dim_time_df = read_query_to_df("SELECT date_id_pk, full_date FROM dim_time").with_columns(
        pl.col("full_date").cast(pl.Date)
    )
    dim_medicine_df = read_query_to_df("SELECT medicine_id_pk, medicine_sku, unit_cost FROM dim_medicine")
    dim_vendor_df = read_query_to_df("SELECT vendor_id_pk, vendor_account FROM dim_vendor")
    
    # 3. Prepare the Supply logs for join_asof vendor lookup
    supply_path = Path("data/STG_EHP__SPLY.csv")
    if not supply_path.exists():
        raise FileNotFoundError(f"Missing supply file: {supply_path}")
        
    supply_df = (
        pl.read_csv(supply_path)
        .select([
            pl.col("MAT_SKU").cast(pl.String),
            pl.col("RCVD_DATE").str.to_date(format="%Y-%m-%d", strict=False),
            pl.col("VEN_ACC").cast(pl.String)
        ])
        .drop_nulls()
        .sort("RCVD_DATE")
    )
    
    invn_dir = Path("data/STG_EHP__INVN")
    invn_files = sorted(invn_dir.glob("*.csv"))
    if not invn_files:
        raise FileNotFoundError(f"No transaction files inside {invn_dir}")
        
    console.print(f"  Ingesting {len(invn_files)} files chunk by chunk...")
    total_rows = 0
    
    fact_columns = [
        "date_id_fk", 
        "medicine_id_fk", 
        "vendor_id_fk", 
        "opening_qty", 
        "received_qty", 
        "issued_qty", 
        "closed_qty",
        "stock_availability_pct",
        "valuasi",
        "pengeluaran",
        "wastage_ratio_pct"
    ]
    
    for idx, filepath in enumerate(invn_files, 1):
        df = pl.read_csv(filepath)
        
        # Clean timestamps and quantities
        df_clean = (
            df.select([
                pl.col("MAT_SKU").cast(pl.String),
                pl.col("INGTN_TS").str.to_date(format="%Y-%m-%d", strict=False).alias("movement_date"),
                pl.col("OPEN_QTY").cast(pl.Float64).fill_null(0.0),
                pl.col("RCVD_QTY").cast(pl.Float64).fill_null(0.0),
                pl.col("ISSD_QTY").cast(pl.Float64).fill_null(0.0),
                pl.col("CLSD_QTY").cast(pl.Float64).fill_null(0.0),
            ])
            .drop_nulls("movement_date")
            .sort("movement_date")
        )
        
        # Find which vendor shipped this medicine batch using closest-match received date (join_asof)
        df_mapped = df_clean.join_asof(
            supply_df,
            left_on="movement_date",
            right_on="RCVD_DATE",
            by="MAT_SKU",
            strategy="backward"
        ).drop_nulls("VEN_ACC")
        
        # Reduce records by aggregating quantities at the natural key level first (O(1) memory grouping)
        df_grouped = (
            df_mapped.group_by(["movement_date", "MAT_SKU", "VEN_ACC"])
            .agg([
                pl.col("OPEN_QTY").sum().alias("opening_qty"),
                pl.col("RCVD_QTY").sum().alias("received_qty"),
                pl.col("ISSD_QTY").sum().alias("issued_qty"),
                pl.col("CLSD_QTY").sum().alias("closed_qty")
            ])
        )
        
        # Map natural keys to surrogate keys on the aggregated dataset (10x fewer join rows!)
        df_fact = (
            df_grouped
            .join(dim_time_df, left_on="movement_date", right_on="full_date")
            .rename({"date_id_pk": "date_id_fk"})
            .join(dim_medicine_df, left_on="MAT_SKU", right_on="medicine_sku")
            .rename({"medicine_id_pk": "medicine_id_fk"})
            .join(dim_vendor_df, left_on="VEN_ACC", right_on="vendor_account")
            .rename({"vendor_id_pk": "vendor_id_fk"})
        )
        
        # Compute the 4 daily analytical metrics directly in memory
        df_metrics = df_fact.with_columns([
            pl.when(pl.col("opening_qty") + pl.col("received_qty") > 0)
            .then((pl.col("closed_qty") * 100.0) / (pl.col("opening_qty") + pl.col("received_qty")))
            .otherwise(0.0)
            .round(2)
            .alias("stock_availability_pct"),
            
            (pl.col("closed_qty") * pl.col("unit_cost")).alias("valuasi"),
            
            (pl.col("issued_qty") * pl.col("unit_cost")).alias("pengeluaran"),
            
            pl.when(pl.col("received_qty") > 0)
            .then(((pl.col("received_qty") - pl.col("issued_qty")) * 100.0) / pl.col("received_qty"))
            .otherwise(0.0)
            .round(2)
            .alias("wastage_ratio_pct")
        ])
        
        # Direct high-performance bulk COPY load into database
        execute_direct_copy(
            df=df_metrics,
            target_table="fact_pharmacy_inventory",
            columns=fact_columns
        )
        
        total_rows += len(df_metrics)
        if idx % 10 == 0 or idx == len(invn_files):
            console.print(f"    Ingested {idx}/{len(invn_files)} files... ({total_rows} rows loaded)")
            
    # 4. Re-enable indexes and constraints after load
    console.print("  [yellow]⚡ Re-enabling indexes and foreign key constraints on fact table...[/yellow]")
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE fact_pharmacy_inventory ADD CONSTRAINT pk_fact_pharmacy_inventory "
            "PRIMARY KEY (date_id_fk, medicine_id_fk, vendor_id_fk);"
        ))
        conn.execute(text(
            "ALTER TABLE fact_pharmacy_inventory ADD CONSTRAINT fact_pharmacy_inventory_date_id_fk_fkey "
            "FOREIGN KEY (date_id_fk) REFERENCES dim_time(date_id_pk);"
        ))
        conn.execute(text(
            "ALTER TABLE fact_pharmacy_inventory ADD CONSTRAINT fact_pharmacy_inventory_medicine_id_fk_fkey "
            "FOREIGN KEY (medicine_id_fk) REFERENCES dim_medicine(medicine_id_pk);"
        ))
        conn.execute(text(
            "ALTER TABLE fact_pharmacy_inventory ADD CONSTRAINT fact_pharmacy_inventory_vendor_id_fk_fkey "
            "FOREIGN KEY (vendor_id_fk) REFERENCES dim_vendor(vendor_id_pk);"
        ))
        conn.execute(text("CREATE INDEX ix_fact_date ON fact_pharmacy_inventory(date_id_fk);"))
        conn.execute(text("CREATE INDEX ix_fact_medicine ON fact_pharmacy_inventory(medicine_id_fk);"))
        conn.execute(text("CREATE INDEX ix_fact_vendor ON fact_pharmacy_inventory(vendor_id_fk);"))
        
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    console.print(f"🎉 Ingesti tabel fakta selesai dalam: {minutes} menit {seconds} detik.")
    console.print("  [green]✅ Completed fact table loading successfully[/green]")

def run_single_step(name):
    """Helper to run a step by name with timing."""
    if name not in steps:
        console.print(f"[red]❌ Step '{name}' does not exist.[/red]")
        sys.exit(1)
        
    console.rule(f"[bold blue]{name}")
    start = time.perf_counter()
    try:
        steps[name]()
        elapsed = time.perf_counter() - start
        console.print(f"  [green]✨ Done in {elapsed:.2f}s[/green]\n")
    except Exception as e:
        console.print(f"  [red]💥 Failed: {e}[/red]\n")
        raise

@click.group()
def cli():
    """🏥 Pharmacy Star Schema ETL Orchestrator"""
    pass

@cli.command("deploy-schema")
def deploy_schema():
    """Deploys all SQL DDL schema scripts to PostgreSQL."""
    console.print("\n🏥 Deploying database tables from DDL files...\n")
    sql_dir = Path(__file__).resolve().parent.parent / "sql"
    sql_files = sorted(sql_dir.glob("*.sql"))
    
    if not sql_files:
        console.print("[yellow]⚠️ No DDL SQL scripts found.[/yellow]")
        return
        
    engine = get_engine()
    try:
        with engine.begin() as conn:
            for sql_file in sql_files:
                if sql_file.name in ["README.sql", "kpi_queries.sql", "queries.sql"]:
                    continue
                console.print(f"  → Executing {sql_file.name}...")
                sql_content = sql_file.read_text(encoding="utf-8")
                conn.execute(text(sql_content))
                console.print("    [green]Success[/green]")
        console.print("\n[bold green]🎉 Database schema fully deployed.[/bold green]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Deployment failed:[/red] {e}")
        sys.exit(1)

@cli.command("list-steps")
def list_steps():
    """Displays all registered ETL steps."""
    table = Table(title="📋 Registered ETL Pipeline Steps", show_lines=True)
    table.add_column("No", style="cyan", justify="right")
    table.add_column("Step Name", style="bold white")
    table.add_column("Purpose", style="dim")
    
    for i, (name, func) in enumerate(steps.items(), 1):
        doc = (func.__doc__ or "No description").strip().split("\n")[0]
        table.add_row(str(i), name, doc)
    console.print(table)

@cli.command("run-step")
@click.argument("name")
def run_step(name):
    """Executes a single ETL step."""
    run_single_step(name)

@cli.command("run-all")
def run_all():
    """Runs the entire ETL pipeline in sequential order."""
    console.print(f"\n🏥 Launching full pipeline ({len(steps)} steps)...\n")
    start_time = time.perf_counter()
    
    for name in steps:
        run_single_step(name)
        
    elapsed = time.perf_counter() - start_time
    console.print(f"[bold green]🎉 All ETL stages completed in {elapsed:.2f}s[/bold green]")

if __name__ == "__main__":
    cli()
