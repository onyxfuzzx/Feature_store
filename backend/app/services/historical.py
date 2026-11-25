"""One PostgreSQL lateral lookup statement for an entire observation frame."""

import json

from sqlalchemy import text


def historical_rows(db, observations, feature_id_map):
    result = [
        {
            "entity_key": item.entity_key,
            "event_time": item.event_time.isoformat(),
            **{name: None for name in feature_id_map.values()},
        }
        for item in observations
    ]
    if not observations or not feature_id_map:
        return result
    rows = db.execute(
        text("""
        SELECT o.ordinal, f.feature_id, latest.value
        FROM jsonb_to_recordset(CAST(:observations AS jsonb))
             AS o(ordinal integer, entity_key text, event_time timestamptz)
        CROSS JOIN unnest(CAST(:feature_ids AS uuid[])) AS f(feature_id)
        LEFT JOIN LATERAL (
            SELECT v.value FROM feature_store.feature_values_offline v
            WHERE v.entity_key = o.entity_key AND v.feature_id = f.feature_id
              AND v.event_time <= o.event_time
            ORDER BY v.event_time DESC LIMIT 1
        ) latest ON true
    """),
        {
            "observations": json.dumps(
                [
                    dict(
                        ordinal=index,
                        entity_key=item.entity_key,
                        event_time=item.event_time.isoformat(),
                    )
                    for index, item in enumerate(observations)
                ]
            ),
            "feature_ids": [str(identity) for identity in feature_id_map],
        },
    )
    for ordinal, feature_id, value in rows:
        result[ordinal][feature_id_map[feature_id]] = value
    return result
