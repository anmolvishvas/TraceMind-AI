import { useState, useEffect } from "react";
import { Header } from "./components/Header";
import { OverviewDashboard } from "./components/OverviewDashboard";
import { IncidentExplorer } from "./components/IncidentExplorer";
import { RCAPanel } from "./components/RCAPanel";
import { LogStreamViewer } from "./components/LogStreamViewer";
import { KnowledgeBaseView } from "./components/KnowledgeBaseView";
import { ChaosModal } from "./components/ChaosModal";
import {
  fetchIncidents,
  fetchRecentAnomalies,
  triggerChaosSimulation,
} from "./api/client";
import { Incident, AnomalyDataPoint, ChaosScenario } from "./types";
import { Flame, ArrowRight, X } from "lucide-react";

export default function App(): JSX.Element {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyDataPoint[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] =
    useState<string>("INC-2026-8812");
  const [isChaosModalOpen, setIsChaosModalOpen] = useState<boolean>(false);
  const [isSimulatingChaos, setIsSimulatingChaos] = useState<boolean>(false);
  const [chaosNotification, setChaosNotification] = useState<{
    message: string;
    incidentId: string;
  } | null>(null);

  const loadData = async () => {
    const [incList, anomList] = await Promise.all([
      fetchIncidents(),
      fetchRecentAnomalies(),
    ]);
    setIncidents(incList);
    setAnomalies(anomList);
    if (incList.length > 0 && !selectedIncidentId) {
      setSelectedIncidentId(incList[0].incident_id);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSimulateChaos = async (scenario: ChaosScenario) => {
    setIsSimulatingChaos(true);
    try {
      const resp = await triggerChaosSimulation(scenario);
      await loadData();
      setSelectedIncidentId(resp.incident.incident_id);
      setChaosNotification({
        message: resp.message,
        incidentId: resp.incident.incident_id,
      });
      setIsChaosModalOpen(false);
      setActiveTab("rca");
    } catch (err) {
      console.error("Chaos injection error:", err);
    } finally {
      setIsSimulatingChaos(false);
    }
  };

  const activeIncidentCount = incidents.filter(
    (i) => i.status !== "RESOLVED" && i.status !== "CLOSED"
  ).length;

  return (
    <div className="min-h-screen bg-[#090D16] text-[#F9FAFB] flex flex-col font-sans">
      {/* Global Application Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        activeIncidentCount={activeIncidentCount}
        onOpenChaosModal={() => setIsChaosModalOpen(true)}
      />

      {/* Floating Chaos Injection Success Notification Toast */}
      {chaosNotification && (
        <div className="bg-gradient-to-r from-orange-950/80 via-[#1E1B4B]/80 to-gray-900 border-b border-orange-500/40 px-4 py-2.5 transition animate-in slide-in-from-top">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-2 text-xs">
              <Flame className="w-4 h-4 text-orange-400 shrink-0 animate-bounce" />
              <span className="font-semibold text-orange-200">
                Outage Injected:
              </span>
              <span className="text-gray-300">
                {chaosNotification.message}
              </span>
              <button
                onClick={() => {
                  setSelectedIncidentId(chaosNotification.incidentId);
                  setActiveTab("rca");
                }}
                className="ml-2 inline-flex items-center space-x-1 text-cyan-400 hover:text-cyan-300 font-mono underline"
              >
                <span>View {chaosNotification.incidentId} in RCA</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>
            <button
              onClick={() => setChaosNotification(null)}
              className="text-gray-400 hover:text-white p-1"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Main Tab View Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {activeTab === "overview" && (
          <OverviewDashboard
            incidents={incidents}
            anomalies={anomalies}
            onSelectIncident={(id) => setSelectedIncidentId(id)}
            onNavigateTab={(tab) => setActiveTab(tab)}
            onOpenChaosModal={() => setIsChaosModalOpen(true)}
            onQuickSimulate={handleSimulateChaos}
            isSimulating={isSimulatingChaos}
          />
        )}

        {activeTab === "incidents" && (
          <IncidentExplorer
            incidents={incidents}
            onSelectIncident={(id) => setSelectedIncidentId(id)}
            onNavigateTab={(tab) => setActiveTab(tab)}
            onRefreshIncidents={loadData}
          />
        )}

        {activeTab === "rca" && (
          <RCAPanel
            incidents={incidents}
            selectedIncidentId={selectedIncidentId}
            onSelectIncident={(id) => setSelectedIncidentId(id)}
          />
        )}

        {activeTab === "logs" && <LogStreamViewer />}

        {activeTab === "rag" && <KnowledgeBaseView />}
      </main>

      {/* Interactive Chaos Simulation Modal */}
      <ChaosModal
        isOpen={isChaosModalOpen}
        onClose={() => setIsChaosModalOpen(false)}
        onSimulate={handleSimulateChaos}
        isSimulating={isSimulatingChaos}
      />

      {/* Persistent Footer */}
      <footer className="border-t border-gray-800 py-6 px-4 sm:px-8 text-center text-xs text-gray-500">
        TraceMind AI — Developed by Anmol Vishvas (anmol23vishvas@gmail.com). Licensed under Apache 2.0.
      </footer>
    </div>
  );
}
