import { FC, useState } from "react";
import {
  ArrowRight,
  Filter,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { Incident, IncidentDetail, IncidentStatus } from "../types";
import { fetchIncidentDetail, transitionIncident } from "../api/client";

interface IncidentExplorerProps {
  incidents: Incident[];
  onSelectIncident: (id: string) => void;
  onNavigateTab: (tab: string) => void;
  onRefreshIncidents: () => void;
}

export const IncidentExplorer: FC<IncidentExplorerProps> = ({
  incidents,
  onSelectIncident,
  onNavigateTab,
  onRefreshIncidents,
}) => {
  const [selectedIncident, setSelectedIncident] = useState<IncidentDetail | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isTransitioning, setIsTransitioning] = useState<boolean>(false);

  const filteredIncidents = incidents.filter((inc) => {
    const matchesStatus =
      statusFilter === "ALL" ||
      (statusFilter === "ACTIVE" && inc.status !== "RESOLVED" && inc.status !== "CLOSED") ||
      inc.status === statusFilter;
    const matchesQuery =
      searchQuery === "" ||
      inc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      inc.incident_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      inc.lead_service.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesQuery;
  });

  const handleOpenDetail = async (incident: Incident) => {
    const detail = await fetchIncidentDetail(incident.incident_id);
    setSelectedIncident(detail);
  };

  const handleStatusTransition = async (newStatus: IncidentStatus) => {
    if (!selectedIncident) return;
    setIsTransitioning(true);
    try {
      const updated = await transitionIncident(selectedIncident.incident_id, newStatus);
      setSelectedIncident((prev) => (prev ? { ...prev, status: updated.status } : null));
      onRefreshIncidents();
    } finally {
      setIsTransitioning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Controls Bar */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-3 w-full md:w-auto">
          <div className="relative flex-1 md:w-72">
            <input
              type="text"
              placeholder="Search by ID, title, or service..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#1A2333] border border-gray-700 rounded-lg px-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            />
          </div>
          <div className="flex items-center space-x-1.5 text-xs text-gray-400">
            <Filter className="w-4 h-4" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-[#1A2333] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-2 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">Active (Unresolved)</option>
              <option value="INVESTIGATING">Investigating</option>
              <option value="IDENTIFIED">Identified</option>
              <option value="RESOLVED">Resolved</option>
            </select>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs text-gray-400 self-end md:self-auto">
          <span>Showing {filteredIncidents.length} incidents</span>
          <button
            onClick={onRefreshIncidents}
            className="p-1.5 hover:bg-gray-800 rounded-md transition text-gray-400 hover:text-white"
            title="Refresh Incidents"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Layout: List on Left, Timeline Drawer on Right when opened */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Incident Table */}
        <div className={selectedIncident ? "lg:col-span-7" : "lg:col-span-12"}>
          <div className="bg-[#111827] border border-gray-800 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#161F30] text-gray-400 font-medium border-b border-gray-800">
                  <tr>
                    <th className="px-4 py-3">Incident</th>
                    <th className="px-4 py-3">Lead Service</th>
                    <th className="px-4 py-3">Severity</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Started</th>
                    <th className="px-4 py-3 text-right">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60 font-normal">
                  {filteredIncidents.map((incident) => {
                    const isSelected = selectedIncident?.incident_id === incident.incident_id;
                    return (
                      <tr
                        key={incident.id}
                        onClick={() => handleOpenDetail(incident)}
                        className={`cursor-pointer transition ${
                          isSelected ? "bg-cyan-950/20 border-l-2 border-cyan-400" : "hover:bg-[#1E293B]/40"
                        }`}
                      >
                        <td className="px-4 py-3.5">
                          <div className="font-mono text-cyan-400 font-semibold">{incident.incident_id}</div>
                          <div className="font-medium text-white truncate max-w-xs mt-0.5">{incident.title}</div>
                        </td>
                        <td className="px-4 py-3.5">
                          <span className="px-2 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-300 font-mono text-[11px]">
                            {incident.lead_service}
                          </span>
                        </td>
                        <td className="px-4 py-3.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              incident.severity === "CRITICAL"
                                ? "bg-red-500/10 text-red-400 border border-red-500/20"
                                : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            }`}
                          >
                            {incident.severity}
                          </span>
                        </td>
                        <td className="px-4 py-3.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              incident.status === "RESOLVED"
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 animate-pulse"
                            }`}
                          >
                            {incident.status}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-gray-400">
                          {new Date(incident.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenDetail(incident);
                            }}
                            className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
                          >
                            <ArrowRight className="w-4 h-4" />
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

        {/* Selected Incident Timeline Drawer */}
        {selectedIncident && (
          <div className="lg:col-span-5 bg-[#111827] border border-gray-800 rounded-xl p-5 space-y-5">
            {/* Header */}
            <div className="flex items-start justify-between pb-3 border-b border-gray-800">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs text-cyan-400 font-bold">
                    {selectedIncident.incident_id}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      selectedIncident.severity === "CRITICAL"
                        ? "bg-red-500/10 text-red-400 border border-red-500/20"
                        : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                    }`}
                  >
                    {selectedIncident.severity}
                  </span>
                </div>
                <h3 className="text-sm font-bold text-white mt-1 leading-snug">
                  {selectedIncident.title}
                </h3>
              </div>
              <button
                onClick={() => setSelectedIncident(null)}
                className="text-gray-400 hover:text-white text-xs px-2 py-1 bg-gray-800 rounded"
              >
                ✕
              </button>
            </div>

            {/* RCA Callout Action */}
            <div className="p-3 bg-gradient-to-r from-cyan-950/40 to-blue-950/30 border border-cyan-500/30 rounded-lg flex items-center justify-between">
              <div className="text-xs">
                <span className="font-semibold text-cyan-300 flex items-center space-x-1">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400 mr-1" />
                  Evidence-Grounded RCA Ready
                </span>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  Analyze supporting logs and generate verified hypotheses
                </p>
              </div>
              <button
                onClick={() => {
                  onSelectIncident(selectedIncident.incident_id);
                  onNavigateTab("rca");
                }}
                className="px-3 py-1.5 bg-cyan-500 hover:bg-cyan-400 text-[#090D16] font-bold text-xs rounded-md shadow transition"
              >
                Open RCA
              </button>
            </div>

            {/* Affected Services & Blast Radius */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                Affected Services (Blast Radius)
              </span>
              <div className="flex flex-wrap gap-1.5">
                {selectedIncident.affected_services.map((svc) => (
                  <span
                    key={svc}
                    className="px-2 py-0.5 bg-gray-800 border border-gray-700 text-gray-300 text-[11px] font-mono rounded"
                  >
                    {svc}
                  </span>
                ))}
              </div>
            </div>

            {/* State Transition Actions */}
            <div className="space-y-1.5 pt-2 border-t border-gray-800">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                Transition Operational State
              </span>
              <div className="grid grid-cols-3 gap-2">
                {(["INVESTIGATING", "IDENTIFIED", "RESOLVED"] as IncidentStatus[]).map((status) => (
                  <button
                    key={status}
                    disabled={selectedIncident.status === status || isTransitioning}
                    onClick={() => handleStatusTransition(status)}
                    className={`py-1.5 text-xs font-semibold rounded border transition ${
                      selectedIncident.status === status
                        ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40"
                        : "bg-gray-800/60 text-gray-400 border-gray-700 hover:text-white hover:bg-gray-800"
                    }`}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </div>

            {/* Chronological Timeline Milestones */}
            <div className="space-y-3 pt-2 border-t border-gray-800">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider flex items-center justify-between">
                <span>Incident Progression Timeline</span>
                <span className="text-gray-500 font-mono text-[10px]">
                  {selectedIncident.timeline?.milestones.length || 0} Milestones
                </span>
              </span>

              <div className="relative pl-5 border-l-2 border-gray-800 space-y-4 my-2">
                {selectedIncident.timeline?.milestones.map((m, idx) => (
                  <div key={idx} className="relative group">
                    <div className="absolute -left-[27px] top-1 w-3.5 h-3.5 rounded-full bg-[#111827] border-2 border-cyan-400 flex items-center justify-center">
                      <div className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-[10px] text-gray-500">
                          {new Date(m.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                        <span className="text-[10px] font-bold px-1.5 py-0.2 bg-gray-800 text-gray-300 rounded font-mono">
                          {m.milestone_type}
                        </span>
                      </div>
                      <div className="text-xs font-semibold text-white mt-0.5">{m.title}</div>
                      <p className="text-[11px] text-gray-400 mt-0.5 leading-relaxed">{m.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
