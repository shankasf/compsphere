"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import {
  Monitor,
  Loader2,
  MousePointer2,
  MousePointerClick,
  Maximize2,
} from "lucide-react";
import { VncScreen } from "react-vnc";
import type { VncScreenHandle } from "react-vnc";

interface BrowserViewProps {
  vncUrl: string | null;
  taskStatus?: string;
}

export function BrowserView({ vncUrl, taskStatus }: BrowserViewProps) {
  const [controlEnabled, setControlEnabled] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    "disconnected" | "connecting" | "connected" | "error"
  >("disconnected");

  const vncRef = useRef<VncScreenHandle>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Toggle viewOnly directly on the RFB object (react-vnc prop alone is unreliable)
  const toggleControl = useCallback(() => {
    const next = !controlEnabled;
    setControlEnabled(next);
    if (vncRef.current?.rfb) {
      vncRef.current.rfb.viewOnly = !next;
    }
  }, [controlEnabled]);

  // ResizeObserver: re-apply scaleViewport when panel resizes to prevent blank canvas
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      if (vncRef.current?.rfb) {
        // @ts-expect-error scaleViewport exists on noVNC RFB
        vncRef.current.rfb.scaleViewport = true;
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Sync fullscreen state with browser API
  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  const handleFullscreen = () => {
    const container = document.getElementById("browser-container");
    if (!container) return;
    if (!isFullscreen) {
      container.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  };

  const onConnect = useCallback(() => {
    setConnectionStatus("connected");
    // Re-apply settings after connection establishes
    if (vncRef.current?.rfb) {
      // @ts-expect-error scaleViewport exists on noVNC RFB
      vncRef.current.rfb.scaleViewport = true;
      vncRef.current.rfb.viewOnly = !controlEnabled;
    }
  }, [controlEnabled]);

  const onDisconnect = useCallback(() => {
    setConnectionStatus("disconnected");
  }, []);

  const onSecurityFailure = useCallback(() => {
    setConnectionStatus("error");
  }, []);

  // Build full wss:// URL from the relative VNC path
  const getWsUrl = (): string => {
    if (!vncUrl) return "";
    if (typeof window === "undefined") return "";
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${vncUrl}`;
  };

  if (!vncUrl) {
    return (
      <div className="flex flex-col h-full bg-gray-900 rounded-lg">
        <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Monitor className="w-4 h-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-gray-200">
              Browser View
            </h2>
          </div>
        </div>

        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="relative w-20 h-20 mx-auto mb-4">
              <div className="absolute inset-0 rounded-2xl bg-gray-800 flex items-center justify-center">
                <Monitor className="w-8 h-8 text-gray-600" />
              </div>
              {(taskStatus === "running" || taskStatus === "pending") && (
                <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-gray-900 flex items-center justify-center">
                  <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                </div>
              )}
            </div>
            <p className="text-sm text-gray-400 font-medium">
              {taskStatus === "running"
                ? "Starting browser..."
                : taskStatus === "pending"
                ? "Initializing..."
                : "Waiting for browser..."}
            </p>
            <p className="text-xs text-gray-600 mt-1">
              The live browser view will appear here
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      id="browser-container"
      className="flex flex-col h-full bg-gray-900 rounded-lg"
    >
      {/* Toolbar */}
      <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Monitor
            className={`w-4 h-4 ${
              connectionStatus === "connected"
                ? "text-green-500"
                : connectionStatus === "connecting"
                ? "text-yellow-500"
                : "text-red-500"
            }`}
          />
          <h2 className="text-sm font-semibold text-gray-200">
            Browser View
          </h2>
          {connectionStatus === "connected" && (
            <div className="w-2 h-2 rounded-full bg-green-500 pulse-dot" />
          )}
          {connectionStatus === "connecting" && (
            <Loader2 className="w-3 h-3 text-yellow-500 animate-spin" />
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={toggleControl}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              controlEnabled
                ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                : "text-gray-400 hover:text-gray-300 hover:bg-gray-800"
            }`}
            title={
              controlEnabled
                ? "Release control"
                : "Take control of the browser"
            }
          >
            {controlEnabled ? (
              <MousePointerClick className="w-3.5 h-3.5" />
            ) : (
              <MousePointer2 className="w-3.5 h-3.5" />
            )}
            {controlEnabled ? "Controlling" : "Take Control"}
          </button>

          <button
            onClick={handleFullscreen}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-300 hover:bg-gray-800 transition-colors"
            title="Toggle fullscreen"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* VNC Screen */}
      <div ref={containerRef} className="flex-1 min-h-0 overflow-hidden">
        <VncScreen
          ref={vncRef}
          url={getWsUrl()}
          scaleViewport
          viewOnly={!controlEnabled}
          focusOnClick
          style={{ width: "100%", height: "100%" }}
          rfbOptions={{ wsProtocols: ["binary"] }}
          autoConnect
          retryDuration={3000}
          onConnect={onConnect}
          onDisconnect={onDisconnect}
          onSecurityFailure={onSecurityFailure}
          loadingUI={
            <div className="flex items-center justify-center h-full w-full">
              <div className="text-center">
                <Loader2 className="w-8 h-8 text-blue-400 animate-spin mx-auto mb-2" />
                <p className="text-sm text-gray-400">
                  Connecting to browser...
                </p>
              </div>
            </div>
          }
          background="#111827"
        />
      </div>
    </div>
  );
}
