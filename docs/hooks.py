"""Copy agent discovery resources that MkDocs excludes from normal pages."""

from pathlib import Path
from shutil import copytree


def on_post_build(*, config: object, **_: object) -> None:
    docs = Path("docs")
    site_dir = Path(str(config.site_dir))
    target = site_dir / ".well-known"
    copytree(docs / ".well-known", target, dirs_exist_ok=True)
    skill = Path("plugins/cadence/skills/cadence/SKILL.md")
    (target / "skills" / "cadence").mkdir(parents=True, exist_ok=True)
    (target / "skills" / "cadence" / "SKILL.md").write_text(
        skill.read_text(encoding="utf-8"), encoding="utf-8"
    )

    pages = []
    for page in sorted(docs.rglob("*.md")):
        if ".well-known" in page.parts:
            continue
        relative = page.relative_to(docs)
        content = page.read_text(encoding="utf-8")
        pages.append(f"\n\n---\n\n# {relative}\n\n{content}")
    (site_dir / "llms-full.txt").write_text(
        "# Cadence documentation\n" + "".join(pages), encoding="utf-8"
    )
