#!/usr/bin/env python3
import ast
import sys
from pathlib import Path


def radon_cc(path):
    try:
        from radon.complexity import cc_visit
    except ImportError:
        return None
    total = 0
    for file in Path(path).rglob("*.py"):
        if "tests" in str(file) or "venv" in str(file):
            continue
        with open(file, "r", encoding="utf-8") as f:
            try:
                nodes = cc_visit(f.read())
                for node in nodes:
                    total += node.complexity
            except Exception:
                pass
    return total


def docstring_coverage(path):
    total_functions = 0
    documented = 0
    for file in Path(path).rglob("*.py"):
        if "tests" in str(file) or "venv" in str(file):
            continue
        with open(file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                total_functions += 1
                if ast.get_docstring(node):
                    documented += 1
    return documented / total_functions if total_functions else 1.0


def main():
    root = Path(__file__).parent.parent
    coverage = docstring_coverage(root)
    cc = radon_cc(root)
    print(f"Docstring coverage: {coverage * 100:.1f}%")
    if cc is not None:
        print(f"Total cyclomatic complexity: {cc}")
    else:
        print("radon not installed, skip complexity.")

    if coverage < 0.2:
        print("Docstring coverage below 20%")
        sys.exit(1)
    if cc is not None and cc > 150:
        print("Complexity is high, consider refactoring.")


if __name__ == "__main__":
    main()
