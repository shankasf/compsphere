"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Panel,
  Group as PanelGroup,
  Separator as PanelResizeHandle,
} from "react-resizable-panels";
import dynamic from "next/dynamic";
import { ChatPanel } from "@/components/ChatPanel";
import { ChatTopBar } from "@/components/ChatTopBar";

// BrowserView imports react-vnc which accesses `window` at module load —
// skip SSR for the entire component so refs and sizing work correctly.
const BrowserView = dynamic(
  () => import("@/components/BrowserView").then((m) => m.BrowserView),
  { ssr: false }
);
import { useAgentWebSocket } from "@/lib/ws";
import { apiRequest, isAuthenticated } from "@/lib/api";
import { XCircle, Loader2 } from "lucide-react";
import Link from "next/link";

interface TaskDetails {
  id: string;
  prompt: string;
  status: "pending" | "running" | "idle" | "completed" | "failed";
  vnc_url: string | null;
  created_at: string;
}

export default function ChatConversationPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.taskId as string;

  const [task, setTask] = useState<TaskDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showBrowser, setShowBrowser] = useState(true);

  const { messages, sendMessage, isConnected } = useAgentWebSocket(taskId);

  const fetchTask = useCallback(async () => {
    try {
      const data = await apiRequest(`/api/tasks/${taskId}`);
      setTask(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load task details."
      );
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }
    fetchTask();

    const interval = setInterval(fetchTask, 5000);
    return () => clearInterval(interval);
  }, [router, fetchTask]);

  const toggleSidebar = () => {
    window.dispatchEvent(new Event("toggle-sidebar"));
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-gray-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <XCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">Failed to load task</h2>
          <p className="text-gray-400 text-sm mb-4">{error}</p>
          <Link
            href="/chat"
            className="text-blue-400 hover:text-blue-300 text-sm font-medium"
          >
            Back to Chat
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
      <ChatTopBar
        prompt={task?.prompt || ""}
        status={task?.status || "pending"}
        isConnected={isConnected}
        showBrowser={showBrowser}
        onToggleBrowser={() => setShowBrowser(!showBrowser)}
        onToggleSidebar={toggleSidebar}
      />

      <div className="flex-1 overflow-hidden">
        {showBrowser ? (
          <PanelGroup
            orientation="horizontal"
            className="h-full"
            resizeTargetMinimumSize={{ coarse: 20, fine: 10 }}
          >
            <Panel
              defaultSize={40}
              minSize={20}
              className="h-full min-h-0 overflow-hidden"
            >
              <ChatPanel
                messages={messages}
                onSendMessage={sendMessage}
                isConnected={isConnected}
              />
            </Panel>

            <PanelResizeHandle className="w-1.5 hover:w-2 bg-[#1e1e2e] hover:bg-blue-500/20 active:bg-blue-500/30 transition-all cursor-col-resize flex items-center justify-center group">
              <div className="w-0.5 h-8 rounded-full bg-gray-700 group-hover:bg-blue-400 group-active:bg-blue-500 transition-colors" />
            </PanelResizeHandle>

            <Panel
              defaultSize={60}
              minSize={20}
              className="h-full min-h-0 overflow-hidden p-1"
            >
              <BrowserView
                vncUrl={task?.vnc_url || null}
                taskStatus={task?.status}
              />
            </Panel>
          </PanelGroup>
        ) : (
          <ChatPanel
            messages={messages}
            onSendMessage={sendMessage}
            isConnected={isConnected}
          />
        )}
      </div>
    </>
  );
}
