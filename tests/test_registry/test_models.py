"""Tests for sovereign/registry/models.py."""

from __future__ import annotations

from datetime import date

import pytest

from sovereign.registry.models import PlayerOverride, RawPeopleRecord, ResolvedPlayer


class TestRawPeopleRecord:
    """Tests for RawPeopleRecord Pydantic model."""

    def test_minimal_valid(self) -> None:
        """Only identifier and name are required."""
        r = RawPeopleRecord(identifier="virat-kohli", name="Virat Kohli")
        assert r.identifier == "virat-kohli"
        assert r.name == "Virat Kohli"

    def test_full_record(self) -> None:
        """All optional fields are accepted."""
        r = RawPeopleRecord(
            identifier="ms-dhoni",
            name="MS Dhoni",
            unique_name="Mahendra Singh Dhoni",
            key_cricinfo="28081",
            key_cricbuzz="1",
        )
        assert r.unique_name == "Mahendra Singh Dhoni"
        assert r.key_cricinfo == "28081"

    def test_empty_identifier_raises(self) -> None:
        """Empty identifier raises ValidationError."""
        with pytest.raises(Exception):
            RawPeopleRecord(identifier="  ", name="Some Player")

    def test_empty_name_raises(self) -> None:
        """Empty name raises ValidationError."""
        with pytest.raises(Exception):
            RawPeopleRecord(identifier="abc123", name="")


class TestResolvedPlayer:
    """Tests for ResolvedPlayer Pydantic model."""

    def test_valid_player(self) -> None:
        """Valid player instantiation."""
        p = ResolvedPlayer(
            player_id="virat-kohli-ind",
            name="Virat Kohli",
            country="India",
            role="batsman",
        )
        assert p.player_id == "virat-kohli-ind"
        assert p.role == "batsman"

    def test_invalid_slug_raises(self) -> None:
        """player_id with uppercase raises ValueError."""
        with pytest.raises(Exception):
            ResolvedPlayer(player_id="Virat_Kohli", name="Virat Kohli")

    def test_invalid_role_raises(self) -> None:
        """Unknown role raises ValueError."""
        with pytest.raises(Exception):
            ResolvedPlayer(
                player_id="virat-kohli-ind",
                name="Virat Kohli",
                role="striker",
            )

    def test_from_raw(self) -> None:
        """from_raw builds a ResolvedPlayer from a RawPeopleRecord."""
        raw = RawPeopleRecord(
            identifier="virat-kohli",
            name="Virat Kohli",
            unique_name="Virat Kohli (India)",
        )
        resolved = ResolvedPlayer.from_raw(raw, country="India", role="batsman")
        assert resolved.player_id == "virat-kohli"
        assert resolved.name == "Virat Kohli"
        assert resolved.country == "India"
        # unique_name differs from name so it's added as alias
        assert "Virat Kohli (India)" in resolved.aliases

    def test_from_raw_no_unique_name(self) -> None:
        """from_raw without unique_name leaves aliases empty."""
        raw = RawPeopleRecord(identifier="ab-de-villiers", name="AB de Villiers")
        resolved = ResolvedPlayer.from_raw(raw)
        assert resolved.aliases == []

    def test_serialise_round_trip(self) -> None:
        """model_dump / model_validate round-trip."""
        p = ResolvedPlayer(
            player_id="rohit-sharma-ind",
            name="Rohit Sharma",
            dob=date(1987, 4, 30),
        )
        data = p.model_dump()
        restored = ResolvedPlayer.model_validate(data)
        assert restored.player_id == p.player_id
        assert restored.dob == p.dob


class TestPlayerOverride:
    """Tests for PlayerOverride Pydantic model."""

    def test_valid_override(self) -> None:
        """Valid override instantiation."""
        o = PlayerOverride(
            alias="msd",
            player_id="ms-dhoni-ind",
            reason="common abbreviation",
        )
        assert o.alias == "msd"
        assert o.player_id == "ms-dhoni-ind"

    def test_alias_forced_lowercase(self) -> None:
        """Alias is normalised to lowercase."""
        o = PlayerOverride(alias="MSD", player_id="ms-dhoni-ind")
        assert o.alias == "msd"

    def test_invalid_player_id_raises(self) -> None:
        """player_id with spaces raises ValueError."""
        with pytest.raises(Exception):
            PlayerOverride(alias="msd", player_id="MS Dhoni IND")

    def test_reason_optional(self) -> None:
        """reason field is optional."""
        o = PlayerOverride(alias="virat", player_id="virat-kohli-ind")
        assert o.reason is None
