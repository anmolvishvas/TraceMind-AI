import { FC, useState, useEffect } from "react";
import {
  X,
  Zap,
  Database,
  Layers,
  Cpu,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  ArrowRight,
  Flame,
} from "lucide-react";
import { ChaosScenario, ScenarioMetadata } from "../types";
import { fetchChaosScenarios } from "../api/client";

interface ChaosModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSimulate: (scenario: ChaosScenario) => Promise<void>;
  isSimulating: boolean;
}

export const ChaosModal: FC<ChaosModalProps> = ({
  isOpen,
  onClose,
  onSimulate,
  isSimulating,
}) => {
  const [scenarios, setScenarios] = useState<ScenarioMetadata[]>([]);
  const [selectedScenario, setSelectedScenario] =
    useState<ChaosScenario>("db_pool_starvation");
  const [loadingScenarios, setLoadingScenarios] = useState<boolean>(true);

  useEffect(() => {
    if (isOpen) {
      setLoadingScenarios(true);
      fetchChaosScenarios()
        .then((items) => {
          setScenarios(items);
          if (items.length > 0) {
            setSelectedScenario(items[0].scenario);
          }
        })
        .finally(() => setLoadingScenarios(false));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const current = scenarios.find((s) => s.scenario === selectedScenario) || scenarios[0];

  const getIcon = (iconName: string) => {
    switch (iconName) {
      case "database":
        return <Database className="w-5 h-5 text-amber-400" />;
      case "zap":
        return <Zap className="w-5 h-5 text-cyan-400" />;
      case "layers":
        return <Layers className="w-5 h-5 text-indigo-400" />;
      case "cpu":
        return <Cpu className="w-5 h-5 text-rose-400" />;
      default:
        return <Flame className="w-5 h-5 text-orange-400" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-[#0F172A] border border-gray-800 rounded-2xl max-w-2xl w-full shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-[#131E36]">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-orange-500/20 border border-orange-500/30 text-orange-400">
              <Flame className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                Chaos Engineering Sandbox
                <span className="px-2 py-0.5 text-[10px] uppercase font-mono font-bold tracking-wider bg-orange-500/20 text-orange-400 border border-orange-500/30 rounded">
                  Live Injection
                </span>
              </h2>
              <p className="text-xs text-gray-400">
                Simulate real-world failure patterns to test anomaly detection & autonomous RCA.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isSimulating}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-5 overflow-y-auto flex-1">
          {loadingScenarios ? (
            <div className="py-12 flex flex-col items-center justify-center text-gray-400 space-y-2">
              <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
              <span className="text-xs">Loading chaos failure scenarios...</span>
            </div>
          ) : (
            <>
              {/* Scenario Selector Grid */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-gray-300">
                  Select Production Failure Scenario:
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {scenarios.map((sc) => {
                    const isSelected = selectedScenario === sc.scenario;
                    return (
                      <div
                        key={sc.scenario}
                        onClick={() => !isSimulating && setSelectedScenario(sc.scenario)}
                        className={`p-3.5 rounded-xl border text-left cursor-pointer transition-all ${
                          isSelected
                            ? "bg-cyan-950/30 border-cyan-500/60 shadow-lg shadow-cyan-950/40 ring-1 ring-cyan-500/40"
                            : "bg-[#111827] border-gray-800 hover:border-gray-700 hover:bg-gray-800/40"
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="p-1.5 rounded-lg bg-gray-800/80 border border-gray-700">
                            {getIcon(sc.icon)}
                          </div>
                          <span
                            className={`px-1.5 py-0.5 text-[10px] font-mono font-bold rounded ${
                              sc.severity === "CRITICAL"
                                ? "bg-red-500/20 text-red-400 border border-red-500/30"
                                : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                            }`}
                          >
                            {sc.severity}
                          </span>
                        </div>
                        <h4 className="mt-2 text-xs font-bold text-white leading-tight">
                          {sc.name}
                        </h4>
                        <p className="mt-1 text-[11px] text-gray-400 line-clamp-2">
                          {sc.description}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Scenario Deep Dive Details Card */}
              {current && (
                <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-300">
                      Telemetry & Blast Radius Details
                    </span>
                    <span className="text-[11px] font-mono text-cyan-400">
                      Lead: {current.lead_service}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2.5 rounded-lg bg-gray-900/60 border border-gray-800/80">
                      <span className="text-[11px] text-gray-400 block mb-1">
                        Affected Services:
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {current.affected_services.map((svc) => (
                          <span
                            key={svc}
                            className="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-[10px] font-mono text-gray-300"
                          >
                            {svc}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-gray-900/60 border border-gray-800/80">
                      <span className="text-[11px] text-gray-400 block mb-1">
                        Injected Artifacts:
                      </span>
                      <span className="text-[11px] text-emerald-400 font-mono">
                        ~16 logs + Z-Score/IQR anomalies + Runbook RAG
                      </span>
                    </div>
                  </div>

                  <div>
                    <span className="text-[11px] text-gray-400 block mb-1">
                      Expected Outage Symptoms:
                    </span>
                    <ul className="space-y-1">
                      {current.symptoms.map((symptom, idx) => (
                        <li
                          key={idx}
                          className="flex items-center space-x-2 text-[11px] text-gray-300"
                        >
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                          <span>{symptom}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-gray-800 bg-[#131E36] flex items-center justify-between">
          <div className="text-[11px] text-gray-400 flex items-center space-x-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Telemetry safely isolated within testing sandbox.</span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={onClose}
              disabled={isSimulating}
              className="px-3.5 py-2 rounded-lg text-xs font-medium text-gray-400 hover:text-white hover:bg-gray-800 transition"
            >
              Cancel
            </button>
            <button
              onClick={() => onSimulate(selectedScenario)}
              disabled={isSimulating || loadingScenarios}
              className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white rounded-lg text-xs font-semibold shadow-lg shadow-orange-500/20 disabled:opacity-50 transition"
            >
              {isSimulating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Injecting Chaos...</span>
                </>
              ) : (
                <>
                  <Flame className="w-4 h-4" />
                  <span>Trigger Incident Now</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
