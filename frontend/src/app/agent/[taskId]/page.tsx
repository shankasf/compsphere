"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function AgentRedirectPage() {
  const params = useParams();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/chat/${params.taskId}`);
  }, [params.taskId, router]);

  return null;
}
