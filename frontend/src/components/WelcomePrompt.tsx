"use client";

import { useState, useRef, useEffect, FormEvent } from "react";
import { Send, Loader2, Search, FileText, Globe, Sparkles } from "lucide-react";

interface WelcomePromptProps {
  onSubmit: (prompt: string) => void;
  isLoading: boolean;
}

const TEMPLATES = [
  {
    icon: <Search className="w-4 h-4" />,
    label: "Research a topic",
    prompt: "Research the latest developments in ",
    description: "Search and summarize information",
  },
  {
    icon: <FileText className="w-4 h-4" />,
    label: "Fill out a form",
    prompt:
      "Go to the website and fill out the form with the following information: ",
    description: "Auto-fill web forms",
  },
  {
    icon: <Globe className="w-4 h-4" />,
    label: "Browse a website",
    prompt: "Navigate to and extract the following information: ",
    description: "Navigate and extract data",
  },
];

export function WelcomePrompt({ onSubmit, isLoading }: WelcomePromptProps) {
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [prompt]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isLoading) return;
    setError("");
    onSubmit(prompt.trim());
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleTemplateClick = (templatePrompt: string) => {
    setPrompt(templatePrompt);
    textareaRef.current?.focus();
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.selectionStart = templatePrompt.length;
        textareaRef.current.selectionEnd = templatePrompt.length;
      }
    }, 0);
  };

  return (
    <div className="flex flex-col items-center w-full max-w-2xl mx-auto px-4 fade-in">
      {/* Icon + Heading */}
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/15 to-purple-600/15 border border-blue-500/20 flex items-center justify-center mb-5">
        <Sparkles className="w-7 h-7 text-blue-400" />
      </div>
      <h1 className="text-2xl font-semibold text-white mb-2 tracking-tight">
        What can I help you with?
      </h1>
      <p className="text-sm text-gray-500 mb-8">
        Describe a task and the AI agent will control a browser to complete it.
      </p>

      {/* Input area */}
      <form onSubmit={handleSubmit} className="w-full">
        {error && (
          <div className="rounded-xl bg-red-500/8 border border-red-500/15 px-4 py-3 text-[13px] text-red-400 mb-4">
            {error}
          </div>
        )}

        <div className="relative rounded-2xl border border-[#1e1e2e] bg-[#12121a] focus-within:border-blue-500/40 input-glow transition-all">
          <textarea
            ref={textareaRef}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe what you want the agent to do..."
            rows={1}
            className="w-full px-4 pt-4 pb-14 bg-transparent text-white placeholder-gray-500 resize-none text-[13px] leading-relaxed focus:outline-none"
          />
          <div className="absolute bottom-3 right-3">
            <button
              type="submit"
              disabled={isLoading || !prompt.trim()}
              className="p-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed text-white transition-all shadow-lg shadow-blue-600/20 disabled:shadow-none"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        <p className="text-[10px] text-gray-600 mt-2 text-center">
          Enter to submit &middot; Shift+Enter for newline
        </p>
      </form>

      {/* Template chips */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-8 w-full">
        {TEMPLATES.map((template) => (
          <button
            key={template.label}
            type="button"
            onClick={() => handleTemplateClick(template.prompt)}
            className="flex flex-col items-start gap-1.5 px-4 py-3 rounded-xl border border-[#1e1e2e] bg-[#12121a] text-left hover:border-[#2a2a3e] hover:bg-[#1a1a28] transition-all group hover-lift"
          >
            <div className="flex items-center gap-2 text-gray-400 group-hover:text-blue-400 transition-colors">
              {template.icon}
              <span className="text-[13px] font-medium">{template.label}</span>
            </div>
            <span className="text-[11px] text-gray-600">{template.description}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
