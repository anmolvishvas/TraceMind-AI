"""Unit tests for statistical anomaly detectors (Z-Score, IQR, Isolation Forest, Ensemble)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.anomaly_detection.baseline import HistoricalBaselineCalculator
from app.anomaly_detection.statistical import (
    CompositeAnomalyDetector,
    IQRDetector,
    IsolationForestDetector,
    ZScoreDetector,
)
from app.schemas.anomaly import AnomalySeverity, AnomalyType, DetectionMethod, MetricDataPoint


@pytest.fixture
def baseline_and_points() -> tuple[any, list[MetricDataPoint]]:
    """Generate baseline and standard telemetry points with injected outliers."""
    calc = HistoricalBaselineCalculator()
    # Normal distribution with mean ~ 10, std ~ 1
    normal_history = [10.0, 10.2, 9.8, 10.5, 9.5, 10.1, 9.9, 10.3, 9.7, 10.0]
    baseline = calc.compute_baseline_from_series("order-service", normal_history)

    now = datetime.now(UTC)
    points = [
        MetricDataPoint(
            timestamp=now + timedelta(minutes=i), value=val, service_name="order-service"
        )
        for i, val in enumerate([10.1, 9.9, 10.2, 25.0, 10.0, 10.3, 40.0])
    ]
    return baseline, points


def test_z_score_detector_spike(baseline_and_points: tuple[any, list[MetricDataPoint]]) -> None:
    """Verify Z-score flags values > 3-sigma and classifies severity."""
    baseline, points = baseline_and_points
    detector = ZScoreDetector(threshold=3.0)
    anomalies = detector.detect(points, baseline)

    # Expected outliers: 25.0 (z ~ 15) and 40.0 (z ~ 30)
    assert len(anomalies) == 2
    assert anomalies[0].current_value == 25.0
    assert anomalies[0].detection_method == DetectionMethod.Z_SCORE
    assert anomalies[0].severity == AnomalySeverity.CRITICAL

    assert anomalies[1].current_value == 40.0
    assert anomalies[1].severity == AnomalySeverity.CRITICAL


def test_z_score_no_false_positives() -> None:
    """Ensure normal fluctuations below 3-sigma do not trigger false positives."""
    calc = HistoricalBaselineCalculator()
    baseline = calc.compute_baseline_from_series("auth-service", [10.0, 10.0, 10.0])
    points = [
        MetricDataPoint(timestamp=datetime.now(UTC), value=10.0, service_name="auth-service"),
        MetricDataPoint(timestamp=datetime.now(UTC), value=10.0001, service_name="auth-service"),
    ]
    detector = ZScoreDetector(threshold=3.0)
    anomalies = detector.detect(points, baseline)
    assert len(anomalies) == 0


def test_iqr_detector_outliers(baseline_and_points: tuple[any, list[MetricDataPoint]]) -> None:
    """Verify IQR Tukey fences flag values beyond Q3 + 1.5 * IQR."""
    baseline, points = baseline_and_points
    detector = IQRDetector(k=1.5)
    anomalies = detector.detect(points, baseline)

    assert len(anomalies) >= 2
    assert any(a.current_value == 25.0 for a in anomalies)
    assert any(a.current_value == 40.0 for a in anomalies)
    assert all(a.detection_method == DetectionMethod.IQR for a in anomalies)


def test_isolation_forest_detector() -> None:
    """Verify Isolation Forest flags multi-dimensional outliers in time series."""
    calc = HistoricalBaselineCalculator()
    normal_values = [10.0] * 20
    baseline = calc.compute_baseline_from_series("payment-service", normal_values)

    now = datetime.now(UTC)
    points = [
        MetricDataPoint(
            timestamp=now + timedelta(seconds=i * 10), value=10.0, service_name="payment-service"
        )
        for i in range(15)
    ]
    # Inject sudden outlier
    points.append(
        MetricDataPoint(
            timestamp=now + timedelta(seconds=160), value=95.0, service_name="payment-service"
        )
    )
    points.append(
        MetricDataPoint(
            timestamp=now + timedelta(seconds=170), value=10.0, service_name="payment-service"
        )
    )

    detector = IsolationForestDetector(contamination=0.1)
    anomalies = detector.detect(points, baseline)

    assert len(anomalies) >= 1
    assert any(a.current_value == 95.0 for a in anomalies)
    assert anomalies[0].detection_method == DetectionMethod.ISOLATION_FOREST


def test_composite_ensemble_voting(baseline_and_points: tuple[any, list[MetricDataPoint]]) -> None:
    """Verify Ensemble combines detectors, determines consensus confidence and morphology."""
    baseline, points = baseline_and_points
    ensemble = CompositeAnomalyDetector(z_threshold=3.0, iqr_k=1.5)
    anomalies = ensemble.detect(points, baseline)

    assert len(anomalies) == 2
    for a in anomalies:
        assert a.detection_method == DetectionMethod.ENSEMBLE
        assert a.confidence >= 0.85
        assert a.details["consensus_votes"] >= 2
        assert a.anomaly_type in (AnomalyType.SPIKE, AnomalyType.ERROR_BURST)


def test_composite_ensemble_step_change() -> None:
    """Verify morphology detection identifies sustained step changes."""
    calc = HistoricalBaselineCalculator()
    baseline = calc.compute_baseline_from_series("api", [10.0] * 10)

    now = datetime.now(UTC)
    # 5 consecutive elevated points
    points = [
        MetricDataPoint(timestamp=now + timedelta(minutes=i), value=50.0, service_name="api")
        for i in range(5)
    ]

    ensemble = CompositeAnomalyDetector()
    anomalies = ensemble.detect(points, baseline)

    assert len(anomalies) > 0
    assert anomalies[0].anomaly_type == AnomalyType.STEP_CHANGE
