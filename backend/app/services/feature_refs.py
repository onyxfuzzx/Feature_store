"""Resolve bounded batches without a query per reference or guessing ambiguous names."""

from collections import Counter
from uuid import UUID

from app.db.models.feature_store import FeatureDefinition, FeatureGroup
from fastapi import HTTPException
from sqlalchemy import and_, or_


def reference_filter(reference, environment=None):
    parts = []
    if environment:
        parts.append(FeatureGroup.environment == environment)
    try:
        identity = UUID(reference)
    except ValueError:
        identity = None
    if identity:
        parts.append(FeatureDefinition.id == identity)
    elif ":" in reference:
        group, name = reference.split(":", 1)
        if "/" in group:
            scope, group = group.split("/", 1)
            parts.append(FeatureGroup.environment == scope)
        parts.extend([FeatureGroup.name == group, FeatureDefinition.name == name])
    else:
        parts.append(FeatureDefinition.name == reference)
    return and_(*parts)


def matches(reference, feature, group, environment):
    if environment and group.environment != environment:
        return False
    try:
        return feature.id == UUID(reference)
    except ValueError:
        pass
    if ":" not in reference:
        return feature.name == reference
    scope, name = reference.split(":", 1)
    if "/" in scope:
        env, scope = scope.split("/", 1)
        if group.environment != env:
            return False
    return group.name == scope and feature.name == name


def resolve_feature(db, reference, environment=None):
    features, _ = resolve_features(db, [str(reference)], environment)
    return features[0]


def resolve_features(db, references, environment=None):
    references = [str(ref) for ref in references]
    if not references:
        return [], {}
    candidates = (
        db.query(FeatureDefinition, FeatureGroup)
        .join(FeatureGroup, FeatureGroup.id == FeatureDefinition.group_id)
        .filter(or_(*(reference_filter(ref, environment) for ref in references)))
        .all()
    )
    selected = []
    for ref in references:
        found = [(f, g) for f, g in candidates if matches(ref, f, g, environment)]
        if not found:
            raise HTTPException(422, f"Unknown feature reference in requested scope: {ref}")
        if len(found) != 1:
            raise HTTPException(
                422, f"Ambiguous feature reference; use UUID or environment/group:name: {ref}"
            )
        selected.append(found[0])
    features = [f for f, _ in selected]
    if len({feature.id for feature in features}) != len(features):
        raise HTTPException(422, "A feature may be requested only once, including aliases")
    names = Counter(feature.name for feature in features)
    mapping = {}
    for ref, (feature, group) in zip(references, selected):
        if ":" in ref:
            key = ref
        elif names[feature.name] > 1 or feature.name in {"entity_key", "event_time"}:
            key = f"{group.environment}/{group.name}:{feature.name}"
        else:
            key = feature.name
        mapping[feature.id] = key
    return features, mapping
