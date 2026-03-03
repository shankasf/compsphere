"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, usePathname, useParams } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { apiRequest, isAuthenticated } from "@/lib/api";

interface Task {
  id: string;
  prompt: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
}

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const activeTaskId = params?.taskId as string | undefined;

  const fetchTasks = useCallback(async () => {
    try {
      const data = await apiRequest("/api/tasks");
      setTasks(Array.isArray(data) ? data : data.tasks || []);
    } catch {
      // apiRequest redirects on 401
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }
    fetchTasks();
  }, [router, fetchTasks]);

  // Re-fetch tasks when navigating between routes
  useEffect(() => {
    if (isAuthenticated()) {
      fetchTasks();
    }
  }, [pathname, fetchTasks]);

  const handleDeleteTask = useCallback(async (taskId: string) => {
    try {
      await apiRequest(`/api/tasks/${taskId}`, { method: "DELETE" });
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
      if (activeTaskId === taskId) {
        router.push("/chat");
      }
    } catch {
      // ignore — error already logged by apiRequest
    }
  }, [activeTaskId, router]);

  // Listen for sidebar toggle events from child pages
  useEffect(() => {
    const handler = () => setSidebarOpen((prev) => !prev);
    window.addEventListener("toggle-sidebar", handler);
    return () => window.removeEventListener("toggle-sidebar", handler);
  }, []);

  return (
    <div className="h-screen flex bg-gray-950">
      <Sidebar
        tasks={tasks}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        activeTaskId={activeTaskId}
        onDeleteTask={handleDeleteTask}
      />
      <div className="flex-1 min-w-0 h-full flex flex-col">
        {children}
      </div>
    </div>
  );
}
