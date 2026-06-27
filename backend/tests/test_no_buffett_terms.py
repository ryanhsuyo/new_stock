from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_TERMS = ("buf" + "fett", "Buf" + "fett", "巴" + "菲特")
SCAN_DIRS = (
    ROOT / "backend" / "app",
    ROOT / "backend" / "scripts",
    ROOT / "backend" / "tests",
    ROOT / "backend" / "docs",
    ROOT / "frontend" / "src",
    ROOT / "frontend" / "tests",
)
SCAN_FILES = (
    ROOT / "README.md",
    ROOT / "backend" / "README.md",
)


def _iter_text_files():
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {
                ".css",
                ".md",
                ".mjs",
                ".py",
                ".ts",
                ".tsx",
            }:
                yield path
    for path in SCAN_FILES:
        if path.exists():
            yield path


def test_project_has_no_forbidden_legacy_terms():
    matches: list[str] = []
    for path in _iter_text_files():
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(term in line for term in FORBIDDEN_TERMS):
                rel = path.relative_to(ROOT)
                matches.append(f"{rel}:{lineno}:{line.strip()}")

    assert not matches, "\n".join(matches[:80])
