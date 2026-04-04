## Working Agreements

### ./inventra-api

This is the main API of the project.

- Built with **Python 3.12**
- Dependency management is handled using **uv**

### Development Guidelines

After making any changes, always run the following commands:

- Format imports:
  `uv run isort .`

- Format code:
  `uv run black .`

- Lint:
  `uv run flake8 .`

- Run tests (with coverage):
  `uv run pytest -v --cov`

## Commits 

Follow this commit message pattern:

* `(type): <short description>`

where:
- `type` is `feat`, `fix` or `chore`
- The description must be consise and up to **100 characters**
- Use imperative mood (e.g, `add`, `fix`, `update`)