## Working Agreements

### Project Structure

#### `./inventra-api`

This is the main API of the project.

- Built with **Python 3.12**
- Dependency management uses **uv**

#### `./inventra-collector`

This service consumes Kafka topics, scrapes data from external sources, parses the results, and publishes the processed data to another Kafka topic.

- Built with **Python 3.12**
- Dependency management uses **uv**

### Development Guidelines

Before running formatting, linting, or tests, change into the service directory you are working on.

After making changes, always run:

- Format imports: `uv run isort .`
- Format code: `uv run black .`
- Lint: `uv run flake8 .`
- Run tests with coverage: `uv run pytest -v --cov`

Do not skip these checks unless the user explicitly asks you to.

## Commits

Follow this commit message pattern:

- `(type): <short description>`

Where:

- `type` must be one of `feat`, `fix`, or `chore`
- The description must be concise and up to **100 characters**
- Use the imperative mood, for example: `add`, `fix`, `update`

## Pull Requests

- Always create a pull request for changes
- Never commit directly to the `main` branch
- Never push directly to the `main` branch
- Keep pull requests short, focused, and easy for humans to review
- If the work is too large or mixes concerns, split it into multiple pull requests when necessary
