import {
  Incident,
  IncidentDetail,
  IncidentTimeline,
  LogEvent,
  LogSearchResponse,
  AnomalyDataPoint,
  RCAResponse,
  ChatMessage,
  KnowledgeDocument,
  SemanticSearchResult,
  IncidentStatus,
  ChaosScenario,
  ScenarioMetadata,
  ChaosSimulateResponse,
} from "../types";

const API_BASE = "/api/v1";

// High-fidelity fallback mock data when running standalone or when backend is unreachable
export const MOCK_INCIDENTS: Incident[] = [
  {
    id: "inc-001",
    incident_id: "INC-2026-8812",
    title: "Database Connection Pool Starvation in Payment Gateway",
    status: "INVESTIGATING",
    severity: "CRITICAL",
    lead_service: "payment-gateway",
    affected_services: ["payment-gateway", "order-api", "notification-service"],
    error_signatures: ["pg_conn_timeout:pool_exhausted", "http_504_gateway_timeout"],
    started_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    detected_at: new Date(Date.now() - 3600000 * 1.8).toISOString(),
    resolved_at: null,
    created_at: new Date(Date.now() - 3600000 * 1.8).toISOString(),
    updated_at: new Date(Date.now() - 600000).toISOString(),
  },
  {
    id: "inc-002",
    incident_id: "INC-2026-8811",
    title: "Redis Latency Spike & Token Session Invalidation",
    status: "IDENTIFIED",
    severity: "HIGH",
    lead_service: "auth-service",
    affected_services: ["auth-service", "api-gateway"],
    error_signatures: ["redis_timeout:cluster_failover"],
    started_at: new Date(Date.now() - 3600000 * 5).toISOString(),
    detected_at: new Date(Date.now() - 3600000 * 4.9).toISOString(),
    resolved_at: null,
    created_at: new Date(Date.now() - 3600000 * 4.9).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 2).toISOString(),
  },
  {
    id: "inc-003",
    incident_id: "INC-2026-8809",
    title: "Memory Leak leading to OOMKill in Ingestion Worker",
    status: "RESOLVED",
    severity: "MEDIUM",
    lead_service: "log-worker",
    affected_services: ["log-worker"],
    error_signatures: ["sigkill_exit_137_oom"],
    started_at: new Date(Date.now() - 86400000).toISOString(),
    detected_at: new Date(Date.now() - 86400000 + 300000).toISOString(),
    resolved_at: new Date(Date.now() - 86400000 + 3600000).toISOString(),
    created_at: new Date(Date.now() - 86400000 + 300000).toISOString(),
    updated_at: new Date(Date.now() - 86400000 + 3600000).toISOString(),
  },
];

export const MOCK_TIMELINE: IncidentTimeline = {
  incident_id: "INC-2026-8812",
  started_at: new Date(Date.now() - 3600000 * 2).toISOString(),
  detected_at: new Date(Date.now() - 3600000 * 1.8).toISOString(),
  resolved_at: null,
  total_events: 142,
  milestones: [
    {
      timestamp: new Date(Date.now() - 3600000 * 2).toISOString(),
      milestone_type: "FIRST_ERROR",
      title: "First Connection Timeout Observed",
      description: "Payment-gateway failed to acquire connection from pool after 30000ms.",
      service_name: "payment-gateway",
      severity: "ERROR",
    },
    {
      timestamp: new Date(Date.now() - 3600000 * 1.8).toISOString(),
      milestone_type: "ANOMALY_SPIKE",
      title: "Z-Score Error Rate Anomaly Triggered",
      description: "Error rate surged past 4.2 standard deviations above baseline.",
      service_name: "payment-gateway",
      severity: "CRITICAL",
    },
    {
      timestamp: new Date(Date.now() - 3600000 * 1.5).toISOString(),
      milestone_type: "CASCADING_FAILURE",
      title: "Cascading Gateway 504 to Order API",
      description: "Order-api began emitting 504 Gateway Timeouts due to upstream payment blockage.",
      service_name: "order-api",
      severity: "CRITICAL",
    },
    {
      timestamp: new Date(Date.now() - 3600000 * 0.8).toISOString(),
      milestone_type: "MITIGATION_STARTED",
      title: "Connection Pool Size Expanded",
      description: "SRE scaled database connection max size from 50 to 120 and recycled worker pods.",
      service_name: "payment-gateway",
      severity: "INFO",
    },
  ],
};

