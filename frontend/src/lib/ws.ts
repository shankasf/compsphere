"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { logger } from "./logger";

export interface AgentMessage {
  id: string;
  type: "assistant" | "user" | "tool_use" | "tool_result" | "status" | "error";
  content: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  timestamp: string;
}

interface UseAgentWebSocketReturn {
  messages: AgentMessage[];
  sendMessage: (content: string) => void;
  isConnected: boolean;
}

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || '';

export function useAgentWebSocket(taskId: string): UseAgentWebSocketReturn {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 10;

  // Guard against StrictMode double-mount reconnection loops
  const mountedRef = useRef(false);

  // Content-based deduplication: key → timestamp
  const seenRef = useRef<Map<string, number>>(new Map());

  const getWsUrl = useCallback(() => {
    if (WS_BASE) {
      return `${WS_BASE}/ws/agent/${taskId}`;
    }
    if (typeof window === "undefined") return "";
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/ws/agent/${taskId}`;
  }, [taskId]);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const url = getWsUrl();
    if (!url) return;

    const token = localStorage.getItem("token");
    const wsUrl = token ? `${url}?token=${token}` : url;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        logger.info("WebSocket connected", { component: "ws", taskId });
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Skip result messages (defense in depth — backend also skips them)
          if (data.type === "result") return;

          // Content-based deduplication (2-second window)
          const dedupKey = `${data.type}:${data.content || ""}:${data.tool_name || ""}`;
          const now = Date.now();
          const lastSeen = seenRef.current.get(dedupKey);
          if (lastSeen && now - lastSeen < 2000) return;
          seenRef.current.set(dedupKey, now);

          // Prune old entries periodically
          if (seenRef.current.size > 200) {
            const cutoff = now - 5000;
            seenRef.current.forEach((ts, key) => {
              if (ts < cutoff) seenRef.current.delete(key);
            });
          }

          const message: AgentMessage = {
            id: data.id || `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            type: data.type || "assistant",
            content: data.content || "",
            tool_name: data.tool_name,
            tool_input: data.tool_input,
            timestamp: data.timestamp || new Date().toISOString(),
          };

          if (data.type === "error") {
            logger.warn(`Agent error: ${data.content}`, { component: "ws", taskId });
          }

          setMessages((prev) => [...prev, message]);
        } catch {
          logger.warn("Received non-JSON WebSocket message", { component: "ws", taskId });
          const message: AgentMessage = {
            id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            type: "assistant",
            content: event.data,
            timestamp: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, message]);
        }
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        wsRef.current = null;

        logger.info(`WebSocket closed (code=${event.code})`, { component: "ws", taskId });

        // Don't reconnect if component has unmounted (StrictMode cleanup)
        if (!mountedRef.current) return;

        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttemptsRef.current),
            30000
          );
          logger.debug(`WebSocket reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1})`, {
            component: "ws",
            taskId,
          });
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!mountedRef.current) return;
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
        } else {
          logger.error("WebSocket max reconnect attempts reached", undefined, {
            component: "ws",
            taskId,
          });
        }
      };

      ws.onerror = () => {
        logger.error("WebSocket error", undefined, { component: "ws", taskId });
      };
    } catch (error) {
      logger.error("WebSocket connection failed", error, { component: "ws", taskId });
      setIsConnected(false);
    }
  }, [getWsUrl, taskId]);

  // Use a ref to always call the latest `connect` without adding it as a
  // dependency.  This prevents React StrictMode double-mount from tearing
  // down a still-connecting WebSocket (the cause of the "closed before
  // connection is established" console error).
  const connectRef = useRef(connect);
  connectRef.current = connect;

  useEffect(() => {
    if (!taskId) return;
    mountedRef.current = true;
    connectRef.current();

    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        const ws = wsRef.current;
        wsRef.current = null;
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        } else if (ws.readyState === WebSocket.CONNECTING) {
          // Avoid "closed before connection established" warning in
          // React StrictMode — wait for it to open, then close.
          ws.onopen = () => ws.close();
          ws.onerror = () => {};
          ws.onmessage = () => {};
        }
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  const sendMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "user",
          content,
        })
      );
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: "user",
          content,
          timestamp: new Date().toISOString(),
        },
      ]);
    } else {
      logger.warn("Cannot send message: WebSocket not connected", { component: "ws", taskId });
    }
  }, [taskId]);

  return { messages, sendMessage, isConnected };
}
