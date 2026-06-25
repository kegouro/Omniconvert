PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: help install install-all gui test test-fast lint format clean

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "%-12s %s\n", $$1, $$2}'

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

install: $(BIN)/python ## Instala el paquete en modo editable + deps de desarrollo
	$(BIN)/pip install -e ".[dev]"

install-all: $(BIN)/python ## Igual que install, más los extras (extended, OCR, GUI)
	$(BIN)/pip install -e ".[dev,extended,ocr,gui]"

gui: ## Abre la interfaz gráfica
	$(BIN)/python -m omni_convert gui

test: ## Ejecuta los tests
	$(BIN)/pytest

test-fast: ## Ejecuta los tests en paralelo (pytest-xdist)
	$(BIN)/pytest -n auto

lint: ## Revisa estilo y errores con ruff
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests

format: ## Formatea el código y aplica fixes automáticos
	$(BIN)/ruff format src tests
	$(BIN)/ruff check --fix src tests

clean: ## Elimina venv, cachés y artefactos de build
	rm -rf $(VENV) build dist *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
