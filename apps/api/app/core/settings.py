from __future__ import annotations

import os

from dataclasses import (
    dataclass,
)


# ============================================================
# HELPERS
# ============================================================

def _read_bool(
    name: str,
    default: bool,
) -> bool:

    raw_value = os.getenv(
        name
    )


    if raw_value is None:

        return default


    normalized = (
        raw_value
        .strip()
        .casefold()
    )


    if normalized in {
        "1",
        "true",
        "yes",
        "on",
    }:

        return True


    if normalized in {
        "0",
        "false",
        "no",
        "off",
    }:

        return False


    raise ValueError(
        f"{name} must be a boolean value."
    )


def _read_positive_int(
    name: str,
    default: int,
) -> int:

    raw_value = os.getenv(
        name
    )


    if raw_value is None:

        return default


    value = int(
        raw_value
    )


    if value < 1:

        raise ValueError(
            f"{name} must be >= 1."
        )


    return value

def _read_csv(
    name: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:

    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    values = tuple(
        item.strip()
        for item in raw_value.split(",")
        if item.strip()
    )

    if not values:
        raise ValueError(
            f"{name} must contain at least one value."
        )

    return values


# ============================================================
# APPLICATION SETTINGS
# ============================================================

@dataclass(
    frozen=True
)
class AppSettings:

    environment: str

    log_level: str

    max_conversations: int

    max_request_bytes: int

    docs_enabled: bool

    service_name: str

    service_version: str

    allowed_hosts: tuple[str, ...]


    @classmethod
    def from_env(
        cls,
    ) -> "AppSettings":

        environment = (
            os.getenv(
                "AGDA_ENV",
                "development",
            )
            .strip()
            .casefold()
        )


        allowed_environments = {
            "development",
            "test",
            "staging",
            "production",
        }


        if (
            environment
            not in allowed_environments
        ):

            raise ValueError(
                "AGDA_ENV must be one of: "
                + ", ".join(
                    sorted(
                        allowed_environments
                    )
                )
            )


        log_level = (
            os.getenv(
                "AGDA_LOG_LEVEL",
                (
                    "INFO"
                    if environment
                    != "production"
                    else "WARNING"
                ),
            )
            .strip()
            .upper()
        )


        allowed_log_levels = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }


        if (
            log_level
            not in allowed_log_levels
        ):

            raise ValueError(
                "AGDA_LOG_LEVEL contains "
                "an unsupported level."
            )


        docs_default = (
            environment
            != "production"
        )


        return cls(
            environment=
                environment,

            log_level=
                log_level,

            max_conversations=
                _read_positive_int(
                    "AGDA_MAX_CONVERSATIONS",
                    500,
                ),

            max_request_bytes=
                _read_positive_int(
                    "AGDA_MAX_REQUEST_BYTES",
                    16384,
                ),

            docs_enabled=
                _read_bool(
                    "AGDA_DOCS_ENABLED",
                    docs_default,
                ),

            service_name=
                os.getenv(
                    "AGDA_SERVICE_NAME",
                    "AgDA API",
                ).strip(),

            service_version=
                os.getenv(
                    "AGDA_SERVICE_VERSION",
                    "0.1.0",
                ).strip(),

            allowed_hosts=
                _read_csv(
                    "AGDA_ALLOWED_HOSTS",
                    (
                        "*",
                    )
                    if environment
                    in {
                        "development",
                        "test",
                    }
                    else (
                        "localhost",
                        "127.0.0.1",
                    ),
                ),
        )


settings = (
    AppSettings.from_env()
)