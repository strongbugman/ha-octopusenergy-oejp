from __future__ import annotations

from octopusenergy_oejp_demo.redaction import redact_json, redact_path, scrub_error_text


def test_redacts_sensitive_keys_and_paths():
    payload = {
        "email": "person@example.com",
        "access_token": "secret-token",
        "nested": {"refresh": "refresh-token", "value": "kept"},
    }

    assert redact_json(payload) == {
        "email": "[REDACTED]",
        "access_token": "[REDACTED]",
        "nested": {"refresh": "[REDACTED]", "value": "kept"},
    }
    assert redact_path("/v1/accounts/A-123/electricity-meter-points/MP-789/meters/M-0001/consumption/") == (
        "/v1/accounts/{account}/electricity-meter-points/{meter_point}/meters/{meter}/consumption/"
    )
    assert scrub_error_text("Authorization: Bearer abc.def.ghi") == "Authorization: Bearer [REDACTED]"
