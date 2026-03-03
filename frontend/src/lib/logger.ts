/**
 * Client-side logging utility for CompSphere.
 *
 * - Structured log levels (debug, info, warn, error)
 * - Sends errors/warnings to the backend for centralized analysis
 * - Captures unhandled errors and promise rejections
 * - Includes page URL and component context in every log
 */

type LogLevel = "debug" | "info" | "warn" | "error";

const LOG_ENDPOINT = `${process.env.NEXT_PUBLIC_API_URL || ""}/api/client-logs`;

const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

// Only send warn+ to the server to avoid flooding
const REMOTE_MIN_LEVEL: LogLevel = "warn";
// Console min level (show everything in dev)
const CONSOLE_MIN_LEVEL: LogLevel =
  process.env.NODE_ENV === "production" ? "info" : "debug";

interface LogContext {
  component?: string;
  taskId?: string;
  sessionId?: string;
  [key: string]: unknown;
}

function shouldLog(level: LogLevel, minLevel: LogLevel): boolean {
  return LEVEL_PRIORITY[level] >= LEVEL_PRIORITY[minLevel];
}

function consoleLog(level: LogLevel, message: string, ctx?: LogContext): void {
  if (!shouldLog(level, CONSOLE_MIN_LEVEL)) return;

  const prefix = `[CompSphere:${level.toUpperCase()}]`;
  const args: unknown[] = [prefix, message];
  if (ctx) args.push(ctx);

  switch (level) {
    case "error":
      console.error(...args);
      break;
    case "warn":
      console.warn(...args);
      break;
    case "info":
      console.info(...args);
      break;
    default:
      console.debug(...args);
  }
}

function sendToServer(
  level: LogLevel,
  message: string,
  stack?: string,
  ctx?: LogContext
): void {
  if (!shouldLog(level, REMOTE_MIN_LEVEL)) return;
  if (typeof window === "undefined") return;

  const payload = {
    level,
    message,
    stack: stack || undefined,
    url: window.location.href,
    component: ctx?.component,
    user_agent: navigator.userAgent,
    extra: ctx,
  };

  // Use sendBeacon for reliability (works even during page unload)
  // Fall back to fetch if sendBeacon is unavailable
  const body = JSON.stringify(payload);
  if (navigator.sendBeacon) {
    navigator.sendBeacon(LOG_ENDPOINT, new Blob([body], { type: "application/json" }));
  } else {
    fetch(LOG_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {
      // Silently fail - don't cause cascading errors from logging
    });
  }
}

export const logger = {
  debug(message: string, ctx?: LogContext): void {
    consoleLog("debug", message, ctx);
  },

  info(message: string, ctx?: LogContext): void {
    consoleLog("info", message, ctx);
  },

  warn(message: string, ctx?: LogContext): void {
    consoleLog("warn", message, ctx);
    sendToServer("warn", message, undefined, ctx);
  },

  error(message: string, error?: unknown, ctx?: LogContext): void {
    const stack =
      error instanceof Error ? error.stack : error ? String(error) : undefined;
    const msg = error instanceof Error ? `${message}: ${error.message}` : message;

    consoleLog("error", msg, ctx);
    sendToServer("error", msg, stack, ctx);
  },
};

/**
 * Install global error handlers. Call once in your root layout/app.
 */
export function installGlobalErrorHandlers(): void {
  if (typeof window === "undefined") return;

  window.addEventListener("error", (event) => {
    logger.error("Uncaught error", event.error, {
      component: "global",
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    } as LogContext);
  });

  window.addEventListener("unhandledrejection", (event) => {
    logger.error("Unhandled promise rejection", event.reason, {
      component: "global",
    });
  });
}
