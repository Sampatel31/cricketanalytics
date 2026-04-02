#!/usr/bin/env python3
"""CLI script for generating the 2D Galaxy View visualization.

Usage::

    python scripts/visualize_galaxy.py \\
        --features-parquet data/models/features_matrix_T20I_2024.parquet \\
        --archetypes-json data/models/archetypes_T20I_2024.json \\
        --output-dir data/visualizations \\
        --format T20I \\
        --season 2024
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate 2D Galaxy View")
    parser.add_argument(
        "--features-parquet",
        required=True,
        help="Path to feature matrix Parquet file",
    )
    parser.add_argument(
        "--archetypes-json",
        required=True,
        help="Path to archetypes JSON file",
    )
    parser.add_argument(
        "--output-dir",
        default="data/visualizations",
        help="Output directory",
    )
    parser.add_argument("--format", default="T20I", help="Cricket format label")
    parser.add_argument("--season", default="2024", help="Season label")
    parser.add_argument(
        "--models-dir",
        default="data/models",
        help="Directory containing UMAP models",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    logger = logging.getLogger("visualize_galaxy")

    try:
        import plotly.graph_objects as go
    except ImportError:
        logger.error("plotly is required: pip install plotly kaleido")
        return 1

    import numpy as np
    import polars as pl

    from sovereign.intelligence.reducer import DimensionalityReducer

    parquet_path = pathlib.Path(args.features_parquet)
    archetypes_path = pathlib.Path(args.archetypes_json)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not parquet_path.exists():
        logger.error("Features Parquet not found: %s", parquet_path)
        return 1
    if not archetypes_path.exists():
        logger.error("Archetypes JSON not found: %s", archetypes_path)
        return 1

    logger.info("Loading features from %s", parquet_path)
    features_df = pl.read_parquet(str(parquet_path))

    with archetypes_path.open() as fh:
        archetypes_data = json.load(fh)

    # Get 2D coordinates
    reducer = DimensionalityReducer(models_dir=args.models_dir)
    if not reducer.load_models():
        logger.info("Fitting new UMAP models for visualization")
        reducer.fit(features_df, force=True)

    coords_2d = reducer.transform_viz(features_df)
    player_ids = features_df["player_id"].to_list() if "player_id" in features_df.columns else [f"p{i}" for i in range(len(features_df))]

    # Colour by archetype if available
    label_map: dict[str, str] = {}
    if "player_id" in features_df.columns:
        for arc in archetypes_data:
            label_map[arc["code"]] = arc["label"]

    fig = go.Figure()
    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
        "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
    ]

    if archetypes_data:
        # Render one trace per archetype with distinct colors
        for i, arc in enumerate(archetypes_data):
            color = colors[i % len(colors)]
            fig.add_trace(
                go.Scatter(
                    x=coords_2d[:, 0],
                    y=coords_2d[:, 1],
                    mode="markers",
                    name=arc["label"],
                    marker=dict(size=8, color=color, opacity=0.7),
                    text=player_ids,
                    hovertemplate="<b>%{text}</b><br>(%{x:.2f}, %{y:.2f})<extra></extra>",
                )
            )
    else:
        fig.add_trace(
            go.Scatter(
                x=coords_2d[:, 0],
                y=coords_2d[:, 1],
                mode="markers",
                name="Players",
                marker=dict(size=8, color=colors[0], opacity=0.7),
                text=player_ids,
                hovertemplate="<b>%{text}</b><br>(%{x:.2f}, %{y:.2f})<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"Galaxy View — {args.format} {args.season}",
        xaxis_title="UMAP Dimension 1",
        yaxis_title="UMAP Dimension 2",
        template="plotly_dark",
        width=1200,
        height=800,
    )

    html_name = f"galaxy_view_{args.format}_{args.season}.html"
    html_path = output_dir / html_name
    fig.write_html(str(html_path))
    logger.info("HTML visualization saved to %s", html_path)

    try:
        png_name = f"galaxy_view_{args.format}_{args.season}.png"
        png_path = output_dir / png_name
        fig.write_image(str(png_path))
        logger.info("PNG visualization saved to %s", png_path)
    except Exception as exc:
        logger.warning("Could not save PNG (kaleido required): %s", exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
