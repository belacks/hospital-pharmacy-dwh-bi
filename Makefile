# ============================================================
# Pharmacy DWH — Makefile
# ============================================================
# Convenience targets for Docker and ETL operations.
#
# Usage:
#   make up          → Start PostgreSQL only
#   make psql        → Open psql shell
#   make etl-run     → Run full ETL pipeline in container
#   make clean       → Nuke everything (containers + volumes)
# ============================================================

.PHONY: up up-all down ps psql etl-shell etl-run etl-step rebuild clean logs help

# Default target
help: ## Show this help message
	@echo ""
	@echo "🏥 Pharmacy DWH — Available Commands"
	@echo "======================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""

# -----------------------------------------------------------
# Docker Compose — Infrastructure
# -----------------------------------------------------------
up: ## Start PostgreSQL only (for DBeaver / host dev)
	docker compose up -d postgres

up-all: ## Start everything including ETL container
	docker compose --profile etl up -d

down: ## Stop all containers
	docker compose --profile etl down

ps: ## Show container status
	docker compose --profile etl ps

logs: ## Tail PostgreSQL logs
	docker compose logs -f postgres

# -----------------------------------------------------------
# Database Access
# -----------------------------------------------------------
psql: ## Open psql shell inside PostgreSQL container
	docker compose exec postgres psql -U $${POSTGRES_USER:-pharmacy_admin} -d $${POSTGRES_DB:-pharmacy_dwh}

# -----------------------------------------------------------
# ETL Container
# -----------------------------------------------------------
etl-shell: ## Open bash shell inside ETL container
	docker compose --profile etl run --rm etl bash

etl-run: ## Run full ETL pipeline
	docker compose --profile etl run --rm etl python -m etl.run_pipeline run-all

etl-step: ## Run single ETL step (usage: make etl-step STEP=load-dim-medicine)
	docker compose --profile etl run --rm etl python -m etl.run_pipeline run-step $(STEP)

etl-list: ## List registered ETL steps
	docker compose --profile etl run --rm etl python -m etl.run_pipeline list-steps

# -----------------------------------------------------------
# Build & Maintenance
# -----------------------------------------------------------
rebuild: ## Rebuild ETL Docker image (no cache)
	docker compose build --no-cache etl

clean: ## ⚠️  Nuke everything: containers, volumes, images
	docker compose --profile etl down -v --rmi local --remove-orphans
	@echo "🧹 Cleaned up all containers, volumes, and local images."
