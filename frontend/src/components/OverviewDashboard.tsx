import { FC } from "react";
import {
  AlertTriangle,
  Activity,
  TrendingUp,
  Cpu,
  ArrowRight,
  Clock,
  Layers,
  Flame,
  Zap,
  Database,
  Loader2,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";
import { Incident, AnomalyDataPoint, ChaosScenario } from "../types";

interface OverviewProps {
  incidents: Incident[];
  anomalies: AnomalyDataPoint[];
  onSelectIncident: (id: string) => void;
  onNavigateTab: (tab: string) => void;
  onOpenChaosModal?: () => void;
  onQuickSimulate?: (scenario: ChaosScenario) => Promise<void>;
  isSimulating?: boolean;
}

export const OverviewDashboard: FC<OverviewProps> = ({
  incidents,
  anomalies,
  onSelectIncident,
  onNavigateTab,
  onOpenChaosModal,
  onQuickSimulate,
  isSimulating,
}) => {
  const activeIncidents = incidents.filter(
    (i) => i.status !== "RESOLVED" && i.status !== "CLOSED"
  );
  const criticalCount = incidents.filter((i) => i.severity === "CRITICAL").length;
  const anomalyCount = anomalies.filter((a) => a.is_anomaly).length;

  // Chart data from anomalies telemetry
  const chartData = anomalies.map((a) => ({
    time: a.timestamp,
    errorRate: a.metric_value,
    expected: a.expected_value,
    isAnomaly: a.is_anomaly,
  }));

  // Service error aggregation
  const serviceDistribution = [
    { service: "payment-gateway", errors: 94 },
    { service: "order-api", errors: 48 },
    { service: "auth-service", errors: 22 },
    { service: "notification", errors: 12 },
    { service: "search-api", errors: 6 },
  ];

  return (
    <div className="space-y-6">
      {/* Top Banner Alert if active incidents exist */}
      {activeIncidents.length > 0 && (
        <div className="bg-gradient-to-r from-red-950/40 via-red-900/20 to-gray-900/40 border border-red-500/40 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg shadow-red-950/20">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400">
              <AlertTriangle className="w-5 h-5 animate-bounce" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-red-300">
                {activeIncidents.length} Active Operational Incident(s) Under Investigation
              </h3>
              <p className="text-xs text-gray-400">
                Lead service <span className="font-mono text-white">{activeIncidents[0].lead_service}</span> experiencing elevated error rates and cascading gateway timeouts.
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              onSelectIncident(activeIncidents[0].incident_id);
              onNavigateTab("rca");
            }}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-300 rounded-lg text-xs font-semibold transition"
          >
            <span>Investigate RCA</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Chaos Engineering Simulation Sandbox Banner */}
      <div className="bg-gradient-to-r from-[#1E1B4B]/60 via-[#1E1B4B]/30 to-[#0F172A] border border-indigo-500/30 rounded-xl p-4 sm:p-5 shadow-lg shadow-indigo-950/20">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <div className="p-1.5 rounded-lg bg-orange-500/20 border border-orange-500/30 text-orange-400">
                <Flame className="w-4 h-4 animate-pulse" />
              </div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                Simulate Incident / Chaos Trigger
                <span className="px-2 py-0.5 text-[10px] font-mono font-bold tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 rounded">
                  Interactive Demo
                </span>
              </h3>
            </div>
            <p className="text-xs text-gray-300 max-w-2xl">
              Inject synthetic microservice failure telemetry into TraceMind to see statistical anomaly detection, trace-based event correlation, and AI-grounded root cause analysis in action.
            </p>
          </div>

          {/* Quick Scenario Triggers */}
          <div className="flex flex-wrap items-center gap-2">
            {onQuickSimulate && (
              <>
                <button
                  onClick={() => onQuickSimulate("db_pool_starvation")}
                  disabled={isSimulating}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-gray-900/90 hover:bg-gray-800 border border-amber-500/30 hover:border-amber-500/60 text-amber-300 rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-50"
                  title="Simulate PostgreSQL connection pool exhaustion in payment-gateway"
                >
                  <Database className="w-3.5 h-3.5 text-amber-400" />
                  <span>DB Pool Starvation</span>
                </button>

                <button
                  onClick={() => onQuickSimulate("redis_cache_failover")}
                  disabled={isSimulating}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-gray-900/90 hover:bg-gray-800 border border-cyan-500/30 hover:border-cyan-500/60 text-cyan-300 rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-50"
                  title="Simulate Redis failover and cache stampede in auth-service"
                >
                  <Zap className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Redis Failover</span>
                </button>

                <button
                  onClick={() => onQuickSimulate("kafka_consumer_lag")}
                  disabled={isSimulating}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-gray-900/90 hover:bg-gray-800 border border-indigo-500/30 hover:border-indigo-500/60 text-indigo-300 rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-50"
                  title="Simulate Kafka consumer group rebalance storm and lag spike"
                >
                  <Layers className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Kafka Lag</span>
                </button>

                <button
                  onClick={() => onQuickSimulate("pod_memory_leak")}
                  disabled={isSimulating}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-gray-900/90 hover:bg-gray-800 border border-rose-500/30 hover:border-rose-500/60 text-rose-300 rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-50"
                  title="Simulate JVM memory leak and Pod OOMKilled in search-indexer"
                >
                  <Cpu className="w-3.5 h-3.5 text-rose-400" />
                  <span>Pod OOMKill</span>
                </button>
              </>
            )}

            {onOpenChaosModal && (
              <button
                onClick={onOpenChaosModal}
                disabled={isSimulating}
                className="flex items-center space-x-1 px-3 py-1.5 bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/50 text-indigo-200 rounded-lg text-xs font-semibold transition"
              >
                {isSimulating ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <>
                    <span>All Scenarios</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 4 Metric KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Active Incidents */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition">
          <div className="flex items-center justify-between text-gray-400 text-xs font-medium">
            <span>Active Incidents</span>
            <AlertTriangle className={`w-4 h-4 ${activeIncidents.length > 0 ? "text-red-400" : "text-emerald-400"}`} />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold font-mono text-white">{activeIncidents.length}</span>
            <span className="text-xs text-red-400 font-medium">({criticalCount} Critical)</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-gray-400 pt-2 border-t border-gray-800/80">
            <span>Total Logged: {incidents.length}</span>
            <span className="text-emerald-400">Resolution: 67%</span>
          </div>
        </div>

        {/* Statistical Anomalies */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition">
          <div className="flex items-center justify-between text-gray-400 text-xs font-medium">
            <span>Statistical Anomalies (24h)</span>
            <Activity className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold font-mono text-white">{anomalyCount}</span>
            <span className="text-xs text-amber-400 font-medium">Z-Score / IQR</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-gray-400 pt-2 border-t border-gray-800/80">
            <span>Max Deviation: 4.2σ</span>
            <span className="text-cyan-400">Decoupled from LLM</span>
          </div>
        </div>

        {/* Ingested Log Events */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition">
          <div className="flex items-center justify-between text-gray-400 text-xs font-medium">
            <span>Ingested Events</span>
            <TrendingUp className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold font-mono text-white">128.4k</span>
            <span className="text-xs text-cyan-400 font-medium">Events/day</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-gray-400 pt-2 border-t border-gray-800/80">
            <span>Error Ratio: 2.1%</span>
            <span className="text-gray-400">Micro-batched</span>
          </div>
        </div>

        {/* RAG Knowledge Corpus */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition">
          <div className="flex items-center justify-between text-gray-400 text-xs font-medium">
            <span>RAG Knowledge Vectors</span>
            <Cpu className="w-4 h-4 text-violet-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold font-mono text-white">1,536</span>
            <span className="text-xs text-violet-400 font-medium">Dimensions</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-gray-400 pt-2 border-t border-gray-800/80">
            <span>pgvector HNSW</span>
            <span className="text-emerald-400">&lt;50ms Latency</span>
          </div>
        </div>
      </div>

      {/* Visual Analytics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Real-time Telemetry & Error Burst Detection (2 Columns) */}
        <div className="lg:col-span-2 bg-[#111827] border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                <span>Error Telemetry & Statistical Spike Detection</span>
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Evaluated against dynamically calculated rolling baselines without LLM hallucinations
              </p>
            </div>
            <div className="flex items-center space-x-2 text-xs">
              <span className="flex items-center text-cyan-400 font-mono">
                <span className="w-2 h-2 rounded-full bg-cyan-400 mr-1.5" />
                Observed Error Rate
              </span>
              <span className="flex items-center text-gray-500 font-mono ml-2">
                <span className="w-2 h-2 rounded-full bg-gray-500 mr-1.5" />
                Baseline Expected
              </span>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="errorColor" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06B6D4" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#06B6D4" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                <XAxis dataKey="time" stroke="#6B7280" fontSize={11} tickLine={false} />
                <YAxis stroke="#6B7280" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0F172A",
                    borderColor: "#374151",
                    borderRadius: "0.5rem",
                    fontSize: "12px",
                  }}
                  itemStyle={{ color: "#06B6D4" }}
                />
                <Area
                  type="monotone"
                  dataKey="errorRate"
                  stroke="#06B6D4"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#errorColor)"
                  name="Error Rate (req/s)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Service Error Distribution (1 Column) */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
                <Layers className="w-4 h-4 text-violet-400" />
                <span>Service Error Volume</span>
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">Top failing microservice domains</p>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={serviceDistribution}
                layout="vertical"
                margin={{ top: 5, right: 20, left: 30, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" horizontal={false} />
                <XAxis type="number" stroke="#6B7280" fontSize={11} />
                <YAxis
                  dataKey="service"
                  type="category"
                  stroke="#6B7280"
                  fontSize={10}
                  tickLine={false}
                  width={75}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0F172A",
                    borderColor: "#374151",
                    borderRadius: "0.5rem",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="errors" fill="#8B5CF6" radius={[0, 4, 4, 0]} name="Errors Logged" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Operational Incidents Table Preview */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl overflow-hidden">
        <div className="p-5 border-b border-gray-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Correlated Operational Incidents</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Multi-dimensional log correlation across timestamps, trace IDs, and exception signatures
            </p>
          </div>
          <button
            onClick={() => onNavigateTab("incidents")}
            className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
          >
            <span>View All Incidents</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#161F30] text-gray-400 font-medium border-b border-gray-800">
              <tr>
                <th className="px-5 py-3">Incident ID</th>
                <th className="px-5 py-3">Title & Primary Signature</th>
                <th className="px-5 py-3">Lead Service</th>
                <th className="px-5 py-3">Severity</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Detected</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 font-normal">
              {incidents.map((incident) => {
                const isCritical = incident.severity === "CRITICAL";
                const isResolved = incident.status === "RESOLVED";

                return (
                  <tr key={incident.id} className="hover:bg-[#1E293B]/40 transition group">
                    <td className="px-5 py-3.5 font-mono text-cyan-400 font-medium">
                      {incident.incident_id}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="font-medium text-white max-w-md truncate">{incident.title}</div>
                      <div className="text-[11px] text-gray-400 font-mono mt-0.5">
                        {incident.error_signatures[0] || "signature_pending"}
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="px-2 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-300 font-mono text-[11px]">
                        {incident.lead_service}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${
                          isCritical
                            ? "bg-red-500/10 text-red-400 border border-red-500/20"
                            : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        }`}
                      >
                        {incident.severity}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold ${
                          isResolved
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 animate-pulse"
                        }`}
                      >
                        {incident.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-gray-400 flex items-center space-x-1">
                      <Clock className="w-3.5 h-3.5" />
                      <span>{new Date(incident.detected_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => {
                          onSelectIncident(incident.incident_id);
                          onNavigateTab("rca");
                        }}
                        className="px-2.5 py-1 bg-[#1F2937] hover:bg-cyan-500/20 hover:text-cyan-300 text-gray-300 rounded border border-gray-700 hover:border-cyan-500/40 transition text-[11px] font-medium"
                      >
                        Analyze RCA
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
