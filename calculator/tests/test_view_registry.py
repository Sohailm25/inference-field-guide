# ABOUTME: Tests for calculator view registry and documentation consistency.
# ABOUTME: Ensures app, examples, and README stay aligned around current shipped views.

from pathlib import Path

import yaml

from calculator.view_registry import (
    APPENDIX_VIEW_NAMES,
    IMPLEMENTED_APP_TABS,
    VIEW_REGISTRY,
    view_by_internal_name,
    view_by_public_name,
)

ROOT = Path(__file__).resolve().parents[2]


def test_app_tabs_are_registered():
    for tab_name in IMPLEMENTED_APP_TABS:
        assert view_by_public_name(tab_name).status in {"implemented_ui", "template_ui"}


def test_appendix_views_are_registered():
    public_names = {view.public_name for view in VIEW_REGISTRY}
    missing = set(APPENDIX_VIEW_NAMES) - public_names
    assert not missing


def test_example_seed_views_resolve_to_registry_entries():
    seed_paths = sorted(ROOT.glob("examples/*/calculator-seed.yaml"))
    assert seed_paths

    unresolved = []
    for seed_path in seed_paths:
        seed = yaml.safe_load(seed_path.read_text())
        for internal_name in seed.get("calculator_views", []):
            try:
                view_by_internal_name(internal_name)
            except KeyError:
                unresolved.append((seed_path.name, internal_name))

    assert unresolved == []


def test_readme_describes_current_example_scales():
    readme = (ROOT / "README.md").read_text()

    assert "239 tests" not in readme
    assert "262 tests" not in readme
    assert "The test suite verifies" in readme
    assert "12-request trace" not in readme
    assert "$0.234" in readme
    assert "1.65x" in readme
    assert "$0.172" in readme
    assert "12.1x" in readme
