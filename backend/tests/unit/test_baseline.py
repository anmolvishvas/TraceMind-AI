"""Unit tests for HistoricalBaselineCalculator and EMA."""

import pytest

from app.anomaly_detection.baseline import MIN_STD_DEV_FLOOR, HistoricalBaselineCalculator


def test_baseline_empty_series() -> None:
    """Verify baseline calculation for empty dataset."""
    calc = HistoricalBaselineCalculator()
    baseline = calc.compute_baseline_from_series("payment-service", [])
    assert baseline.service_name == "payment-service"
    assert baseline.mean == 0.0
    assert baseline.std_dev == MIN_STD_DEV_FLOOR
    assert baseline.sample_size == 0
    assert baseline.iqr == 0.0


def test_baseline_single_element() -> None:
    """Verify baseline calculation for single observation."""
    calc = HistoricalBaselineCalculator()
    baseline = calc.compute_baseline_from_series("auth-service", [42.0])
    assert baseline.service_name == "auth-service"
    assert baseline.mean == 42.0
    assert baseline.std_dev == MIN_STD_DEV_FLOOR
    assert baseline.sample_size == 1
    assert baseline.median == 42.0


def test_baseline_known_distribution() -> None:
    """Verify baseline statistical properties on known numerical series."""
    calc = HistoricalBaselineCalculator()
    series = [10.0, 12.0, 11.0, 10.5, 11.5, 9.5, 10.0, 12.5]
    baseline = calc.compute_baseline_from_series("api-gateway", series)

    assert baseline.service_name == "api-gateway"
    assert baseline.sample_size == len(series)
    assert 10.0 < baseline.mean < 12.0
    assert baseline.std_dev > 0.5
    assert baseline.q1 < baseline.median < baseline.q3
    assert baseline.iqr == pytest.approx(baseline.q3 - baseline.q1)


def test_ema_calculation() -> None:
    """Verify exponential moving average smoothing."""
    series = [10.0, 20.0, 30.0, 40.0]
    ema = HistoricalBaselineCalculator.compute_exponential_moving_average(series, alpha=0.5)

    assert len(ema) == 4
    assert ema[0] == 10.0
    assert ema[1] == 15.0  # 0.5 * 20 + 0.5 * 10
    assert ema[2] == 22.5  # 0.5 * 30 + 0.5 * 15
    assert ema[3] == 31.25  # 0.5 * 40 + 0.5 * 22.5


def test_ema_invalid_alpha() -> None:
    """Verify ValueError is raised on invalid alpha."""
    with pytest.raises(ValueError, match="Alpha must be in range"):
        HistoricalBaselineCalculator.compute_exponential_moving_average([1.0], alpha=0.0)

    with pytest.raises(ValueError, match="Alpha must be in range"):
        HistoricalBaselineCalculator.compute_exponential_moving_average([1.0], alpha=1.5)


@pytest.mark.asyncio
async def test_baseline_redis_fallback() -> None:
    """Verify get_or_create_service_baseline works when Redis is None."""
    calc = HistoricalBaselineCalculator(redis_client=None)
    baseline = await calc.get_or_create_service_baseline(
        service_name="cart-service",
        fallback_series=[1.0, 2.0, 3.0, 4.0, 5.0],
    )
    assert baseline.service_name == "cart-service"
    assert baseline.mean == 3.0
    assert baseline.sample_size == 5
