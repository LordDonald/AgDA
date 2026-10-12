"""Validate a release against saved data in an explicitly selected environment.

Require --expected-environment staging or production, including inside a container.
The origin defaults to localhost at PORT (or 8000). Health must confirm the exact
requested environment and stable Wave5 contracts before analytical POSTs are
permitted. No provider refreshes, configuration changes or deployments are used.
"""

import argparse
import os
import re
import sys

try:
    # Also supports executing this source through stdin in the API container.
    from tools.validate_phase28_staging import (
        CheckFailure, StagingClient, check_questions, check_saved_data, emit, require,
    )
except ModuleNotFoundError as error:
    if error.name not in ("tools", "tools.validate_phase28_staging"):
        raise
    # Direct execution sets sys.path[0] to this script's tools directory.
    from validate_phase28_staging import (
        CheckFailure, StagingClient, check_questions, check_saved_data, emit, require,
    )


class ReleaseClient(StagingClient):
    def __init__(self, base_url, *, expected_environment):
        require(expected_environment in ("staging", "production"),
                "An explicit staging or production environment is required.")
        super().__init__(base_url)
        self.expected_environment = expected_environment

    def health(self, check):
        # Revoke the inherited gate on every attempt, including revalidation.
        self.staging_verified = False
        body = self.request("/v1/health")
        require(body.get("environment") == self.expected_environment,
                "Environment does not exactly match the explicit selection; analytical POSTs refused.")
        require(body.get("ready") is True and body.get("status") == "ready", "Wave5 core is not ready.")
        require(body.get("data_version") == "wave5_v1", "Wave5 data version changed.")
        require(body.get("release_state") == "stable", "Wave5 release is not stable.")
        require(body.get("metric_version") == "1.0.0", "Wave5 metric version changed.")
        require(body.get("registered_metrics") == 18, "Wave5 metric count changed.")
        require(body.get("external_sources", {}).get("affects_core_readiness") is False,
                "External sources must not affect core readiness.")
        # This inherited name is only the HTTP gate; the environment above is exact.
        self.staging_verified = True
        emit(check, environment=self.expected_environment, data_version="wave5_v1",
             release_state="stable", metric_version="1.0.0", registered_metrics=18,
             ready=True, affects_core_readiness=False)


class SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error may echo supplied URLs or other sensitive input.
        raise CheckFailure("Invalid arguments; explicitly select --expected-environment staging or production.")


def main(argv=None):
    try:
        parser = SanitizedArgumentParser(description=__doc__)
        parser.add_argument("--expected-environment", required=True, choices=("staging", "production"),
                            help="Required exact target environment; there is no production default.")
        parser.add_argument("--base-url", help="HTTP(S) origin; defaults to localhost at PORT (or 8000).")
        args = parser.parse_args(argv)
        base_url = args.base_url
        if not base_url:
            port = os.environ.get("PORT", "8000")
            require(bool(re.fullmatch(r"[0-9]{1,5}", port)) and 1 <= int(port) <= 65535,
                    "PORT must be a valid TCP port.")
            base_url = f"http://127.0.0.1:{port}"
        client = ReleaseClient(base_url, expected_environment=args.expected_environment)
        client.health("core_before")
        try:
            check_saved_data(client)
            check_questions(client)
        finally:
            client.health("core_after")
    except CheckFailure as error:
        emit("phase29_release", status="failed", reason=str(error))
        return 1
    except Exception as error:
        # Never echo response bodies, request data, URLs, paths or exception details.
        emit("phase29_release", status="failed", reason="Unexpected response shape or execution error.",
             error_type=type(error).__name__)
        return 1
    emit("phase29_release", environment=args.expected_environment, result="success")
    return 0


if __name__ == "__main__":
    sys.exit(main())
