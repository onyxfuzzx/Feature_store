"""One rejection policy for both batch and streaming feature writes."""

import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator


class ValidationRules(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    allow_null: StrictBool = True
    min_value: float | None = None
    max_value: float | None = None
    required_type: (
        Literal["int", "integer", "float", "double", "number", "str", "string", "bool", "boolean"]
        | None
    ) = None

    @model_validator(mode="after")
    def ordered_bounds(self):
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("min_value must not exceed max_value")
        return self


def parse_rules(raw: str | None) -> dict:
    if raw is None:
        return {}
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("Validation rules must be a JSON object")
        return ValidationRules.model_validate(value).model_dump(exclude_none=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid validation rules: {exc}") from exc


def coerce_value(value, dtype):
    if dtype in {"str", "string"}:
        return str(value)
    if dtype in {"bool", "boolean"}:
        if str(value).lower() not in {"true", "false", "0", "1"}:
            raise ValueError("expected boolean")
        return str(value).lower() in {"true", "1"}
    number = float(value)
    if isinstance(value, bool) or not math.isfinite(number):
        raise ValueError("expected finite number")
    if dtype in {"int", "integer"}:
        if not number.is_integer():
            raise ValueError("expected integer")
        return int(number)
    if dtype in {"float", "double", "number"}:
        return number
    raise ValueError(f"Unsupported feature type: {dtype}")


def validate_value(value, rules: dict, dtype: str | None = None) -> list[str]:
    if value is None:
        return ["null_not_allowed"] if rules.get("allow_null") is False else []
    errors = []
    expected_type = rules.get("required_type") or dtype
    if expected_type:
        try:
            coerce_value(value, expected_type)
        except (ValueError, TypeError, OverflowError):
            errors.append(f"expected_{expected_type}")
    if rules.get("min_value") is not None or rules.get("max_value") is not None:
        try:
            number = coerce_value(value, "float")
            if rules.get("min_value") is not None and number < rules["min_value"]:
                errors.append("below_min_value")
            if rules.get("max_value") is not None and number > rules["max_value"]:
                errors.append("above_max_value")
        except (ValueError, TypeError, OverflowError):
            errors.append("expected_finite_number")
    return errors
