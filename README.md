# 🏥 Hospital Pharmacy DWH & BI

> Data Warehouse & Business Intelligence system for **RSUD Ir. Soekarno Sukoharjo** — Pharmacy Inventory Management.

This project implements a full DWH pipeline: from raw staging data (EHP system exports) through ETL transformation into a Star Schema, with a BI dashboard layer for pharmacy operational analytics.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Database | PostgreSQL 16 (Docker) | DWH storage, window functions, CTEs |
| ETL Processing | Python 3.11 + Polars | High-performance data transformation |
| ETL CLI | Click + Rich | Pipeline orchestration with nice output |
| Dependency Mgmt | uv | Fast, deterministic Python package management |
| Containerization | Docker + Docker Compose | Reproducible infrastructure |
| BI Dashboard | Streamlit *(Fase 5+)* | Interactive analytics interface |

---

## Prerequisites

- **Docker Desktop** (with WSL2 backend if on Windows)
- **Python 3.11+** (via conda/miniconda)
- **uv** — `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## Quick Start

### 1. Clone & Setup Environment

```bash
git clone <repo-url>
cd hospital-pharmacy-dwh-bi

# Create .env from template
cp .env.example .env
# Edit .env → set POSTGRES_PASSWORD
```

### 2. Start PostgreSQL

```bash
make up
# Verify it's healthy:
make ps
```

### 3. Connect to Database

```bash
# Via psql in container:
make psql

# Or connect DBeaver/pgAdmin to localhost:5432
```

### 4. Setup Python (Host Development)

```bash
# Create conda env (if not exists)
conda create -n dwh_env python=3.11 -y
conda activate dwh_env

# Install dependencies with uv
uv sync

# Verify ETL module:
python -m etl.run_pipeline list-steps
```

### 5. Run ETL in Container

```bash
# Build ETL image:
docker compose build etl

# List available steps:
make etl-list

# Run full pipeline:
make etl-run

# Run single step:
make etl-step STEP=load-dim-medicine
```

---

## Project Structure

```
hospital-pharmacy-dwh-bi/
├── data/
│   ├── raw/                    # Source CSVs from EHP system (gitignored)
│   ├── samples/                # Sliced subsets for dev (gitignored)
│   ├── STG_EHP__INVN/          # 98 inventory CSV files (~82M rows)
│   ├── STG_EHP__MDCN.csv       # Medicine master (~346K rows)
│   ├── STG_EHP__SPLY.csv       # Supply records (~721K rows)
│   ├── STG_EHP__VNDR.csv       # Vendor master
│   └── ERD Relationship Text.txt
├── etl/                        # Python ETL package
│   ├── __init__.py
│   ├── config.py               # Database config & connection helpers
│   └── run_pipeline.py         # CLI pipeline runner (Click)
├── sql/                        # DDL & DML scripts (Fase 3+)
├── scripts/                    # Utility shell scripts
├── tests/                      # pytest test suite
│   └── test_smoke.py           # Infrastructure smoke tests
├── docker-compose.yml          # PostgreSQL + ETL services
├── Dockerfile                  # Multi-stage ETL container
├── pyproject.toml              # Python project config (uv/hatch)
├── Makefile                    # Convenience commands
├── .env.example                # Environment template (committed)
├── .env                        # Actual credentials (gitignored)
└── laporan_DWH_Kel3_REVISED.pdf
```

---

## Star Schema Design

*(Documented in laporan BAB 4.1 & 4.4)*

```
                    ┌──────────────┐
                    │  dim_time    │
                    └──────┬───────┘
                           │
┌──────────────┐   ┌───────┴────────────────┐   ┌──────────────┐
│ dim_medicine │───│ fact_pharmacy_inventory │───│  dim_vendor  │
└──────────────┘   └────────────────────────┘   └──────────────┘
```

- **1 Fact Table:** `fact_pharmacy_inventory`
- **3 Dimension Tables:** `dim_medicine`, `dim_time`, `dim_vendor`
- **Vendor Resolution:** via Supply table lookup at ETL time (Option B)

---

## Development Workflow

| Command | Description |
|---------|-------------|
| `make up` | Start PostgreSQL |
| `make psql` | Open database shell |
| `make etl-list` | Show pipeline steps |
| `make etl-run` | Run full pipeline |
| `make etl-step STEP=<name>` | Run single step |
| `make etl-shell` | Bash into ETL container |
| `make rebuild` | Rebuild ETL image |
| `make clean` | Reset everything |

---

## Phases

| Phase | Description | Status |
|-------|-------------|--------|
| Fase 1 | Infrastructure Setup (Docker, Python, CLI) | ✅ Current |
| Fase 2 | Source CSV Ingestion & Sampling | ⏳ Next |
| Fase 3 | DDL Execution (Star Schema tables) | 🔜 |
| Fase 4 | ETL Transform & Load | 🔜 |
| Fase 5 | BI Dashboard (Streamlit) | 🔜 |
