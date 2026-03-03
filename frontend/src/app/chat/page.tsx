"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiRequest } from "@/lib/api";
import { WelcomePrompt } from "@/components/WelcomePrompt";

export default function NewChatPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (prompt: string) => {
    setIsLoading(true);
    try {
      const data = await apiRequest("/api/tasks", {
        method: "POST",
        body: JSON.stringify({
          name: prompt.slice(0, 80),
          prompt,
        }),
      });
      const taskId = data.id || data.task_id;
      router.push(`/chat/${taskId}`);
    } catch {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex items-center justify-center">
      <WelcomePrompt onSubmit={handleSubmit} isLoading={isLoading} />
    </div>
  );
}
