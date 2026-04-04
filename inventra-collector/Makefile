.PHONY: isort black flake8 tests

PROJECT_PATH=.

isort:
	uv run isort $(ISORT_ARGS) $(PROJECT_PATH)

black:
	uv run black $(BLACK_ARGS) $(PROJECT_PATH)

flake8:
	uv run flake8 $(PROJECT_PATH)

tests:
	uv run pytest -v --cov=inventra_collector --cov-report=xml

lint: isort black flake8