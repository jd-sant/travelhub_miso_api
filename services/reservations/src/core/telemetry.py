from uuid import uuid4

from fastapi import Header


def resolve_correlation_id(x_correlation_id: str | None = Header(default=None)) -> str:
    if x_correlation_id and x_correlation_id.strip():
        return x_correlation_id.strip()
    return str(uuid4())
