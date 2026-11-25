"""Resolve UUID, name, group:name, or environment/group:name without guessing."""
from collections import Counter
from uuid import UUID

from fastapi import HTTPException
from app.db.models.feature_store import FeatureDefinition, FeatureGroup


def resolve_feature(db, reference, environment=None):
    reference = str(reference)
    query = db.query(FeatureDefinition).join(FeatureGroup, FeatureGroup.id == FeatureDefinition.group_id)
    if environment:
        query = query.filter(FeatureGroup.environment == environment)
    try:
        identity = UUID(reference)
    except ValueError:
        identity = None
    if identity:
        query = query.filter(FeatureDefinition.id == identity)
    elif ":" in reference:
        group, name = reference.split(":", 1)
        if "/" in group:
            scope, group = group.split("/", 1)
            query = query.filter(FeatureGroup.environment == scope)
        query = query.filter(FeatureGroup.name == group, FeatureDefinition.name == name)
    else:
        query = query.filter(FeatureDefinition.name == reference)
    candidates = query.limit(2).all()
    if not candidates:
        raise HTTPException(422, f"Unknown feature reference in requested scope: {reference}")
    if len(candidates) != 1:
        raise HTTPException(422, f"Ambiguous feature reference; use UUID or environment/group:name: {reference}")
    return candidates[0]


def resolve_features(db, references, environment=None):
    features = [resolve_feature(db, ref, environment) for ref in references]
    if len({feature.id for feature in features}) != len(features):
        raise HTTPException(422, "A feature may be requested only once, including aliases")
    names = Counter(feature.name for feature in features)
    mapping = {}
    for ref, feature in zip(references, features):
        if ":" in ref:
            key = ref
        elif names[feature.name] > 1 or feature.name in {"entity_key", "event_time"}:
            group = db.get(FeatureGroup, feature.group_id)
            key = f"{group.environment}/{group.name}:{feature.name}"
        else:
            key = feature.name
        mapping[feature.id] = key
    return features, mapping
