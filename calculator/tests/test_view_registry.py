# ABOUTME: Tests for calculator view registry and documentation consistency.
# ABOUTME: Ensures app, examples, and README stay aligned around current shipped views.

from pathlib import Path

import yaml

from calculator.view_registry import (
    ADVANCED_APP_TABS,
    APPENDIX_VIEW_NAMES,
    CORE_APP_TABS,
    IMPLEMENTED_APP_TABS,
    VIEW_REGISTRY,
    view_by_internal_name,
    view_by_public_name,
)

ROOT = Path(__file__).resolve().parents[2]


def test_app_tabs_are_registered():
    for tab_name in IMPLEMENTED_APP_TABS:
        assert view_by_public_name(tab_name).status in {"implemented_ui", "template_ui"}


def test_core_and_advanced_tabs_cover_implemented():
    assert CORE_APP_TABS[1:] + ADVANCED_APP_TABS == IMPLEMENTED_APP_TABS


def test_decision_trees_tab_removed():
    all_names = {v.public_name for v in VIEW_REGISTRY}
    assert "Decision Trees" not in all_names
    assert "Decision Trees" not in CORE_APP_TABS
    assert "Decision Trees" not in ADVANCED_APP_TABS


def test_appendix_views_are_registered():
    public_names = {view.public_name for view in VIEW_REGISTRY}
    missing = set(APPENDIX_VIEW_NAMES) - public_names
    assert not missing

    assert view_by_public_name("Dedicated Break-Even").internal_name == (
        "Dedicated Utilization Gate v1"
    )


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


def test_app_explains_full_lcpr_vs_profile_estimator():
    app = (ROOT / "calculator" / "app.py").read_text()

    assert "Loaded Cost Per Request" not in app
    assert "successful_requests" not in app
    assert "token\\_cost} + \\text{retry\\_cost}" not in app
    assert "accepted work" in app
    assert "Loaded Cost Per Result" in app


def test_app_has_no_stale_essay_or_wrong_part_references():
    app = (ROOT / "calculator" / "app.py").read_text()

    assert "Part 1 of the essay" not in app
    assert "Decision trees from the essay" not in app
    assert "Decision trees from the book" not in app
    assert "Part 0 of the essay" not in app
    assert "token-volume version of the dedicated break-even gate from Part 4" in app


def test_source_snapshot_browser_does_not_infer_evidence_from_yaml_comments():
    app = (ROOT / "calculator" / "app.py").read_text()

    assert '"[PUBLIC" in str' not in app
    assert "comment_only" in app