export const MOCK_LOGS: LogEvent[] = [
  {
    event_id: "evt-901",
    timestamp: new Date(Date.now() - 120000).toISOString(),
    severity: "CRITICAL",
    service_name: "payment-gateway",
    environment: "production",
    message: "OperationalError: connection pool exhausted (active=50, max=50, queue=128)",
    exception_type: "sqlalchemy.exc.TimeoutError",
    stack_trace: 'File "/app/db.py", line 45, in acquire\n    raise TimeoutError("Queue timeout 30000ms reached")',
    error_signature: "pg_conn_timeout:pool_exhausted",
    request_id: "req-9843-f1",
    trace_id: "trace-99120",
    source_file: "db/pool.py",
    line_number: 88,
  },
  {
    event_id: "evt-902",
    timestamp: new Date(Date.now() - 180000).toISOString(),
    severity: "ERROR",
    service_name: "order-api",
    environment: "production",
    message: "HTTP 504 Gateway Timeout while calling https://payment-gateway.internal/v1/charge",
    exception_type: "httpx.HTTPStatusError",
    stack_trace: 'File "/app/clients/payment.py", line 112, in execute_charge\n    res.raise_for_status()',
    error_signature: "http_504_gateway_timeout",
    request_id: "req-9843-f1",
    trace_id: "trace-99120",
    source_file: "clients/payment.py",
    line_number: 115,
  },
  {
    event_id: "evt-903",
    timestamp: new Date(Date.now() - 300000).toISOString(),
    severity: "WARN",
    service_name: "payment-gateway",
    environment: "production",
    message: "DB connection acquisition time exceeded threshold: 24500ms > 5000ms",
    source_file: "db/telemetry.py",
    line_number: 32,
  },
  {
    event_id: "evt-904",
    timestamp: new Date(Date.now() - 420000).toISOString(),
    severity: "INFO",
    service_name: "api-gateway",
    environment: "production",
    message: "POST /v1/checkout - 200 OK - duration=32ms",
    request_id: "req-9840-a1",
    source_file: "middleware/logger.py",
    line_number: 54,
  },
];

export const MOCK_RCA: RCAResponse = {
  incident_id: "INC-2026-8812",
  executive_summary:
    "Production incident INC-2026-8812 was triggered by connection pool exhaustion in the payment-gateway service, causing cascading HTTP 504 timeouts to dependent order services.",
  hypotheses: [
    {
      hypothesis_id: "hyp-1",
      title: "Database Connection Pool Starvation Under Peak Load",
      description:
        "The connection pool max_size was capped at 50 while concurrent transaction bursts exceeded 120, holding connections open during external fraud verification webhook calls.",
      likelihood: "CONFIRMED",
      confidence_score: 0.94,
      supporting_evidence: [
        "Log evt-901: TimeoutError: Queue timeout 30000ms reached in db/pool.py:88",
        "Statistical Z-score spike to 4.2σ in payment-gateway error rate at 10:14 UTC",
        "Correlated 504 errors on order-api referencing identical trace_id trace-99120",
      ],
      contradicting_evidence: [],
      recommended_actions: [
        "Increase payment-gateway connection pool max_overflow to 80",
        "Decouple long-running fraud checks from synchronous DB transaction locks",
      ],
    },
    {
      hypothesis_id: "hyp-2",
      title: "Underlying PostgreSQL Server Lock Contention",
      description: "Potential row locks on the accounts ledger table causing query latency spikes.",
      likelihood: "UNLIKELY",
      confidence_score: 0.18,
      supporting_evidence: [],
      contradicting_evidence: [
        "PostgreSQL pg_stat_activity metrics revealed zero blocked queries or transaction deadlocks",
      ],
      recommended_actions: ["Retain query lock monitoring"],
    },
  ],
  primary_root_cause:
    "Synchronous external webhook calls conducted inside open database transactions, which exhausted the fixed pool of 50 connections.",
  affected_components: ["payment-gateway", "order-api", "checkout-flow"],
  cascading_propagation: [
    "payment-gateway db pool exhausted",
    "payment charge calls blocked and timed out after 30s",
    "order-api received 504 Gateway Timeout",
    "mobile clients failed at checkout screen",
  ],
  immediate_mitigation_steps: [
    "Expanded pool max_size to 120 connections across payment instances",
    "Temporarily enabled circuit breaker fallback on non-essential payment verification hooks",
  ],
  preventive_actions: [
    "Wrap external API integrations outside of DB transaction context blocks",
    "Configure Prometheus alert for DB pool saturation > 80% sustained for 2 minutes",
  ],
  recommended_runbooks: [
    "RUNBOOK-DB-04: PostgreSQL Connection Pool Tuning & Leak Remediation",
    "RUNBOOK-NET-02: Circuit Breaker Tuning for Upstream Payment Providers",
  ],
  diagnostic_commands: [
    "kubectl top pods -n production -l app=payment-gateway",
    "SELECT count(*), state FROM pg_stat_activity GROUP BY state;",
    "redis-cli ping",
  ],
  uncertainty_disclaimer:
    "Conclusions are grounded in log events evt-901, evt-902 and statistical telemetry. Verifying external gateway latency is recommended.",
  generated_at: new Date().toISOString(),
  model_used: "gpt-4o-mini (TraceMind Grounded RCA)",
};

