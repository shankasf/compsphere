"use client";

import { useState, FormEvent, useRef, useEffect } from "react";
import { apiRequest } from "@/lib/api";
import {
  X,
  Loader2,
  Search,
  FileText,
  Globe,
  Send,
} from "lucide-react";

interface TaskInputProps {
  onClose: () => void;
  onTaskCreated: (taskId: string) => void;
}

const TEMPLATES = [
  {
    icon: <Search className="w-4 h-4" />,
    label: "Research a topic",
    prompt: "Research the latest developments in ",
  },
  {
    icon: <FileText className="w-4 h-4" />,
    label: "Fill out a form",
    prompt: "Go to the website and fill out the form with the following information: ",
  },
  {
    icon: <Globe className="w-4 h-4" />,
    label: "Browse a website",
    prompt: "Navigate to and extract the following information: ",
  },
];

export function TaskInput({ onClose, onTaskCreated }: TaskInputProps) {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setError("");
    setLoading(true);

    try {
      const data = await apiRequest("/api/tasks", {
        method: "POST",
        body: JSON.stringify({ name: prompt.trim().slice(0, 80), prompt: prompt.trim() }),
      });
      onTaskCreated(data.id || data.task_id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create task."
      );
      setLoading(false);
    }
  };

  const handleTemplateClick = (templatePrompt: string) => {
    setPrompt(templatePrompt);
    textareaRef.current?.focus();
    // Move cursor to end
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.selectionStart = templatePrompt.length;
        textareaRef.current.selectionEnd = templatePrompt.length;
      }
    }, 0);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-2xl rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl shadow-black/50">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="text-lg font-semibold">New Task</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6">
          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400 mb-4">
              {error}
            </div>
          )}

          {/* Quick-start templates */}
          <div className="flex flex-wrap gap-2 mb-4">
            {TEMPLATES.map((template) => (
              <button
                key={template.label}
                type="button"
                onClick={() => handleTemplateClick(template.prompt)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-700 bg-gray-800/50 text-sm text-gray-300 hover:text-white hover:border-gray-600 hover:bg-gray-800 transition-all"
              >
                {template.icon}
                {template.label}
              </button>
            ))}
          </div>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe what you want the agent to do..."
            rows={5}
            className="w-full px-4 py-3 rounded-xl bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:border-blue-500 transition-colors resize-none text-sm leading-relaxed"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                handleSubmit(e);
              }
            }}
          />

          <div className="flex items-center justify-between mt-4">
            <p className="text-xs text-gray-500">
              Ctrl+Enter to submit
            </p>
            <button
              type="submit"
              disabled={loading || !prompt.trim()}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/30 disabled:cursor-not-allowed text-white font-medium text-sm transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  Start Task
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
