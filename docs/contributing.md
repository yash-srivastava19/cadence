# Contributing

Cadence is alpha software. A contribution is complete when the code, tests, and documentation agree about the behavior.

## Set up

```bash
git clone https://github.com/yash-srivastava19/cadence
cd cadence
make dev
```

Without Docker, use `make install`; database integration tests skip when `TEST_DATABASE_URL` is not set.

## Checks

```bash
make lint
make test
```

The checks include mypy, ruff, import-linter, unit tests, integration tests, and documentation tests. The documentation tests compile Python examples, check referenced scripts, and check that documented environment variables are read by Cadence.

## Documentation changes

Choose the page type that matches the reader's need:

- **Tutorials** teach a complete learning journey.
- **Guides** solve one practical problem.
- **Concepts** explain why the system behaves as it does.
- **Reference** states exact commands, fields, and values.
- **Research** records evidence and limitations from real runs.

Keep examples copyable. State whether a behavior is current, experimental, deprecated, or planned. If a command, manifest field, verdict, or environment variable changes, update its reference page and the relevant guide in the same change.

## Database migrations

Migrations live in `cadence/migrations/` inside the package:

```bash
uv run alembic revision --autogenerate -m "what it does"
uv run cadence db upgrade --url "$TEST_DATABASE_URL"
```

Autogenerate does not write grants. Update `cadence/migrations/grants.py` for a new table. Also update `EXPECTED_REVISION` in `cadence/control/storage.py`; CI checks it against Alembic's head.

## Pull requests

1. Branch from `main`.
2. Keep the change small enough to read.
3. Explain why in the commit message; the code says what.
4. Run `make lint && make test` before pushing.

Use the issue templates when reporting a problem. Include what you ran, what you expected, and what happened.
