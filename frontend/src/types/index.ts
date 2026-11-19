export type IncidentStatus = "DETECTED" | "INVESTIGATING" | "IDENTIFIED" | "MONITORING" | "RESOLVED" | "CLOSED";
export type IncidentSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface Incident {
  id: string;
  incident_id: string;
  title: string;
  status: IncidentStatus;
  severity: IncidentSeverity;
  lead_service: string;
  affected_services: string[];
  error_signatures: string[];
  started_at: string;
  detected_at: string;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimelineMilestone {
  timestamp: string;
  milestone_type: string;
  title: string;
  description: string;
  service_name?: string | null;
  severity?: string | null;
  metadata?: Record<string, unknown>;
}

export interface IncidentTimeline {
  incident_id: string;
  started_at: string;
  detected_at: string;
  resolved_at?: string | null;
  total_events: number;
  milestones: TimelineMilestone[];
}

export interface IncidentDetail extends Incident {
  timeline?: IncidentTimeline;
}

export interface LogEvent {
  event_id: string;
  timestamp: string;
  severity: "DEBUG" | "INFO" | "WARN" | "WARNING" | "ERROR" | "CRITICAL";
  service_name: string;
  environment: string;
  message: string;
  exception_type?: string | null;
  stack_trace?: string | null;
  error_signature?: string | null;
  request_id?: string | null;
  trace_id?: string | null;
  span_id?: string | null;
  correlation_id?: string | null;
  source_file?: string | null;
  line_number?: number | null;
  metadata?: Record<string, unknown>;
}

export interface LogSearchResponse {
  total: number;
  limit: number;
  offset: number;
  events: LogEvent[];
}

export interface AnomalyDataPoint {
  id: string;
  timestamp: string;
  service_name: string;
  metric_name: string;
  metric_value: number;
  expected_value: number;
  score: number;
  method: string;
  is_anomaly: boolean;
  severity: IncidentSeverity;
}

export interface RootCauseHypothesis {
  hypothesis_id: string;
  title: string;
  description: string;
  likelihood: "CONFIRMED" | "HIGH" | "MEDIUM" | "LOW" | "UNLIKELY";
  confidence_score: number;
  supporting_evidence?: (string | { reference?: string; excerpt?: string })[];
  contradicting_evidence?: string[];
  falsification_checks?: string[];
  recommended_actions?: string[];
}

export interface RCAResponse {
  incident_id: string;
  executive_summary: string;
  hypotheses: RootCauseHypothesis[];
  primary_root_cause?: string | RootCauseHypothesis | null;
  affected_components: string[];
  cascading_propagation: string[];
  immediate_mitigation_steps: string[];
  preventive_actions: string[];
  recommended_runbooks: string[];
  diagnostic_commands: string[];
  uncertainty_disclaimer: string;
  generated_at: string;
  model_used: string;
}

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  content: string;
  timestamp: string;
  citations?: (string | { citation_type?: string; source_id?: string; service_name?: string; excerpt?: string; reference?: string })[];
  suggested_commands?: (string | { command?: string })[];
}

export interface KnowledgeDocument {
  id: string;
  title: string;
  document_type: string;
  source: string;
  created_at: string;
  chunk_count: number;
}

export interface SemanticSearchResult {
  chunk_id: string;
  document_id: string;
  title: string;
  content: string;
  similarity_score: number;
}

export type ChaosScenario =
  | "db_pool_starvation"
  | "redis_cache_failover"
  | "kafka_consumer_lag"
  | "pod_memory_leak";

export interface ScenarioMetadata {
  scenario: ChaosScenario;
  name: string;
  description: string;
  lead_service: string;
  affected_services: string[];
  severity: string;
  symptoms: string[];
  icon: string;
}

export interface ChaosSimulateResponse {
  incident: Incident;
  scenario: ChaosScenario;
  injected_logs_count: number;
  injected_anomalies_count: number;
  runbook_title: string;
  message: string;
  extra_details?: Record<string, unknown>;
}
