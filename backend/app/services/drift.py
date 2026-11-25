"""Version-specific training histograms and recorded inference-window PSI runs."""
from bisect import bisect_right
from collections import defaultdict
import json
import math

from fastapi import HTTPException
from app.db.models.model_registry import DriftBaseline, DriftRun, InferenceObservation, ModelLineage
from app.services.feature_refs import resolve_feature


def linked_features(db, version):
    features = {}
    for lineage in db.query(ModelLineage).filter_by(model_version_id=version.id).order_by(ModelLineage.created_at, ModelLineage.id):
        try:
            references = json.loads(lineage.feature_ids_json or "[]")
        except ValueError as exc:
            raise HTTPException(422, "Model lineage contains invalid feature JSON") from exc
        if not isinstance(references, list):
            raise HTTPException(422, "Model lineage must be a JSON list")
        for reference in references:
            feature = resolve_feature(db, reference)
            features[str(feature.id)] = feature
    return features


def histogram(values, boundaries):
    counts = [0] * (len(boundaries) + 1)
    for value in values:
        counts[bisect_right(boundaries, value)] += 1
    return counts


def distribution(values, num_bins=5):
    lower, upper = min(values), max(values)
    if lower == upper:
        epsilon = max(abs(lower) * 1e-6, 1e-6)
        boundaries = [lower - epsilon, upper + epsilon]
    else:
        boundaries = [lower + (upper - lower) * i / num_bins for i in range(1, num_bins)]
    if not all(math.isfinite(value) for value in boundaries):
        raise HTTPException(422, "Training samples exceed supported numeric range")
    return {"boundaries": boundaries, "counts": histogram(values, boundaries), "sample_count": len(values)}


def psi_from_counts(expected, actual):
    # Symmetric pseudocount smoothing keeps empty bins finite and normalized.
    expected_total = sum(expected) + 0.5 * len(expected)
    actual_total = sum(actual) + 0.5 * len(actual)
    score = 0.0
    for baseline_count, current_count in zip(expected, actual):
        p = (baseline_count + 0.5) / expected_total
        q = (current_count + 0.5) / actual_total
        score += (q - p) * math.log(q / p)
    return round(max(0.0, score), 6)


def calculate_psi(baseline, current, num_bins=5):
    if not baseline or not current:
        return None
    reference = distribution(baseline, num_bins)
    return psi_from_counts(reference["counts"], histogram(current, reference["boundaries"]))


def latest_baseline(db, version_id):
    return db.query(DriftBaseline).filter_by(model_version_id=version_id).order_by(DriftBaseline.created_at.desc(), DriftBaseline.id.desc()).first()


def capture_baseline(db, version, payload):
    linked = linked_features(db, version)
    if not linked:
        raise HTTPException(422, "Link this version's training features before capturing a baseline")
    distributions = {}
    for reference, samples in payload.samples.items():
        feature = resolve_feature(db, reference)
        key = str(feature.id)
        if key not in linked or key in distributions:
            raise HTTPException(422, "Baseline samples must identify distinct linked features")
        distributions[key] = distribution(samples)
    baseline = DriftBaseline(model_version_id=version.id, window_start=payload.window_start,
                             window_end=payload.window_end, distributions=distributions)
    db.add(baseline)
    db.flush()
    return baseline


def record_run(db, version, payload):
    linked = linked_features(db, version)
    baseline = latest_baseline(db, version.id)
    observations = db.query(InferenceObservation).filter(
        InferenceObservation.model_version_id == version.id,
        InferenceObservation.observed_at >= payload.window_start,
        InferenceObservation.observed_at < payload.window_end,
    ).limit(100001).all()
    if len(observations) > 100000:
        raise HTTPException(422, "Window exceeds 100000 inference observations; use a smaller window")
    samples = defaultdict(list)
    for observation in observations:
        for feature_id, value in observation.values_json.items():
            if feature_id in linked and isinstance(value, (int, float)) and math.isfinite(value):
                samples[feature_id].append(value)
    metrics = []
    for key, feature in linked.items():
        reference = baseline.distributions.get(key) if baseline else None
        current = samples[key]
        enough = reference and reference["sample_count"] >= payload.min_samples and len(current) >= payload.min_samples
        psi = psi_from_counts(reference["counts"], histogram(current, reference["boundaries"])) if enough else None
        metrics.append({"feature_id": key, "feature": feature.name, "current_psi": psi,
                        "baseline_sample_count": reference["sample_count"] if reference else 0,
                        "current_sample_count": len(current),
                        "status": "measured" if enough else "insufficient_data",
                        "drift_detected": psi > 0.2 if psi is not None else None})
    status = "measured" if metrics and all(item["status"] == "measured" for item in metrics) else "insufficient_data"
    run = DriftRun(model_version_id=version.id, baseline_id=baseline.id if baseline else None,
                   window_start=payload.window_start, window_end=payload.window_end,
                   status=status, result_json={"metrics": metrics, "min_samples": payload.min_samples})
    db.add(run)
    db.flush()
    return run


def summary(db, model, version):
    baseline = latest_baseline(db, version.id) if version else None
    runs = db.query(DriftRun).filter_by(model_version_id=version.id, baseline_id=baseline.id if baseline else None).order_by(
        DriftRun.created_at.desc(), DriftRun.id.desc()).limit(50).all() if version else []
    latest = runs[0] if runs else None
    features = linked_features(db, version) if version else {}
    latest_metrics = {item["feature_id"]: item for item in latest.result_json["metrics"]} if latest else {}
    metrics = []
    for key, feature in features.items():
        item = dict(latest_metrics.get(key, {"feature_id": key, "feature": feature.name, "current_psi": None,
                    "baseline_sample_count": baseline.distributions.get(key, {}).get("sample_count", 0) if baseline else 0,
                    "current_sample_count": 0, "status": "not_measured", "drift_detected": None}))
        item["history"] = [dict(date=run.created_at.isoformat(), run_id=str(run.id), psi=measurement["current_psi"],
                               status=measurement["status"], window_start=run.window_start.isoformat(),
                               window_end=run.window_end.isoformat())
                           for run in reversed(runs) for measurement in run.result_json["metrics"]
                           if measurement["feature_id"] == key]
        metrics.append(item)
    return {"model_id": str(model.id), "version": version.version if version else None,
            "version_id": str(version.id) if version else None,
            "status": latest.status if latest else ("not_measured" if baseline else "baseline_missing"),
            "baseline": {"id": str(baseline.id), "window_start": baseline.window_start.isoformat(),
                         "window_end": baseline.window_end.isoformat(), "created_at": baseline.created_at.isoformat()} if baseline else None,
            "latest_run": {"id": str(latest.id), "window_start": latest.window_start.isoformat(),
                           "window_end": latest.window_end.isoformat(), "created_at": latest.created_at.isoformat()} if latest else None,
            "metrics": metrics, "thresholds": {"no_drift": 0.1, "moderate_drift": 0.2}}
