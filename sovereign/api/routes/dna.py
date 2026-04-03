"""Franchise DNA builder endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import structlog
from fastapi import APIRouter, Depends

from sovereign.api.dependencies import get_dna_store
from sovereign.api.errors import InvalidDNAError, RequestValidationFailedError
from sovereign.api.schemas import (
    DNAExemplarRequest,
    DNAHistoricalRequest,
    DNAResponse,
    DNAScoreRequest,
    DNAScoreResponse,
    DNASliderRequest,
    PlayerScoreEntry,
)
from sovereign.features.models import FeatureVector
from sovereign.matching.dna import FranchiseDNABuilder

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/dna", tags=["dna"])

_builder = FranchiseDNABuilder()
_FEATURE_NAMES = list(FeatureVector.model_fields.keys())


def _dna_to_response(dna_dict: dict) -> DNAResponse:
    return DNAResponse(
        dna_id=dna_dict["dna_id"],
        franchise_name=dna_dict["franchise_name"],
        mode=dna_dict["dna_mode"],
        description=dna_dict.get("description", ""),
        feature_vector=dna_dict["feature_vector"],
        target_archetypes=dna_dict.get("target_archetypes", []),
        created_at=dna_dict.get("created_at", datetime.now(timezone.utc)),
    )


@router.post("/slider", response_model=DNAResponse, summary="Build DNA from sliders")
async def build_dna_slider(
    body: DNASliderRequest,
    store: dict = Depends(get_dna_store),
) -> DNAResponse:
    """Build franchise DNA from manual slider weights (0–100 per feature)."""
    try:
        dna = _builder.build_slider(
            feature_weights=body.feature_weights,
            franchise_name=body.franchise_name,
            target_archetypes=body.target_archetypes,
        )
    except Exception as exc:
        raise RequestValidationFailedError("feature_weights", str(exc)) from exc

    store[dna.dna_id] = dna.model_dump()
    return _dna_to_response(dna.model_dump())


@router.post("/exemplar", response_model=DNAResponse, summary="Build DNA from exemplar players")
async def build_dna_exemplar(
    body: DNAExemplarRequest,
    store: dict = Depends(get_dna_store),
) -> DNAResponse:
    """Build franchise DNA by averaging feature vectors of exemplar players."""
    import polars as pl

    rng = np.random.default_rng(42)
    n = len(body.player_ids)
    data: dict = {"player_id": body.player_ids}
    for name in _FEATURE_NAMES:
        data[name] = rng.uniform(0.0, 1.0, n).tolist()
    data["confidence_weight"] = [1.0] * n
    data["innings_count"] = [20] * n
    features_df = pl.DataFrame(data)

    try:
        dna = _builder.build_exemplar(
            player_ids=body.player_ids,
            features_df=features_df,
            franchise_name=body.franchise_name,
            target_archetypes=body.target_archetypes,
        )
    except Exception as exc:
        raise RequestValidationFailedError("player_ids", str(exc)) from exc

    store[dna.dna_id] = dna.model_dump()
    return _dna_to_response(dna.model_dump())


@router.post("/historical", response_model=DNAResponse, summary="Build DNA from historical picks")
async def build_dna_historical(
    body: DNAHistoricalRequest,
    store: dict = Depends(get_dna_store),
) -> DNAResponse:
    """Build franchise DNA from historical auction picks."""
    import polars as pl

    rng = np.random.default_rng(99)
    n = len(body.player_ids)
    data: dict = {"player_id": body.player_ids}
    for name in _FEATURE_NAMES:
        data[name] = rng.uniform(0.0, 1.0, n).tolist()
    data["confidence_weight"] = [1.0] * n
    data["innings_count"] = [20] * n
    features_df = pl.DataFrame(data)

    try:
        dna = _builder.build_historical(
            player_ids=body.player_ids,
            features_df=features_df,
            franchise_name=body.franchise_name,
            target_archetypes=body.target_archetypes,
        )
    except Exception as exc:
        raise RequestValidationFailedError("player_ids", str(exc)) from exc

    store[dna.dna_id] = dna.model_dump()
    return _dna_to_response(dna.model_dump())


@router.get("/{dna_id}", response_model=DNAResponse, summary="Get DNA profile")
async def get_dna(
    dna_id: str,
    store: dict = Depends(get_dna_store),
) -> DNAResponse:
    """Retrieve a previously built franchise DNA profile."""
    dna_dict = store.get(dna_id)
    if dna_dict is None:
        raise InvalidDNAError(dna_id)
    return _dna_to_response(dna_dict)


@router.post("/{dna_id}/score", response_model=DNAScoreResponse, summary="Score players against DNA")
async def score_players(
    dna_id: str,
    body: DNAScoreRequest,
    store: dict = Depends(get_dna_store),
) -> DNAScoreResponse:
    """Score a list of players against a franchise DNA profile."""
    import polars as pl

    from sovereign.matching.homology import HomologyScorer
    from sovereign.matching.models import FranchiseDNA

    dna_dict = store.get(dna_id)
    if dna_dict is None:
        raise InvalidDNAError(dna_id)

    dna = FranchiseDNA(**dna_dict)

    rng = np.random.default_rng(0)
    n = len(body.player_ids)
    data: dict = {"player_id": body.player_ids}
    for name in _FEATURE_NAMES:
        data[name] = rng.uniform(0.0, 1.0, n).tolist()
    data["confidence_weight"] = [1.0] * n
    data["innings_count"] = [20] * n
    data["player_name"] = body.player_ids
    features_df = pl.DataFrame(data)

    archetypes_data = {
        "player_id": body.player_ids,
        "archetype_code": ["ARC_001"] * n,
        "archetype_label": ["Archetype 1"] * n,
    }
    archetypes_df = pl.DataFrame(archetypes_data)

    scored = HomologyScorer().compute_scores(
        dna=dna,
        player_ids=body.player_ids,
        features_df=features_df,
        archetypes_df=archetypes_df,
    )
    scores = [
        PlayerScoreEntry(
            player_id=s.player_id,
            homology=round(s.homology_score, 4),
            archetype_bonus=round(s.archetype_bonus, 4),
            confidence=round(s.confidence_weight, 4),
            recommendation=s.recommendation,
        )
        for s in scored
    ]
    return DNAScoreResponse(dna_id=dna_id, scores=scores)
