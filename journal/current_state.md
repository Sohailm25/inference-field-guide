# Inference Field Guide — Current State

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Research + Scaffold | COMPLETE | All verification done, repo scaffolded |
| Phase 2a: Calculator Core | COMPLETE | Core engine + profiles (46 tests) |
| Phase 2b: CLI + Verification | COMPLETE | CLI (5 commands), essay number verification, sweep output (80 tests) |
| Phase 2c: Streamlit App | COMPLETE | 4-tab interactive web UI deployed |
| Phase 3: Essay | COMPLETE | Parts 0-5 written (~9,469 words), all numbers calculator-verified |
| Phase 4: Site + Templates | COMPLETE | Essay published on sohailmo.ai with longform TOC layout |
| Phase 5: Polish + Publish | COMPLETE | Decision tree SVGs, table styling, Streamlit Cloud deployment |

## Deployment Status (2026-05-11)

### sohailmo.ai (Pelican / GitHub Pages)
- **URL**: sohailmo.ai/inference-field-guide/
- **Repo**: Sohailm25/Sohailm25.github.io (master branch)
- **Deploy**: GitHub Actions — completed successfully
- **Features**: Sticky sidebar TOC, mobile dropdown TOC, dark-themed tables, 4 pre-rendered decision tree SVGs

### Streamlit Calculator
- **Repo**: github.com/Sohailm25/inference-field-guide (main branch)
- **Main file**: calculator/app.py
- **Requirements**: requirements-streamlit.txt
- **Theme**: .streamlit/config.toml (dark theme matching sohailmo.ai)
- **Status**: Code pushed, ready for Streamlit Cloud connection
- **Target URL**: inference-field-guide.streamlit.app

### Streamlit App Tabs
1. **LCPR Comparison**: Sidebar profile selector (5 presets + custom), comparison table with overhead ratios, Plotly bar chart color-coded by deployment mode
2. **Sensitivity Analysis**: Parameter dropdown (retry_rate, quality_gate, I/O tokens, volume), range slider, multi-provider line chart
3. **Break-Even Analysis**: Serverless vs dedicated selector, break-even metrics, cost-vs-volume chart with crossover annotation
4. **Decision Trees**: 4 Mermaid diagrams in expanders with context text

## Test Coverage
- 114 tests total (46 core + 22 CLI + 12 essay verification + 34 additional)
- All passing after Streamlit app addition

## Essay Statistics
- **Word count**: ~9,469
- **Tables**: 5 data tables
- **Decision trees**: 4 (migration gate, sourcing patterns, build-vs-buy, vendor selection)
- **Evidence tags**: [PUBLIC], [REPORTED], [MODELED], [MEASURED], [VENDOR CLAIM]
- **Calculator link**: inference-field-guide.streamlit.app

## Repo Location
`/Users/sohailmo/inference-field-guide/` (standalone repo, separate from togetherai)
