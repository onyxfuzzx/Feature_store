from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field, FiniteFloat, field_validator, model_validator


class ObservationWindow(BaseModel):
    window_start: datetime
    window_end: datetime

    @field_validator("window_start", "window_end")
    @classmethod
    def utc(cls, value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @model_validator(mode="after")
    def ordered(self):
        if self.window_start >= self.window_end:
            raise ValueError("window_start must precede window_end (end is exclusive)")
        return self


class BaselineCreate(ObservationWindow):
    samples: dict[str, list[FiniteFloat]] = Field(min_length=1, max_length=100)

    @field_validator("samples")
    @classmethod
    def bounded_samples(cls, value):
        if sum(map(len, value.values())) > 100000 or any(
            len(items) < 2 for items in value.values()
        ):
            raise ValueError("Provide 2+ training samples per feature, at most 100000 total")
        return value


class DriftRunCreate(ObservationWindow):
    version: str | None = None
    min_samples: int = Field(default=20, ge=2, le=10000)

    @model_validator(mode="after")
    def bounded_window(self):
        if self.window_end - self.window_start > timedelta(days=31):
            raise ValueError("Drift observation windows are limited to 31 days")
        return self
