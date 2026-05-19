# ABOUTME: Streamlit-Cloud-hosted "we moved" landing for the legacy URL.
# ABOUTME: inference-econ.streamlit.app -> sohailmo.ai/book/calculator/

import streamlit as st

NEW_URL = "https://sohailmo.ai/book/calculator/"

st.set_page_config(
    page_title="Moved — Production Inference Economics Calculator",
    page_icon="$",
    layout="centered",
)

st.markdown(
    f"""
    <meta http-equiv="refresh" content="3; url={NEW_URL}">
    <script>setTimeout(() => window.location.replace("{NEW_URL}"), 3000);</script>

    <div style="max-width: 600px; margin: 4rem auto; font-family: Newsreader, Georgia, serif;">
      <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
                text-transform: uppercase; letter-spacing: 0.12em;
                color: #3A4F2A;">
        The Inference Field Guide · MMXXVI
      </p>
      <h1 style="font-family: 'Instrument Serif', Georgia, serif;
                 font-style: italic; font-weight: 400;
                 font-size: 2.5rem; color: #1a1a1a; margin: 0.5rem 0 1rem;
                 letter-spacing: -0.005em;">
        The calculator has moved.
      </h1>
      <p style="font-family: 'Newsreader', Georgia, serif;
                font-size: 1.15rem; line-height: 1.6; color: #1a1a1a;">
        Production Inference Economics is now hosted under the book at:
      </p>
      <p style="font-family: 'JetBrains Mono', monospace;
                font-size: 1rem; padding: 0.75rem 1rem;
                background: #f7f1e2; border-left: 3px solid #3A4F2A;
                margin: 1rem 0;">
        <a href="{NEW_URL}" style="color: #5C2A1E; text-decoration: none;">{NEW_URL}</a>
      </p>
      <p style="color: #5C2A1E; font-family: 'JetBrains Mono', monospace;
                font-size: 0.85rem; font-style: italic;">
        Redirecting in 3 seconds…
      </p>
      <hr style="border: none; height: 1px; background: #a3ad8a;
                 max-width: 40%; margin: 2rem 0;">
      <p style="color: #5a5a5a; font-size: 0.85rem;">
        The companion to the book at
        <a href="https://sohailmo.ai/book/" style="color: #5C2A1E;">sohailmo.ai/book/</a>.
        Source at
        <a href="https://github.com/Sohailm25/inference-field-guide" style="color: #5C2A1E;">github.com/Sohailm25/inference-field-guide</a>.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)
