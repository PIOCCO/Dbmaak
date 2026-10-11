from pathlib import Path

import pytest
from pydantic import ValidationError

from business.loader import load_business_profile
from business.registry import BusinessRegistry


def test_demo_salon_profile_loads() -> None:
    path = Path("config/businesses/demo_salon.yaml")
    profile = load_business_profile(path)
    assert profile.id == "demo_salon"
    assert profile.services[0].bookable is True
    assert profile.inbound_phone_numbers[0].startswith("+")


def test_duplicate_service_ids_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        """
id: bad_biz
display_name: Bad
services:
  - id: cut
    name: Cut
    duration_minutes: 30
  - id: cut
    name: Cut again
    duration_minutes: 30
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_business_profile(bad)


def test_registry_lists_profiles() -> None:
    registry = BusinessRegistry.from_directory(Path("config/businesses"))
    assert "demo_salon" in registry.list_ids()
