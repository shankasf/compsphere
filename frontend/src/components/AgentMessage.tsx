"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Bot,
  User,
  Wrench,
  CheckCircle2,
  AlertCircle,
  Info,
  Copy,
  Check,
} from "lucide-react";
import type { AgentMessage as AgentMessageType } from "@/lib/ws";

interface AgentMessageProps {
  message: AgentMessageType;
}

export function AgentMessage({ message }: AgentMessageProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderContent = () => {
    switch (message.type) {
      case "user":
        return (
          <div className="flex gap-3 message-enter justify-end">
            <div className="flex-1 min-w-0 flex flex-col items-end">
              <div className="flex items-baseline gap-2 mb-1.5">
                <span className="text-[11px] text-gray-500">
                  {formatTime(message.timestamp)}
                </span>
                <span className="text-[11px] font-medium text-blue-400/80">You</span>
              </div>
              <div className="max-w-[85%] px-4 py-2.5 rounded-2xl rounded-tr-md bg-blue-600 text-white shadow-sm shadow-blue-600/10">
                <p className="text-[13px] leading-relaxed whitespace-pre-wrap break-words">
                  {message.content}
                </p>
              </div>
            </div>
            <div className="w-8 h-8 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center shrink-0 mt-5">
              <User className="w-3.5 h-3.5 text-blue-400" />
            </div>
          </div>
        );

      case "assistant":
        return (
          <div className="flex gap-3 message-enter">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 flex items-center justify-center shrink-0 mt-5">
              <Bot className="w-3.5 h-3.5 text-purple-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2 mb-1.5">
                <span className="text-[11px] font-medium text-purple-400/80">
                  Agent
                </span>
                <span className="text-[11px] text-gray-500">
                  {formatTime(message.timestamp)}
                </span>
              </div>
              <div className="max-w-[90%] group relative">
                <div className="px-4 py-2.5 rounded-2xl rounded-tl-md bg-[#1a1a28] border border-[#252535] text-gray-200">
                  <p className="text-[13px] leading-relaxed whitespace-pre-wrap break-words">
                    {message.content}
                  </p>
                </div>
                <button
                  onClick={() => handleCopy(message.content)}
                  className="absolute -bottom-3 right-2 opacity-0 group-hover:opacity-100 p-1 rounded-md bg-gray-800 border border-gray-700 text-gray-400 hover:text-white transition-all"
                  title="Copy message"
                >
                  {copied ? (
                    <Check className="w-3 h-3 text-green-400" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </button>
              </div>
            </div>
          </div>
        );

      case "tool_use":
        return (
          <div className="flex gap-3 message-enter pl-11">
            <div className="flex-1 min-w-0">
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#14141e] border border-[#1e1e2e] hover:border-[#2a2a3e] text-gray-400 hover:text-gray-300 transition-all text-xs"
              >
                <Wrench className="w-3 h-3 text-gray-500" />
                <span className="font-mono font-medium">
                  {message.tool_name || "tool"}
                </span>
                {isExpanded ? (
                  <ChevronDown className="w-3 h-3 text-gray-600" />
                ) : (
                  <ChevronRight className="w-3 h-3 text-gray-600" />
                )}
                <span className="text-gray-600 font-normal ml-auto">
                  {formatTime(message.timestamp)}
                </span>
              </button>
              {isExpanded && message.tool_input && (
                <div className="mt-1.5 ml-1 p-3 rounded-lg bg-[#0e0e16] border border-[#1e1e2e] overflow-x-auto">
                  <pre className="text-[11px] text-gray-500 font-mono whitespace-pre-wrap break-words leading-relaxed">
                    {JSON.stringify(message.tool_input, null, 2)}
                  </pre>
                </div>
              )}
              {!isExpanded && message.content && (
                <p className="text-[11px] text-gray-600 mt-1 ml-1 truncate max-w-md">
                  {message.content}
                </p>
              )}
            </div>
          </div>
        );

      case "tool_result":
        return (
          <div className="flex gap-3 message-enter pl-11">
            <div className="flex-1 min-w-0">
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-500/5 border border-green-500/10 hover:border-green-500/20 text-green-400/70 hover:text-green-400 transition-all text-xs"
              >
                <CheckCircle2 className="w-3 h-3" />
                <span className="font-medium">Result</span>
                {isExpanded ? (
                  <ChevronDown className="w-3 h-3 text-green-600/50" />
                ) : (
                  <ChevronRight className="w-3 h-3 text-green-600/50" />
                )}
                <span className="text-gray-600 font-normal ml-auto">
                  {formatTime(message.timestamp)}
                </span>
              </button>
              {isExpanded && (
                <div className="mt-1.5 ml-1 p-3 rounded-lg bg-green-500/5 border border-green-500/10 overflow-x-auto">
                  <pre className="text-[11px] text-green-300/60 font-mono whitespace-pre-wrap break-words leading-relaxed">
                    {message.content}
                  </pre>
                </div>
              )}
            </div>
          </div>
        );

      case "status":
        return (
          <div className="flex items-center justify-center gap-2 py-2 message-enter">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-yellow-500/5 border border-yellow-500/10">
              <Info className="w-3 h-3 text-yellow-500/70" />
              <span className="text-[11px] text-yellow-500/70">
                {message.content}
              </span>
              <span className="text-[11px] text-gray-600">
                {formatTime(message.timestamp)}
              </span>
            </div>
          </div>
        );

      case "error":
        return (
          <div className="flex gap-3 message-enter">
            <div className="w-8 h-8 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center shrink-0 mt-5">
              <AlertCircle className="w-3.5 h-3.5 text-red-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2 mb-1.5">
                <span className="text-[11px] font-medium text-red-400/80">Error</span>
                <span className="text-[11px] text-gray-600">
                  {formatTime(message.timestamp)}
                </span>
              </div>
              <div className="max-w-[90%] px-4 py-2.5 rounded-2xl rounded-tl-md bg-red-500/5 border border-red-500/10">
                <p className="text-[13px] text-red-300/80 whitespace-pre-wrap break-words leading-relaxed">
                  {message.content}
                </p>
              </div>
            </div>
          </div>
        );

      default:
        return (
          <div className="flex gap-3 message-enter">
            <div className="w-8 h-8 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center shrink-0 mt-0.5">
              <Bot className="w-3.5 h-3.5 text-gray-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] text-gray-300 whitespace-pre-wrap break-words leading-relaxed">
                {message.content}
              </p>
            </div>
          </div>
        );
    }
  };

  return <div className="px-4 py-1.5">{renderContent()}</div>;
}
