ABOUTME: Index and refresh protocol for the 2026-05-12 source snapshot packet.
ABOUTME: Defines what each YAML file covers, volatility rules, and publication safety checks.

# Source Snapshot - 2026-05-12

## Purpose

This directory contains machine-readable source snapshots for Production Inference
Economics worked examples, derivations, and calculator seed data. Body prose should
cite snapshot IDs, not copy volatile provider tables.

## Files

| File | Scope |
| --- | --- |
| `providers.yaml` | Provider pricing surfaces, billing units, deployment modes, and regions. |
| `cache-semantics.yaml` | Prompt-cache mechanics: TTL, prefix rules, write/read accounting, scope. |
| `hardware.yaml` | Accelerator specs relevant to serving physics derivations. |
| `benchmark-sources.yaml` | Benchmark suites, scenarios, result links, and methodology caveats. |
| `model-licenses.yaml` | Open-model license and acceptable-use constraints for example models. |

## Refresh Protocol

1. Re-open every `source_url` in each YAML file.
2. Diff current page against the recorded row.
3. Update `accessed_at` and changed fields.
4. Mark changed rows with `changed_since_last: true`.
5. Re-run calculator seed and example calculations from updated rows.
6. Refresh within 7 days of any publication event.

## Volatility Rules

| Claim type | Volatility | Refresh trigger |
| --- | --- | --- |
| Exact token price | High | Pre-publication and pre-calculator-release |
| Cache TTL and model support | High | Pre-caching chapter |
| Batch/cache stacking | High | Pre-examples using both features |
| Model availability | High | Pre-model-selection examples |
| Hardware specs | Medium | Monthly and pre-hardware examples |
| MLPerf results | Medium | Per MLPerf release |
| Model license terms | Medium | Pre-model example and pre-publication |
| Data handling terms | Medium-high | Pre-security claims |

## Evidence Labels

Every row uses one of:
- `official_pricing`: from provider pricing page
- `official_docs`: from provider API/product docs
- `official_security`: from provider data-handling/security page
- `official_hardware_spec`: from hardware vendor product page
- `official_model_card`: from model card on Hugging Face or vendor site
- `official_license`: from license file or terms page
- `benchmark_results`: from benchmark organization results page

## Publication Safety Checks

Before using any row in public prose:
- Does it have `accessed_at`, `source_url`, region, model ID, and deployment mode?
- Does every cache example include TTL, minimum prefix, and hit-rate assumption?
- Does every batch example state latency window and cache stacking behavior?
- Does every dedicated example include measured goodput, not peak TPS?
- Does every security example start with feasible-set gates?
- Does every model example link to the selected model card and license?
- Are exact provider numbers absent from durable chapter prose unless dated?
