"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Globe, SquarePen, LogOut, X } from "lucide-react";
import { ConversationItem } from "@/components/ConversationItem";
import { removeToken } from "@/lib/api";

interface Task {
  id: string;
  prompt: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
}

interface SidebarProps {
  tasks: Task[];
  isOpen: boolean;
  onToggle: () => void;
  activeTaskId?: string;
  onDeleteTask: (taskId: string) => void;
}

function groupByDate(tasks: Task[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  const groups: { label: string; tasks: Task[] }[] = [
    { label: "Today", tasks: [] },
    { label: "Yesterday", tasks: [] },
    { label: "Previous 7 Days", tasks: [] },
    { label: "Older", tasks: [] },
  ];

  for (const task of tasks) {
    const date = new Date(task.created_at);
    if (date >= today) {
      groups[0].tasks.push(task);
    } else if (date >= yesterday) {
      groups[1].tasks.push(task);
    } else if (date >= weekAgo) {
      groups[2].tasks.push(task);
    } else {
      groups[3].tasks.push(task);
    }
  }

  return groups.filter((g) => g.tasks.length > 0);
}

export function Sidebar({ tasks, isOpen, onToggle, activeTaskId, onDeleteTask }: SidebarProps) {
  const router = useRouter();

  const handleLogout = () => {
    removeToken();
    window.location.href = "/auth/login";
  };

  // Get user email from token (JWT payload) — deferred to avoid hydration mismatch
  const [userEmail, setUserEmail] = useState("");
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        setUserEmail(payload.sub || payload.email || "");
      } catch {
        // ignore
      }
    }
  }, []);

  const groups = groupByDate(tasks);

  const sidebarContent = (
    <div className="flex flex-col h-full bg-[#0a0a0f] border-r border-[#1e1e2e]">
      {/* Top: Logo + New Chat */}
      <div className="flex items-center justify-between px-4 py-3.5 border-b border-[#1e1e2e] shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/10">
            <Globe className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-semibold text-white tracking-tight">CompSphere</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => router.push("/chat")}
            className="p-2 rounded-lg text-gray-500 hover:text-white hover:bg-[#1a1a28] transition-colors"
            title="New Chat"
          >
            <SquarePen className="w-4 h-4" />
          </button>
          {/* Close button (mobile) */}
          <button
            onClick={onToggle}
            className="p-2 rounded-lg text-gray-500 hover:text-white hover:bg-[#1a1a28] transition-colors md:hidden"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Middle: Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-5">
        {groups.length === 0 ? (
          <div className="text-center py-12 fade-in">
            <p className="text-xs text-gray-600">No conversations yet</p>
            <p className="text-[10px] text-gray-700 mt-1">Start a new chat to begin</p>
          </div>
        ) : (
          groups.map((group) => (
            <div key={group.label}>
              <p className="px-3 py-1 text-[10px] font-semibold text-gray-500 uppercase tracking-widest">
                {group.label}
              </p>
              <div className="mt-1 space-y-0.5">
                {group.tasks.map((task) => (
                  <ConversationItem
                    key={task.id}
                    task={task}
                    isActive={task.id === activeTaskId}
                    onClick={() => {
                      router.push(`/chat/${task.id}`);
                      // Close on mobile
                      if (window.innerWidth < 768) onToggle();
                    }}
                    onDelete={onDeleteTask}
                  />
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Bottom: User + Sign Out */}
      <div className="px-3 py-3 border-t border-[#1e1e2e] shrink-0">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-[#2a2a3e] flex items-center justify-center shrink-0">
              <span className="text-[10px] font-medium text-gray-400">
                {userEmail ? userEmail[0].toUpperCase() : "?"}
              </span>
            </div>
            <span className="text-[11px] text-gray-500 truncate max-w-[140px]">
              {userEmail}
            </span>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] text-gray-600 hover:text-red-400 hover:bg-red-500/5 transition-colors"
          >
            <LogOut className="w-3 h-3" />
            <span className="hidden sm:inline">Sign Out</span>
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <div className="hidden md:block w-[260px] shrink-0 h-full">
        {sidebarContent}
      </div>

      {/* Mobile overlay */}
      {isOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden"
            onClick={onToggle}
          />
          <div className="fixed inset-y-0 left-0 w-[280px] z-50 md:hidden shadow-2xl shadow-black/50">
            {sidebarContent}
          </div>
        </>
      )}
    </>
  );
}
