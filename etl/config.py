import os
from pathlib import Path
import polars as pl
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load env variables from root directory
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path if env_path.exists() else None)

# DB connection config
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "pharmacy_dwh")

if not DB_PASS:
    raise ValueError("POSTGRES_PASSWORD is not set in env or .env file.")

# SQLAlchemy and Polars URIs
CONN_STR = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
POLARS_URI = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

_engine = None

def get_engine():
    """Lazily instantiates and caches the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(CONN_STR, pool_pre_ping=True, pool_size=5)
    return _engine

def read_query_to_df(query: str) -> pl.DataFrame:
    """Executes a SQL query and returns result as a Polars DataFrame."""
    return pl.read_database(query=query, connection=get_engine())

def test_connection() -> bool:
    """Simple healthcheck connectivity check."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1")).fetchone()
        return True
    except Exception as e:
        raise ConnectionError(f"Database connection failed: {e}")

def execute_upsert(
    df: pl.DataFrame,
    target_table: str,
    unique_key: str,
    columns: list[str],
    update_columns: list[str],
    accumulate: bool = False,
) -> None:
    """
    Saves a Polars DataFrame to a target table via a temporary staging table to support SQL UPSERT.
    We do this because Polars does not natively support SQL 'ON CONFLICT' statements.
    
    If 'accumulate' is True, conflicting numeric records (e.g. quantities in fact tables) 
    will sum up instead of overwriting, which is perfect for iterative chunk loads.
    """
    temp_stage = f"tmp_{target_table}_stage"
    
    # 1. Create the empty staging table structure first
    df.limit(0).write_database(
        table_name=temp_stage,
        connection=POLARS_URI,
        if_table_exists="replace",
    )
    
    # 2. Bulk copy the data using psycopg2 COPY protocol (100x faster than standard SQLAlchemy inserts)
    import io
    buf = io.BytesIO()
    df.write_csv(buf, include_header=False)
    buf.seek(0)
    
    raw_conn = get_engine().raw_connection()
    try:
        with raw_conn.cursor() as cur:
            cur.copy_expert(f"COPY {temp_stage} FROM STDIN WITH CSV", buf)
        raw_conn.commit()
    finally:
        raw_conn.close()
    
    cols_joined = ", ".join(columns)
    
    if update_columns:
        if accumulate:
            # Add new batch metrics to the existing values in the DWH, handling non-additive ratios correctly
            rules = []
            for col in update_columns:
                if col == "stock_availability_pct":
                    rules.append(
                        f"stock_availability_pct = ROUND((( {target_table}.closed_qty + EXCLUDED.closed_qty ) * 100.0) / "
                        f"NULLIF({target_table}.opening_qty + EXCLUDED.opening_qty + {target_table}.received_qty + EXCLUDED.received_qty, 0), 2)"
                    )
                elif col == "wastage_ratio_pct":
                    rules.append(
                        f"wastage_ratio_pct = ROUND((( {target_table}.received_qty + EXCLUDED.received_qty - "
                        f"( {target_table}.issued_qty + EXCLUDED.issued_qty ) ) * 100.0) / "
                        f"NULLIF({target_table}.received_qty + EXCLUDED.received_qty, 0), 2)"
                    )
                else:
                    rules.append(f"{col} = {target_table}.{col} + EXCLUDED.{col}")
            update_rules = ", ".join(rules)
        else:
            # Standard overwrite
            update_rules = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
            
        upsert_sql = f"""
        INSERT INTO {target_table} ({cols_joined})
        SELECT {cols_joined} FROM {temp_stage}
        ON CONFLICT ({unique_key}) DO UPDATE
        SET {update_rules};
        """
    else:
        upsert_sql = f"""
        INSERT INTO {target_table} ({cols_joined})
        SELECT {cols_joined} FROM {temp_stage}
        ON CONFLICT ({unique_key}) DO NOTHING;
        """
        
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(upsert_sql))
        conn.execute(text(f"DROP TABLE IF EXISTS {temp_stage};"))

def execute_direct_copy(
    df: pl.DataFrame,
    target_table: str,
    columns: list[str],
) -> None:
    """
    Directly copies a Polars DataFrame into a target table using psycopg2 COPY protocol.
    Bypasses staging tables and ON CONFLICT statements for maximum performance.
    """
    import io
    buf = io.BytesIO()
    df.select(columns).write_csv(buf, include_header=False)
    buf.seek(0)
    
    raw_conn = get_engine().raw_connection()
    try:
        with raw_conn.cursor() as cur:
            cur.copy_expert(f"COPY {target_table} ({', '.join(columns)}) FROM STDIN WITH CSV", buf)
        raw_conn.commit()
    finally:
        raw_conn.close()

