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

    # Target is content/extra/book/calculator/ so Pelican's EXTRA_PATH_METADATA
    # walker (in book repo's pelicanconf.py:35-42) picks the files up as static
    # content. Pelican's CI uses DELETE_OUTPUT_DIRECTORY=True so committing
    # directly to output/ would be wiped on every build.
    target = book_repo / "content" / "extra" / "book" / "calculator"
    print(f"[2/3] Copying {build_dir}/ -> {target}/")
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(build_dir, target)
    print("  OK")

    print("[3/3] Done.")
    print(f"  Calculator copied to: {target}/")
    print("  Next:")
    print(f"    cd {book_repo}")
    print("    git add content/extra/book/calculator/")
    print(f"    git commit -m 'feat(book): redeploy Marimo calculator'")
    print("    git push origin master")
    print("  GitHub Actions will rebuild Pelican + serve at sohailmo.ai/book/calculator/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