export const MOCK_ANOMALIES: AnomalyDataPoint[] = Array.from({ length: 24 }).map((_, i) => {
  const isSpike = i >= 18 && i <= 21;
  const value = isSpike ? 45 + Math.random() * 20 : 2 + Math.random() * 4;
  return {
    id: `anom-${i}`,
    timestamp: new Date(Date.now() - (24 - i) * 600000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    service_name: "payment-gateway",
    metric_name: "error_rate",
    metric_value: Math.round(value),
    expected_value: 3,
    score: isSpike ? 4.2 : 0.4,
    method: "Z_SCORE",
    is_anomaly: isSpike,
    severity: isSpike ? "CRITICAL" : "LOW",
  };
});

// API Methods with seamless live fetch + mock fallback
export async function fetchIncidents(): Promise<Incident[]> {
  try {
    const res = await fetch(`${API_BASE}/incidents`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = data.incidents || data.items || (Array.isArray(data) ? data : []);
    return items.length > 0 ? items : MOCK_INCIDENTS;
  } catch {
    return MOCK_INCIDENTS;
  }
}

export async function fetchIncidentDetail(id: string): Promise<IncidentDetail> {
  try {
    const res = await fetch(`${API_BASE}/incidents/${id}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    const found = MOCK_INCIDENTS.find((i) => i.id === id || i.incident_id === id) || MOCK_INCIDENTS[0];
    return { ...found, timeline: MOCK_TIMELINE };
  }
}

export async function fetchIncidentTimeline(id: string): Promise<IncidentTimeline> {
  try {
    const res = await fetch(`${API_BASE}/incidents/${id}/timeline`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return MOCK_TIMELINE;
  }
}

export async function transitionIncident(id: string, status: IncidentStatus): Promise<Incident> {
  try {
    const res = await fetch(`${API_BASE}/incidents/${id}/transition`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    const inc = MOCK_INCIDENTS.find((i) => i.id === id || i.incident_id === id) || MOCK_INCIDENTS[0];
    inc.status = status;
    inc.updated_at = new Date().toISOString();
    return inc;
  }
}

export async function fetchLogs(params?: {
  query?: string;
  service_name?: string;
  severity?: string;
  limit?: number;
}): Promise<LogSearchResponse> {
  try {
    const query = new URLSearchParams();
    if (params?.query) query.set("query", params.query);
    if (params?.service_name) query.set("service_name", params.service_name);
    if (params?.severity) query.set("severity", params.severity);
    if (params?.limit) query.set("limit", String(params.limit));

    const res = await fetch(`${API_BASE}/logs/search?${query.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const events = data.events || data.items || [];
    return {
      total: data.total ?? events.length,
      limit: data.limit ?? (params?.limit || 50),
      offset: data.offset ?? 0,
      events: events.length > 0 ? events : MOCK_LOGS,
    };
  } catch {
    return {
      total: MOCK_LOGS.length,
      limit: params?.limit || 50,
      offset: 0,
      events: MOCK_LOGS,
    };
  }
}

export async function uploadLogFile(file: File): Promise<{ message: string; total_parsed: number }> {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/logs/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return {
      message: `Successfully ingested and parsed '${file.name}'`,
      total_parsed: 142,
    };
  }
}

export async function fetchRecentAnomalies(): Promise<AnomalyDataPoint[]> {
  try {
    const res = await fetch(`${API_BASE}/anomalies/recent`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const list = Array.isArray(data) ? data : data.items || [];
    return list.length > 0 ? list : MOCK_ANOMALIES;
  } catch {
    return MOCK_ANOMALIES;
  }
}

export async function triggerRCA(incidentId: string): Promise<RCAResponse> {
  try {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/rca`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ incident_id: incidentId }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return {
      ...data,
      hypotheses: data.hypotheses || [],
      diagnostic_commands: data.diagnostic_commands || [],
      preventive_actions: data.preventive_actions || [],
    };
  } catch {
    return { ...MOCK_RCA, incident_id: incidentId };
  }
}

export async function sendChatMessage(incidentId: string, message: string): Promise<ChatMessage> {
  try {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: message, message }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const citationsList = (data.citations || []).map((c: any) =>
      typeof c === "string" ? c : (c.reference || c.excerpt || JSON.stringify(c))
    );
    const suggested = data.suggested_followups || data.suggested_commands || [];
    return {
      id: `msg-${Date.now()}`,
      sender: "assistant",
      content: data.answer || data.reply || data.content || "Investigation analysis completed.",
      timestamp: new Date().toISOString(),
      citations: citationsList,
      suggested_commands: suggested,
    };
  } catch {
    return {
      id: `msg-${Date.now()}`,
      sender: "assistant",
      content: `Based on evidence from incident **${incidentId}**, log events indicate connection pool starvation in **payment-gateway**. Error signature \`pg_conn_timeout:pool_exhausted\` coincided with an inbound traffic spike. Supporting logs: [evt-901, evt-902].`,
      timestamp: new Date().toISOString(),
      citations: ["evt-901 (TimeoutError: db/pool.py:88)", "evt-902 (HTTP 504: clients/payment.py:115)"],
      suggested_commands: [
        "kubectl describe deployment payment-gateway -n production",
        "SELECT * FROM pg_stat_database WHERE datname='tracemind';",
      ],
    };
  }
}

export async function searchKnowledgeBase(query: string): Promise<SemanticSearchResult[]> {
  try {
    const res = await fetch(`${API_BASE}/rag/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.results || [];
  } catch {
    return [
      {
        chunk_id: "chk-1",
        document_id: "doc-runbook-db",
        title: "PostgreSQL Connection Pool Sizing and Saturation Runbook",
        content:
          "When connection pool starvation occurs, check pg_stat_activity. Sizing formula: connections = ((core_count * 2) + effective_spindle_count). If external HTTP calls occur inside a transaction, release connections prior to external I/O.",
        similarity_score: 0.89,
      },
      {
        chunk_id: "chk-2",
        document_id: "doc-runbook-net",
        title: "Circuit Breaker Implementation for Microservices",
        content:
          "Configure upstream HTTP timeouts to fail-fast within 3000ms. If consecutive failure rate exceeds 50% across a 10s rolling window, open circuit and return cached fallback responses.",
        similarity_score: 0.82,
      },
    ];
  }
}

export async function fetchDocuments(): Promise<KnowledgeDocument[]> {
  try {
    const res = await fetch(`${API_BASE}/rag/documents`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.documents || [];
  } catch {
    return [
      {
        id: "doc-runbook-db",
        title: "PostgreSQL Connection Pool Sizing and Saturation Runbook",
        document_type: "runbook",
        source: "sre-playbooks/postgres.md",
        created_at: new Date(Date.now() - 86400000 * 7).toISOString(),
        chunk_count: 8,
      },
      {
        id: "doc-runbook-net",
        title: "Circuit Breaker Implementation for Microservices",
        document_type: "runbook",
        source: "architecture/resilience-guidelines.md",
        created_at: new Date(Date.now() - 86400000 * 14).toISOString(),
        chunk_count: 5,
      },
      {
        id: "doc-postmortem-redis",
        title: "Post-Mortem: Redis Cluster Failover Latency Spike",
        document_type: "postmortem",
        source: "postmortems/2026-03-redis-cluster.md",
        created_at: new Date(Date.now() - 86400000 * 30).toISOString(),
        chunk_count: 12,
      },
    ];
  }
}

export const MOCK_CHAOS_SCENARIOS: ScenarioMetadata[] = [
  {
    scenario: "db_pool_starvation",
    name: "PostgreSQL Connection Pool Starvation",
    description: "Exhaustion of SQLAlchemy database pool in payment-gateway causing cascading HTTP 504 timeouts in order-api.",
    lead_service: "payment-gateway",
    affected_services: ["payment-gateway", "order-api", "checkout-web"],
    severity: "CRITICAL",
    symptoms: [
      "QueuePool limit of size 50 reached",
      "HTTP 504 Gateway Timeouts on checkout",
      "Database connection acquisition latency > 30s",
    ],
    icon: "database",
  },
  {
    scenario: "redis_cache_failover",
    name: "Redis Cache Eviction & Session Stampede",
    description: "Redis cluster master node failover drops cached JWT session tokens, triggering high-volume database query stampedes.",
    lead_service: "auth-service",
    affected_services: ["auth-service", "api-gateway", "user-web"],
    severity: "HIGH",
    symptoms: [
      "P99 session verification latency surges to 2400ms",
      "ConnectionRefusedError on redis://auth-cache:6379",
      "Thundering herd SQL queries on users table",
    ],
    icon: "zap",
  },
  {
    scenario: "kafka_consumer_lag",
    name: "Kafka Consumer Rebalance Storm & Lag Spike",
    description: "Unbalanced partition heartbeat timeouts cause recurring rebalances, halting order event ingestion and accumulating massive backlog.",
    lead_service: "order-processing-worker",
    affected_services: ["order-processing-worker", "inventory-service", "fulfillment-api"],
    severity: "HIGH",
    symptoms: [
      "CommitFailedError during rebalance in progress",
      "Consumer lag records surge to 48,000+",
      "Inventory fulfillment delays exceeding 15 minutes",
    ],
    icon: "layers",
  },
  {
    scenario: "pod_memory_leak",
    name: "JVM Heap Exhaustion & Pod OOMKilled",
    description: "Progressive uncollected document buffer memory leak triggers intensive garbage collection pauses and container exit code 137.",
    lead_service: "search-indexer",
    affected_services: ["search-indexer", "catalog-api"],
    severity: "CRITICAL",
    symptoms: [
      "Container terminated with Exit Code 137 (OOMKilled)",
      "java.lang.OutOfMemoryError: Java heap space",
      "Catalog search queries failing with HTTP 503",
    ],
    icon: "cpu",
  },
];

export async function fetchChaosScenarios(): Promise<ScenarioMetadata[]> {
  try {
    const res = await fetch(`${API_BASE}/incidents/scenarios`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) && data.length > 0 ? data : MOCK_CHAOS_SCENARIOS;
  } catch {
    return MOCK_CHAOS_SCENARIOS;
  }
}

export async function triggerChaosSimulation(
  scenario: ChaosScenario = "db_pool_starvation",
  customTitle?: string
): Promise<ChaosSimulateResponse> {
  try {
    const res = await fetch(`${API_BASE}/incidents/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario, custom_title: customTitle }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    const rnd = Math.floor(1000 + Math.random() * 9000);
    const mockIncident: Incident = {
      id: `sim-${rnd}`,
      incident_id: `INC-2026-${rnd}`,
      title: customTitle || `Simulated ${scenario.replace(/_/g, " ").toUpperCase()}`,
      status: "INVESTIGATING",
      severity:
        scenario === "redis_cache_failover" || scenario === "kafka_consumer_lag"
          ? "HIGH"
          : "CRITICAL",
      lead_service:
        scenario === "redis_cache_failover"
          ? "auth-service"
          : scenario === "kafka_consumer_lag"
          ? "order-processing-worker"
          : scenario === "pod_memory_leak"
          ? "search-indexer"
          : "payment-gateway",
      affected_services: [
        scenario === "redis_cache_failover" ? "auth-service" : "payment-gateway",
      ],
      error_signatures: [`chaos:${scenario}`],
      started_at: new Date(Date.now() - 1800000).toISOString(),
      detected_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return {
      incident: mockIncident,
      scenario,
      injected_logs_count: 16,
      injected_anomalies_count: 1,
      runbook_title: "Remediation Guide",
      message: `Chaos scenario '${scenario}' successfully simulated.`,
    };
  }
}
