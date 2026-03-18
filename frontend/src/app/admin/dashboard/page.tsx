"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Shield,
  DollarSign,
  Users,
  Activity,
  Zap,
  TrendingUp,
  LogOut,
  RefreshCw,
  MessageSquare,
  Layers,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "";

interface Stats {
  total_users: number;
  total_tasks: number;
  total_sessions: number;
  active_sessions: number;
  total_messages: number;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_read_tokens: number;
  total_cache_creation_tokens: number;
  cache_hit_rate: number;
  estimated_savings_usd: number;
  cost_today: number;
  cost_this_week: number;
  cost_this_month: number;
  model_pricing: Record<string, { input: number; output: number; cache_read: number; cache_write: number; name: string }>;
}

interface UserUsage {
  user_id: string;
  email: string;
  task_count: number;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  last_active: string | null;
}

interface UsageLog {
  id: string;
  task_id: string;
  session_id: string;
  user_id: string;
  user_email: string | null;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_creation_tokens: number;
  total_cost_usd: number;
  duration_ms: number;
  num_turns: number;
  created_at: string;
}

interface CostUpdate {
  type: string;
  session_id?: string;
  task_id?: string;
  user_id?: string;
  cost_usd?: number;
  input_tokens?: number;
  output_tokens?: number;
  cache_read_tokens?: number;
  cache_creation_tokens?: number;
  duration_ms?: number;
  num_turns?: number;
  cumulative_cost?: number;
  cumulative_input_tokens?: number;
  cumulative_output_tokens?: number;
  cumulative_cache_read_tokens?: number;
  cumulative_cache_creation_tokens?: number;
  timestamp?: string;
}

function formatCost(cost: number): string {
  if (cost >= 1) return `$${cost.toFixed(2)}`;
  if (cost >= 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(6)}`;
}

function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}K`;
  return tokens.toString();
}

