"""Feature engineering package for Sovereign Cricket Analytics.

This package transforms raw cricket deliveries into 54-dimensional
behavioral fingerprints for every player.  Each dimension captures a
specific aspect of player behaviour:

- Pressure Response  (12 features): how the player performs under SPI tiers
- Phase Performance  (12 features): powerplay / middle / death splits
- Tactical          (15 features): behavioral patterns and decision-making
- Stability          (9 features):  form trajectory and career consistency
- Opposition Quality (6 features):  context-adjusted metrics vs ranked attacks
"""

from sovereign.features.models import (
    FeatureComputationError,
    FeatureStats,
    FeatureVector,
    InsufficientDataError,
    PlayerFeatures,
)

__all__ = [
    "FeatureComputationError",
    "FeatureStats",
    "FeatureVector",
    "InsufficientDataError",
    "PlayerFeatures",
]
