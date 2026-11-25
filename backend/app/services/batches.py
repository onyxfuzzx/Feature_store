from datetime import UTC

from fastapi import HTTPException


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def unique_events(records):
    unique = {}
    for original in records:
        row = dict(original)
        row["event_time"] = utc(row["event_time"])
        key = row["entity_key"], row["feature_id"], row["event_time"]
        previous = unique.get(key)
        if previous is not None and previous["value"] != row["value"]:
            raise HTTPException(409, "Conflicting replay within the same batch")
        unique[key] = row
    return list(unique.values())
