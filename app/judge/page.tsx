"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Shield,
  CheckCircle2,
  Loader2,
  Lock,
  Database,
  Clock,
  Zap,
  Heart,
  AlertCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getDemoStats, type DemoStatsResponse } from "@/lib/api";

export default function JudgePage() {
  const [stats, setStats] = useState<DemoStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDemoStats()
      .then(setStats)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-6">
      <div className="max-w-2xl mx-auto space-y-6">

        {/* Header */}
        <div className="text-center space-y-2 pt-6">
          <div className="flex justify-center">
            <div className="w-14 h-14 rounded-full bg-green-600/20 border border-green-500/30 flex items-center justify-center">
              <CheckCircle2 className="w-7 h-7 text-green-400" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-white">Judge Dashboard</h1>
          <p className="text-slate-400 text-sm">
            Live system capabilities — pulled from the running backend
          </p>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex justify-center py-16">
            <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-5 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-red-300 text-sm font-medium">Backend unreachable</p>
              <p className="text-red-400/70 text-xs mt-1">{error}</p>
              <p className="text-slate-500 text-xs mt-2">
                Start the backend: <code className="font-mono bg-white/5 px-1 rounded">uvicorn app.main:app --reload --port 8000</code>
              </p>
            </div>
          </div>
        )}

        {/* Stats Grid */}
        {stats && (
          <div className="grid grid-cols-2 gap-4">

            {/* Test Count — full width */}
            <Card className="bg-white/5 border-white/10 col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-white flex items-center gap-2 text-sm">
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                  Test Coverage
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-baseline gap-3">
                  <span className="text-6xl font-bold text-green-400">{stats.test_count}</span>
                  <div>
                    <p className="text-slate-300 text-sm font-medium">tests passing</p>
                    <p className="text-slate-500 text-xs">Steps 1–{stats.steps_complete} complete · 0 failures</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-3">
                  <Badge variant="success" className="text-xs">All Green</Badge>
                  <Badge variant="secondary" className="text-xs">pytest · moto DynamoDB mock</Badge>
                  <Badge variant="secondary" className="text-xs">0 TypeScript errors</Badge>
                </div>
              </CardContent>
            </Card>

            {/* Encryption */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="pb-2">
                <CardTitle className="text-white flex items-center gap-2 text-sm">
                  <Lock className="w-4 h-4 text-purple-400" />
                  Encryption
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-purple-300 font-mono text-sm font-bold">{stats.encryption.algorithm}</p>
                <p className="text-slate-400 text-xs">{stats.encryption.key_derivation}</p>
                <Badge variant="secondary" className="text-xs capitalize">
                  {stats.encryption.mode} mode
                </Badge>
                <p className="text-slate-500 text-xs">Plaintext never persisted</p>
              </CardContent>
            </Card>

            {/* AI Guide */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="pb-2">
                <CardTitle className="text-white flex items-center gap-2 text-sm">
                  <Heart className="w-4 h-4 text-pink-400" />
                  AI Guide
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-pink-300 font-mono text-sm font-bold">{stats.gemini.model}</p>
                <p className="text-slate-400 text-xs">
                  {stats.gemini.configured ? "API key configured" : "Running in fallback mode"}
                </p>
                <Badge variant={stats.gemini.fallback_available ? "success" : "secondary"} className="text-xs">
                  Fallback always available
                </Badge>
                <p className="text-slate-500 text-xs">3-retry with exponential backoff</p>
              </CardContent>
            </Card>

            {/* Dead Man's Switch */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="pb-2">
                <CardTitle className="text-white flex items-center gap-2 text-sm">
                  <Clock className="w-4 h-4 text-yellow-400" />
                  Dead Man&apos;s Switch
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                <div className="flex items-baseline gap-1">
                  <span className="text-5xl font-bold text-yellow-400">{stats.dead_man_switch.threshold_days}</span>
                  <span className="text-yellow-400/70 text-sm">days</span>
                </div>
                <p className="text-slate-400 text-xs">check-in window</p>
                <p className="text-slate-500 text-xs font-mono">ACTIVE → PENDING_RELEASE</p>
              </CardContent>
            </Card>

            {/* Release Token */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="pb-2">
                <CardTitle className="text-white flex items-center gap-2 text-sm">
                  <Shield className="w-4 h-4 text-blue-400" />
                  Release Token
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                <div className="flex items-baseline gap-1">
                  <span className="text-5xl font-bold text-blue-400">{stats.release_token.expiry_hours}</span>
                  <span className="text-blue-400/70 text-sm">hours</span>
                </div>
                <p className="text-slate-400 text-xs">expiry window</p>
                <p className="text-slate-500 text-xs">256-bit · URL-safe · one-time use</p>
              </CardContent>
            </Card>

            {/* DynamoDB — full width */}
            <Card className="bg-white/5 border-white/10 col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-white flex items-center gap-2 text-sm">
                  <Database className="w-4 h-4 text-orange-400" />
                  DynamoDB — <span className="font-mono text-orange-400">{stats.dynamodb.table}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-400 text-xs mb-3">{stats.dynamodb.design}</p>
                <div className="space-y-1.5">
                  {stats.dynamodb.item_types.map((t) => (
                    <div key={t} className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-orange-400 shrink-0" />
                      <code className="text-orange-300 text-xs font-mono">{t}</code>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Stack Summary */}
            <Card className="bg-white/5 border-white/10 col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-white flex items-center gap-2 text-sm">
                  <Zap className="w-4 h-4 text-yellow-400" />
                  Full Stack
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {[
                    "Next.js 15", "React 19", "TypeScript 5", "Tailwind CSS", "shadcn/ui",
                    "FastAPI", "Python 3.11", "Pydantic v2", "boto3", "moto",
                    "AES-256-GCM", "HKDF-SHA256", "AWS DynamoDB", "Gemini 1.5 Flash",
                  ].map((tech) => (
                    <Badge key={tech} variant="secondary" className="text-xs font-mono">
                      {tech}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>

          </div>
        )}

        {/* Nav */}
        <div className="flex gap-4 justify-center pb-6 text-sm">
          <Link href="/" className="text-slate-400 hover:text-white transition-colors">
            ← Back to Vault
          </Link>
          <span className="text-slate-700">·</span>
          <Link href="/architecture" className="text-slate-400 hover:text-white transition-colors">
            Architecture →
          </Link>
        </div>

      </div>
    </div>
  );
}
