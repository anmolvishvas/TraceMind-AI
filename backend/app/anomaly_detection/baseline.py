"""Historical statistical baseline calculation for operational telemetry and error rates."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import numpy as np

from app.schemas.anomaly import ServiceBaseline

if TYPE_CHECKING:
    from redis.asyncio import Redis

    RedisClient = Redis[str]
else:
    RedisClient = Any

logger = logging.getLogger("tracemind.anomaly.baseline")

# Default floor to prevent division by zero in zero-variance distributions
MIN_STD_DEV_FLOOR = 1e-4


class HistoricalBaselineCalculator:
    """
    Computes statistical profiles (Mean, Variance, StdDev, Median, IQR, EMA)
    for service telemetry over rolling observation windows.
    """

    def __init__(self, redis_client: RedisClient | None = None) -> None:
        self.redis = redis_client

    def compute_baseline_from_series(
        self,
        service_name: str,
        values: list[float],
        metric_name: str = "error_rate",
        window_hours: int = 168,
    ) -> ServiceBaseline:
        """
        Calculate complete statistical baseline from a list of numerical observations.
        Handles small sample sizes, edge cases, and zero variance gracefully.
        """
        if not values:
            return ServiceBaseline(
                service_name=service_name,
                metric_name=metric_name,
                window_hours=window_hours,
                mean=0.0,
                std_dev=MIN_STD_DEV_FLOOR,
                median=0.0,
                iqr=0.0,
                q1=0.0,
                q3=0.0,
                sample_size=0,
                updated_at=datetime.now(UTC),
            )

        arr = np.array(values, dtype=np.float64)
        sample_size = len(arr)

        mean_val = float(np.mean(arr))
        # Use ddof=1 for sample standard deviation if sample_size > 1
        std_val = float(np.std(arr, ddof=1)) if sample_size > 1 else 0.0

        # Enforce minimum noise floor to prevent division by zero
        if std_val < MIN_STD_DEV_FLOOR:
            std_val = MIN_STD_DEV_FLOOR

        q1 = float(np.percentile(arr, 25))
        median_val = float(np.median(arr))
        q3 = float(np.percentile(arr, 75))
        iqr_val = float(max(0.0, q3 - q1))

        return ServiceBaseline(
            service_name=service_name,
            metric_name=metric_name,
            window_hours=window_hours,
            mean=mean_val,
            std_dev=std_val,
            median=median_val,
            iqr=iqr_val,
            q1=q1,
            q3=q3,
            sample_size=sample_size,
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    def compute_exponential_moving_average(
        values: list[float],
        alpha: float = 0.2,
    ) -> list[float]:
        """
        Calculate rolling Exponential Moving Average (EMA).
        EMA_t = alpha * x_t + (1 - alpha) * EMA_{t-1}
        """
        if not values:
            return []

        if not 0.0 < alpha <= 1.0:
            raise ValueError(f"Alpha must be in range (0.0, 1.0], got {alpha}")

        ema = [values[0]]
        for val in values[1:]:
            next_val = (alpha * val) + ((1.0 - alpha) * ema[-1])
            ema.append(next_val)

        return ema

    async def get_or_create_service_baseline(
        self,
        service_name: str,
        metric_name: str = "error_rate",
        fallback_series: list[float] | None = None,
    ) -> ServiceBaseline:
        """
        Retrieve service baseline from Redis cache, or calculate from fallback
        observations if cache is cold.
        """
        cache_key = f"tracemind:baseline:{service_name}:{metric_name}"

        if self.redis is not None:
            try:
                cached_json = await self.redis.get(cache_key)
                if cached_json:
                    return ServiceBaseline.model_validate_json(cached_json)
            except Exception as exc:
                logger.warning("Failed to retrieve baseline from Redis: %s", exc)

        # Compute from provided series or create safe default baseline
        series = fallback_series or [0.0, 0.0, 0.0]
        baseline = self.compute_baseline_from_series(
            service_name=service_name,
            values=series,
            metric_name=metric_name,
        )

        if self.redis is not None:
            try:
                await self.redis.set(
                    cache_key,
                    baseline.model_dump_json(),
                    ex=3600,  # 1 hour TTL
                )
            except Exception as exc:
                logger.debug("Failed to cache baseline in Redis: %s", exc)

        return baseline
