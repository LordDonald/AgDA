from __future__ import annotations

import os


# ============================================================
# PRODUCTION HOST CONFIGURATION
# ============================================================

os.environ["AGDA_ENV"] = "production"
os.environ["AGDA_ALLOWED_HOSTS"] = "agda.example.com"


from fastapi.testclient import TestClient

from apps.api.app.main import app


# ============================================================
# TEST
# ============================================================

client = TestClient(app)


allowed_response = client.get(
    "/v1/live",
    headers={
        "Host": "agda.example.com",
    },
)


blocked_response = client.get(
    "/v1/live",
    headers={
        "Host": "evil.example.com",
    },
)


assert (
    allowed_response.status_code
    == 200
), allowed_response.text


assert (
    blocked_response.status_code
    == 400
), blocked_response.text


assert (
    "invalid host"
    in blocked_response.text.casefold()
), blocked_response.text


print(
    "Allowed production host:",
    allowed_response.status_code,
)

print(
    "Blocked untrusted host:",
    blocked_response.status_code,
)

print(
    "TRUSTED HOST TEST: PASSED"
)