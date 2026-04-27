"""Rename Ninja schema classes across backend/**/*.py.

Reads the rename table from frontend/scripts/codemod/rename-table.json and
rewrites every matching `class OldName(...)` declaration plus every Name
reference (imports, annotations, decorator args, attribute bases, …) to
NewName. Uses libcst so comments and formatting survive.

Restrict a run to a subset with `--names OldA,OldB,...` — without it the
whole table is applied (used in CI / one-shot runs; per-PR batches always
pass the explicit list).

Out of scope: string-literal references (fixture data, admin field configs,
`extra_data` JSON). Those are caught by `make test` per the plan; libcst
Name nodes don't span strings.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import libcst as cst

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent.parent
RENAME_TABLE = BACKEND.parent / "frontend" / "scripts" / "codemod" / "rename-table.json"


class RenameTransformer(cst.CSTTransformer):
    def __init__(self, rename_map: dict[str, str]) -> None:
        super().__init__()
        self.rename_map = rename_map

    def leave_Name(  # noqa: N802 — libcst dispatch method name
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.Name:
        new = self.rename_map.get(updated_node.value)
        if new is None:
            return updated_node
        return updated_node.with_changes(value=new)


def load_rename_map(names_filter: list[str] | None) -> dict[str, str]:
    full: dict[str, str] = json.loads(RENAME_TABLE.read_text())
    if names_filter is None:
        return full
    missing = [n for n in names_filter if n not in full]
    if missing:
        sys.exit(f"--names entries not in rename table: {missing}")
    return {k: full[k] for k in names_filter}


def iter_python_files() -> list[Path]:
    return [
        p
        for p in BACKEND.rglob("*.py")
        if ".venv" not in p.parts
        and "node_modules" not in p.parts
        and "__pycache__" not in p.parts
    ]


def rewrite_file(path: Path, transformer: RenameTransformer) -> bool:
    src = path.read_text()
    # Cheap pre-filter: skip files that don't contain any old name as a
    # substring. Avoids parsing every backend .py file.
    if not any(name in src for name in transformer.rename_map):
        return False
    module = cst.parse_module(src)
    new_module = module.visit(transformer)
    if new_module.code == src:
        return False
    path.write_text(new_module.code)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--names",
        help="Comma-separated subset of OldName entries from rename-table.json. "
        "Omit to apply the whole table.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report files that would change; write nothing.",
    )
    args = parser.parse_args()

    names_filter = (
        [n.strip() for n in args.names.split(",") if n.strip()] if args.names else None
    )
    rename_map = load_rename_map(names_filter)
    transformer = RenameTransformer(rename_map)

    print(f"Renaming {len(rename_map)} schema(s) across backend/**/*.py")
    for old, new in rename_map.items():
        print(f"  {old} -> {new}")

    changed: list[Path] = []
    for path in iter_python_files():
        src = path.read_text()
        if not any(name in src for name in rename_map):
            continue
        module = cst.parse_module(src)
        new_module = module.visit(transformer)
        if new_module.code == src:
            continue
        changed.append(path)
        if not args.dry_run:
            path.write_text(new_module.code)

    verb = "Would rewrite" if args.dry_run else "Rewrote"
    print(f"{verb} {len(changed)} file(s):")
    for p in changed:
        print(f"  {p.relative_to(BACKEND)}")


if __name__ == "__main__":
    main()
