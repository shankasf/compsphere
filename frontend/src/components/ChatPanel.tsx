"use client";

import { useRef, useEffect, useState, FormEvent } from "react";
import { AgentMessage } from "@/components/AgentMessage";
import type { AgentMessage as AgentMessageType } from "@/lib/ws";
import { Send, ArrowDown } from "lucide-react";

interface ChatPanelProps {
  messages: AgentMessageType[];
  onSendMessage: (content: string) => void;
  isConnected: boolean;
}

export function ChatPanel({
  messages,
  onSendMessage,
  isConnected,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Show/hide scroll-to-bottom button
  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    setShowScrollBtn(!atBottom);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [input]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || !isConnected) return;

    onSendMessage(trimmed);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#0a0a0f]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#1e1e2e] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <h2 className="text-sm font-semibold text-gray-200 tracking-tight">Agent Chat</h2>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-gray-800/50">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                isConnected ? "bg-emerald-400 pulse-dot" : "bg-gray-600"
              }`}
            />
            <span className={`text-[10px] font-medium ${isConnected ? "text-emerald-400/80" : "text-gray-500"}`}>
              {isConnected ? "Live" : "Offline"}
            </span>
          </div>
        </div>
      </div>

      {/* Messages area */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto py-4 relative"
      >
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-center px-6 fade-in">
            <div>
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 flex items-center justify-center mx-auto mb-4">
                <div className="flex gap-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-purple-400/60 typing-dot" />
                  <div className="w-1.5 h-1.5 rounded-full bg-purple-400/60 typing-dot" />
                  <div className="w-1.5 h-1.5 rounded-full bg-purple-400/60 typing-dot" />
                </div>
              </div>
              <p className="text-sm text-gray-400 font-medium">
                Waiting for agent...
              </p>
              <p className="text-xs text-gray-600 mt-1.5">
                Messages will appear here once the agent starts
              </p>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <AgentMessage key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} className="h-2" />
          </>
        )}

        {/* Scroll to bottom button */}
        {showScrollBtn && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-4 left-1/2 -translate-x-1/2 p-2 rounded-full bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:bg-gray-700 transition-all shadow-lg"
          >
            <ArrowDown className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Input area */}
      <div className="px-3 py-3 border-t border-[#1e1e2e] shrink-0 bg-[#0c0c14]">
        <form
          onSubmit={handleSubmit}
          className="flex items-end gap-2 rounded-xl border border-[#1e1e2e] bg-[#12121a] px-3 py-2 input-glow focus-within:border-blue-500/40 transition-all"
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isConnected
                ? "Message the agent..."
                : "Connecting..."
            }
            disabled={!isConnected}
            rows={1}
            className="flex-1 bg-transparent text-[13px] text-white placeholder-gray-500 resize-none focus:outline-none disabled:opacity-40 disabled:cursor-not-allowed leading-relaxed py-1 max-h-[120px]"
          />
          <button
            type="submit"
            disabled={!isConnected || !input.trim()}
            className="p-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed text-white transition-all shrink-0 mb-0.5"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
        <p className="text-[10px] text-gray-600 mt-1.5 text-center">
          Enter to send &middot; Shift+Enter for newline
        </p>
      </div>
    </div>
  );
}
