"""Bound list responses while preserving the existing JSON-array API contract."""

from fastapi import Query, Response


def page(query, response: Response, limit: int, offset: int):
    records = query.offset(offset).limit(limit + 1).all()
    if len(records) > limit:
        response.headers["X-Next-Offset"] = str(offset + limit)
    response.headers["X-Page-Limit"] = str(limit)
    return records[:limit]


def page_limit():
    return Query(default=100, ge=1, le=500)


def page_offset():
    return Query(default=0, ge=0, le=1000000)
