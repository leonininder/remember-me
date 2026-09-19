.PHONY: install test cov lint demo bakeoff clean

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
PIP ?= $(PYTHON) -m pip

install:
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

cov:
	$(PYTHON) -m pytest -q --cov=remember_me --cov-report=term-missing

lint:
	$(PYTHON) -m ruff check src tests

demo:
	@command -v remember-me >/dev/null 2>&1 && remember-me demo || $(PYTHON) -m remember_me.cli demo

bakeoff:
	@command -v remember-me >/dev/null 2>&1 && remember-me bakeoff --out bakeoff_metrics.json || $(PYTHON) -m remember_me.cli bakeoff --out bakeoff_metrics.json

clean:
	rm -rf .pytest_cache .coverage htmlcov dist build *.egg-info bakeoff_metrics.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
