"""Check the documentation against the code.

Compiles every Python example, resolves every symbol it imports, checks every
script it names exists, and checks every environment variable it names is read.

Opt a block out with ``<!-- docs-test: skip -->`` on the line before its fence.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest

REPO = Path(__file__).resolve().parent.parent
DOC_FILES = sorted(REPO.glob("docs/**/*.md")) + [REPO / "README.md"]

FENCE = re.compile(
    r"(?P<skip><!--\s*docs-test:\s*skip\s*-->\s*\n)?"
    r"^```(?P<lang>[\w-]*)[^\n]*\n(?P<body>.*?)^```",
    re.MULTILINE | re.DOTALL,
)
IMPORT = re.compile(
    r"^\s*(?:from\s+(?P<mod>(?:src|cadence)[\w.]*)\s+import\s+(?P<names>[^\n#]+)"
    r"|import\s+(?P<plain>(?:src|cadence)[\w.]*))",
    re.MULTILINE,
)
ENV_VAR = re.compile(r"\b(CADENCE_[A-Z0-9_]+|[A-Z0-9_]*API_KEY)\b")
SCRIPT = re.compile(r"^\s*(?:\$\s*)?python3?\s+(?P<path>[\w./-]+\.py)", re.MULTILINE)
ALLOW_ENV = re.compile(r"<!--\s*docs-test:\s*allow-env\s+(?P<names>[^>]+?)\s*-->")

# Placeholders and other vendors' keys, plus two names the docs mention only to
# say Cadence does not use them.
ENV_ALLOWED_IN_PROSE = {
    "YOUR_API_KEY",
    "OPENAI_API_KEY",
    "CO_API_KEY",
    "GOOGLE_API_KEY",
    "GENAI_API_KEY",
}


@dataclass(frozen=True)
class Block:
    doc: Path
    line: int
    lang: str
    body: str

    def __str__(self) -> str:  # what pytest -v prints
        return f"{self.doc.relative_to(REPO)}:{self.line}"


def _blocks(lang: str | None = None) -> Iterator[Block]:
    for doc in DOC_FILES:
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        for m in FENCE.finditer(text):
            if m.group("skip"):
                continue
            if lang is not None and m.group("lang") != lang:
                continue
            yield Block(
                doc=doc,
                line=text.count("\n", 0, m.start("body")) + 1,
                lang=m.group("lang"),
                body=m.group("body"),
            )


def _module_path(dotted: str) -> Path | None:
    base = REPO / Path(dotted.replace(".", "/"))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def _public_names(path: Path) -> set[str]:
    """Top-level names a module exports. Static, so importing has no side effects."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(a.asname or a.name.split(".")[0] for a in node.names)
    return names


PY_BLOCKS = list(_blocks("python"))
assert PY_BLOCKS, "no ```python blocks found -- the extractor is broken, not the docs"


@pytest.mark.parametrize("block", PY_BLOCKS, ids=str)
def test_python_example_is_valid_python(block: Block) -> None:
    """A reader copies this, so it has to parse."""
    try:
        compile(block.body, str(block.doc), "exec")
    except SyntaxError as exc:
        pytest.fail(
            f"{block} is not valid Python: {exc.msg} (example line {exc.lineno})\n"
            f"  {(exc.text or '').strip()}"
        )


def _documented_imports() -> list[tuple[Path, int, str, list[str]]]:
    found = []
    for doc in DOC_FILES:
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        for m in IMPORT.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            if m.group("plain"):
                found.append((doc, line, m.group("plain"), []))
                continue
            raw = m.group("names").split(" as ")[0]
            names = [n.strip() for n in raw.strip(" ()").split(",") if n.strip()]
            found.append((doc, line, m.group("mod"), names))
    return found


@pytest.mark.parametrize(
    "doc,line,module,names",
    _documented_imports(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_documented_import_resolves(
    doc: Path, line: int, module: str, names: list[str]
) -> None:
    """Every symbol the docs import exists, under the name the docs use."""
    where = f"{doc.relative_to(REPO)}:{line}"
    path = _module_path(module)
    assert path is not None, f"{where} imports `{module}`, which does not exist"

    if not names or names == ["*"]:
        return
    exported = _public_names(path)
    missing = [n for n in names if n not in exported]
    assert not missing, (
        f"{where} imports {missing} from `{module}`, which does not define "
        f"{'them' if len(missing) > 1 else 'it'}"
    )


@pytest.mark.parametrize("doc", DOC_FILES, ids=lambda p: str(p.relative_to(REPO)))
def test_referenced_scripts_exist(doc: Path) -> None:
    """`python foo.py` in the docs means foo.py is in the repo."""
    if not doc.exists():
        pytest.skip(f"{doc.name} not present")
    missing = {
        m.group("path")
        for m in SCRIPT.finditer(doc.read_text(encoding="utf-8"))
        if not (REPO / m.group("path")).exists()
    }
    assert not missing, f"{doc.relative_to(REPO)} tells you to run {sorted(missing)}"


def _source_text() -> str:
    parts = []
    for pattern in ("src/**/*.py", "cadence/**/*.py", "*.py", "conf/*.yaml"):
        for f in REPO.glob(pattern):
            if ".venv" in f.parts or "venv" in f.parts:
                continue
            parts.append(f.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


@pytest.mark.parametrize("doc", DOC_FILES, ids=lambda p: str(p.relative_to(REPO)))
def test_documented_env_vars_are_read(doc: Path) -> None:
    """An environment variable in the docs is one the code actually reads."""
    if not doc.exists():
        pytest.skip(f"{doc.name} not present")
    source = _source_text()
    text = doc.read_text(encoding="utf-8")
    declared = {
        name.strip()
        for m in ALLOW_ENV.finditer(text)
        for name in m.group("names").split(",")
    }
    allowed = ENV_ALLOWED_IN_PROSE | declared
    documented = set(ENV_VAR.findall(text))
    invented = sorted(v for v in documented - allowed if v not in source)
    assert not invented, (
        f"{doc.relative_to(REPO)} documents {invented}, which nothing reads. "
        f"Delete the claim, implement it, or -- if the page names it in order "
        f"to say it does not exist -- declare it with "
        f"`<!-- docs-test: allow-env NAME,NAME -->`."
    )
