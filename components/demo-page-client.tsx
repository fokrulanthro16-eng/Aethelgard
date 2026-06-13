"use client";

import { useState } from "react";
import Link from "next/link";
import { Loader2, CheckCircle2, Shield, Database, AlertCircle, ExternalLink, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { setupDemo, getDemoStats, type DemoSetupResponse, type DemoStatsResponse } from "@/lib/api";

export default function DemoPageClient() {
  const [loading, setLoading] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [result, setResult] = useState<DemoSetupResponse | null>(null);
  const [stats, setStats] = useState<DemoStatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSetupDemo() {
    setLoading(true);
    setError(null);
    try {
      const data = await setupDemo();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Setup failed — is the backend running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  async function handleLoadStats() {
    setStatsLoading(true);
    setError(null);
    try {
      const data = await getDemoStats();
      setStats(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach backend — is it running on port 8000?");
    } finally {
      setStatsLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-6">
      <div className="max-w-2xl mx-auto space-y-6">

        {/* Header */}
        <div className="pt-6 space-y-1">
          <div className="flex items-center gap-2">
            <Badge variant="warning" className="text-xs font-mono">DEV ONLY</Badge>
            <span className="text-slate-500 text-xs font-mono">NODE_ENV={process.env.NODE_ENV}</span>
          </div>
          <h1 className="text-2xl font-bold text-white mt-2">Developer Tools</h1>
          <p className="text-slate-400 text-sm">
            This page is hidden in production. Use it to seed demo data and inspect system state.
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-4 flex items-start gap-3">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <p className="text-red-300 text-sm">{error}</p>
          </div>
        )}

        {/* Demo Setup */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2 text-base">
              <Zap className="w-4 h-4 text-yellow-400" />
              Demo Scenario Setup
            </CardTitle>
            <CardDescription className="text-slate-400">
              Creates (or resets) a pre-populated demo vault: 5 encrypted entries, PENDING_RELEASE status,
              and a ready-to-use nominee release token.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button
              className="bg-yellow-500 hover:bg-yellow-400 text-yellow-950 font-bold gap-2"
              onClick={handleSetupDemo}
              disabled={loading}
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Setting up demo…</>
              ) : (
                <><Zap className="w-4 h-4" /> Setup Demo Scenario</>
              )}
            </Button>

            {result && (
              <div className="bg-black/30 border border-white/10 rounded-xl p-4 space-y-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                  <span className="text-green-400 text-sm font-semibold">Demo ready</span>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Demo email</span>
                    <span className="text-white font-mono">{result.demo_email}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Nominee email</span>
                    <span className="text-white font-mono">{result.nominee_email}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Vault entries</span>
                    <span className="text-white">{result.vault_entries.length} encrypted entries</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Release token</span>
                    <span className="text-white font-mono text-xs truncate ml-4">{result.release_token.slice(0, 20)}…</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Token expires</span>
                    <span className="text-white text-xs">{new Date(result.release_expires_at).toLocaleString()}</span>
                  </div>
                </div>

                <div className="border-t border-white/10 pt-3 space-y-2">
                  <p className="text-slate-400 text-xs font-semibold uppercase tracking-wide">Vault entries created</p>
                  {result.vault_entries.map((e) => (
                    <div key={e.entry_id} className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs capitalize shrink-0">{e.entry_type}</Badge>
                      <span className="text-slate-300 text-xs">{e.title}</span>
                    </div>
                  ))}
                </div>

                <div className="border-t border-white/10 pt-3 space-y-2">
                  <p className="text-slate-400 text-xs font-semibold uppercase tracking-wide">Next steps</p>
                  <ol className="space-y-1.5 text-xs text-slate-400 list-decimal list-inside">
                    <li>
                      <a href="/" className="text-blue-400 hover:text-blue-300 underline">Open the main app</a>
                      {" "}and sign in as <span className="font-mono text-white">{result.demo_email}</span>
                    </li>
                    <li>
                      Visit the nominee release portal:{" "}
                      <a
                        href={`/release/${result.release_token}`}
                        className="text-blue-400 hover:text-blue-300 underline font-mono"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        /release/{result.release_token.slice(0, 16)}… <ExternalLink className="w-3 h-3 inline" />
                      </a>
                    </li>
                    <li>Approve the release, then generate the AI Family Guide.</li>
                  </ol>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* System Stats */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2 text-base">
              <Database className="w-4 h-4 text-blue-400" />
              System Stats
            </CardTitle>
            <CardDescription className="text-slate-400">
              Live capability report from <span className="font-mono">GET /demo/stats</span>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              className="border-white/20 text-white hover:bg-white/10 gap-2 mb-4"
              onClick={handleLoadStats}
              disabled={statsLoading}
            >
              {statsLoading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Loading…</>
              ) : (
                "Load Stats"
              )}
            </Button>

            {stats && (
              <div className="space-y-2 text-sm">
                {[
                  ["Tests passing", `${stats.test_count}`],
                  ["Steps complete", `${stats.steps_complete} / 6`],
                  ["Encryption", `${stats.encryption.algorithm} · ${stats.encryption.key_derivation}`],
                  ["Encryption mode", stats.encryption.mode],
                  ["AI model", stats.gemini.model],
                  ["Gemini configured", stats.gemini.configured ? "Yes" : "No (fallback active)"],
                  ["Check-in window", `${stats.dead_man_switch.threshold_days} days`],
                  ["Token expiry", `${stats.release_token.expiry_hours} hours`],
                  ["DynamoDB table", stats.dynamodb.table],
                  ["DB design", stats.dynamodb.design],
                ].map(([label, value]) => (
                  <div key={label} className="flex justify-between gap-4">
                    <span className="text-slate-400">{label}</span>
                    <span className="text-white font-mono text-xs text-right">{value}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Reference links */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2 text-base">
              <Shield className="w-4 h-4 text-slate-400" />
              Reference Pages
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {[
                { label: "API Docs", href: "http://localhost:8000/docs", ext: true },
                { label: "Architecture", href: "/architecture", ext: false },
                { label: "Judge Dashboard", href: "/judge", ext: false },
                { label: "Main App", href: "/", ext: false },
              ].map(({ label, href, ext }) => (
                <a
                  key={label}
                  href={href}
                  target={ext ? "_blank" : undefined}
                  rel={ext ? "noopener noreferrer" : undefined}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:text-white hover:border-white/30 text-sm transition-colors"
                >
                  {label}
                  {ext && <ExternalLink className="w-3 h-3" />}
                </a>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Back */}
        <div className="pb-6 text-center">
          <Link href="/" className="text-slate-500 hover:text-slate-300 text-sm transition-colors">
            ← Back to main app
          </Link>
        </div>

      </div>
    </div>
  );
}
