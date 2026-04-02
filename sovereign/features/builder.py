"""Feature Builder — orchestrate all five modules into one 54D vector.

This module is the entry point for Phase 2.  It drives all five feature
modules (pressure response, phase performance, tactical, stability, opposition
quality) and merges their outputs into a single :class:`FeatureVector` per
player.

Output schema
-------------
The :meth:`FeatureBuilder.build_all` method returns a Polars DataFrame with:

- ``player_id``, ``format_type``, ``season``, ``confidence_weight``,
  ``innings_count``
- 54 feature columns named after the :class:`~sovereign.features.models.FeatureVector`
  fields

``None`` / ``NaN`` values are replaced by the column mean across all players
before the DataFrame is returned, so the output is always fully populated.
"""

from __future__ import annotations

import logging
import pathlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

import polars as pl

from sovereign.features.models import (
    FeatureVector,
    PlayerFeatures,
    compute_confidence_weight,
)
from sovereign.features.opposition import OppositionQualityFeatures
from sovereign.features.phase_performance import PhasePerformanceFeatures
from sovereign.features.pressure_response import PressureResponseFeatures
from sovereign.features.stability import StabilityFeatures
from sovereign.features.tactical import TacticalFeatures

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker function (must be module-level for pickling with ProcessPoolExecutor)
# ---------------------------------------------------------------------------


def _build_player_worker(args: tuple) -> dict:
    """Top-level worker function executed in a subprocess.

    Args:
        args: Tuple of ``(player_id, player_df, format_type, seasons_data,
              match_info, role)``.

    Returns:
        Dictionary with ``player_id`` and all 54 raw feature values
        (``None`` where computation failed or data was insufficient).
    """
    (
        player_id,
        player_df,
        format_type,
        seasons_data,
        match_info,
        role,
    ) = args

    record: dict = {"player_id": player_id}
    try:
        # Pressure response
        prf = PressureResponseFeatures()
        record.update(prf.compute(player_id, player_df))
    except Exception as exc:
        logger.warning("PressureResponseFeatures failed for %s: %s", player_id, exc)

    try:
        # Phase performance
        ppf = PhasePerformanceFeatures()
        record.update(ppf.compute(player_id, player_df, format_type, role))
    except Exception as exc:
        logger.warning("PhasePerformanceFeatures failed for %s: %s", player_id, exc)

    try:
        # Tactical
        tf = TacticalFeatures()
        record.update(tf.compute(player_id, player_df))
    except Exception as exc:
        logger.warning("TacticalFeatures failed for %s: %s", player_id, exc)

    try:
        # Stability
        sf = StabilityFeatures()
        record.update(sf.compute(player_id, seasons_data or []))
    except Exception as exc:
        logger.warning("StabilityFeatures failed for %s: %s", player_id, exc)

    try:
        # Opposition quality
        oqf = OppositionQualityFeatures()
        record.update(oqf.compute(player_id, player_df, match_info or []))
    except Exception as exc:
        logger.warning(
            "OppositionQualityFeatures failed for %s: %s", player_id, exc
        )

    return record


# ---------------------------------------------------------------------------
# FeatureBuilder
# ---------------------------------------------------------------------------


