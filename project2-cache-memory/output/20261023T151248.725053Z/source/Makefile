# Public report interface: acquisition always precedes analysis.
.DEFAULT_GOAL := all
.NOTPARALLEL:
PYTHON ?= ../.venv-analysis/bin/python
.PHONY: all benchmark plots
all benchmark plots:
	$(PYTHON) ../shared/report_pipeline.py $@ --project 2 --root . $(if $(RUN_DIR),--run-dir "$(RUN_DIR)",)
