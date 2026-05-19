#!/usr/bin/env python3
# ABOUTME: Cross-repo deploy: build Marimo app, copy to book repo's output dir.
# ABOUTME: Run after marimo_app.py changes to update the unified site preview.

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Marimo calculator and deploy to book repo's output dir."
    )
    parser.add_argument(
        "--book-repo",
        default="/Users/sohailmo/Documents/Sohailm25.github.io",
        help="Path to the Sohailm25.github.io repo (default: %(default)s)",
    )
    parser.add_argument(
        "--marimo-app",
        default="calculator/marimo_app.py",
        help="Path to the Marimo app entry point (default: %(default)s)",
    )
    parser.add_argument(
        "--venv-marimo",
        default=".venv/bin/marimo",
        help="Path to marimo CLI in the local venv (default: %(default)s)",
    )
    args = parser.parse_args()

    build_dir = Path("marimo-build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()

    print(f"[1/3] Building Marimo app: {args.marimo_app} -> {build_dir}/")
    res = subprocess.run(
        [args.venv_marimo, "export", "html-wasm", args.marimo_app, "-o", str(build_dir)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(f"BUILD FAILED:\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}")
        return 1
    print("  OK")

    book_repo = Path(args.book_repo)
    if not book_repo.exists():
        print(f"WARNING: book repo not found at {book_repo}")
        print("  Skipping copy step. Build is at marimo-build/ for manual handling.")
        return 0

    target = book_repo / "output" / "book" / "calculator"
    print(f"[2/3] Copying {build_dir}/ -> {target}/")
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(build_dir, target)
    print("  OK")

    print("[3/3] Done.")
    print(f"  Calculator deployed to: {target}/")
    print(f"  Local preview: cd {book_repo} && python -m http.server -d output 8000")
    print("    then open: http://localhost:8000/book/calculator/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
