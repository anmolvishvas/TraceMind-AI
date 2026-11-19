import { FC } from "react";
import { Activity, ShieldCheck, Terminal, Cpu } from "lucide-react";

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  activeIncidentCount: number;
}

export const Header: FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  activeIncidentCount,
}) => {
  const tabs = [
    { id: "overview", label: "Overview", icon: Activity },
    { id: "incidents", label: "Incidents & Timelines", icon: ShieldCheck, badge: activeIncidentCount },
    { id: "rca", label: "AI Root Cause & Copilot", icon: Cpu },
    { id: "logs", label: "Logs & Ingestion", icon: Terminal },
    { id: "rag", label: "Runbooks & RAG", icon: ShieldCheck },
  ];

  return (
    <header className="border-b border-gray-800 bg-[#0F172A]/90 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab("overview")}>
            <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 text-white font-bold">
              <Activity className="w-5 h-5 text-white animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-base font-extrabold tracking-tight text-white">TraceMind AI</span>
                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded">
                  AIOps v0.1
                </span>
              </div>
              <p className="text-[11px] text-gray-400">Autonomous Incident Intelligence Platform</p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden md:flex items-center space-x-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm shadow-cyan-500/10"
                      : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/60"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                  {tab.badge !== undefined && tab.badge > 0 && (
                    <span className="ml-1 px-1.5 py-0.2 bg-red-500/20 text-red-400 border border-red-500/30 rounded-full text-[10px] font-mono">
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right Status */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-xs text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span className="font-mono text-[11px]">Engine Online</span>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Navigation bar */}
      <div className="md:hidden flex overflow-x-auto border-t border-gray-800 px-4 py-2 space-x-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 rounded text-xs whitespace-nowrap ${
              activeTab === tab.id
                ? "bg-cyan-500/20 text-cyan-400 font-semibold"
                : "text-gray-400 hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </header>
  );
};
