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

    # Marimo's WASM runtime (Pyodide) doesn't have access to the local
    # filesystem, so `from calculator.X import Y` fails. Run the bundler first
    # to produce a self-contained file that inlines the calculator package
    # + provider_pricing.yaml + marimo-theme.css.
    print("[1/5] Bundling calculator package into marimo_app_wasm.py")
    res = subprocess.run(
        ["python3", "scripts/bundle_marimo_for_wasm.py"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(f"BUNDLE FAILED:\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}")
        return 1
    print(f"  OK: {res.stdout.strip().splitlines()[-1]}")

    wasm_src = "calculator/marimo_app_wasm.py"
    print(f"[2/5] Building Marimo WASM from {wasm_src} -> {build_dir}/")
    res = subprocess.run(
        [args.venv_marimo, "export", "html-wasm", wasm_src, "-o", str(build_dir)],
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
    # Marimo's WASM export bundles a few files we don't want shipped:
    # - CLAUDE.md: Marimo's AI-assistant prompt; Pelican tries to render it
    #   as a Markdown article and warns. Strip before copy.
    junk = ["CLAUDE.md"]
    for name in junk:
        p = build_dir / name
        if p.exists():
            p.unlink()
            print(f"  removed Marimo bundle junk: {name}")

    target = book_repo / "content" / "extra" / "book" / "calculator"
    print(f"[3/5] Copying {build_dir}/ -> {target}/")
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(build_dir, target)
    print("  OK")

    # Marimo's exported index.html preloads Lora + PTSans + FiraMono and ships
    # Marimo's bundled stylesheets in <head>. The cell-level mo.Html() theme
    # injection at runtime ends up scoped to a cell output and DOES NOT cascade
    # over the App-level branding (watermark, banner) or Radix-rendered widgets
    # outside cells. To fix: inject BOTH our Google Fonts stylesheet AND the
    # full marimo-theme.css contents into the bundle's <head>, AFTER Marimo's
    # own stylesheet links, so source order puts our rules last in the cascade.
    print("[4/5] Injecting site fonts + theme CSS into bundle's index.html")
    idx = target / "index.html"
    if idx.exists():
        html = idx.read_text()
        theme_css_path = Path("calculator/static/marimo-theme.css")
        theme_css = theme_css_path.read_text() if theme_css_path.exists() else ""

        if "fonts.googleapis.com" not in html:
            inject = (
                '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                '    <link rel="stylesheet" '
                'href="https://fonts.googleapis.com/css2?'
                'family=Instrument+Serif:ital@0;1&'
                'family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,700&'
                'family=JetBrains+Mono:wght@400;500;600;700&display=swap">\n    '
                "<style data-source=\"marimo-theme.css\">\n"
                + theme_css +
                "\n    </style>\n  "
            )
            html = html.replace("</head>", inject + "</head>", 1)
            idx.write_text(html)
            print("  OK: fonts + theme CSS injected into <head>")
        else:
            print("  SKIP: index.html already references fonts.googleapis.com")
    else:
        print(f"  WARN: {idx} not found; skipping font + theme injection")

    print("[5/5] Done.")
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