class FeatureBuilder:
    """Orchestrate feature computation for an entire cohort of players.

    Usage::

        builder = FeatureBuilder(n_workers=4, batch_size=100)
        df = builder.build_all(
            player_ids=["p1", "p2"],
            deliveries_df=deliveries,
            seasons_data={"p1": [...], "p2": [...]},
            format_type="T20I",
            season="2024",
        )
        # df has shape (n_players, 59) including metadata columns

    Args:
        n_workers: Number of parallel workers (``ProcessPoolExecutor``).
            Use 1 to run sequentially (easier debugging).
        batch_size: Players processed per batch (for memory management).
    """

    def __init__(self, n_workers: int = 4, batch_size: int = 100) -> None:
        self.n_workers = n_workers
        self.batch_size = batch_size

        # Canonical feature names from FeatureVector
        self._feature_names: list[str] = list(FeatureVector.model_fields.keys())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_all(
        self,
        player_ids: list[str],
        deliveries_df: pl.DataFrame,
        seasons_data: Optional[dict[str, list[dict]]] = None,
        match_info: Optional[dict[str, list[dict]]] = None,
        format_type: str = "T20I",
        season: str = "2024",
        role_map: Optional[dict[str, str]] = None,
        output_dir: Optional[str] = None,
    ) -> pl.DataFrame:
        """Build the full player × 54 feature matrix.

        Args:
            player_ids: List of player IDs to process.
            deliveries_df: Full delivery-level DataFrame.  Must contain a
                ``batter_id`` or ``player_id`` column to filter per-player.
            seasons_data: Mapping from player_id to their seasons data list
                (as expected by :class:`~sovereign.features.stability.StabilityFeatures`).
            match_info: Mapping from player_id to their per-match info list
                (as expected by :class:`~sovereign.features.opposition.OppositionQualityFeatures`).
            format_type: Cricket format string (``'T20I'``, ``'ODI'``, ``'TEST'``).
            season: Season label (e.g. ``"2024"``).
            role_map: Optional mapping from player_id → ``'batter'`` or
                ``'bowler'``.  Defaults to ``'batter'`` for all players.
            output_dir: If provided, save the Parquet output to this directory.

        Returns:
            Polars DataFrame with columns:
            ``player_id``, ``format_type``, ``season``, ``confidence_weight``,
            ``innings_count``, plus all 54 feature columns.
        """
        seasons_data = seasons_data or {}
        match_info = match_info or {}
        role_map = role_map or {}

        # Determine the player column name
        player_col = self._detect_player_column(deliveries_df)

        all_records: list[dict] = []

        # Process in batches
        for batch_start in range(0, len(player_ids), self.batch_size):
            batch = player_ids[batch_start: batch_start + self.batch_size]
            logger.info(
                "Processing batch %d/%d (%d players)",
                batch_start // self.batch_size + 1,
                -(-len(player_ids) // self.batch_size),
                len(batch),
            )
            batch_records = self._process_batch(
                batch,
                deliveries_df,
                player_col,
                seasons_data,
                match_info,
                format_type,
                role_map,
            )
            all_records.extend(batch_records)

        if not all_records:
            logger.warning("No feature records produced; returning empty DataFrame.")
            return pl.DataFrame()

        # Build raw DataFrame
        raw_df = pl.DataFrame(all_records)

        # Compute innings count and confidence weight per player
        innings_counts = self._compute_innings_counts(
            player_ids, deliveries_df, player_col
        )
        innings_df = pl.DataFrame(
            {
                "player_id": list(innings_counts.keys()),
                "innings_count": list(innings_counts.values()),
            }
        )
        raw_df = raw_df.join(innings_df, on="player_id", how="left")

        # Impute NaN/None with column mean
        feature_df = self._impute_nulls(raw_df)

        # Add metadata columns
        n = len(feature_df)
        feature_df = feature_df.with_columns([
            pl.lit(format_type).alias("format_type"),
            pl.lit(season).alias("season"),
        ])

        # Compute confidence weight
        def _cw(ic: Optional[int]) -> float:
            return compute_confidence_weight(int(ic) if ic is not None else 0)

        feature_df = feature_df.with_columns(
            pl.col("innings_count")
            .map_elements(_cw, return_dtype=pl.Float64)
            .alias("confidence_weight")
        )

        # Reorder columns
        meta_cols = [
            "player_id", "format_type", "season", "confidence_weight",
            "innings_count",
        ]
        feat_cols = [c for c in self._feature_names if c in feature_df.columns]
        final_df = feature_df.select(meta_cols + feat_cols)

        # Optionally save to Parquet
        if output_dir:
            self._save_parquet(final_df, output_dir, format_type, season)

        return final_df

    def build_player(
        self,
        player_id: str,
        deliveries_df: pl.DataFrame,
        format_type: str = "T20I",
        seasons_data: Optional[list[dict]] = None,
        match_info: Optional[list[dict]] = None,
        role: str = "batter",
    ) -> PlayerFeatures:
        """Build a :class:`PlayerFeatures` record for a single player.

        Args:
            player_id: Player ID.
            deliveries_df: Delivery-level DataFrame *already filtered* to this
                player.
            format_type: Cricket format.
            seasons_data: Stability seasons data for this player.
            match_info: Opposition quality match data for this player.
            role: ``'batter'`` or ``'bowler'``.

        Returns:
            Fully populated :class:`PlayerFeatures` with computed features.
        """
        raw = _build_player_worker(
            (
                player_id,
                deliveries_df,
                format_type,
                seasons_data or [],
                match_info or [],
                role,
            )
        )

        innings_count = self._count_innings(deliveries_df)
        fv_data = {
            k: v for k, v in raw.items() if k in FeatureVector.model_fields
        }
        fv = FeatureVector(**fv_data)

        return PlayerFeatures(
            player_id=player_id,
            format_type=format_type,
            season="",
            features=fv,
            confidence_weight=compute_confidence_weight(innings_count),
            innings_count=innings_count,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_batch(
        self,
        batch: list[str],
        deliveries_df: pl.DataFrame,
        player_col: str,
        seasons_data: dict[str, list[dict]],
        match_info: dict[str, list[dict]],
        format_type: str,
        role_map: dict[str, str],
    ) -> list[dict]:
        """Process a batch of players, optionally in parallel."""
        args_list = []
        for pid in batch:
            player_df = deliveries_df.filter(pl.col(player_col) == pid)
            args_list.append(
                (
                    pid,
                    player_df,
                    format_type,
                    seasons_data.get(pid, []),
                    match_info.get(pid, []),
                    role_map.get(pid, "batter"),
                )
            )

        records: list[dict] = []
        if self.n_workers <= 1 or len(args_list) <= 1:
            for args in args_list:
                records.append(_build_player_worker(args))
        else:
            with ProcessPoolExecutor(max_workers=self.n_workers) as pool:
                futures = {
                    pool.submit(_build_player_worker, args): args[0]
                    for args in args_list
                }
                for fut in as_completed(futures):
                    try:
                        records.append(fut.result())
                    except Exception as exc:
                        pid = futures[fut]
                        logger.error(
                            "Worker failed for player %s: %s", pid, exc
                        )
                        records.append({"player_id": pid})

        return records

    def _impute_nulls(self, df: pl.DataFrame) -> pl.DataFrame:
        """Replace None / NaN in feature columns with the column mean."""
        feat_cols = [
            c for c in self._feature_names if c in df.columns
        ]
        exprs = []
        for col in feat_cols:
            col_mean = df[col].cast(pl.Float64).mean()
            fill_val = col_mean if col_mean is not None else 0.0
            exprs.append(
                pl.col(col)
                .cast(pl.Float64)
                .fill_null(fill_val)
                .fill_nan(fill_val)
                .alias(col)
            )
        if exprs:
            df = df.with_columns(exprs)
        return df

    def _compute_innings_counts(
        self,
        player_ids: list[str],
        deliveries_df: pl.DataFrame,
        player_col: str,
    ) -> dict[str, int]:
        """Estimate innings count per player from the deliveries DataFrame."""
        counts: dict[str, int] = {}
        for pid in player_ids:
            pdf = deliveries_df.filter(pl.col(player_col) == pid)
            counts[pid] = self._count_innings(pdf)
        return counts

    @staticmethod
    def _count_innings(player_df: pl.DataFrame) -> int:
        """Count unique innings in *player_df*."""
        if "innings_number" in player_df.columns:
            try:
                return int(player_df["innings_number"].n_unique())
            except Exception:
                pass
        if "match_id" in player_df.columns:
            try:
                return int(player_df["match_id"].n_unique())
            except Exception:
                pass
        # Fallback: treat the entire dataset as one innings
        return 1 if len(player_df) > 0 else 0

    @staticmethod
    def _detect_player_column(df: pl.DataFrame) -> str:
        """Return the first player-ID column found in *df*."""
        for col in ("batter_id", "player_id", "bowler_id"):
            if col in df.columns:
                return col
        raise ValueError(
            "deliveries_df must contain one of: batter_id, player_id, bowler_id"
        )

    @staticmethod
    def _save_parquet(
        df: pl.DataFrame,
        output_dir: str,
        format_type: str,
        season: str,
    ) -> pathlib.Path:
        """Save *df* as a Parquet file and return the path."""
        out = pathlib.Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        fname = f"features_matrix_{format_type}_{season}.parquet"
        path = out / fname
        df.write_parquet(str(path))
        logger.info("Feature matrix saved to %s", path)
        return path
