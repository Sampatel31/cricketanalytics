"""YAML/JSON Cricsheet file parser.

Supports both Cricsheet schema v1 (pre-2023, ``batsman`` key) and
v2 (post-2023, ``batter`` key, nested ``overs`` structure).

Usage::

    from pathlib import Path
    from sovereign.ingestion.parser import MatchParser

    parser = MatchParser()
    match = parser.parse(Path("mi_vs_csk.yaml"))
    if match is not None:
        print(len(match.deliveries))
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Generator, Iterable, Optional

import structlog
import yaml

from sovereign.ingestion.classifier import MatchClassifier, _is_franchise
from sovereign.ingestion.models import (
    MatchInfo,
    ParsedMatch,
    RawDelivery,
)

try:
    import orjson as _json_lib

    def _load_json(path: Path) -> dict:
        with path.open("rb") as fh:
            return _json_lib.loads(fh.read())

except ImportError:
    import json as _json_std

    def _load_json(path: Path) -> dict:  # type: ignore[misc]
        with path.open("r", encoding="utf-8") as fh:
            return _json_std.load(fh)


log = structlog.get_logger(__name__)

_classifier = MatchClassifier()


class MatchParseError(Exception):
    """Raised for unrecoverable parse errors."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Parse error in {path}: {reason}")


def _load_file(path: Path) -> dict:
    """Load YAML or JSON file and return the raw dict."""
    if not path.exists():
        raise MatchParseError(path, "File does not exist")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    elif suffix == ".json":
        data = _load_json(path)
    else:
        # Try YAML for unknown extensions
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise MatchParseError(path, "Root element is not a mapping")
    return data


def _parse_date(raw: object) -> date:
    """Parse a date from various Cricsheet representations."""
    if isinstance(raw, date):
        return raw
    if isinstance(raw, (list, tuple)) and raw:
        raw = raw[0]
    if isinstance(raw, str):
        return datetime.strptime(raw, "%Y-%m-%d").date()
    raise ValueError(f"Cannot parse date: {raw!r}")


def _extract_match_info(info: dict, path: Path) -> MatchInfo:
    """Extract :class:`MatchInfo` from the ``info`` block."""
    teams: list[str] = info.get("teams") or []
    if len(teams) < 2:
        raise MatchParseError(path, "Match info missing teams")

    # Date
    raw_dates = info.get("dates") or info.get("date")
    if not raw_dates:
        raise MatchParseError(path, "Match info missing date")
    match_date = _parse_date(raw_dates if not isinstance(raw_dates, list) else raw_dates[0])

    # match_id: derive from path if not present
    match_id = str(info.get("match_id") or path.stem)

    # Event / competition name
    event = info.get("event") or info.get("competition") or {}
    if isinstance(event, dict):
        event_name: Optional[str] = event.get("name")
        event_stage: Optional[str] = event.get("stage") or event.get("match_number")
        if isinstance(event_stage, int):
            event_stage = str(event_stage)
    else:
        event_name = str(event) if event else None
        event_stage = None

    return MatchInfo(
        match_id=match_id,
        date=match_date,
        format=info.get("match_type") or info.get("format") or "UNKNOWN",
        team1=teams[0],
        team2=teams[1],
        venue=info.get("venue"),
        event_name=event_name,
        event_stage=str(event_stage) if event_stage is not None else None,
        gender=info.get("gender", "male"),
        season=str(info.get("season")) if info.get("season") else None,
        match_type=info.get("match_type"),
        overs=info.get("overs"),
    )


def _is_wide(delivery: dict) -> bool:
    extras = delivery.get("extras") or {}
    return "wides" in extras


def _is_noball(delivery: dict) -> bool:
    extras = delivery.get("extras") or {}
    return "noballs" in extras


