import { describe, it, expect } from "vitest";
import {
  fetchIncidents,
  fetchIncidentDetail,
  fetchIncidentTimeline,
  fetchLogs,
  fetchRecentAnomalies,
  triggerRCA,
  sendChatMessage,
  searchKnowledgeBase,
  fetchDocuments,
  transitionIncident,
  fetchChaosScenarios,
  triggerChaosSimulation,
  MOCK_INCIDENTS,
  MOCK_LOGS,
  MOCK_RCA,
  MOCK_ANOMALIES,
} from "./api/client";

describe("TraceMind Frontend Architecture & API Client Tests", () => {
  it("validates mock incident dataset integrity", () => {
    expect(MOCK_INCIDENTS.length).toBeGreaterThanOrEqual(3);
    const primary = MOCK_INCIDENTS[0];
    expect(primary.incident_id).toBe("INC-2026-8812");
    expect(primary.severity).toBe("CRITICAL");
    expect(primary.affected_services).toContain("payment-gateway");
  });

  it("validates mock log telemetry and error signatures", () => {
    expect(MOCK_LOGS.length).toBeGreaterThanOrEqual(4);
    const errorEvent = MOCK_LOGS.find((l) => l.severity === "CRITICAL");
    expect(errorEvent).toBeDefined();
    expect(errorEvent?.error_signature).toBe("pg_conn_timeout:pool_exhausted");
    expect(errorEvent?.service_name).toBe("payment-gateway");
  });

  it("validates RCA structure with mandatory citations and hypotheses", () => {
    expect(MOCK_RCA.incident_id).toBe("INC-2026-8812");
    expect(MOCK_RCA.hypotheses.length).toBeGreaterThanOrEqual(2);
    const confirmedHypothesis = MOCK_RCA.hypotheses.find((h) => h.likelihood === "CONFIRMED");
    expect(confirmedHypothesis).toBeDefined();
    expect(confirmedHypothesis?.supporting_evidence?.length).toBeGreaterThan(0);
    expect(confirmedHypothesis?.confidence_score).toBeGreaterThan(0.9);
  });

  it("validates statistical anomaly points", () => {
    expect(MOCK_ANOMALIES.length).toBe(24);
    const anomalies = MOCK_ANOMALIES.filter((a) => a.is_anomaly);
    expect(anomalies.length).toBeGreaterThan(0);
    expect(anomalies[0].method).toBe("Z_SCORE");
  });

  it("fetches incidents via fallback or API client", async () => {
    const incidents = await fetchIncidents();
    expect(incidents.length).toBeGreaterThan(0);
    expect(incidents[0].incident_id).toBeDefined();
  });

  it("fetches incident detail and timeline", async () => {
    const detail = await fetchIncidentDetail("INC-2026-8812");
    expect(detail.incident_id).toBe("INC-2026-8812");
    expect(detail.timeline).toBeDefined();
    expect(detail.timeline?.milestones.length).toBeGreaterThan(0);

    const timeline = await fetchIncidentTimeline("INC-2026-8812");
    expect(timeline.incident_id).toBe("INC-2026-8812");
    expect(timeline.total_events).toBeGreaterThan(0);
  });

  it("transitions incident operational state", async () => {
    const updated = await transitionIncident("INC-2026-8812", "RESOLVED");
    expect(updated.status).toBe("RESOLVED");
  });

  it("fetches log events with multi-criteria filters", async () => {
    const logsRes = await fetchLogs({ severity: "CRITICAL", service_name: "payment-gateway" });
    expect(logsRes.events).toBeDefined();
    expect(logsRes.events.length).toBeGreaterThan(0);
  });

  it("fetches recent statistical anomaly series", async () => {
    const anoms = await fetchRecentAnomalies();
    expect(anoms.length).toBeGreaterThan(0);
  });

  it("generates evidence-grounded RCA report", async () => {
    const rca = await triggerRCA("INC-2026-8812");
    expect(rca.incident_id).toBe("INC-2026-8812");
    expect(rca.hypotheses.length).toBeGreaterThan(0);
    expect(rca.uncertainty_disclaimer).toBeDefined();
  });

  it("sends investigation query to AI Assistant Copilot", async () => {
    const chat = await sendChatMessage("INC-2026-8812", "Why did errors spike?");
    expect(chat.sender).toBe("assistant");
    expect(chat.content).toContain("INC-2026-8812");
    expect(chat.citations).toBeDefined();
  });

  it("performs semantic search on operational runbooks", async () => {
    const results = await searchKnowledgeBase("PostgreSQL connection starvation");
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].title).toContain("PostgreSQL");
    expect(results[0].similarity_score).toBeGreaterThan(0.5);
  });

  it("lists indexed knowledge documents", async () => {
    const docs = await fetchDocuments();
    expect(docs.length).toBeGreaterThan(0);
    expect(docs[0].document_type).toBeDefined();
  });

  it("fetches chaos failure scenarios catalog", async () => {
    const scenarios = await fetchChaosScenarios();
    expect(scenarios.length).toBe(4);
    const ids = scenarios.map((s) => s.scenario);
    expect(ids).toContain("db_pool_starvation");
    expect(ids).toContain("redis_cache_failover");
    expect(ids).toContain("kafka_consumer_lag");
    expect(ids).toContain("pod_memory_leak");
  });

  it("triggers chaos outage simulation successfully", async () => {
    const res = await triggerChaosSimulation("redis_cache_failover", "Test Redis Chaos");
    expect(res.scenario).toBe("redis_cache_failover");
    expect(res.incident).toBeDefined();
    expect(res.incident.lead_service).toBe("auth-service");
    expect(res.injected_logs_count).toBeGreaterThan(0);
    expect(res.message).toBeDefined();
  });
});
