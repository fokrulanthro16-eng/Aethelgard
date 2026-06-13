"use client";

import Link from "next/link";
import { Shield, Zap, Database, Clock, Users, Heart, Lock } from "lucide-react";

const NODES = [
  {
    id: "frontend",
    icon: Users,
    title: "Next.js Frontend",
    subtitle: "React 19 · Tailwind CSS · shadcn/ui",
    description:
      "Browser-based dashboard: vault management, I AM OK check-in, nominee release portal, and AI guide reader. Zero plaintext data sent to any analytics service.",
    color: "blue",
  },
  {
    id: "api",
    icon: Zap,
    title: "FastAPI Backend",
    subtitle: "Python 3.11 · Pydantic v2 · Uvicorn",
    description:
      "20 REST routes. Pydantic validates every request and response. CORS-secured. EventBridge-ready for serverless deployment.",
    color: "violet",
  },
  {
    id: "encryption",
    icon: Lock,
    title: "AES-256-GCM Encryption Layer",
    subtitle: "HKDF-SHA256 · cryptography library · per-user keys",
    description:
      "Plaintext never touches the database. Each user gets a unique key derived via HKDF-SHA256 from a master secret. A fresh 12-byte random nonce per write prevents ciphertext reuse. GCM authentication tag detects tampering.",
    color: "purple",
  },
  {
    id: "db",
    icon: Database,
    title: "AWS DynamoDB",
    subtitle: "Single-table design · PAY_PER_REQUEST · serverless",
    description:
      "Three item types share one table: METADATA (user record), VAULT#<uuid> (encrypted entry), RELEASE#<token>/REQUEST (nominee token). No admin overhead; scales to millions of users.",
    color: "orange",
  },
  {
    id: "dms",
    icon: Clock,
    title: "Dead Man's Switch Engine",
    subtitle: "90-day countdown · ACTIVE → PENDING_RELEASE",
    description:
      "A daily scan (EventBridge → Lambda in production) detects users who have missed their check-in window and atomically advances them to PENDING_RELEASE. A check-in at any point resets the clock.",
    color: "red",
  },
  {
    id: "release",
    icon: Shield,
    title: "Nominee Release Portal",
    subtitle: "256-bit token · 72-hour expiry · one-time use",
    description:
      "A cryptographically secure URL-safe token is created for the nominee. The portal validates the token, marks it USED (conditional DynamoDB write), and transitions the vault to RELEASED — no replay possible.",
    color: "pink",
  },
  {
    id: "ai",
    icon: Heart,
    title: "Gemini AI Guide Generator",
    subtitle: "Gemini 1.5 Flash · 3-retry backoff · fallback always available",
    description:
      "Decrypts the vault, groups entries by type, and sends a structured prompt to Gemini. If the API is unavailable or unconfigured, a deterministic fallback guide is generated — the system always returns a result.",
    color: "green",
  },
] as const;

type Color = (typeof NODES)[number]["color"];

const COLORS: Record<Color, { border: string; bg: string; icon: string; dot: string; num: string }> = {
  blue:   { border: "border-blue-500/40",   bg: "bg-blue-500/10",   icon: "text-blue-400",   dot: "bg-blue-500",   num: "text-blue-400" },
  violet: { border: "border-violet-500/40", bg: "bg-violet-500/10", icon: "text-violet-400", dot: "bg-violet-500", num: "text-violet-400" },
  purple: { border: "border-purple-500/40", bg: "bg-purple-500/10", icon: "text-purple-400", dot: "bg-purple-500", num: "text-purple-400" },
  orange: { border: "border-orange-500/40", bg: "bg-orange-500/10", icon: "text-orange-400", dot: "bg-orange-500", num: "text-orange-400" },
  red:    { border: "border-red-500/40",    bg: "bg-red-500/10",    icon: "text-red-400",    dot: "bg-red-500",    num: "text-red-400" },
  pink:   { border: "border-pink-500/40",   bg: "bg-pink-500/10",   icon: "text-pink-400",   dot: "bg-pink-500",   num: "text-pink-400" },
  green:  { border: "border-green-500/40",  bg: "bg-green-500/10",  icon: "text-green-400",  dot: "bg-green-500",  num: "text-green-400" },
};

export default function ArchitecturePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-6">
      <div className="max-w-2xl mx-auto space-y-6">

        {/* Header */}
        <div className="text-center space-y-2 pt-6">
          <div className="flex justify-center">
            <div className="w-14 h-14 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
              <Shield className="w-7 h-7 text-blue-400" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-white">System Architecture</h1>
          <p className="text-slate-400 text-sm">
            End-to-end data flow — from browser vault to AI-generated family guide
          </p>
        </div>

        {/* Flow */}
        <div className="space-y-0">
          {NODES.map((node, idx) => {
            const c = COLORS[node.color];
            const Icon = node.icon;
            const isLast = idx === NODES.length - 1;
            return (
              <div key={node.id} className="flex flex-col items-center">
                <div className={`w-full border ${c.border} ${c.bg} rounded-xl p-4 flex items-start gap-4`}>
                  <div className={`w-10 h-10 rounded-lg border ${c.border} flex items-center justify-center shrink-0 mt-0.5`}>
                    <Icon className={`w-5 h-5 ${c.icon}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-white font-semibold text-sm">{node.title}</h3>
                      <span className={`w-1.5 h-1.5 rounded-full ${c.dot} shrink-0`} />
                    </div>
                    <p className={`font-mono text-xs ${c.icon} mt-0.5`}>{node.subtitle}</p>
                    <p className="text-slate-400 text-xs mt-1.5 leading-relaxed">{node.description}</p>
                  </div>
                  <span className={`font-mono text-xs ${c.num} opacity-50 shrink-0 pt-0.5`}>
                    {String(idx + 1).padStart(2, "0")}
                  </span>
                </div>
                {!isLast && (
                  <div className="flex flex-col items-center py-0.5">
                    <div className="w-px h-4 bg-white/10" />
                    <span className="text-slate-600 text-xs leading-none">↓</span>
                    <div className="w-px h-4 bg-white/10" />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Nav */}
        <div className="flex gap-4 justify-center pb-6 text-sm">
          <Link href="/" className="text-slate-400 hover:text-white transition-colors">
            ← Back to Vault
          </Link>
          <span className="text-slate-700">·</span>
          <Link href="/judge" className="text-slate-400 hover:text-white transition-colors">
            Judge Dashboard →
          </Link>
        </div>

      </div>
    </div>
  );
}
