"use client";

import { useEffect } from "react";
import { installGlobalErrorHandlers } from "@/lib/logger";

export function GlobalErrorHandler() {
  useEffect(() => {
    installGlobalErrorHandlers();
  }, []);

  return null;
}
