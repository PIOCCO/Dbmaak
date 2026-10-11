from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from business.models import BusinessProfile


def load_business_profile(path: Path) -> BusinessProfile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationError.from_exception_data(
            "BusinessProfile",
            [{"type": "dict_type", "loc": (), "input": raw, "msg": "Expected mapping"}],
        )
    return BusinessProfile.model_validate(raw)


def load_business_directory(directory: Path) -> dict[str, BusinessProfile]:
    profiles: dict[str, BusinessProfile] = {}
    if not directory.exists():
        return profiles
    for path in sorted(directory.glob("*.yaml")):
        profile = load_business_profile(path)
        profiles[profile.id] = profile
    return profiles
