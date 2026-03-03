"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";

interface Task {
  id: string;
  prompt: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
}

interface ConversationItemProps {
  task: Task;
  isActive: boolean;
  onClick: () => void;
  onDelete: (taskId: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  running: "bg-emerald-400",
  pending: "bg-yellow-400",
  completed: "bg-gray-500",
  failed: "bg-red-400",
};

function formatRelativeTime(dateStr: string) {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m`;
  if (diffHours < 24) return `${diffHours}h`;
  if (diffDays < 7) return `${diffDays}d`;
  return date.toLocaleDateString();
}

export function ConversationItem({
  task,
  isActive,
  onClick,
  onDelete,
}: ConversationItemProps) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div
      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-all group cursor-pointer ${
        isActive
          ? "bg-[#1a1a28] border-l-2 border-blue-500 pl-2.5"
          : "hover:bg-[#14141e]"
      }`}
      onClick={onClick}
    >
      <div
        className={`w-1.5 h-1.5 rounded-full shrink-0 ${
          STATUS_COLORS[task.status] || "bg-gray-500"
        } ${task.status === "running" ? "pulse-dot" : ""}`}
      />
      <div className="flex-1 min-w-0">
        <p
          className={`text-[13px] truncate leading-snug ${
            isActive ? "text-white font-medium" : "text-gray-400 group-hover:text-gray-200"
          }`}
        >
          {task.prompt}
        </p>
      </div>
      {confirming ? (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(task.id);
            setConfirming(false);
          }}
          className="text-[11px] text-red-400 hover:text-red-300 shrink-0 font-medium px-1.5 py-0.5 rounded bg-red-500/10"
        >
          Delete?
        </button>
      ) : (
        <>
          <span className="text-[10px] text-gray-600 shrink-0 group-hover:hidden">
            {formatRelativeTime(task.created_at)}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setConfirming(true);
            }}
            className="hidden group-hover:flex shrink-0 p-1 rounded-md text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-colors"
            title="Delete chat"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </>
      )}
    </div>
  );
}
