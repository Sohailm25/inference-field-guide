# ABOUTME: Encode/decode WorkloadProfile for URL-safe sharing via query parameters.
# ABOUTME: Produces compact base64-JSON strings suitable for st.query_params.

from __future__ import annotations

import base64
import json
from dataclasses import asdict, fields

from calculator.lcpr import WorkloadProfile


def encode_profile(profile: WorkloadProfile) -> str:
    """Encode a WorkloadProfile as a URL-safe base64 JSON string."""
    data = asdict(profile)
    json_bytes = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(json_bytes).decode()


def decode_profile(encoded: str) -> WorkloadProfile:
    """Decode a URL-safe base64 JSON string into a WorkloadProfile.

    Missing fields are filled with WorkloadProfile defaults.
    Raises ValueError on malformed input.
    """
    try:
        json_bytes = base64.urlsafe_b64decode(encoded.encode())
        data = json.loads(json_bytes)
    except Exception as exc:
        raise ValueError(f"Invalid permalink: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Permalink must encode a JSON object")

    # Build kwargs with defaults for missing required fields
    field_defaults = {
        "avg_input_tokens": 0,
        "avg_output_tokens": 0,
        "monthly_requests": 0,
        "retry_rate": 0.0,
        "quality_gate_pass_rate": 1.0,
        "repair_cost_per_failure": 0.0,
        "engineering_hours_per_month": 0,
        "engineer_hourly_cost": 0,
    }
    known = {f.name for f in fields(WorkloadProfile)}
    kwargs = {k: field_defaults[k] for k in known if k in field_defaults}
    kwargs.update({k: v for k, v in data.items() if k in known})
    return WorkloadProfile(**kwargs)
