import React from "react";
import { Activity, AlertTriangle, ShieldCheck, Cpu, Terminal, FileText } from "lucide-react";

export default function App(): JSX.Element {
  return (
    <div className="min-h-screen bg-[#090D16] text-[#F9FAFB] flex flex-col">
      {/* Top Navigation */}
      <header className="border-b border-gray-800 bg-[#111827]/80 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">TraceMind AI</h1>
            <p className="text-xs text-gray-400">Production Incident Intelligence & RCA</p>
          </div>
        </div>
        <div className="flex items-center space-x-4">
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            Telemetry Pipeline Ready
          </span>
          <span className="text-xs text-gray-400 font-mono">v0.1.0-alpha</span>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8 space-y-8">
        {/* Hero Section */}
        <div className="bg-gradient-to-r from-cyan-950/30 via-[#111827] to-violet-950/30 border border-gray-800 rounded-xl p-8 relative overflow-hidden">
          <div className="max-w-3xl space-y-4">
            <div className="inline-flex items-center space-x-2 text-cyan-400 text-sm font-semibold tracking-wide uppercase">
              <Cpu className="w-4 h-4" />
              <span>AIOps Incident Intelligence Engine</span>
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl text-white">
              Autonomous Log Intelligence, Statistical Anomaly Detection & Evidence-First RCA
            </h2>
            <p className="text-gray-300 text-base leading-relaxed">
              TraceMind AI transforms raw, unstructured application logs into correlated incident timelines,
              detects statistical error bursts without LLM hallucinations, and provides verified, citation-backed
              root cause investigations.
            </p>
          </div>
        </div>

        {/* 4 KPI Metrics Preview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-[#111827] border border-gray-800 rounded-lg p-5">
            <div className="flex items-center justify-between text-gray-400 text-sm">
              <span>Active Incidents</span>
              <AlertTriangle className="w-4 h-4 text-red-400" />
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-white">0</div>
            <p className="text-xs text-emerald-400 mt-1">All services healthy</p>
          </div>

          <div className="bg-[#111827] border border-gray-800 rounded-lg p-5">
            <div className="flex items-center justify-between text-gray-400 text-sm">
              <span>Ingested Events (24h)</span>
              <Terminal className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-white">0</div>
            <p className="text-xs text-gray-400 mt-1">Ready for log batch upload</p>
          </div>

          <div className="bg-[#111827] border border-gray-800 rounded-lg p-5">
            <div className="flex items-center justify-between text-gray-400 text-sm">
              <span>Statistical Baselines</span>
              <Activity className="w-4 h-4 text-amber-400" />
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-white">Z-Score / IQR</div>
            <p className="text-xs text-gray-400 mt-1">Independent Python ML math</p>
          </div>

          <div className="bg-[#111827] border border-gray-800 rounded-lg p-5">
            <div className="flex items-center justify-between text-gray-400 text-sm">
              <span>RAG Knowledge Vectors</span>
              <ShieldCheck className="w-4 h-4 text-violet-400" />
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-white">pgvector HNSW</div>
            <p className="text-xs text-gray-400 mt-1">Sub-50ms cosine similarity</p>
          </div>
        </div>

        {/* Documentation Links Card */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-6">
          <div className="flex items-center space-x-2 text-white font-semibold text-lg mb-4">
            <FileText className="w-5 h-5 text-cyan-400" />
            <span>Architecture & Engineering Specifications</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <a
              href="https://github.com/anmolvishvas/TraceMind-AI/blob/main/docs/PRD.md"
              target="_blank"
              rel="noreferrer"
              className="p-4 rounded-lg bg-[#1F2937]/50 hover:bg-[#1F2937] border border-gray-700/50 transition block"
            >
              <div className="font-semibold text-cyan-300">Product Requirements (PRD)</div>
              <p className="text-gray-400 text-xs mt-1">User journeys, acceptance tables, and success metrics.</p>
            </a>
            <a
              href="https://github.com/anmolvishvas/TraceMind-AI/blob/main/docs/ARCHITECTURE.md"
              target="_blank"
              rel="noreferrer"
              className="p-4 rounded-lg bg-[#1F2937]/50 hover:bg-[#1F2937] border border-gray-700/50 transition block"
            >
              <div className="font-semibold text-cyan-300">System Architecture</div>
              <p className="text-gray-400 text-xs mt-1">Mermaid topology, canonical schemas, and subsystem boundaries.</p>
            </a>
            <a
              href="https://github.com/anmolvishvas/TraceMind-AI/blob/main/docs/RULES.md"
              target="_blank"
              rel="noreferrer"
              className="p-4 rounded-lg bg-[#1F2937]/50 hover:bg-[#1F2937] border border-gray-700/50 transition block"
            >
              <div className="font-semibold text-cyan-300">Engineering Rulebook</div>
              <p className="text-gray-400 text-xs mt-1">Strict standards for Python, async, security, RAG, and tests.</p>
            </a>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-6 px-8 text-center text-xs text-gray-500">
        TraceMind AI — Developed by Anmol Vishvas (anmol23vishvas@gmail.com). Licensed under Apache 2.0.
      </footer>
    </div>
  );
}
