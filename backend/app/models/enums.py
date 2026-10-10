"""Enumerations shared by models and schemas."""

import enum


class SpiceLevel(str, enum.Enum):
    mild = "mild"
    medium = "medium"
    extra_spicy = "extra_spicy"


class RoastStatus(str, enum.Enum):
    completed = "completed"
    refused = "refused"
    failed = "failed"
