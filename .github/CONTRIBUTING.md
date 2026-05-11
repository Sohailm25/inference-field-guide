# Contributing

## Updating Pricing Data

Provider pricing changes frequently. To update:

1. Edit `calculator/provider_pricing.yaml`
2. Add the date of the update as a comment
3. Update only the prices you've personally verified against the provider's public pricing page
4. Submit a PR with a link to the pricing page as evidence

## Reporting Errors

If you find a factual error in the essay or calculator:

1. Open an issue with the specific claim and the correct information
2. Include a source (link to public page, benchmark, or documentation)
3. Note whether this affects the calculator output

## Code Changes

- Calculator changes require passing tests: `pytest calculator/tests/`
- Format with: `ruff format .`
- Lint with: `ruff check .`

## Evidence Tags

When adding claims about vendors, use the evidence tag system:

- `[PUBLIC]` — from vendor's public docs/pricing page
- `[MEASURED]` — from your own production experience
- `[REPORTED]` — from third-party benchmarks or customer references
- `[MODELED]` — calculated/estimated, show your methodology