function formatDuration(ms: number): string {
  if (ms >= 60000) return `${(ms / 60000).toFixed(1)}m`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function AdminDashboard() {
  const router = useRouter();
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<UserUsage[]>([]);
  const [logs, setLogs] = useState<UsageLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [wsConnected, setWsConnected] = useState(false);
  const [liveUpdates, setLiveUpdates] = useState<CostUpdate[]>([]);
  const [liveCost, setLiveCost] = useState<number>(0);
  const [liveInputTokens, setLiveInputTokens] = useState<number>(0);
  const [liveOutputTokens, setLiveOutputTokens] = useState<number>(0);
  const wsRef = useRef<WebSocket | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "users" | "logs" | "pricing">("overview");

  const getToken = () => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("admin_token");
  };

  const adminFetch = useCallback(
    async (path: string) => {
      const token = getToken();
      if (!token) {
        router.push("/admin");
        throw new Error("No admin token");
      }
      const sep = path.includes("?") ? "&" : "?";
      const res = await fetch(`${API_BASE}${path}${sep}token=${token}`, {
        headers: { "Content-Type": "application/json" },
      });
      if (res.status === 401) {
        localStorage.removeItem("admin_token");
        router.push("/admin");
        throw new Error("Unauthorized");
      }
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      return res.json();
    },
    [router]
  );

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [statsData, usersData, logsData] = await Promise.all([
        adminFetch("/api/admin/stats"),
        adminFetch("/api/admin/users"),
        adminFetch("/api/admin/usage?limit=20"),
      ]);
      setStats(statsData);
      setUsers(usersData);
      setLogs(logsData);
      setLiveCost(statsData.total_cost_usd);
      setLiveInputTokens(statsData.total_input_tokens);
      setLiveOutputTokens(statsData.total_output_tokens);
      setError("");
    } catch (err) {
      if (err instanceof Error && err.message !== "No admin token") {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [adminFetch]);

  // Connect to admin WebSocket for real-time cost updates
  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/admin");
      return;
    }

    fetchData();

    // WebSocket connection
    const wsBase = WS_BASE || (typeof window !== "undefined"
      ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`
      : "");
    const wsUrl = `${wsBase}/api/admin/ws/costs?token=${token}`;

    const connectWs = () => {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => setWsConnected(true);

        ws.onmessage = (event) => {
          try {
            const data: CostUpdate = JSON.parse(event.data);
            if (data.type === "init" || data.type === "cost_update") {
              if (data.cumulative_cost !== undefined) {
                setLiveCost(data.cumulative_cost);
              }
              if (data.cumulative_input_tokens !== undefined) {
                setLiveInputTokens(data.cumulative_input_tokens);
              }
              if (data.cumulative_output_tokens !== undefined) {
                setLiveOutputTokens(data.cumulative_output_tokens);
              }
            }
            if (data.type === "cost_update") {
              setLiveUpdates((prev) => [data, ...prev].slice(0, 50));
            }
          } catch {
            // ignore parse errors
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          // Reconnect after 3 seconds
          setTimeout(connectWs, 3000);
        };

        ws.onerror = () => setWsConnected(false);
      } catch {
        // ignore connection errors
      }
    };

    connectWs();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [router, fetchData]);

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    router.push("/admin");
  };

  if (loading && !stats) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="flex items-center gap-3 text-gray-400">
          <RefreshCw className="w-5 h-5 animate-spin" />
          Loading admin dashboard...
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-950/90 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-orange-600 flex items-center justify-center">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <h1 className="text-lg font-semibold">Admin Portal</h1>
            <div
              className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs ${
                wsConnected
                  ? "bg-green-500/10 text-green-400"
                  : "bg-yellow-500/10 text-yellow-400"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  wsConnected ? "bg-green-400 pulse-dot" : "bg-yellow-400"
                }`}
              />
              {wsConnected ? "Live" : "Reconnecting"}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchData}
              className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
              title="Refresh data"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {error && (
          <div className="mb-6 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Live Cost Banner */}
        <div className="mb-6 p-4 rounded-xl bg-gradient-to-r from-red-500/10 via-orange-500/10 to-yellow-500/10 border border-orange-500/20">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <div className="flex items-center gap-2 text-sm text-orange-400 mb-1">
                <TrendingUp className="w-4 h-4" />
                Real-time Total Cost
              </div>
              <div className="text-3xl font-bold text-white">
                {formatCost(liveCost)}
              </div>
            </div>
            <div className="flex gap-6 flex-wrap">
              <div>
                <div className="text-xs text-gray-400">Input Tokens</div>
                <div className="text-lg font-semibold text-blue-400">
                  {formatTokens(liveInputTokens)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Output Tokens</div>
                <div className="text-lg font-semibold text-purple-400">
                  {formatTokens(liveOutputTokens)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Cache Hit Rate</div>
                <div className="text-lg font-semibold text-emerald-400">
                  {stats ? `${(stats.cache_hit_rate * 100).toFixed(1)}%` : "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Cache Savings</div>
                <div className="text-lg font-semibold text-emerald-400">
                  {stats ? formatCost(stats.estimated_savings_usd) : "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Active Sessions</div>
                <div className="text-lg font-semibold text-green-400">
                  {stats?.active_sessions ?? 0}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-gray-800 overflow-x-auto">
          {(
            [
              { key: "overview", label: "Overview", icon: Activity },
              { key: "users", label: "Users", icon: Users },
              { key: "logs", label: "Usage Logs", icon: Layers },
              { key: "pricing", label: "Pricing", icon: DollarSign },
            ] as const
          ).map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === key
                  ? "border-orange-500 text-white"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Overview Tab */}
        {activeTab === "overview" && stats && (
          <div className="space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                icon={DollarSign}
                label="Cost Today"
                value={formatCost(stats.cost_today)}
                color="text-green-400"
                bgColor="bg-green-500/10"
              />
              <StatCard
                icon={DollarSign}
                label="Cost This Week"
                value={formatCost(stats.cost_this_week)}
                color="text-blue-400"
                bgColor="bg-blue-500/10"
              />
              <StatCard
                icon={DollarSign}
                label="Cost This Month"
                value={formatCost(stats.cost_this_month)}
                color="text-purple-400"
                bgColor="bg-purple-500/10"
              />
              <StatCard
                icon={DollarSign}
                label="Total Cost (All Time)"
                value={formatCost(stats.total_cost_usd)}
                color="text-orange-400"
                bgColor="bg-orange-500/10"
              />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                icon={Users}
                label="Total Users"
                value={stats.total_users.toString()}
                color="text-cyan-400"
                bgColor="bg-cyan-500/10"
              />
              <StatCard
                icon={Layers}
                label="Total Tasks"
                value={stats.total_tasks.toString()}
                color="text-indigo-400"
                bgColor="bg-indigo-500/10"
              />
              <StatCard
                icon={Activity}
                label="Total Sessions"
                value={stats.total_sessions.toString()}
                color="text-pink-400"
                bgColor="bg-pink-500/10"
              />
              <StatCard
                icon={MessageSquare}
                label="Total Messages"
                value={formatTokens(stats.total_messages)}
                color="text-yellow-400"
                bgColor="bg-yellow-500/10"
              />
            </div>

            {/* Cache Performance */}
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-6 h-6 rounded-md bg-emerald-500/20 flex items-center justify-center">
                  <Zap className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <h3 className="font-medium text-sm text-emerald-400">Prompt Cache Performance</h3>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className="p-3 rounded-lg bg-gray-800/50">
                  <div className="text-xs text-gray-400">Cache Hit Rate</div>
                  <div className="text-xl font-bold text-emerald-400 mt-1">
                    {(stats.cache_hit_rate * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-gray-800/50">
                  <div className="text-xs text-gray-400">Cache Read Tokens</div>
                  <div className="text-xl font-bold text-emerald-400 mt-1">
                    {formatTokens(stats.total_cache_read_tokens)}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-0.5">@ $0.30/MTok</div>
                </div>
                <div className="p-3 rounded-lg bg-gray-800/50">
                  <div className="text-xs text-gray-400">Cache Write Tokens</div>
                  <div className="text-xl font-bold text-yellow-400 mt-1">
                    {formatTokens(stats.total_cache_creation_tokens)}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-0.5">@ $3.75/MTok</div>
                </div>
                <div className="p-3 rounded-lg bg-gray-800/50">
                  <div className="text-xs text-gray-400">Uncached Input</div>
                  <div className="text-xl font-bold text-blue-400 mt-1">
                    {formatTokens(stats.total_input_tokens)}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-0.5">@ $3.00/MTok</div>
                </div>
                <div className="p-3 rounded-lg bg-gray-800/50">
                  <div className="text-xs text-gray-400">Est. Savings</div>
                  <div className="text-xl font-bold text-emerald-400 mt-1">
                    {formatCost(stats.estimated_savings_usd)}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-0.5">vs. no caching</div>
                </div>
              </div>
            </div>

            {/* Live Cost Feed */}
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-2">
                <Zap className="w-4 h-4 text-orange-400" />
                <h3 className="font-medium text-sm">Live Cost Feed</h3>
                <span className="text-xs text-gray-500">
                  (updates in real-time)
                </span>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {liveUpdates.length === 0 ? (
                  <div className="px-4 py-8 text-center text-gray-500 text-sm">
                    Waiting for agent activity...
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800/50 sticky top-0">
                      <tr>
                        <th className="px-4 py-2 text-left text-gray-400 font-medium">
                          Time
                        </th>
                        <th className="px-4 py-2 text-left text-gray-400 font-medium">
                          Session
                        </th>
                        <th className="px-4 py-2 text-right text-gray-400 font-medium">
                          Cost
                        </th>
                        <th className="px-4 py-2 text-right text-gray-400 font-medium">
                          Tokens
                        </th>
                        <th className="px-4 py-2 text-right text-gray-400 font-medium">
                          Turns
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {liveUpdates.map((update, i) => (
                        <tr
                          key={i}
                          className={`border-t border-gray-800/50 ${
                            i === 0 ? "bg-orange-500/5" : ""
                          }`}
                        >
                          <td className="px-4 py-2 text-gray-400">
                            {update.timestamp
                              ? timeAgo(update.timestamp)
                              : "now"}
                          </td>
                          <td className="px-4 py-2 text-gray-300 font-mono text-xs">
                            {update.session_id?.slice(0, 8) || "-"}
                          </td>
                          <td className="px-4 py-2 text-right text-green-400 font-medium">
                            {formatCost(update.cost_usd || 0)}
                          </td>
                          <td className="px-4 py-2 text-right text-gray-300">
                            {formatTokens(
                              (update.input_tokens || 0) +
                                (update.output_tokens || 0)
                            )}
                          </td>
                          <td className="px-4 py-2 text-right text-gray-400">
                            {update.num_turns || "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Users Tab */}
        {activeTab === "users" && (
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-800/50">
                <tr>
                  <th className="px-4 py-3 text-left text-gray-400 font-medium">
                    Email
                  </th>
                  <th className="px-4 py-3 text-right text-gray-400 font-medium">
                    Tasks
                  </th>
                  <th className="px-4 py-3 text-right text-gray-400 font-medium">
                    Total Cost
                  </th>
                  <th className="px-4 py-3 text-right text-gray-400 font-medium">
                    Input Tokens
                  </th>
                  <th className="px-4 py-3 text-right text-gray-400 font-medium">
                    Output Tokens
                  </th>
                  <th className="px-4 py-3 text-right text-gray-400 font-medium">
                    Last Active
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-4 py-8 text-center text-gray-500"
                    >
                      No users found
                    </td>
                  </tr>
                ) : (
                  users.map((user) => (
                    <tr
                      key={user.user_id}
                      className="border-t border-gray-800/50 hover:bg-gray-800/30"
                    >
                      <td className="px-4 py-3 text-white">{user.email}</td>
                      <td className="px-4 py-3 text-right text-gray-300">
                        {user.task_count}
                      </td>
                      <td className="px-4 py-3 text-right text-green-400 font-medium">
                        {formatCost(user.total_cost_usd)}
                      </td>
                      <td className="px-4 py-3 text-right text-blue-400">
                        {formatTokens(user.total_input_tokens)}
                      </td>
                      <td className="px-4 py-3 text-right text-purple-400">
                        {formatTokens(user.total_output_tokens)}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-400">
                        {user.last_active ? timeAgo(user.last_active) : "-"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Usage Logs Tab */}
        {activeTab === "logs" && (
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-800/50">
                <tr>
                  <th className="px-3 py-3 text-left text-gray-400 font-medium">
                    Time
                  </th>
                  <th className="px-3 py-3 text-left text-gray-400 font-medium">
                    User
                  </th>
                  <th className="px-3 py-3 text-right text-gray-400 font-medium">
                    Cost
                  </th>
                  <th className="px-3 py-3 text-right text-gray-400 font-medium">
                    Input
                  </th>
                  <th className="px-3 py-3 text-right text-gray-400 font-medium">
                    Cache Read
                  </th>
                  <th className="px-3 py-3 text-right text-gray-400 font-medium">
                    Cache Write
                  </th>
                  <th className="px-3 py-3 text-right text-gray-400 font-medium">
                    Output
                  </th>
                  <th className="px-3 py-3 text-right text-gray-400 font-medium">
                    Duration
                  </th>
                  <th className="px-3 py-3 text-right text-gray-400 font-medium">
                    Turns
                  </th>
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 ? (
                  <tr>
                    <td
                      colSpan={9}
                      className="px-4 py-8 text-center text-gray-500"
                    >
                      No usage logs yet. Costs will appear here once agents run
                      tasks.
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => {
                    const totalInput = log.input_tokens + log.cache_read_tokens + log.cache_creation_tokens;
                    const hitRate = totalInput > 0 ? log.cache_read_tokens / totalInput : 0;
                    return (
                      <tr
                        key={log.id}
                        className="border-t border-gray-800/50 hover:bg-gray-800/30"
                      >
                        <td className="px-3 py-3 text-gray-400">
                          {timeAgo(log.created_at)}
                        </td>
                        <td className="px-3 py-3 text-gray-300">
                          {log.user_email || log.user_id.slice(0, 8)}
                        </td>
                        <td className="px-3 py-3 text-right text-green-400 font-medium">
                          {formatCost(log.total_cost_usd)}
                        </td>
                        <td className="px-3 py-3 text-right text-blue-400">
                          {formatTokens(log.input_tokens)}
                        </td>
                        <td className="px-3 py-3 text-right text-emerald-400">
                          {formatTokens(log.cache_read_tokens)}
                          {hitRate > 0 && (
                            <span className="text-[10px] text-emerald-500/70 ml-1">
                              {(hitRate * 100).toFixed(0)}%
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-3 text-right text-yellow-400">
                          {formatTokens(log.cache_creation_tokens)}
                        </td>
                        <td className="px-3 py-3 text-right text-purple-400">
                          {formatTokens(log.output_tokens)}
                        </td>
                        <td className="px-3 py-3 text-right text-gray-400">
                          {formatDuration(log.duration_ms)}
                        </td>
                        <td className="px-3 py-3 text-right text-gray-400">
                          {log.num_turns}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pricing Tab */}
        {activeTab === "pricing" && stats && (
          <div className="space-y-6">
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-800">
                <h3 className="font-medium text-sm">LLM Model Pricing</h3>
                <p className="text-xs text-gray-500 mt-1">
                  Per 1M tokens (USD) — Anthropic API rates
                </p>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-gray-800/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-gray-400 font-medium">
                      Model
                    </th>
                    <th className="px-4 py-3 text-right text-gray-400 font-medium">
                      Input (per 1M)
                    </th>
                    <th className="px-4 py-3 text-right text-gray-400 font-medium">
                      Cache Read
                    </th>
                    <th className="px-4 py-3 text-right text-gray-400 font-medium">
                      Cache Write
                    </th>
                    <th className="px-4 py-3 text-right text-gray-400 font-medium">
                      Output (per 1M)
                    </th>
                    <th className="px-4 py-3 text-right text-gray-400 font-medium">
                      Cache Discount
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(stats.model_pricing).map(
                    ([key, pricing]) => {
                      const discount = pricing.input > 0
                        ? ((1 - pricing.cache_read / pricing.input) * 100).toFixed(0)
                        : "0";
                      return (
                        <tr
                          key={key}
                          className="border-t border-gray-800/50 hover:bg-gray-800/30"
                        >
                          <td className="px-4 py-3">
                            <div className="text-white font-medium">
                              {pricing.name}
                            </div>
                            <div className="text-xs text-gray-500 font-mono">
                              {key}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right text-blue-400">
                            ${pricing.input.toFixed(2)}
                          </td>
                          <td className="px-4 py-3 text-right text-emerald-400">
                            ${pricing.cache_read.toFixed(2)}
                          </td>
                          <td className="px-4 py-3 text-right text-yellow-400">
                            ${pricing.cache_write.toFixed(2)}
                          </td>
                          <td className="px-4 py-3 text-right text-purple-400">
                            ${pricing.output.toFixed(2)}
                          </td>
                          <td className="px-4 py-3 text-right text-emerald-400 font-medium">
                            {discount}% off
                          </td>
                        </tr>
                      );
                    }
                  )}
                </tbody>
              </table>
            </div>

            {/* Cost Summary */}
            <div className="rounded-xl border border-orange-500/30 bg-orange-500/5 p-6">
              <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-orange-400" />
                Total LLM API Cost
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-gray-800/50">
                  <div className="text-sm text-gray-400">Total Spend</div>
                  <div className="text-2xl font-bold text-green-400 mt-1">
                    {formatCost(stats.total_cost_usd)}
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-gray-800/50">
                  <div className="text-sm text-gray-400">Input Tokens</div>
                  <div className="text-2xl font-bold text-blue-400 mt-1">
                    {formatTokens(stats.total_input_tokens)}
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-gray-800/50">
                  <div className="text-sm text-gray-400">Output Tokens</div>
                  <div className="text-2xl font-bold text-purple-400 mt-1">
                    {formatTokens(stats.total_output_tokens)}
                  </div>
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-4">
                Infrastructure: self-hosted Hetzner VPS (no per-container compute costs)
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
  bgColor,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  color: string;
  bgColor: string;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-8 h-8 rounded-lg ${bgColor} flex items-center justify-center`}>
          <Icon className={`w-4 h-4 ${color}`} />
        </div>
      </div>
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}
