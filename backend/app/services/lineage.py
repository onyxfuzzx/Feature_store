"""Build dependency edges from registered IDs and source records only."""
from fastapi import HTTPException
from app.db.models.feature_store import FeatureDefinition, FeatureGroup, FeatureLineage
from app.db.models.model_registry import Model, ModelVersion
from app.services.drift import linked_features


def graph(db, model_id=None, feature_id=None):
    if model_id and not db.get(Model, model_id):
        raise HTTPException(404, "Model not found")
    feature = db.get(FeatureDefinition, feature_id) if feature_id else None
    if feature_id and not feature:
        raise HTTPException(404, "Feature not found")
    versions = db.query(ModelVersion).filter_by(model_id=model_id).all() if model_id else db.query(ModelVersion).all()
    nodes, edges = {}, {}
    def node(identity, label, kind, **metadata):
        nodes[identity] = {"id": identity, "label": label, "type": kind, "metadata": metadata}
    def edge(source, target, label):
        edges[(source, target)] = {"source": source, "target": target, "label": label}
    def add_feature(item):
        identity = f"feat:{item.id}"
        node(identity, item.name, "feature", dtype=item.dtype, status=item.status)
        group = db.get(FeatureGroup, item.group_id)
        group_id = f"grp:{group.id}"
        node(group_id, group.name, "feature_group", environment=group.environment)
        edge(group_id, identity, "contains")
        sources = db.query(FeatureLineage).filter_by(feature_id=item.id).all()
        if not sources:
            unknown = f"unknown:{item.id}"
            node(unknown, "Source not registered", "unknown_source", status="unknown")
            edge(unknown, identity, "unknown source")
        for source in sources:
            source_id = f"source:{source.source_table}"
            node(source_id, source.source_table, "source_table")
            edge(source_id, identity, "transforms")
    if feature:
        add_feature(feature)
    for version in versions:
        inputs = linked_features(db, version)
        if feature_id and str(feature_id) not in inputs:
            continue
        model = db.get(Model, version.model_id)
        model_node, version_node = f"model:{model.id}", f"version:{version.id}"
        node(model_node, model.name, "model", environment=model.environment)
        node(version_node, f"v{version.version} ({version.stage})", "model_version", stage=version.stage)
        edge(model_node, version_node, "version")
        for item in inputs.values():
            add_feature(item)
            edge(f"feat:{item.id}", version_node, "trained_on")
        if version.stage == "Production":
            endpoint = f"endpoint:{version.id}"
            node(endpoint, f"POST /models/{model.id}/predict", "endpoint", version=version.version)
            edge(version_node, endpoint, "serves")
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}
