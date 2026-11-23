import ast
from pathlib import Path

DOMAIN = Path(__file__).resolve().parents[2] / "src" / "cloneclient" / "domain"
FORBIDDEN = ("cloneclient.ui", "cloneclient.services", "cloneclient.infrastructure")


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_domain_does_not_import_outer_layers() -> None:
    for path in DOMAIN.rglob("*.py"):
        for name in imports(path):
            assert not name.startswith(FORBIDDEN), f"{path} imports {name}"
