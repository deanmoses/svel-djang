from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.analytics

DUCKDB = shutil.which("duckdb")
RUNNER = Path(__file__).parents[3] / "scripts" / "analysis" / "analysis"


def query(database: Path, sql: str) -> str:
    assert DUCKDB is not None
    result = subprocess.run(
        [DUCKDB, "-noheader", "-list", database, sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def table_names(database: Path) -> list[str]:
    return query(
        database, "SELECT table_name FROM duckdb_tables() ORDER BY table_name;"
    ).splitlines()


@pytest.fixture(scope="session")
def runner_env(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Run the analysis runner against a throwaway empty catalog.

    Its defaults are the developer's own ``db.sqlite3`` and ``db.analytics.duckdb``.
    Pointing both somewhere else leaves that snapshot alone and drops what these
    tests spend on rows they never read: they assert on relation names and
    structure, while ``browse`` materializes every public relation -- over the real
    catalog, a hundred and thirty megabytes, three times in one test.

    Migrating the source rather than reusing the real one also keeps the schema the
    build reads in step with the migrations in the tree, which is what makes these
    tests the gate on foundation-vs-model drift.
    """
    workdir = tmp_path_factory.mktemp("analysis")
    source = workdir / "catalog.sqlite3"
    migrate = subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput"],
        cwd=Path(__file__).parents[2],
        env={**os.environ, "DATABASE_URL": f"sqlite:///{source}"},
        capture_output=True,
        text=True,
    )
    assert migrate.returncode == 0, (
        f"migrating the throwaway catalog failed:\n{migrate.stderr}"
    )
    return {
        **os.environ,
        "FLIPCOMMONS_ANALYSIS_SOURCE_DB": str(source),
        "FLIPCOMMONS_ANALYSIS_SNAPSHOT": str(workdir / "analytics.duckdb"),
    }


@pytest.mark.skipif(DUCKDB is None, reason="DuckDB CLI is not installed")
def test_browse_materializes_public_relations_and_replaces_previous_output(
    tmp_path: Path, runner_env: dict[str, str]
) -> None:
    analysis = tmp_path / "example.sql"
    output = tmp_path / "example.browse.duckdb"
    analysis.write_text(
        """
        CREATE VIEW visible AS SELECT 1 AS value;
        COMMENT ON VIEW visible IS 'One row, for the counter to find.';
        CREATE TABLE materialized AS SELECT 2 AS value;
        CREATE VIEW _private AS SELECT 2 AS value;
        """,
    )

    first = subprocess.run(
        [RUNNER, "browse", analysis],
        env=runner_env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert output.exists()
    # The counts cover the analysis's own relations PLUS the baked foundation's, and
    # the foundation's number moves with the schema — so the message is shape-checked
    # and the analysis's own relations are asserted by name.
    assert re.fullmatch(
        rf"wrote {re.escape(str(output))} \(\d+ public relations, \d+ documented\)",
        first.stdout.strip(),
    )
    names = table_names(output)
    assert "visible" in names
    assert "materialized" in names
    assert "_private" not in names
    # A foundation relation rides along: a campaign export is self-contained.
    assert "models" in names
    assert query(output, "SELECT value FROM visible;") == "1"

    analysis.write_text(
        """
        CREATE VIEW visible AS SELECT 3 AS value;
        CREATE VIEW added AS SELECT 4 AS value;
        """,
    )
    subprocess.run(
        [RUNNER, "browse", analysis],
        env=runner_env,
        check=True,
        capture_output=True,
        text=True,
    )

    names = table_names(output)
    assert "added" in names
    assert "materialized" not in names
    assert query(output, "SELECT value FROM visible;") == "3"

    analysis.write_text(
        "CREATE VIEW visible AS SELECT error('refresh failed') AS value;",
    )
    failed = subprocess.run(
        [RUNNER, "browse", analysis],
        env=runner_env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert failed.returncode != 0
    assert query(output, "SELECT value FROM visible;") == "3"
    assert list(tmp_path.glob("*.tmp.*")) == []


def describe(env: dict[str, str]) -> str:
    return subprocess.run(
        [RUNNER, "describe"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.mark.skipif(DUCKDB is None, reason="DuckDB CLI is not installed")
def test_describe_groups_the_foundation_and_leads_with_the_spine(
    runner_env: dict[str, str],
) -> None:
    relations, _, macros = describe(runner_env).partition("— macros —")

    headers = [ln for ln in relations.splitlines() if ln.startswith("═══")]
    assert headers, "the foundation listing is not grouped"
    # §10 is the spine, and the audit is a lint layer numbered far below it.
    # Alphabetically the audit sorts first, which is the defect being guarded against.
    assert headers[0].startswith("═══ MODELS")
    assert next(i for i, h in enumerate(headers) if h.startswith("═══ AUDIT")) > 0

    # The regression: a reopened DuckDB database hands back catalog oids in NAME order,
    # so ordering the listing by oid silently means ordering it alphabetically.
    names = [
        ln for ln in relations.splitlines() if ln and not ln.startswith((" ", "═"))
    ]
    assert names.index("models") < min(
        i for i, n in enumerate(names) if n.startswith("audit_")
    )
    assert macros, "macros are still listed"


@pytest.mark.skipif(DUCKDB is None, reason="DuckDB CLI is not installed")
def test_every_public_relation_is_grouped(runner_env: dict[str, str]) -> None:
    # UNGROUPED is what a relation the index missed lists under, so its absence is the
    # anchor for the source parse behind the index: a rotted regex empties the groups.
    assert "UNGROUPED" not in describe(runner_env)
