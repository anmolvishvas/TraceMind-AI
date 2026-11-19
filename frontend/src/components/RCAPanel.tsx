import { FC, useState, useEffect, type FormEvent } from "react";
import {
  Sparkles,
  ShieldAlert,
  CheckCircle,
  Copy,
  Terminal,
  Send,
  MessageSquare,
  Info,
} from "lucide-react";
import { RCAResponse, ChatMessage, Incident } from "../types";
import { triggerRCA, sendChatMessage } from "../api/client";

interface RCAPanelProps {
  incidents: Incident[];
  selectedIncidentId: string;
  onSelectIncident: (id: string) => void;
}

export const RCAPanel: FC<RCAPanelProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
}) => {
  const [rca, setRca] = useState<RCAResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState<string>("");
  const [isSendingChat, setIsSendingChat] = useState<boolean>(false);
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  // Load RCA report when selected incident changes
  useEffect(() => {
    if (!selectedIncidentId) return;
    setIsLoading(true);
    triggerRCA(selectedIncidentId)
      .then((data) => {
        setRca(data);
        setChatMessages([
          {
            id: "msg-initial",
            sender: "assistant",
            content: `Hello Engineer. I have compiled the evidence-grounded Root Cause Analysis for **${selectedIncidentId}**. Ask me any questions regarding correlated log events, timeline milestones, or remediation steps.`,
            timestamp: new Date().toISOString(),
          },
        ]);
      })
      .finally(() => setIsLoading(false));
  }, [selectedIncidentId]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(text);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  const handleSendMessage = async (e: FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isSendingChat) return;

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: "user",
      content: chatInput,
      timestamp: new Date().toISOString(),
    };

    setChatMessages((prev) => [...prev, userMsg]);
    const prompt = chatInput;
    setChatInput("");
    setIsSendingChat(true);

    try {
      const response = await sendChatMessage(selectedIncidentId, prompt);
      setChatMessages((prev) => [...prev, response]);
    } finally {
      setIsSendingChat(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Incident Selector Header */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-gradient-to-tr from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 rounded-lg text-cyan-400">
            <Sparkles className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm font-bold text-white">Evidence-Grounded Root Cause Analysis</h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                100% Citation Grounded
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Correlated telemetry, statistical spike analysis, and verifiable hypothesis testing
            </p>
          </div>
        </div>

        {/* Dropdown selector */}
        <div className="flex items-center space-x-2 w-full md:w-auto">
          <span className="text-xs text-gray-400">Incident:</span>
          <select
            value={selectedIncidentId}
            onChange={(e) => onSelectIncident(e.target.value)}
            className="bg-[#1A2333] border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-cyan-500 font-mono"
          >
            {incidents.map((inc) => (
              <option key={inc.id} value={inc.incident_id}>
                {inc.incident_id} — {inc.lead_service}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="p-16 text-center bg-[#111827] border border-gray-800 rounded-xl space-y-3">
          <Sparkles className="w-8 h-8 text-cyan-400 mx-auto animate-spin" />
          <h3 className="text-sm font-semibold text-white">Synthesizing Correlated Log Evidence...</h3>
          <p className="text-xs text-gray-400">
            Running LLM hypothesis verification, extracting log citations, and checking runbook knowledge.
          </p>
        </div>
      ) : rca ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Main RCA Report (8 Cols) */}
          <div className="lg:col-span-7 space-y-6">
            {/* Primary Root Cause Highlight */}
            {rca.primary_root_cause && (
              <div className="bg-gradient-to-r from-cyan-950/40 via-[#111827] to-blue-950/30 border border-cyan-500/40 rounded-xl p-5 shadow-lg shadow-cyan-950/20">
                <div className="flex items-center space-x-2 text-cyan-400 text-xs font-bold uppercase tracking-wider mb-2">
                  <ShieldAlert className="w-4 h-4" />
                  <span>Identified Primary Root Cause</span>
                </div>
                <h4 className="text-sm text-cyan-200 font-bold leading-snug">
                  {typeof rca.primary_root_cause === "string"
                    ? rca.primary_root_cause
                    : rca.primary_root_cause.title}
                </h4>
                {typeof rca.primary_root_cause !== "string" && rca.primary_root_cause.description && (
                  <p className="text-xs text-gray-300 mt-1.5 leading-relaxed">
                    {rca.primary_root_cause.description}
                  </p>
                )}
              </div>
            )}

            {/* Executive Summary */}
            <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">
                Executive Incident Summary
              </h3>
              <p className="text-xs text-gray-300 leading-relaxed">
                {rca.executive_summary}
              </p>
            </div>

            {/* Verified Hypotheses with Likelihood & Citations */}
            <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">
                  Hypothesis Evaluation & Supporting Evidence
                </h3>
                <span className="text-[11px] text-gray-400 font-mono">
                  {rca.hypotheses?.length || 0} Hypotheses Formulated
                </span>
              </div>

              <div className="space-y-4">
                {(rca.hypotheses || []).map((hyp) => {
                  const isConfirmed = hyp.likelihood === "CONFIRMED";
                  const isHigh = hyp.likelihood === "HIGH";
                  const isUnlikely = hyp.likelihood === "UNLIKELY";
                  const supportingEv = hyp.supporting_evidence || [];
                  const contradictingEv = hyp.contradicting_evidence || hyp.falsification_checks || [];

                  return (
                    <div
                      key={hyp.hypothesis_id}
                      className={`border rounded-lg p-4 space-y-3 transition ${
                        isConfirmed
                          ? "bg-cyan-950/10 border-cyan-500/40"
                          : isHigh
                          ? "bg-blue-950/10 border-blue-500/30"
                          : "bg-[#161F30]/40 border-gray-800"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center space-x-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                isConfirmed
                                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                                  : isUnlikely
                                  ? "bg-gray-800 text-gray-400 border border-gray-700"
                                  : "bg-blue-500/20 text-blue-300 border border-blue-500/40"
                              }`}
                            >
                              {hyp.likelihood}
                            </span>
                            <span className="text-xs text-gray-400 font-mono">
                              Confidence: {Math.round(hyp.confidence_score * 100)}%
                            </span>
                          </div>
                          <h4 className="text-xs font-bold text-white mt-1">{hyp.title}</h4>
                        </div>
                      </div>

                      <p className="text-xs text-gray-300 leading-relaxed">{hyp.description}</p>

                      {/* Supporting Evidence Citations */}
                      {supportingEv.length > 0 && (
                        <div className="space-y-1 pt-2 border-t border-gray-800">
                          <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">
                            Supporting Log Citations:
                          </span>
                          <ul className="space-y-1">
                            {supportingEv.map((ev: any, i: number) => {
                              const label = typeof ev === "string" ? ev : (ev.reference || ev.excerpt || JSON.stringify(ev));
                              return (
                                <li
                                  key={i}
                                  className="text-[11px] text-gray-300 bg-[#0F172A] border border-gray-800 rounded px-2.5 py-1 font-mono flex items-center space-x-1.5"
                                >
                                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                                  <span className="truncate">{label}</span>
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}

                      {/* Contradicting / Falsification Proof */}
                      {contradictingEv.length > 0 && (
                        <div className="space-y-1 pt-1">
                          <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">
                            Contradicting / Falsification Proof:
                          </span>
                          <ul className="space-y-1">
                            {contradictingEv.map((ev: any, i: number) => {
                              const label = typeof ev === "string" ? ev : (ev.reference || ev.excerpt || JSON.stringify(ev));
                              return (
                                <li
                                  key={i}
                                  className="text-[11px] text-gray-400 bg-[#0F172A] border border-gray-800 rounded px-2.5 py-1 font-mono flex items-center space-x-1.5"
                                >
                                  <Info className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                                  <span>{label}</span>
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Diagnostic Commands & Mitigation Steps */}
            <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 flex items-center space-x-1.5">
                <Terminal className="w-4 h-4 text-cyan-400" />
                <span>Recommended Diagnostic & Triage Commands</span>
              </h3>

              <div className="space-y-2">
                {(rca.diagnostic_commands || []).map((cmd, idx) => {
                  const cmdText = typeof cmd === "string" ? cmd : JSON.stringify(cmd);
                  return (
                    <div
                      key={idx}
                      className="flex items-center justify-between bg-[#0F172A] border border-gray-800 rounded-lg p-2.5 font-mono text-xs text-cyan-300 group"
                    >
                      <span className="truncate mr-3">{cmdText}</span>
                      <button
                        onClick={() => handleCopy(cmdText)}
                        className="p-1 rounded hover:bg-gray-800 text-gray-400 hover:text-white transition flex-shrink-0"
                        title="Copy Command"
                      >
                        {copiedCmd === cmdText ? (
                          <CheckCircle className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Interactive AI Investigation Copilot Drawer (5 Cols) */}
          <div className="lg:col-span-5 flex flex-col h-[750px] bg-[#111827] border border-gray-800 rounded-xl overflow-hidden">
            {/* Copilot Header */}
            <div className="p-4 border-b border-gray-800 bg-[#161F30] flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <MessageSquare className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold text-white">AI Incident Investigation Assistant</span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-400">
                GPT-4o / Context-Bound
              </span>
            </div>

            {/* Message Stream */}
            <div className="flex-1 p-4 overflow-y-auto space-y-3">
              {chatMessages.map((msg) => {
                const isAssistant = msg.sender === "assistant";
                return (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${isAssistant ? "items-start" : "items-end"}`}
                  >
                    <div
                      className={`max-w-[90%] rounded-xl p-3 text-xs leading-relaxed ${
                        isAssistant
                          ? "bg-[#1A2333] border border-gray-700/60 text-gray-200"
                          : "bg-cyan-600 text-white font-medium"
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>

                      {/* Citations if available */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-gray-700/50 space-y-1">
                          <span className="text-[10px] font-bold text-cyan-300 uppercase">
                            Supporting Citations:
                          </span>
                          {msg.citations.map((c: any, i: number) => {
                            const citationText =
                              typeof c === "string"
                                ? c
                                : c.reference ||
                                  (c.service_name && c.source_id
                                    ? `[${c.citation_type || "Source"}: ${c.source_id} (${c.service_name})]`
                                    : c.excerpt || JSON.stringify(c));
                            return (
                              <div key={i} className="text-[10px] font-mono text-gray-400">
                                • {citationText}
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* Suggested commands */}
                      {msg.suggested_commands && msg.suggested_commands.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-gray-700/50 space-y-1">
                          <span className="text-[10px] font-bold text-amber-300 uppercase">
                            Diagnostic Suggestions:
                          </span>
                          {msg.suggested_commands.map((cmd: any, i: number) => {
                            const cmdText =
                              typeof cmd === "string" ? cmd : cmd.command || JSON.stringify(cmd);
                            return (
                              <div
                                key={i}
                                onClick={() => handleCopy(cmdText)}
                                className="text-[10px] font-mono bg-[#090D16] p-1.5 rounded text-cyan-300 border border-gray-800 cursor-pointer hover:border-cyan-500/40 flex items-center justify-between"
                              >
                                <span className="truncate">{cmdText}</span>
                                <Copy className="w-3 h-3 text-gray-500 ml-1 flex-shrink-0" />
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                    <span className="text-[9px] text-gray-500 font-mono mt-1 px-1">
                      {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                );
              })}

              {isSendingChat && (
                <div className="flex items-center space-x-2 text-xs text-cyan-400 font-mono p-2">
                  <Sparkles className="w-3.5 h-3.5 animate-spin" />
                  <span>Cross-referencing telemetry and runbooks...</span>
                </div>
              )}
            </div>

            {/* Chat Input Form */}
            <form onSubmit={handleSendMessage} className="p-3 border-t border-gray-800 bg-[#161F30]">
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  placeholder="Ask why errors spiked, check affected services..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  className="flex-1 bg-[#111827] border border-gray-700 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
                />
                <button
                  type="submit"
                  disabled={!chatInput.trim() || isSendingChat}
                  className="p-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-40 text-[#090D16] rounded-lg transition"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
};
