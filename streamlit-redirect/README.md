# Streamlit Cloud Redirect Page

This is the replacement for the legacy `inference-econ.streamlit.app` deployment. It serves a one-page "we moved" landing that redirects to the new unified URL at `sohailmo.ai/book/calculator/`.

## Deploying

The new calculator (Marimo, WASM-built) lives at `calculator/marimo_app.py` and deploys to `sohailmo.ai/book/calculator/`. The OLD URL needs to redirect there.

Streamlit Cloud doesn't support true HTTP 301s on `*.streamlit.app` subdomains. So this minimal Streamlit app serves a redirect-page in lieu — `<meta http-equiv="refresh">` + JS `window.location.replace()` + visible "we moved" prose styled to match the book's broadsheet aesthetic.

## Manual deploy step (for Sohail)

1. On Streamlit Cloud (https://share.streamlit.io/), find the existing `inference-econ` app.
2. Change the app's entry point from `calculator/app.py` (now `app.py.LEGACY`) to `streamlit-redirect/app.py`.
3. Redeploy.
4. Verify by visiting https://inference-econ.streamlit.app — should redirect to https://sohailmo.ai/book/calculator/ within 3 seconds.

Alternatively, deploy this as a separate Streamlit Cloud app and point the original DNS at it. Whatever's quickest.
