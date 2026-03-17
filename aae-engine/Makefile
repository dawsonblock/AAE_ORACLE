# ============================================================================
# AAE — Autonomous Autonomous Engineering
# Makefile — Developer convenience targets
# ============================================================================

.PHONY: help install install-dev lint test test-unit test-integration \
        bootstrap run-controller run-planner run-agents run-sandbox \
        run-dashboard build-docker up down clean format

PYTHON  := python
PIP     := pip
PYTEST  := pytest
DOCKER  := docker
COMPOSE := docker compose
APP     := src/aae
CONFIG  := configs/system_config.yaml

# ─── Help ────────────────────────────────────────────────────────────────────
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*##"} {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'

# ─── Installation ─────────────────────────────────────────────────────────────
install: ## Install production dependencies
	$(PIP) install -e .

install-dev: ## Install all development dependencies
	$(PIP) install -e ".[dev]"

# ─── Quality ──────────────────────────────────────────────────────────────────
lint: ## Run ruff linter
	ruff check $(APP) scripts tests

format: ## Auto-format code with ruff
	ruff format $(APP) scripts tests

type-check: ## Run mypy type checking
	mypy $(APP)

# ─── Testing ──────────────────────────────────────────────────────────────────
test: ## Run full test suite
	$(PYTEST) tests/ -v

test-unit: ## Run unit tests only
	$(PYTEST) tests/unit/ -v

test-integration: ## Run integration tests (requires Postgres + Redis)
	$(PYTEST) tests/integration/ -v

test-localization: ## Run localization tests
	$(PYTEST) tests/localization/ -v

test-patching: ## Run patching tests
	$(PYTEST) tests/patching/ -v

test-e2e: ## Run end-to-end autonomous patch pipeline test
	$(PYTEST) tests/end_to_end/ -v -s

test-replay: ## Run event replay tests
	$(PYTEST) tests/replay/ -v

test-cov: ## Run tests with coverage report
	$(PYTEST) tests/ --cov=$(APP) --cov-report=html --cov-report=term-missing

# ─── Docker / Compose ─────────────────────────────────────────────────────────
build-docker: ## Build all Docker images
	$(COMPOSE) build

up: ## Start the full stack (storage + controller + workers)
	$(COMPOSE) up -d

down: ## Stop the full stack
	$(COMPOSE) down

logs: ## Follow controller logs
	$(COMPOSE) logs -f controller

ps: ## Show running services
	$(COMPOSE) ps

# ─── Local Runtime ────────────────────────────────────────────────────────────
bootstrap: ## Bootstrap local environment (create DB tables, dirs)
	$(PYTHON) scripts/bootstrap_cluster.py --config $(CONFIG)

run-controller: ## Start the workflow controller locally
	$(PYTHON) scripts/run_controller.py --config $(CONFIG)

run-planner: ## Start a planner worker node locally
	$(PYTHON) scripts/run_planner_node.py --config $(CONFIG)

run-agents: ## Start agent workers locally
	$(PYTHON) scripts/run_agent_worker.py --config $(CONFIG)

run-sandbox: ## Start sandbox worker node locally
	$(PYTHON) scripts/run_sandbox_node.py --config $(CONFIG)

run-dashboard: ## Start the FastAPI dashboard locally
	aae-dashboard

run-demo: ## Run the deep integration demo script
	$(PYTHON) scripts/deep_integration_demo.py

run-learning: ## Run the learning pipeline on existing trajectories
	$(PYTHON) scripts/run_learning_pipeline.py --config $(CONFIG)

# ─── Cluster ──────────────────────────────────────────────────────────────────
deploy-k8s: ## Deploy AAE to Kubernetes cluster
	kubectl apply -f deployment/kubernetes/

scale-planners: ## Scale planner worker pods (usage: make scale-planners N=50)
	kubectl scale deployment aae-planner-worker --replicas=$(N)

scale-agents: ## Scale agent worker pods (usage: make scale-agents N=200)
	kubectl scale deployment aae-agent-worker --replicas=$(N)

scale-sandbox: ## Scale sandbox pods (usage: make scale-sandbox N=300)
	kubectl scale deployment aae-sandbox-worker --replicas=$(N)

# ─── Maintenance ──────────────────────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .artifacts/ htmlcov/ .coverage

clean-docker: ## Remove Docker images and volumes for AAE
	$(COMPOSE) down -v --rmi local

migrate: ## Run database migrations
	$(PYTHON) -c "from aae.persistence.db import PostgresDatabase; \
	  import os; db = PostgresDatabase(os.environ['AAE_DATABASE_URL']); \
	  print('DB ready:', db.enabled)"

# ─── Development Workflow ─────────────────────────────────────────────────────
dev: install-dev bootstrap ## Full local dev setup (install + bootstrap)
	@echo "Development environment ready."
	@echo "Run 'make run-controller' to start the controller."

ci: lint type-check test ## Full CI pipeline (lint + types + tests)
