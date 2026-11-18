"""Statistical anomaly detection algorithms: Z-Score, IQR, Isolation Forest, and Ensemble.

Completely decoupled from LLMs — 100% deterministic, numerical inference.
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
from sklearn.ensemble import IsolationForest

from app.anomaly_detection.baseline import MIN_STD_DEV_FLOOR
from app.schemas.anomaly import (
    AnomalyRecord,
    AnomalySeverity,
    AnomalyType,
    DetectionMethod,
    MetricDataPoint,
    ServiceBaseline,
)

logger = logging.getLogger("tracemind.anomaly.statistical")


class ZScoreDetector:
    """
    Parametric anomaly detector utilizing standard score (Z-Score).
    z = (x - mean) / std_dev
    """

    def __init__(self, threshold: float = 3.0) -> None:
        self.threshold = threshold

    def detect(
        self,
        data_points: list[MetricDataPoint],
        baseline: ServiceBaseline,
    ) -> list[AnomalyRecord]:
        """Evaluate data points against the historical baseline using Z-score."""
        anomalies: list[AnomalyRecord] = []
        std = max(baseline.std_dev, MIN_STD_DEV_FLOOR)

        for pt in data_points:
            z_score = (pt.value - baseline.mean) / std

            if z_score >= self.threshold:
                # Normalize score to [0.0, 1.0] capped at z=10
                norm_score = float(min(1.0, max(0.0, z_score / 10.0)))
                severity = self._classify_severity(z_score)
                confidence = float(min(0.99, 0.5 + (norm_score * 0.49)))

                record = AnomalyRecord(
                    service_name=pt.service_name,
                    timestamp=pt.timestamp,
                    metric_name=baseline.metric_name,
                    current_value=pt.value,
                    baseline_mean=baseline.mean,
                    baseline_std=baseline.std_dev,
                    threshold=baseline.mean + (self.threshold * std),
                    anomaly_score=norm_score,
                    severity=severity,
                    anomaly_type=AnomalyType.SPIKE,
                    detection_method=DetectionMethod.Z_SCORE,
                    confidence=confidence,
                    details={
                        "z_score": round(float(z_score), 3),
                        "threshold_z": self.threshold,
                        "deviation_multiplier": round(
                            float(pt.value / max(baseline.mean, 1e-4)), 2
                        ),
                    },
                )
                anomalies.append(record)

        return anomalies

    def _classify_severity(self, z_score: float) -> AnomalySeverity:
        if z_score >= 6.0:
            return AnomalySeverity.CRITICAL
        if z_score >= 4.5:
            return AnomalySeverity.HIGH
        if z_score >= 3.0:
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW


class IQRDetector:
    """
    Non-parametric anomaly detector utilizing Interquartile Range (Tukey's Fences).
    Threshold = Q3 + (k * IQR)
    """

    def __init__(self, k: float = 1.5) -> None:
        self.k = k

    def detect(
        self,
        data_points: list[MetricDataPoint],
        baseline: ServiceBaseline,
    ) -> list[AnomalyRecord]:
        """Evaluate data points against IQR fences."""
        anomalies: list[AnomalyRecord] = []
        effective_iqr = max(baseline.iqr, MIN_STD_DEV_FLOOR)
        threshold_val = baseline.q3 + (self.k * effective_iqr)

        for pt in data_points:
            if pt.value > threshold_val:
                excess = pt.value - threshold_val
                # Normalized score based on how many IQRs beyond threshold
                iqr_multiple = excess / effective_iqr
                norm_score = float(min(1.0, 0.5 + min(0.5, iqr_multiple * 0.15)))

                severity = (
                    AnomalySeverity.CRITICAL
                    if iqr_multiple >= 3.0
                    else (AnomalySeverity.HIGH if iqr_multiple >= 1.5 else AnomalySeverity.MEDIUM)
                )

                record = AnomalyRecord(
                    service_name=pt.service_name,
                    timestamp=pt.timestamp,
                    metric_name=baseline.metric_name,
                    current_value=pt.value,
                    baseline_mean=baseline.mean,
                    baseline_std=baseline.std_dev,
                    threshold=threshold_val,
                    anomaly_score=norm_score,
                    severity=severity,
                    anomaly_type=AnomalyType.ERROR_BURST,
                    detection_method=DetectionMethod.IQR,
                    confidence=0.85,
                    details={
                        "q1": baseline.q1,
                        "median": baseline.median,
                        "q3": baseline.q3,
                        "iqr": baseline.iqr,
                        "iqr_multiple": round(float(iqr_multiple), 2),
                    },
                )
                anomalies.append(record)

        return anomalies


class IsolationForestDetector:
    """
    Multi-dimensional unsupervised anomaly detector using Scikit-Learn IsolationForest.
    Features extracted: [value, step_delta, deviation_from_mean]
    """

    def __init__(self, contamination: float = 0.05, random_state: int = 42) -> None:
        self.contamination = contamination
        self.random_state = random_state

    def detect(
        self,
        data_points: list[MetricDataPoint],
        baseline: ServiceBaseline,
    ) -> list[AnomalyRecord]:
        """Fit Isolation Forest on time-series feature matrix and flag outliers."""
        if len(data_points) < 5:
            # Not enough samples for meaningful tree isolation
            return []

        # 1. Feature Engineering
        features = []
        prev_val = data_points[0].value

        for pt in data_points:
            delta = pt.value - prev_val
            dev_mean = pt.value - baseline.mean
            features.append([pt.value, delta, dev_mean])
            prev_val = pt.value

        X = np.array(features, dtype=np.float64)

        # 2. Fit and predict with Isolation Forest
        clf = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100,
        )
        clf.fit(X)

        predictions = clf.predict(X)  # -1 for anomaly, 1 for inlier
        raw_scores = clf.score_samples(X)  # Negative anomaly scores

        anomalies: list[AnomalyRecord] = []
        for idx, (pred, raw_score) in enumerate(zip(predictions, raw_scores, strict=False)):
            pt = data_points[idx]
            # Only flag elevated spikes, not abnormal drops in error counts
            if pred == -1 and pt.value > baseline.mean:
                # Raw score is negative; lower means more abnormal
                norm_score = float(min(1.0, max(0.0, -raw_score)))
                severity = (
                    AnomalySeverity.CRITICAL
                    if norm_score >= 0.8
                    else (AnomalySeverity.HIGH if norm_score >= 0.65 else AnomalySeverity.MEDIUM)
                )

                record = AnomalyRecord(
                    service_name=pt.service_name,
                    timestamp=pt.timestamp,
                    metric_name=baseline.metric_name,
                    current_value=pt.value,
                    baseline_mean=baseline.mean,
                    baseline_std=baseline.std_dev,
                    threshold=baseline.mean + (2.0 * max(baseline.std_dev, MIN_STD_DEV_FLOOR)),
                    anomaly_score=norm_score,
                    severity=severity,
                    anomaly_type=AnomalyType.STEP_CHANGE,
                    detection_method=DetectionMethod.ISOLATION_FOREST,
                    confidence=0.88,
                    details={
                        "raw_iforest_score": round(float(raw_score), 4),
                        "feature_vector": [round(float(v), 2) for v in features[idx]],
                    },
                )
                anomalies.append(record)

        return anomalies


class CompositeAnomalyDetector:
    """
    Ensemble anomaly detector combining Z-Score, IQR, and Isolation Forest.
    Fuses multiple independent statistical perspectives to maximize precision
    and eliminate false positives.
    """

    def __init__(
        self,
        z_threshold: float = 3.0,
        iqr_k: float = 1.5,
        iforest_contamination: float = 0.05,
    ) -> None:
        self.z_detector = ZScoreDetector(threshold=z_threshold)
        self.iqr_detector = IQRDetector(k=iqr_k)
        self.iforest_detector = IsolationForestDetector(contamination=iforest_contamination)

    def detect(
        self,
        data_points: list[MetricDataPoint],
        baseline: ServiceBaseline,
    ) -> list[AnomalyRecord]:
        """
        Execute ensemble detection over incoming observations.
        Consensus voting calculates final confidence and assigns morphological type.
        """
        if not data_points:
            return []

        z_anomalies = {a.timestamp: a for a in self.z_detector.detect(data_points, baseline)}
        iqr_anomalies = {a.timestamp: a for a in self.iqr_detector.detect(data_points, baseline)}
        iforest_anomalies = (
            {a.timestamp: a for a in self.iforest_detector.detect(data_points, baseline)}
            if len(data_points) >= 5
            else {}
        )

        all_timestamps = sorted(
            set(z_anomalies.keys()) | set(iqr_anomalies.keys()) | set(iforest_anomalies.keys())
        )
        fused_anomalies: list[AnomalyRecord] = []

        for ts in all_timestamps:
            voters = []
            if ts in z_anomalies:
                voters.append(z_anomalies[ts])
            if ts in iqr_anomalies:
                voters.append(iqr_anomalies[ts])
            if ts in iforest_anomalies:
                voters.append(iforest_anomalies[ts])

            votes_count = len(voters)
            lead_record = voters[0]

            # Highest score among voters
            max_score = max(v.anomaly_score for v in voters)
            avg_score = sum(v.anomaly_score for v in voters) / votes_count

            # Weighted consensus confidence
            if votes_count >= 3:
                confidence = min(0.99, avg_score * 1.1)
                severity = AnomalySeverity.CRITICAL if max_score > 0.7 else AnomalySeverity.HIGH
            elif votes_count == 2:
                confidence = min(0.95, avg_score * 1.05)
                severity = AnomalySeverity.HIGH if max_score > 0.65 else AnomalySeverity.MEDIUM
            else:
                # Single algorithm flag
                confidence = min(0.75, avg_score * 0.9)
                severity = lead_record.severity

            # Determine anomaly morphology
            morphology = self._classify_morphology(ts, data_points, baseline)

            fused_record = AnomalyRecord(
                service_name=lead_record.service_name,
                timestamp=ts,
                metric_name=baseline.metric_name,
                current_value=lead_record.current_value,
                baseline_mean=baseline.mean,
                baseline_std=baseline.std_dev,
                threshold=lead_record.threshold,
                anomaly_score=float(round(max_score, 4)),
                severity=severity,
                anomaly_type=morphology,
                detection_method=DetectionMethod.ENSEMBLE,
                confidence=float(round(confidence, 3)),
                details={
                    "consensus_votes": votes_count,
                    "contributing_algorithms": [v.detection_method.value for v in voters],
                    "mean_voter_score": round(float(avg_score), 3),
                },
            )
            fused_anomalies.append(fused_record)

        return fused_anomalies

    def _classify_morphology(
        self,
        anomaly_ts: datetime,
        data_points: list[MetricDataPoint],
        baseline: ServiceBaseline,
    ) -> AnomalyType:
        """Analyze temporal shape around the anomaly timestamp."""
        timestamps = [pt.timestamp for pt in data_points]
        if anomaly_ts not in timestamps:
            return AnomalyType.SPIKE

        idx = timestamps.index(anomaly_ts)
        current_pt = data_points[idx]

        # Check consecutive elevated points (step change)
        consecutive_elevated = 0
        for i in range(idx, min(len(data_points), idx + 4)):
            if data_points[i].value > (
                baseline.mean + (2.0 * max(baseline.std_dev, MIN_STD_DEV_FLOOR))
            ):
                consecutive_elevated += 1

        if consecutive_elevated >= 3:
            return AnomalyType.STEP_CHANGE

        # Check if rate of change is dramatic (error burst)
        if idx > 0:
            prev_pt = data_points[idx - 1]
            if current_pt.value > (prev_pt.value * 3.0) and current_pt.value >= 10:
                return AnomalyType.ERROR_BURST

        return AnomalyType.SPIKE
