"use client";

import {
  Menu,
  Monitor,
  Clock,
  Play,
  CheckCircle2,
  XCircle,
  MessageCircle,
} from "lucide-react";

interface ChatTopBarProps {
  prompt: string;
  status: string;
  isConnected: boolean;
  showBrowser: boolean;
  onToggleBrowser: () => void;
  onToggleSidebar: () => void;
}

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
  pending: {
    icon: <Clock className="w-3 h-3" />,
    color: "text-yellow-400",
    bg: "bg-yellow-500/8 border-yellow-500/15",
  },
  running: {
    icon: <Play className="w-3 h-3" />,
    color: "text-blue-400",
    bg: "bg-blue-500/8 border-blue-500/15",
  },
  idle: {
    icon: <MessageCircle className="w-3 h-3" />,
    color: "text-purple-400",
    bg: "bg-purple-500/8 border-purple-500/15",
  },
  completed: {
    icon: <CheckCircle2 className="w-3 h-3" />,
    color: "text-emerald-400",
    bg: "bg-emerald-500/8 border-emerald-500/15",
  },
  failed: {
    icon: <XCircle className="w-3 h-3" />,
    color: "text-red-400",
    bg: "bg-red-500/8 border-red-500/15",
  },
};

export function ChatTopBar({
  prompt,
  status,
  isConnected,
  showBrowser,
  onToggleBrowser,
  onToggleSidebar,
}: ChatTopBarProps) {
  const statusCfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending;

  return (
    <div className="h-12 border-b border-[#1e1e2e] bg-[#0a0a0f]/95 backdrop-blur-xl flex items-center justify-between px-4 shrink-0 z-10">
      {/* Left: hamburger (mobile) + prompt */}
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-[#1a1a28] transition-colors md:hidden shrink-0"
        >
          <Menu className="w-4 h-4" />
        </button>

        <span className="text-[13px] font-medium text-gray-300 truncate">
          {prompt || "Loading..."}
        </span>
      </div>

      {/* Right: status + connection + browser toggle */}
      <div className="flex items-center gap-2 shrink-0">
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border ${statusCfg.bg}`}>
          <span className={statusCfg.color}>{statusCfg.icon}</span>
          <span className={`text-[11px] font-medium capitalize ${statusCfg.color}`}>
            {status}
          </span>
        </div>

        <div
          className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-medium ${
            isConnected
              ? "bg-emerald-500/8 text-emerald-400 border border-emerald-500/15"
              : "bg-gray-800/50 text-gray-500 border border-gray-700/30"
          }`}
        >
          <div
            className={`w-1.5 h-1.5 rounded-full ${
              isConnected ? "bg-emerald-400 pulse-dot" : "bg-gray-600"
            }`}
          />
          {isConnected ? "Live" : "Offline"}
        </div>

        <button
          onClick={onToggleBrowser}
          className={`p-1.5 rounded-lg transition-all ${
            showBrowser
              ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
              : "text-gray-500 hover:text-white hover:bg-[#1a1a28]"
          }`}
          title={showBrowser ? "Hide browser" : "Show browser"}
        >
          <Monitor className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
