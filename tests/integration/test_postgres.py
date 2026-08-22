import os

import pytest

OWNER = os.environ.get("DATABASE_URL")
APP = os.environ.get("DATABASE_APP_URL")

if not (OWNER and APP):
    pytest.skip(
        "needs DATABASE_URL and DATABASE_APP_URL; run 'docker compose up -d'",
        allow_module_level=True,
    )

psycopg = pytest.importorskip("psycopg", reason="run 'pip install -e .'")


@pytest.fixture
def audit_table():
    name = "audit_probe"
    with psycopg.connect(OWNER, autocommit=True) as connection:
        connection.execute(f"DROP TABLE IF EXISTS {name}")
        connection.execute(
            f"CREATE TABLE {name} (id bigserial primary key, body text not null)"
        )
        connection.execute(f"GRANT SELECT, INSERT ON {name} TO cadence_app")
        connection.execute(f"REVOKE UPDATE, DELETE ON {name} FROM cadence_app")
        connection.execute(
            f"GRANT USAGE, SELECT ON SEQUENCE {name}_id_seq TO cadence_app"
        )
    yield name
    with psycopg.connect(OWNER, autocommit=True) as connection:
        connection.execute(f"DROP TABLE IF EXISTS {name}")


def test_the_database_is_reachable():
    with psycopg.connect(OWNER) as connection:
        assert connection.execute("select 1").fetchone() == (1,)


def test_the_application_role_is_not_the_owner():
    with psycopg.connect(APP) as connection:
        assert connection.execute("select current_user").fetchone()[0] == "cadence_app"


def test_the_application_can_append(audit_table):
    with psycopg.connect(APP, autocommit=True) as connection:
        connection.execute(f"insert into {audit_table}(body) values ('measured')")
        assert (
            connection.execute(f"select count(*) from {audit_table}").fetchone()[0] == 1
        )


def test_the_application_cannot_rewrite_history(audit_table):
    with psycopg.connect(APP, autocommit=True) as connection:
        connection.execute(f"insert into {audit_table}(body) values ('measured')")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(f"update {audit_table} set body = 'tampered'")


def test_the_application_cannot_erase_history(audit_table):
    with psycopg.connect(APP, autocommit=True) as connection:
        connection.execute(f"insert into {audit_table}(body) values ('measured')")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(f"delete from {audit_table}")
