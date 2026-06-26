from datetime import UTC, datetime
import time


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def unix_seconds() -> str:
    return f"{time.time():.6f}"


def monotonic_seconds() -> str:
    return f"{time.monotonic():.6f}"
