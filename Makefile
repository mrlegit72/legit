PYTHON=python3
VENV=.venv
PIP=$(VENV)/bin/pip
PY=$(VENV)/bin/python

setup:
python3 -m venv $(VENV)
$(PIP) install --upgrade pip
$(PIP) install -r requirements.txt

train:
$(PY) -m phishguard.cli train --data ./data/emails.csv

evaluate:
$(PY) -m phishguard.cli evaluate --data ./data/emails.csv

predict:
$(PY) -m phishguard.cli predict --subject "Test" --body "Hello" --from_address "Tester <tester@example.com>" --json

lint:
$(PY) -m compileall phishguard tests

test:
$(PY) -m pytest -q

.PHONY: setup train evaluate predict lint test
