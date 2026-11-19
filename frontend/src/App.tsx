import { useState, useEffect } from "react";
import { Header } from "./components/Header";
import { OverviewDashboard } from "./components/OverviewDashboard";
import { IncidentExplorer } from "./components/IncidentExplorer";
import { RCAPanel } from "./components/RCAPanel";
import { LogStreamViewer } from "./components/LogStreamViewer";
import { KnowledgeBaseView } from "./components/KnowledgeBaseView";
import { fetchIncidents, fetchRecentAnomalies } from "./api/client";
import { Incident, AnomalyDataPoint } from "./types";

export default function App(): JSX.Element {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyDataPoint[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>("INC-2026-8812");

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
      />

      {/* Main Tab View Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {activeTab === "overview" && (
          <OverviewDashboard
            incidents={incidents}
            anomalies={anomalies}
            onSelectIncident={(id) => setSelectedIncidentId(id)}
            onNavigateTab={(tab) => setActiveTab(tab)}
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

      {/* Persistent Footer */}
      <footer className="border-t border-gray-800 py-6 px-4 sm:px-8 text-center text-xs text-gray-500">
        TraceMind AI — Developed by Anmol Vishvas (anmol23vishvas@gmail.com). Licensed under Apache 2.0.
      </footer>
    </div>
  );
}
