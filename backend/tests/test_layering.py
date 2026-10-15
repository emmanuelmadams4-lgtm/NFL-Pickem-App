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


def test_no_cross_package_private_imports():
    bad = []
    for path, rel, tree in _modules():
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("nflpi.")):
                continue
            target = node.module.split(".")[1]
            if target != _package(rel) and any(a.name.startswith("_") for a in node.names):
                bad.append(f"{path.name}: from {node.module} import {[a.name for a in node.names]}")
    assert not bad, bad


def test_no_cross_package_private_attribute_use():
    bad = []
    for path, rel, tree in _modules():
        imported = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("nflpi."):
                for a in node.names:
                    imported[a.asname or a.name] = node.module.split(".")[1]
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr.startswith("_")
                and not node.attr.startswith("__")
                and isinstance(node.value, ast.Name)
                and imported.get(node.value.id, _package(rel)) != _package(rel)
                and node.value.id in imported
            ):
                bad.append(f"{path.name}: {node.value.id}.{node.attr}")
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
