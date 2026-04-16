.PHONY: generate validate export split test test-schema test-api test-mesh clean stats

PYTHON ?= python3
EXAMPLES_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(EXAMPLES_DIR)/..

generate:
	cd $(PROJECT_ROOT) && $(PYTHON) -m examples.generate generate

validate:
	cd $(PROJECT_ROOT) && $(PYTHON) -m examples.generate validate

export:
	cd $(PROJECT_ROOT) && $(PYTHON) -m examples.generate export

split:
	cd $(PROJECT_ROOT) && $(PYTHON) -m examples.generate split

stats:
	cd $(PROJECT_ROOT) && $(PYTHON) -m examples.generate stats

# Full pipeline
all: generate validate export split
	@echo "Pipeline complete."

# Tests
test-schema:
	cd $(PROJECT_ROOT) && $(PYTHON) -m pytest examples/tests/test_schema_validation.py -v

test-api:
	cd $(PROJECT_ROOT) && docker compose -f examples/tests/docker/docker-compose.single.yml up -d --wait
	cd $(PROJECT_ROOT) && $(PYTHON) -m pytest examples/tests/test_api_submission.py -v
	cd $(PROJECT_ROOT) && docker compose -f examples/tests/docker/docker-compose.single.yml down

test-mesh:
	cd $(PROJECT_ROOT) && docker compose -f examples/tests/docker/docker-compose.mesh3.yml up -d --wait
	cd $(PROJECT_ROOT) && $(PYTHON) -m pytest examples/tests/test_execution_mesh.py -v
	cd $(PROJECT_ROOT) && docker compose -f examples/tests/docker/docker-compose.mesh3.yml down

test: test-schema

clean:
	rm -rf $(EXAMPLES_DIR)/output/
