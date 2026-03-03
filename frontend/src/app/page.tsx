"use client";

import Link from "next/link";
import { Globe, Monitor, Radio, HardDrive, ArrowRight, Sparkles } from "lucide-react";

export default function HomePage() {
  return (
    <div className="relative">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        {/* Background gradient effects */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-[-20%] left-[10%] w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[120px]" />
          <div className="absolute top-[10%] right-[5%] w-[400px] h-[400px] bg-purple-600/10 rounded-full blur-[120px]" />
          <div className="absolute bottom-[-10%] left-[40%] w-[300px] h-[300px] bg-pink-600/5 rounded-full blur-[100px]" />
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-20 sm:pt-32 sm:pb-28">
          <div className="text-center max-w-4xl mx-auto">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-gray-700/50 bg-gray-800/50 text-sm text-gray-300 mb-8">
              <Sparkles className="w-3.5 h-3.5 text-blue-400" />
              <span>AI-Powered Browser Automation</span>
            </div>

            {/* Title */}
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.1] mb-6">
              Your AI Agent,{" "}
              <span className="gradient-text">Ready to Work</span>
            </h1>

            {/* Subtitle */}
            <p className="text-lg sm:text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
              CompSphere runs a real browser to complete tasks for you. Watch it
              work in real-time as it navigates, clicks, and types -- just like
              you would.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/auth/register"
                className="group flex items-center gap-2 px-8 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-base transition-all hover:shadow-lg hover:shadow-blue-600/25"
              >
                Get Started
                <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
              </Link>
              <Link
                href="/auth/login"
                className="flex items-center gap-2 px-8 py-3.5 rounded-xl border border-gray-700 hover:border-gray-600 text-gray-300 hover:text-white font-medium text-base transition-all hover:bg-gray-800/50"
              >
                Sign In
              </Link>
            </div>
          </div>

          {/* Browser preview mock */}
          <div className="mt-20 max-w-5xl mx-auto">
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 overflow-hidden shadow-2xl shadow-black/50">
              {/* Browser chrome */}
              <div className="flex items-center gap-2 px-4 py-3 bg-gray-800/80 border-b border-gray-700/50">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500/80" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                  <div className="w-3 h-3 rounded-full bg-green-500/80" />
                </div>
                <div className="flex-1 mx-4">
                  <div className="bg-gray-700/50 rounded-lg px-4 py-1.5 text-sm text-gray-400 max-w-md mx-auto">
                    agent.compsphere.ai/task/...
                  </div>
                </div>
              </div>
              {/* Content area */}
              <div className="flex h-[360px]">
                {/* Chat side */}
                <div className="w-2/5 border-r border-gray-700/50 p-4 flex flex-col gap-3">
                  <div className="rounded-lg bg-gray-800/50 p-3 text-sm text-gray-300">
                    <div className="text-xs text-blue-400 font-medium mb-1">You</div>
                    Find the top 3 AI startups in healthcare and summarize them
                  </div>
                  <div className="rounded-lg bg-gray-800/50 p-3 text-sm text-gray-300">
                    <div className="text-xs text-purple-400 font-medium mb-1">Agent</div>
                    I will search for healthcare AI startups. Let me open a browser and navigate to the search results...
                  </div>
                  <div className="rounded-lg bg-gray-700/30 p-3 text-sm text-gray-500">
                    <div className="text-xs text-gray-500 font-medium mb-1">Tool: browser.navigate</div>
                    <code className="text-xs">{"{ url: \"google.com/search?q=...\" }"}</code>
                  </div>
                  <div className="rounded-lg bg-gray-800/50 p-3 text-sm text-gray-300">
                    <div className="text-xs text-purple-400 font-medium mb-1">Agent</div>
                    I found several results. Let me click on the first article...
                  </div>
                </div>
                {/* Browser side */}
                <div className="flex-1 bg-gray-900 flex items-center justify-center">
                  <div className="text-center">
                    <Monitor className="w-16 h-16 text-gray-700 mx-auto mb-3" />
                    <p className="text-gray-600 text-sm">Live browser view</p>
                    <p className="text-gray-700 text-xs mt-1">Streaming in real-time</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="relative py-24 border-t border-gray-800/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mb-4">
              How it works
            </h2>
            <p className="text-gray-400 text-lg max-w-2xl mx-auto">
              CompSphere gives your AI agent a full browser environment to
              accomplish any web-based task.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <FeatureCard
              icon={<Globe className="w-6 h-6" />}
              title="Real Browser"
              description="A full Chromium browser runs in a secure sandbox. The AI agent can navigate any website, fill forms, click buttons, and extract data."
              gradient="from-blue-500 to-cyan-500"
            />
            <FeatureCard
              icon={<Radio className="w-6 h-6" />}
              title="Live Streaming"
              description="Watch the browser in real-time through VNC streaming. See every action your agent takes as it happens, with full transparency."
              gradient="from-purple-500 to-pink-500"
            />
            <FeatureCard
              icon={<HardDrive className="w-6 h-6" />}
              title="Persistent Sessions"
              description="Sessions persist across tasks. Your agent remembers context, keeps cookies, and maintains state for complex multi-step workflows."
              gradient="from-orange-500 to-red-500"
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800/50 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Globe className="w-4 h-4" />
            <span>CompSphere</span>
          </div>
          <p className="text-sm text-gray-600">
            Built with AI, for humans.
          </p>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
  gradient,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  gradient: string;
}) {
  return (
    <div className="group relative rounded-xl border border-gray-800 bg-gray-900/50 p-6 hover:border-gray-700 transition-all hover:bg-gray-900/80">
      <div
        className={`w-12 h-12 rounded-lg bg-gradient-to-br ${gradient} flex items-center justify-center text-white mb-4 group-hover:shadow-lg transition-shadow`}
      >
        {icon}
      </div>
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <p className="text-gray-400 text-sm leading-relaxed">{description}</p>
    </div>
  );
}
