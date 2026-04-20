from datetime import UTC, datetime


def get_now() -> datetime:
    """Get UTC datetime. Use this instead of default datetime utility."""
    return datetime.now(tz=UTC)
