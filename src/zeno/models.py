from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MINUTES_PER_DAY = 24 * 60


class FixedBlock(BaseModel):
    """Non-negotiable interval in minutes from 00:00 of the target day."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=120)
    start_minute: int = Field(ge=0, lt=MINUTES_PER_DAY)
    end_minute: int = Field(gt=0, le=MINUTES_PER_DAY)

    @model_validator(mode="after")
    def validate_range(self) -> FixedBlock:
        if self.end_minute <= self.start_minute:
            msg = "end_minute must be greater than start_minute"
            raise ValueError(msg)
        return self


class FlexibleTask(BaseModel):
    """Schedulable activity with optimization metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=120)
    duration_minutes: int = Field(gt=0, le=MINUTES_PER_DAY)
    priority: int = Field(ge=1, le=3)
    category: str = Field(min_length=1, max_length=80)


class DayScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixed_blocks: list[FixedBlock] = Field(default_factory=list)
    flexible_tasks: list[FlexibleTask] = Field(default_factory=list)
    transition_buffer_minutes: int = Field(default=15, ge=0, le=120)


class ScheduledTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    category: str
    priority: int
    start_minute: int
    end_minute: int


class TimelineSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_type: Literal["fixed", "task", "free"]
    id: str
    title: str
    start_minute: int = Field(ge=0, lt=MINUTES_PER_DAY)
    end_minute: int = Field(gt=0, le=MINUTES_PER_DAY)
    category: str | None = None
    priority: int | None = None


class TimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_start_minute: int = 0
    day_end_minute: int = MINUTES_PER_DAY
    transition_buffer_minutes: int
    timeline: list[TimelineSlot]
    scheduled_tasks: list[ScheduledTask]
    unscheduled_tasks: list[FlexibleTask]
