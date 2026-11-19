import { FC, useState, useEffect, Fragment, type FormEvent } from "react";
import {
  Search,
  Upload,
  Terminal,
  FileCode,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { LogEvent } from "../types";
import { fetchLogs, uploadLogFile } from "../api/client";

export const LogStreamViewer: FC = () => {
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [serviceFilter, setServiceFilter] = useState<string>("ALL");
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);

  // Upload modal state
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);

  const loadLogs = async () => {
    const res = await fetchLogs({
      query: searchQuery || undefined,
      severity: severityFilter !== "ALL" ? severityFilter : undefined,
      service_name: serviceFilter !== "ALL" ? serviceFilter : undefined,
    });
    setLogs(res.events);
  };

  useEffect(() => {
    loadLogs();
  }, [severityFilter, serviceFilter]);

  const handleSearchSubmit = (e: FormEvent) => {
    e.preventDefault();
    loadLogs();
  };

  const handleFileUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;
    setIsUploading(true);
    setUploadStatus("Ingesting & parsing micro-batches...");
    try {
      const res = await uploadLogFile(uploadFile);
      setUploadStatus(`Success: ${res.total_parsed} events indexed.`);
      setTimeout(() => {
        setIsUploadModalOpen(false);
        setUploadFile(null);
        setUploadStatus(null);
        loadLogs();
      }, 1500);
    } catch {
      setUploadStatus("Failed to ingest log file.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Controls Bar */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Search Input */}
        <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center space-x-2 w-full md:w-auto">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-gray-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search log messages, trace IDs, exceptions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#1A2333] border border-gray-700 rounded-lg pl-9 pr-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            />
          </div>
          <button
            type="submit"
            className="px-3.5 py-2 bg-[#1F2937] hover:bg-gray-700 text-gray-200 rounded-lg text-xs font-semibold border border-gray-700 transition"
          >
            Filter
          </button>
        </form>

        {/* Severity & Service Filters */}
        <div className="flex items-center space-x-2.5 w-full md:w-auto self-end md:self-auto">
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-[#1A2333] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-2 focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="ERROR">Error</option>
            <option value="WARN">Warning</option>
            <option value="INFO">Info</option>
          </select>

          <select
            value={serviceFilter}
            onChange={(e) => setServiceFilter(e.target.value)}
            className="bg-[#1A2333] border border-gray-700 text-gray-200 text-xs rounded-lg px-2.5 py-2 focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">All Services</option>
            <option value="payment-gateway">payment-gateway</option>
            <option value="order-api">order-api</option>
            <option value="auth-service">auth-service</option>
            <option value="api-gateway">api-gateway</option>
          </select>

          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="flex items-center space-x-1.5 px-3 py-2 bg-cyan-500 hover:bg-cyan-400 text-[#090D16] font-bold rounded-lg text-xs shadow transition flex-shrink-0"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload Logs</span>
          </button>
        </div>
      </div>

      {/* Log Events Table */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <div className="flex items-center space-x-2 text-xs text-gray-400">
            <Terminal className="w-4 h-4 text-cyan-400" />
            <span className="font-semibold text-white">Indexed Log Stream</span>
            <span>({logs.length} events displayed)</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#161F30] text-gray-400 font-medium border-b border-gray-800">
              <tr>
                <th className="px-4 py-2.5 w-10"></th>
                <th className="px-4 py-2.5">Timestamp</th>
                <th className="px-4 py-2.5">Severity</th>
                <th className="px-4 py-2.5">Service</th>
                <th className="px-4 py-2.5">Message</th>
                <th className="px-4 py-2.5">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 font-mono">
              {logs.map((log) => {
                const isExpanded = expandedLogId === log.event_id;
                const isCrit = log.severity === "CRITICAL" || log.severity === "ERROR";
                const isWarn = log.severity === "WARN" || log.severity === "WARNING";

                return (
                  <Fragment key={log.event_id}>
                    <tr
                      onClick={() => setExpandedLogId(isExpanded ? null : log.event_id)}
                      className={`cursor-pointer transition ${
                        isExpanded ? "bg-[#1E293B]/60" : "hover:bg-[#1E293B]/30"
                      }`}
                    >
                      <td className="px-4 py-3 text-gray-500">
                        {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-[11px] whitespace-nowrap">
                        {new Date(log.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            isCrit
                              ? "bg-red-500/10 text-red-400 border border-red-500/20"
                              : isWarn
                              ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                              : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          }`}
                        >
                          {log.severity}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-cyan-300 font-semibold whitespace-nowrap">
                        {log.service_name}
                      </td>
                      <td className="px-4 py-3 text-gray-200 font-sans truncate max-w-lg">
                        {log.message}
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-[11px] whitespace-nowrap">
                        {log.source_file ? `${log.source_file}:${log.line_number || 0}` : "—"}
                      </td>
                    </tr>

                    {/* Expanded details */}
                    {isExpanded && (
                      <tr className="bg-[#0D131F]">
                        <td colSpan={6} className="px-6 py-4 space-y-3 border-b border-gray-800">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[11px] font-mono">
                            <div>
                              <span className="text-gray-500">Event ID:</span>{" "}
                              <span className="text-white">{log.event_id}</span>
                            </div>
                            <div>
                              <span className="text-gray-500">Request ID:</span>{" "}
                              <span className="text-white">{log.request_id || "null"}</span>
                            </div>
                            <div>
                              <span className="text-gray-500">Trace ID:</span>{" "}
                              <span className="text-white">{log.trace_id || "null"}</span>
                            </div>
                            <div>
                              <span className="text-gray-500">Error Signature:</span>{" "}
                              <span className="text-amber-400">{log.error_signature || "none"}</span>
                            </div>
                          </div>

                          {log.stack_trace && (
                            <div className="space-y-1">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-red-400">
                                Exception Stack Trace:
                              </span>
                              <pre className="p-3 bg-[#080C14] border border-gray-800 rounded text-[11px] text-red-300 overflow-x-auto leading-relaxed">
                                {log.stack_trace}
                              </pre>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Upload Modal */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#111827] border border-gray-800 rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-gray-800">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Upload className="w-4 h-4 text-cyan-400" />
                <span>Upload Application Logs</span>
              </h3>
              <button
                onClick={() => setIsUploadModalOpen(false)}
                className="text-gray-400 hover:text-white text-xs px-2 py-1 bg-gray-800 rounded"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleFileUpload} className="space-y-4">
              <div className="border-2 border-dashed border-gray-700 hover:border-cyan-500/50 rounded-xl p-6 text-center space-y-2 transition cursor-pointer">
                <FileCode className="w-8 h-8 text-cyan-400 mx-auto" />
                <div className="text-xs text-gray-300 font-medium">
                  {uploadFile ? uploadFile.name : "Select or drag log file to upload"}
                </div>
                <p className="text-[10px] text-gray-500">
                  Supported: JSON, Python, Java stack traces, Nginx, Docker, Plain text
                </p>
                <input
                  type="file"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="logFileInput"
                />
                <label
                  htmlFor="logFileInput"
                  className="inline-block px-3 py-1.5 bg-[#1F2937] hover:bg-gray-700 text-gray-200 text-xs font-semibold rounded cursor-pointer transition"
                >
                  Browse Computer
                </label>
              </div>

              {uploadStatus && (
                <div className="p-2.5 rounded bg-cyan-950/30 border border-cyan-500/30 text-xs text-cyan-300 font-mono text-center">
                  {uploadStatus}
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2 border-t border-gray-800">
                <button
                  type="button"
                  onClick={() => setIsUploadModalOpen(false)}
                  className="px-3 py-1.5 rounded bg-gray-800 text-gray-300 text-xs font-semibold hover:bg-gray-700 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!uploadFile || isUploading}
                  className="px-4 py-1.5 rounded bg-cyan-500 hover:bg-cyan-400 disabled:opacity-40 text-[#090D16] text-xs font-bold transition shadow"
                >
                  {isUploading ? "Ingesting..." : "Start Ingestion"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
