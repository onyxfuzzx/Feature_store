"""Portable trained linear/logistic models; uploaded code is never executed."""

import math
from typing import Literal
from uuid import UUID

from app.db.models.feature_store import FeatureDefinition
from app.services.artifacts import artifact_path
from app.services.online_store import get_online_store
from app.services.validation import coerce_value
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator


class ModelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    feature_id: UUID | None = None  # absent means a required runtime input
    dtype: Literal["float", "int", "bool"] = "float"


class LinearArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["featureops.linear.v1"]
    task: Literal["binary_classification", "regression"]
    inputs: list[ModelInput] = Field(min_length=1, max_length=1000)
    coefficients: list[FiniteFloat]
    intercept: FiniteFloat
    classes: list[str | int] = Field(default_factory=lambda: [0, 1])

    @model_validator(mode="after")
    def contract(self):
        names = [item.name for item in self.inputs]
        if len(names) != len(set(names)) or "entity_key" in names:
            raise ValueError("Input names must be unique and cannot be entity_key")
        ids = [item.feature_id for item in self.inputs if item.feature_id]
        if len(ids) != len(set(ids)):
            raise ValueError("A feature can occur only once in the input signature")
        if len(self.inputs) != len(self.coefficients):
            raise ValueError("Each ordered input requires one coefficient")
        if self.task == "binary_classification" and (
            len(self.classes) != 2 or self.classes[0] == self.classes[1]
        ):
            raise ValueError("Binary classification requires two distinct classes")
        return self


def load_model(version, db):
    path = artifact_path(version.artifact_uri, version.model_id, version.id)
    if not path.is_file():
        raise HTTPException(404, "Registered artifact is missing from storage")
    try:
        artifact = LinearArtifact.model_validate_json(path.read_bytes())
    except ValueError as exc:
        raise HTTPException(
            422, "Unsupported serving artifact: upload a featureops.linear.v1 JSON model"
        ) from exc
    for item in artifact.inputs:
        if item.feature_id and not db.get(FeatureDefinition, item.feature_id):
            raise HTTPException(422, f"Model input {item.name} refers to an unavailable feature")
    return artifact


def hydrate(artifact, entity_keys, db):
    mapping = {item.feature_id: item.name for item in artifact.inputs if item.feature_id}
    values = get_online_store().get_online_features(entity_keys, mapping, db)
    return [
        {"entity_key": key, **{item.name: values[key].get(item.name) for item in artifact.inputs}}
        for key in entity_keys
    ]


def score(artifact, stored_values, runtime_values):
    runtime_names = {item.name for item in artifact.inputs if item.feature_id is None}
    if set(runtime_values) - runtime_names:
        raise HTTPException(
            422, "Runtime features must match runtime-only inputs in the model signature"
        )
    vector = []
    used = {}
    for item in artifact.inputs:
        value = stored_values.get(item.name) if item.feature_id else runtime_values.get(item.name)
        if value is None:
            raise HTTPException(422, f"Missing required model input: {item.name}")
        try:
            typed = coerce_value(value, item.dtype)
        except (ValueError, TypeError, OverflowError) as exc:
            raise HTTPException(422, f"Invalid {item.dtype} input: {item.name}") from exc
        vector.append(float(typed))
        used[item.name] = str(value)
    try:
        linear = (
            math.fsum(weight * value for weight, value in zip(artifact.coefficients, vector))
            + artifact.intercept
        )
    except (OverflowError, ValueError) as exc:
        raise HTTPException(422, "Model inputs produce a non-finite score") from exc
    if not math.isfinite(linear):
        raise HTTPException(422, "Model inputs produce a non-finite score")
    if artifact.task == "regression":
        return used, {"value": linear}
    probability = (
        1 / (1 + math.exp(-linear)) if linear >= 0 else math.exp(linear) / (1 + math.exp(linear))
    )
    # Match binary linear classifiers: an exactly zero decision selects classes_[0].
    label = artifact.classes[int(linear > 0)]
    return used, {"probability": probability, "prediction_class": label, "label": str(label)}
