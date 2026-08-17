# Elemes Test Suite — Unified Test Runner
#
# Usage:
#   make test-unit          # Unit tests only (fast, no DB, for dev loop)
#   make test-integration   # Integration tests (needs PostgreSQL test DB)
#   make test-all           # Full suite (CI only)
#   make test-smoke         # Smoke test post-deploy
#   make test-list          # List collected tests
#   make test-stats         # Count tests by marker
#
# Env:
#   DATABASE_URL  Required for integration tests (set elemes_test DB)
#   PYTHONPATH    Defaults to services for backend tests
#
# Jika DATABASE_URL tidak diset, integration test yang butuh DB akan otomatis
# di-skip via skipif. test-integration tetap berjalan untuk test yang tidak
# butuh DB (mis. Flask test client tanpa DB).

PYTHON ?= python3
PYTHONPATH ?= services
PYTEST ?= $(PYTHON) -m pytest
export PYTHONPATH

# --- Default (backward-compat): `make test` = test-all ---

.PHONY: test test-unit test-integration test-all test-worker test-smoke test-shell test-list test-stats help

help:
	@echo "Elemes Test Suite:"
	@echo "  make test-unit         Unit tests only (fast, no DB needed)"
	@echo "  make test-integration  Integration tests (needs postgresql test DB)"
	@echo "  make test-all          Full suite (CI only)"
	@echo "  make test-worker       Compiler worker tests (separate project)"
	@echo "  make test-smoke        # Smoke test post-deploy (unit + sub-home subset)"
	@echo "  make test-shell        # Shell regression test (elemes.sh structure)"
	@echo "  make test-list         List collected tests"
	@echo "  make test-stats        Show test counts by marker"

## test-all is the default (backward compat: `make test` == `make test-all`)
test: test-all

## Unit tests only — pure logic, no DB, fast
test-unit:
	$(PYTEST) -m unit -v

## Integration tests — requires PostgreSQL test DB (elemes_test)
test-integration:
	$(PYTEST) -m integration -v

## Full suite (services) — all markers, CI gate
test-all:
	$(PYTEST) -v

## Compiler worker tests (separate project, separate PYTHONPATH)
test-worker:
	cd compiler_worker && PYTHONPATH=. $(PYTEST) -v


## Smoke test — minimal subset, runs inside container post-build
test-smoke:
	$(PYTEST) -m unit -v
	$(PYTEST) services/tests/test_sub_home.py services/tests/test_sub_home_api.py -v

## Shell regression test — elemes.sh structure (dynamic PROJECT_NAME, no hard-coded names)
test-shell:
	bash scripts/test_elemes_sh.sh

## List collected tests
test-list:
	$(PYTEST) --collect-only -q

## Show test counts by marker
test-stats:
	@echo "=== Test counts by marker ==="
	@$(PYTEST) --collect-only -q -m unit 2>/dev/null | grep -c "test" || echo "0"
	@echo "^ unit tests"
	@$(PYTEST) --collect-only -q -m integration 2>/dev/null | grep -c "test" || echo "0"
	@echo "^ integration tests"
	@$(PYTEST) --collect-only -q 2>/dev/null | tail -1
