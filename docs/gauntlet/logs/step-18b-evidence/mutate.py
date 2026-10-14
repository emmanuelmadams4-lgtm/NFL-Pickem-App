"""Tiny stdlib mutation sweep for backend/nflpi/betting (step 18b). Run from backend/:

    DATABASE_URL=... python ../docs/gauntlet/logs/step-18b-evidence/mutate.py [budget_seconds]

One mutation at a time is written into the package file, the three betting test files run, the file is restored.
A mutant that the tests do not fail is a SURVIVOR and is printed. Mutations: comparison swaps, arithmetic swaps,
and/or swaps, True/False flips, number +1 nudges, `not` removal, return-value-to-None for numeric returns.
"""

import ast
import random
import subprocess
import sys
import time
from pathlib import Path

PKG = Path("nflpi/betting")
TESTS = ["tests/test_betting_odds.py", "tests/test_betting_settle.py", "tests/test_betting_edge.py"]
CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
ARITH = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}


class Mutator(ast.NodeTransformer):
    """Applies exactly the Nth mutation site, counting sites in visit order."""

    def __init__(self, target: int):
        self.target, self.count, self.desc = target, 0, ""

    def _hit(self, desc: str, line: int) -> bool:
        hit = self.count == self.target
        if hit:
            self.desc = f"line {line}: {desc}"
        self.count += 1
        return hit

    def visit_Compare(self, node):
        self.generic_visit(node)
        for i, op in enumerate(node.ops):
            if type(op) in CMP and self._hit(f"{type(op).__name__}->{CMP[type(op)].__name__}", node.lineno):
                node.ops[i] = CMP[type(op)]()
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if type(node.op) in ARITH and self._hit(f"{type(node.op).__name__}->{ARITH[type(node.op)].__name__}", node.lineno):
            node.op = ARITH[type(node.op)]()
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if self._hit("and<->or", node.lineno):
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self._hit("drop not", node.lineno):
            return node.operand
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            if self._hit(f"{node.value}->{not node.value}", node.lineno):
                return ast.copy_location(ast.Constant(not node.value), node)
        elif isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if self._hit(f"{node.value}->{node.value + 1}", node.lineno):
                return ast.copy_location(ast.Constant(node.value + 1), node)
        return node


def count_sites(tree_src: str) -> int:
    m = Mutator(-1)
    m.visit(ast.parse(tree_src))
    return m.count


def run_tests() -> bool:
    r = subprocess.run(
        ["uv", "run", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
        capture_output=True, text=True, timeout=300,
    )
    return r.returncode == 0  # True = tests passed = mutant survived


def main() -> None:
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 540
    files = sorted(p for p in PKG.glob("*.py") if p.name != "__init__.py")
    jobs = []
    for f in files:
        src = f.read_text()
        jobs += [(f, src, n) for n in range(count_sites(src))]
    random.Random(18).shuffle(jobs)
    start, killed, survivors, tried = time.time(), 0, [], 0
    for f, src, n in jobs:
        if time.time() - start > budget:
            break
        m = Mutator(n)
        tree = ast.fix_missing_locations(m.visit(ast.parse(src)))
        try:
            f.write_text(ast.unparse(tree) + "\n")
            tried += 1
            if run_tests():
                survivors.append(f"{f.name} {m.desc}")
                print("SURVIVOR", f.name, m.desc, flush=True)
            else:
                killed += 1
        finally:
            f.write_text(src)
    print(f"sites={len(jobs)} tried={tried} killed={killed} survivors={len(survivors)} secs={time.time() - start:.0f}")


if __name__ == "__main__":
    main()