def _parse_delivery_v1(
    delivery: dict,
    innings_number: int,
    batting_team: str,
    bowling_team: str,
    over_number: int,
    ball_number: int,
) -> Optional[RawDelivery]:
    """Parse a v1-schema delivery dict."""
    try:
        batter_id = (
            delivery.get("batsman")
            or delivery.get("batter")
            or delivery.get("striker")
        )
        if not batter_id:
            return None
        bowler_id = delivery.get("bowler")
        if not bowler_id:
            return None
        non_striker_id = delivery.get("non_striker") or ""

        runs_block = delivery.get("runs") or {}
        runs_batter = int(runs_block.get("batsman") or runs_block.get("batter") or 0)
        runs_extras = int(runs_block.get("extras") or 0)
        runs_total = int(runs_block.get("total") or (runs_batter + runs_extras))

        is_wide = _is_wide(delivery)
        is_noball = _is_noball(delivery)
        is_legal = not is_wide and not is_noball

        wickets = delivery.get("wicket") or delivery.get("wickets") or []
        if isinstance(wickets, dict):
            wickets = [wickets]
        is_wicket = len(wickets) > 0
        wicket_kind: Optional[str] = None
        player_dismissed: Optional[str] = None
        if is_wicket and wickets:
            w = wickets[0]
            wicket_kind = w.get("kind")
            player_dismissed = w.get("player_out")

        return RawDelivery(
            batter_id=str(batter_id),
            bowler_id=str(bowler_id),
            non_striker_id=str(non_striker_id),
            batting_team=batting_team,
            bowling_team=bowling_team,
            innings_number=innings_number,
            over_number=over_number,
            ball_number=ball_number,
            runs_batter=runs_batter,
            runs_extras=runs_extras,
            runs_total=runs_total,
            is_legal_ball=is_legal,
            is_wicket=is_wicket,
            wicket_kind=wicket_kind,
            player_dismissed_id=player_dismissed,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("delivery_parse_error", error=str(exc), delivery=delivery)
        return None


def _parse_innings(innings_data: dict, innings_number: int) -> list[RawDelivery]:
    """Parse all deliveries from a single innings block (v1 or v2)."""
    deliveries: list[RawDelivery] = []

    # Determine batting/bowling teams
    batting_team: str = innings_data.get("team") or innings_data.get("batting_team") or ""
    bowling_team: str = innings_data.get("bowling_team") or ""

    # v2 format: overs list
    overs = innings_data.get("overs")
    if overs:
        for over_block in overs:
            over_number = int(over_block.get("over") or 0)
            for ball_idx, delivery in enumerate(over_block.get("deliveries") or []):
                parsed = _parse_delivery_v1(
                    delivery,
                    innings_number,
                    batting_team,
                    bowling_team,
                    over_number,
                    ball_idx,
                )
                if parsed is not None:
                    deliveries.append(parsed)
        return deliveries

    # v1 format: flat deliveries list
    flat_deliveries = innings_data.get("deliveries") or []
    for delivery_wrapper in flat_deliveries:
        # v1 deliveries are usually {"over.ball": {...}}
        if isinstance(delivery_wrapper, dict):
            for key, delivery in delivery_wrapper.items():
                try:
                    parts = str(key).split(".")
                    over_number = int(parts[0])
                    ball_number = int(parts[1]) if len(parts) > 1 else 0
                except (ValueError, IndexError):
                    over_number = 0
                    ball_number = 0
                parsed = _parse_delivery_v1(
                    delivery,
                    innings_number,
                    batting_team,
                    bowling_team,
                    over_number,
                    ball_number,
                )
                if parsed is not None:
                    deliveries.append(parsed)

    return deliveries


class MatchParser:
    """Parse Cricsheet YAML/JSON files into :class:`ParsedMatch` objects."""

    def parse(self, path: Path) -> Optional[ParsedMatch]:
        """Parse a single file.

        Returns ``None`` for franchise-rejected files.
        Raises :class:`MatchParseError` for unrecoverable errors.
        """
        data = _load_file(path)  # raises MatchParseError on missing file

        info: dict = data.get("info") or {}
        if not info:
            raise MatchParseError(path, "Missing 'info' block")

        # Franchise gate
        classification = _classifier.classify(info)
        if classification.is_rejected:
            log.debug(
                "parser_franchise_skip",
                path=str(path),
                reason=classification.rejection_reason,
            )
            return None

        # Extract metadata
        try:
            match_info = _extract_match_info(info, path)
        except MatchParseError:
            raise
        except Exception as exc:
            raise MatchParseError(path, f"Cannot extract match info: {exc}") from exc

        # Parse innings
        innings_list = data.get("innings") or []
        deliveries: list[RawDelivery] = []
        for idx, innings_data in enumerate(innings_list, start=1):
            # v2: innings_data may have a top key like {"1st innings": {...}}
            if isinstance(innings_data, dict):
                # Unwrap outer key if present
                inner = innings_data
                for v in innings_data.values():
                    if isinstance(v, dict):
                        inner = v
                        break
                try:
                    inn_deliveries = _parse_innings(inner, idx)
                    deliveries.extend(inn_deliveries)
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "innings_parse_error",
                        path=str(path),
                        innings=idx,
                        error=str(exc),
                    )

        if not deliveries:
            log.warning("zero_deliveries", path=str(path))

        return ParsedMatch(match_info=match_info, deliveries=deliveries)

    def parse_many(
        self, paths: Iterable[Path]
    ) -> Generator[ParsedMatch, None, None]:
        """Yield :class:`ParsedMatch` objects for each non-franchise file.

        Franchise files and parse errors are skipped silently (logged).
        """
        for path in paths:
            try:
                result = self.parse(path)
                if result is not None:
                    yield result
            except MatchParseError as exc:
                log.warning("parse_error_skip", path=str(path), error=str(exc))
            except Exception as exc:  # noqa: BLE001
                log.error("unexpected_parse_error", path=str(path), error=str(exc))
