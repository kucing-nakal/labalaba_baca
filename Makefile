PYTHON_VERSION=python3.13.3
VENV_NAME=laba2_baca
PYTHON_BIN=$(VENV_NAME)/bin/python
PIP=$(VENV_NAME)/bin/pip

.PHONY: help venv install clean

help:
	@echo "Available targets:"
	@echo "  make venv      - Create uv virtual environment named $(VENV_NAME)"
	@echo "  make install   - Install packages into the venv"
	@echo "  make clean     - Remove the virtual environment"
	@echo ""
	@echo "To activate it:"
	@echo "  source $(VENV_NAME)/bin/activate"

venv:
	uv venv $(VENV_NAME)

install: venv
	uv pip install --python $(PYTHON_BIN) \
		httpx beautifulsoup4 GitPython google-generativeai

clean:
	rm -rf $(VENV_NAME)

activate:
	 source ${VENV_NAME}/bin/activate
