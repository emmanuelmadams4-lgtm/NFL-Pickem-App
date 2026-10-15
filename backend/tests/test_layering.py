"""Layering gate (step 13b): no module reaches into another package's private names."""

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "nflpi"
LOWER_LAYERS = ("predictions", "analytics", "notify")


def _modules():
    for path in sorted(PKG.rglob("*.py")):
        rel = path.relative_to(PKG).with_suffix("").parts
        yield path, rel, ast.parse(path.read_text())


def _package(parts: tuple[str, ...]) -> str:
    return parts[0] if len(parts) > 1 else ""


def private_reaches(rel: tuple[str, ...], tree: ast.AST) -> list[str]:
    """Find private names reached through another nflpi package."""
    current = _package(rel)
    imported: dict[str, str] = {}
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                parts = rel[:-node.level] + tuple((node.module or "").split(".")) if node.module else rel[:-node.level]
                target = parts[0] if parts else ""
            elif node.module == "nflpi":
                target = ""
            elif node.module and node.module.startswith("nflpi."):
                target = node.module.split(".")[1]
            else:
                continue
            for alias in node.names:
                package = alias.name if (node.module == "nflpi" and not node.level) or (
                    node.level and not node.module and not parts
                ) else target
                imported[alias.asname or alias.name] = package
                if package and package != current and alias.name.startswith("_") and not alias.name.startswith("__"):
                    bad.append(f"import {alias.name} from {package}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("nflpi."):
                    imported[alias.asname or "nflpi"] = alias.name.split(".")[1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            name, attr = node.value.id, node.attr
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr"
              and len(node.args) >= 2 and isinstance(node.args[0], ast.Name)
              and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
            name, attr = node.args[0].id, node.args[1].value
        else:
            continue
        if (name in imported and imported[name] != current and attr.startswith("_")
                and not attr.startswith("__")):
            bad.append(f"{name}.{attr}")
    return bad


def test_no_cross_package_private_imports():
    bad = [f"{path.name}: {reach}" for path, rel, tree in _modules()
           for reach in private_reaches(rel, tree) if reach.startswith("import ")]
    assert not bad, bad


def test_no_cross_package_private_attribute_use():
    bad = [f"{path.name}: {reach}" for path, rel, tree in _modules()
           for reach in private_reaches(rel, tree) if not reach.startswith("import ")]
    assert not bad, bad


def test_lower_layers_do_not_import_api_views():
    bad = []
    for path, rel, tree in _modules():
        if _package(rel) not in LOWER_LAYERS:
            continue
        for node in ast.walk(tree):
            names = [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            if isinstance(node, ast.ImportFrom) and node.module == "nflpi.api":
                names += [f"nflpi.api.{a.name}" for a in node.names]
            bad += [f"{path.name}: {n}" for n in names if n in ("nflpi.api.views", "nflpi.api.readmodels")]
    assert not bad, bad


def test_notify_does_not_pull_in_pandas_for_a_dataclass():
    from nflpi.predictions import events

    assert events.ChangeEvent.__module__ == "nflpi.predictions.events"
    tree = ast.parse(Path(events.__file__).read_text())
    imports = [n for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)]
    assert [getattr(n, "module", None) for n in imports] == ["dataclasses"]
