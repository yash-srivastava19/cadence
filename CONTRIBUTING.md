# Contributing to Cadence

Contributions are welcome. This page is the whole setup: clone, one command,
and the tests pass.

## From clone to running

```bash
git clone https://github.com/yash-srivastava19/cadence && cd cadence
make dev
make test
```

`make dev` installs the dependencies with [uv](https://docs.astral.sh/uv/),
starts Postgres and Redis with `docker compose`, and migrates both the
development and the test database. Every step is safe to run again.

Without Docker, `make install` is enough for everything except the database
tests, which skip themselves when `TEST_DATABASE_URL` is not set.

| Command | What it does |
|---|---|
| `make dev` | Dependencies, database, schema. The one command after a clone |
| `make install` | Dependencies only |
| `make db` | Start the containers and migrate both databases |
| `make db-down` | Stop the containers, keeping the data |
| `make test` | Every test, with the URLs from `.env` |
| `make lint` | mypy, ruff, and the layer contract |
| `make fmt` | Format |
| `make coverage` | Tests with a coverage report |

CI runs `make lint`'s checks plus the full suite, so a green `make lint &&
make test` locally means a green pull request.

## What the checks enforce

- **ruff** formats and lints. There is no black and no flake8.
- **mypy** runs over the package.
- **import-linter** enforces the layering: `commands` → `delivery` →
  `control` → `execution` → `parsing` → `observe` → `core` → `lifecycle` →
  `errors`. A stage may know what is below it, never above.
- **The docs tests** (`tests/test_docs.py`) check the README against the
  code: every Python example parses, every script it tells you to run
  exists, and every environment variable it documents is one cadence reads.

## Changing the database schema

Migrations live in `cadence/migrations/`, inside the package, so an
installed cadence can create its own schema.

```bash
uv run alembic revision --autogenerate -m "what it does"
uv run cadence db upgrade --url "$TEST_DATABASE_URL"
```

Two things autogenerate will not write for you:

- **Grants.** `cadence/migrations/grants.py` says what the application role
  may do to each table, which is what makes "the log cannot be edited" an
  invariant rather than a habit. A new table needs a grant.
- **`EXPECTED_REVISION`** in `cadence/control/storage.py`. A test compares it
  with alembic's head, so a migration without it fails CI rather than
  somebody's first run.

## Pull requests

1. Branch from `main`.
2. Keep the change small enough to read. A big diff usually means the design
   is wrong.
3. Say *why* in the commit message. The code says what.
4. `make lint && make test` before pushing.

## Reporting issues

Use the issue templates. A report that says what you ran, what you expected
and what happened is worth more than a long description of either alone.
