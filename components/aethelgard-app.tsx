"use client";

import { useState, useCallback, useEffect } from "react";
import { Shield, Heart, Clock, User, AlertCircle, CheckCircle2, Loader2, Key, Lock, Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  checkIn, createUser, getUser,
  createVaultEntry, listVaultEntries, deleteVaultEntry,
  generateFamilyGuide,
  type CheckInResponse, type UserMetadata,
  type VaultEntryCreateData, type VaultEntryResponse,
  type FamilyGuideResponse,
} from "@/lib/api";

type AppView = "landing" | "register" | "dashboard";

type ToastState = {
  type: "success" | "error" | "idle";
  message: string;
};

const ENTRY_TYPES = ["message", "note", "credentials", "document"] as const;
type EntryType = typeof ENTRY_TYPES[number];

const EMPTY_VAULT_FORM: VaultEntryCreateData = {
  entry_type: "message",
  title: "",
  sensitive_data: "",
  notes: "",
};

export default function AethelgardApp() {
  const [view, setView] = useState<AppView>("landing");
  const [email, setEmail] = useState("");
  const [nomineeEmail, setNomineeEmail] = useState("");
  const [userData, setUserData] = useState<UserMetadata | null>(null);
  const [lastCheckIn, setLastCheckIn] = useState<CheckInResponse | null>(null);
  const [toast, setToast] = useState<ToastState>({ type: "idle", message: "" });
  const [loading, setLoading] = useState(false);

  // Vault state
  const [vaultEntries, setVaultEntries] = useState<VaultEntryResponse[]>([]);
  const [vaultForm, setVaultForm] = useState<VaultEntryCreateData>(EMPTY_VAULT_FORM);
  const [vaultLoading, setVaultLoading] = useState(false);
  const [showVaultForm, setShowVaultForm] = useState(false);

  // Family Guide state
  const [guide, setGuide] = useState<FamilyGuideResponse | null>(null);
  const [guideLoading, setGuideLoading] = useState(false);
  const [guideCopied, setGuideCopied] = useState(false);


  const showToast = useCallback((type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast({ type: "idle", message: "" }), 5000);
  }, []);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    try {
      const user = await createUser({ email: email.trim(), nominee_email: nomineeEmail.trim() || undefined });
      setUserData(user);
      showToast("success", "Your vault has been created. You are now protected.");
      setView("dashboard");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create vault.";
      showToast("error", message);
    } finally {
      setLoading(false);
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    try {
      const user = await getUser(email.trim());
      setUserData(user);
      setView("dashboard");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Vault not found. Please register first.";
      showToast("error", message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCheckIn() {
    if (!userData) return;
    setLoading(true);
    try {
      const result = await checkIn(userData.email);
      setLastCheckIn(result);
      setUserData((prev) => prev ? {
        ...prev,
        last_checkin_at: result.last_checkin_at,
        next_check_due_at: result.next_check_due,
        status: "ACTIVE",
      } : prev);
      showToast("success", "Check-in recorded. Your legacy is safe.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Check-in failed. Please try again.";
      showToast("error", message);
    } finally {
      setLoading(false);
    }
  }

  const loadVaultEntries = useCallback(async (ownerEmail: string) => {
    try {
      const entries = await listVaultEntries(ownerEmail);
      setVaultEntries(entries);
    } catch {
      // non-fatal — vault list is best-effort on dashboard load
    }
  }, []);

  useEffect(() => {
    if (view === "dashboard" && userData) {
      loadVaultEntries(userData.email);
    }
  }, [view, userData?.email, loadVaultEntries]);

  async function handleAddVaultEntry(e: React.FormEvent) {
    e.preventDefault();
    if (!userData || !vaultForm.title.trim() || !vaultForm.sensitive_data.trim()) return;
    setVaultLoading(true);
    try {
      const entry = await createVaultEntry(userData.email, {
        ...vaultForm,
        notes: vaultForm.notes?.trim() || undefined,
      });
      setVaultEntries((prev) => [entry, ...prev]);
      setVaultForm(EMPTY_VAULT_FORM);
      setShowVaultForm(false);
      showToast("success", "Entry saved and encrypted.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save entry.";
      showToast("error", message);
    } finally {
      setVaultLoading(false);
    }
  }

  async function handleDeleteVaultEntry(entryId: string) {
    if (!userData) return;
    try {
      await deleteVaultEntry(userData.email, entryId);
      setVaultEntries((prev) => prev.filter((e) => e.entry_id !== entryId));
      showToast("success", "Entry deleted.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete entry.";
      showToast("error", message);
    }
  }

  async function handleGenerateGuide() {
    if (!userData) return;
    setGuideLoading(true);
    try {
      const result = await generateFamilyGuide(userData.email);
      setGuide(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate guide.";
      showToast("error", message);
    } finally {
      setGuideLoading(false);
    }
  }

  async function handleCopyGuide() {
    if (!guide) return;
    await navigator.clipboard.writeText(guide.guide);
    setGuideCopied(true);
    setTimeout(() => setGuideCopied(false), 2000);
  }

  function formatDate(iso: string) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function daysUntilDue(lastCheckin: string, switchDays: number, nextDueAt?: string | null) {
    const due = nextDueAt
      ? new Date(nextDueAt)
      : new Date(new Date(lastCheckin).getTime() + switchDays * 24 * 60 * 60 * 1000);
    const diff = Math.ceil((due.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    return Math.max(0, diff);
  }

  // ── Landing ──────────────────────────────────────────────────────────────────
  if (view === "landing") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex flex-col items-center justify-center p-6 py-16">
        <div className="max-w-2xl w-full text-center space-y-10">

          {/* Logo */}
          <div className="flex justify-center">
            <div className="relative">
              <div className="w-24 h-24 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
                <Shield className="w-12 h-12 text-blue-400" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full bg-green-500/20 border border-green-400/30 flex items-center justify-center">
                <Heart className="w-4 h-4 text-green-400" />
              </div>
            </div>
          </div>

          {/* Headline */}
          <div className="space-y-3">
            <h1 className="text-5xl font-bold text-white tracking-tight">Aethelgard</h1>
            <p className="text-blue-300 text-lg font-medium">Your Digital Legacy, Protected</p>
            <p className="text-slate-300 text-xl leading-relaxed max-w-lg mx-auto pt-2">
              A secure vault for everything your family will need —
              automatically delivered when the time comes.
            </p>
          </div>

          {/* Trust pillars */}
          <div className="grid grid-cols-3 gap-4 text-center">
            {[
              { icon: Lock, label: "Always Private", desc: "Encrypted before it leaves your device. We can never read your data." },
              { icon: Clock, label: "Always Watching", desc: "Miss 90 days of check-ins and we quietly begin the handover process." },
              { icon: Heart, label: "Always Ready", desc: "Your nominee receives a clear, organised guide the moment they need it." },
            ].map(({ icon: Icon, label, desc }) => (
              <div key={label} className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2">
                <Icon className="w-6 h-6 text-blue-400 mx-auto" />
                <div className="text-white font-semibold text-sm">{label}</div>
                <div className="text-slate-400 text-xs leading-relaxed">{desc}</div>
              </div>
            ))}
          </div>

          {/* How it works */}
          <div className="text-left space-y-4">
            <h2 className="text-center text-white font-semibold text-lg">How it works</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                {
                  num: "01",
                  title: "Create your vault",
                  desc: "Register with your email and name a trusted nominee — the person who will receive your legacy if you're no longer around.",
                },
                {
                  num: "02",
                  title: "Add what matters",
                  desc: "Store bank accounts, passwords, insurance policies, legal documents, and personal messages. Everything in one safe place.",
                },
                {
                  num: "03",
                  title: "Check in regularly",
                  desc: "Press I AM OK every 90 days. One tap tells us you're safe. If you stop checking in, we begin the handover process quietly.",
                },
                {
                  num: "04",
                  title: "Your family is taken care of",
                  desc: "Your nominee receives a secure link. Once they approve the release, an AI guide organises your vault into a clear handover document.",
                },
              ].map(({ num, title, desc }) => (
                <div key={num} className="bg-white/5 border border-white/10 rounded-xl p-4 flex gap-3 text-left">
                  <span className="text-blue-500 font-mono text-xs font-bold pt-0.5 shrink-0">{num}</span>
                  <div>
                    <p className="text-white text-sm font-semibold mb-1">{title}</p>
                    <p className="text-slate-400 text-xs leading-relaxed">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* For families */}
          <div className="border border-slate-700/60 rounded-2xl p-6 text-left space-y-3">
            <h2 className="text-white font-semibold flex items-center gap-2">
              <Heart className="w-4 h-4 text-pink-400" />
              For the people who matter most
            </h2>
            <p className="text-slate-400 text-sm leading-relaxed">
              Most of us have bank accounts our family can&apos;t find, insurance
              policies no one knows about, and passwords that exist only in our
              heads.
            </p>
            <p className="text-slate-400 text-sm leading-relaxed">
              Aethelgard gives you a safe, private place to keep it all organised
              — and a reliable, automated way to pass it on to the people you
              love, without them having to search.
            </p>
          </div>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button
              size="lg"
              className="bg-blue-600 hover:bg-blue-500 text-white px-8"
              onClick={() => { setView("register"); }}
            >
              Create My Vault
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-white/20 text-white hover:bg-white/10 px-8"
              onClick={() => { setView("register"); }}
            >
              Access My Vault
            </Button>
          </div>

          {/* Footer */}
          <div className="space-y-2">
            <p className="text-slate-500 text-xs">
              Your data is encrypted and stored securely. We never read your legacy content.
            </p>
            {process.env.NODE_ENV !== "production" && (
              <a
                href="/demo"
                className="text-slate-700 hover:text-slate-500 text-xs transition-colors"
              >
                Developer Tools
              </a>
            )}
          </div>

        </div>
      </div>
    );
  }

  // ── Register / Login ──────────────────────────────────────────────────────────
  if (view === "register") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center p-6">
        <div className="w-full max-w-md space-y-6">
          <div className="text-center space-y-2">
            <div className="flex justify-center">
              <div className="w-16 h-16 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
                <Shield className="w-8 h-8 text-blue-400" />
              </div>
            </div>
            <h2 className="text-3xl font-bold text-white">Aethelgard</h2>
            <p className="text-slate-400">Enter your email to access your vault</p>
          </div>

          {toast.type !== "idle" && (
            <Alert variant={toast.type === "error" ? "destructive" : "success"}>
              {toast.type === "error" ? (
                <AlertCircle className="h-4 w-4" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              <AlertDescription>{toast.message}</AlertDescription>
            </Alert>
          )}

          {/* Register */}
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <User className="w-5 h-5" /> Create New Vault
              </CardTitle>
              <CardDescription className="text-slate-400">
                First time here? Create your secure digital legacy vault.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleRegister} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="reg-email" className="text-slate-300">Your Email</Label>
                  <Input
                    id="reg-email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="bg-white/10 border-white/20 text-white placeholder:text-slate-500"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="nominee-email" className="text-slate-300">
                    Nominee Email <span className="text-slate-500">(optional)</span>
                  </Label>
                  <Input
                    id="nominee-email"
                    type="email"
                    placeholder="trusted-person@example.com"
                    value={nomineeEmail}
                    onChange={(e) => setNomineeEmail(e.target.value)}
                    className="bg-white/10 border-white/20 text-white placeholder:text-slate-500"
                  />
                  <p className="text-xs text-slate-500">
                    This person will receive your legacy if you miss 90 days of check-ins.
                  </p>
                </div>
                <Button
                  type="submit"
                  className="w-full bg-blue-600 hover:bg-blue-500"
                  disabled={loading}
                >
                  {loading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Creating vault…</>
                  ) : (
                    "Create My Vault"
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Login */}
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Key className="w-5 h-5" /> Access Existing Vault
              </CardTitle>
              <CardDescription className="text-slate-400">
                Already registered? Enter your email to continue.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="login-email" className="text-slate-300">Your Email</Label>
                  <Input
                    id="login-email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="bg-white/10 border-white/20 text-white placeholder:text-slate-500"
                  />
                </div>
                <Button
                  type="submit"
                  variant="outline"
                  className="w-full border-white/20 bg-transparent text-white hover:bg-white/10"
                  disabled={loading}
                >
                  {loading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Accessing vault…</>
                  ) : (
                    "Access My Vault"
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          <button
            onClick={() => setView("landing")}
            className="w-full text-slate-500 hover:text-slate-300 text-sm transition-colors"
          >
            ← Back to home
          </button>
        </div>
      </div>
    );
  }

  // ── Dashboard ─────────────────────────────────────────────────────────────────
  // daysLeft is only meaningful for ACTIVE vaults.
  // PENDING_RELEASE is always 0 (overdue); RELEASED is not applicable (null).
  const daysLeft: number | null =
    userData?.status === "ACTIVE"
      ? daysUntilDue(userData.last_checkin_at, userData.dead_man_switch_days, userData.next_check_due_at)
      : userData?.status === "PENDING_RELEASE"
      ? 0
      : null;

  const isPendingRelease = userData?.status === "PENDING_RELEASE";

  const urgency =
    isPendingRelease ? "critical"
    : daysLeft === null ? "idle"
    : daysLeft > 30 ? "safe"
    : daysLeft > 7 ? "warning"
    : "critical";

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
              <Shield className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h1 className="text-white font-bold text-lg">Aethelgard</h1>
              <p className="text-slate-400 text-xs">{userData?.email}</p>
            </div>
          </div>
          <Badge
            variant={
              urgency === "safe" ? "success"
              : urgency === "warning" ? "warning"
              : urgency === "critical" ? "destructive"
              : "secondary"
            }
          >
            {userData?.status ?? "ACTIVE"}
          </Badge>
        </div>

        {/* Toast */}
        {toast.type !== "idle" && (
          <Alert variant={toast.type === "error" ? "destructive" : "success"}>
            {toast.type === "error" ? (
              <AlertCircle className="h-4 w-4" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            <AlertTitle>{toast.type === "success" ? "Success" : "Error"}</AlertTitle>
            <AlertDescription>{toast.message}</AlertDescription>
          </Alert>
        )}

        {/* PENDING_RELEASE warning */}
        {isPendingRelease && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Legacy Release Pending</AlertTitle>
            <AlertDescription>
              Your check-in window has expired. Press &quot;I AM OK&quot; right now to cancel the release of your vault.
            </AlertDescription>
          </Alert>
        )}

        {/* THE BIG BUTTON — Grandma Theory UX */}
        <Card className="bg-white/5 border-white/10 text-center">
          <CardHeader>
            <CardTitle className="text-white text-2xl">Are you still with us?</CardTitle>
            <CardDescription className="text-slate-400 text-base">
              Press this button to let your loved ones know you&apos;re safe and well.
            </CardDescription>
          </CardHeader>
          <CardContent className="pb-8 space-y-6">
            <Button
              size="xl"
              className={`
                w-full max-w-xs mx-auto text-2xl font-bold py-8 rounded-2xl shadow-2xl transition-all duration-200
                ${urgency === "critical"
                  ? "bg-red-600 hover:bg-red-500 animate-pulse"
                  : urgency === "warning"
                  ? "bg-yellow-500 hover:bg-yellow-400 text-yellow-950"
                  : "bg-green-600 hover:bg-green-500"
                }
              `}
              onClick={handleCheckIn}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="w-8 h-8 animate-spin" />
              ) : (
                "✓  I AM OK"
              )}
            </Button>

            {lastCheckIn && (
              <p className="text-green-400 text-sm">
                Last check-in recorded at {formatDate(lastCheckIn.last_checkin_at)}.
                Next due: {formatDate(lastCheckIn.next_check_due)}.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Dead-man switch status */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2 text-base">
              <Clock className="w-4 h-4 text-blue-400" /> Dead-Man Switch Status
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Check-in period</span>
              <span className="text-white font-medium">{userData?.dead_man_switch_days ?? 90} days</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Last check-in</span>
              <span className="text-white font-medium">
                {userData ? formatDate(userData.last_checkin_at) : "—"}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Next check-in due</span>
              <span className="text-white font-medium">
                {userData?.status !== "ACTIVE"
                  ? "—"
                  : userData?.next_check_due_at
                  ? formatDate(userData.next_check_due_at)
                  : userData
                  ? formatDate(new Date(new Date(userData.last_checkin_at).getTime() + userData.dead_man_switch_days * 86400000).toISOString())
                  : "—"}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Days remaining</span>
              <span
                className={`font-bold text-base ${
                  urgency === "safe" ? "text-green-400"
                  : urgency === "warning" ? "text-yellow-400"
                  : "text-red-400"
                }`}
              >
                {userData?.status === "PENDING_RELEASE"
                  ? "Overdue"
                  : daysLeft !== null
                  ? `${daysLeft} days`
                  : "—"}
              </span>
            </div>
            {userData && daysLeft !== null && (
              <div className="w-full bg-white/10 rounded-full h-2 mt-2">
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${
                    urgency === "safe" ? "bg-green-500"
                    : urgency === "warning" ? "bg-yellow-400"
                    : "bg-red-500"
                  }`}
                  style={{
                    width: `${Math.min(100, (daysLeft / userData.dead_man_switch_days) * 100)}%`,
                  }}
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Legacy Vault ─────────────────────────────────────────────── */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-white flex items-center gap-2 text-base">
                <Lock className="w-4 h-4 text-purple-400" /> Legacy Vault
              </CardTitle>
              <Button
                size="sm"
                variant="outline"
                className="border-white/20 text-white hover:bg-white/10 gap-1"
                onClick={() => setShowVaultForm((v) => !v)}
              >
                <Plus className="w-3 h-3" />
                {showVaultForm ? "Cancel" : "Add Entry"}
              </Button>
            </div>
            <CardDescription className="text-slate-400">
              Encrypted messages, credentials, and documents for your loved ones.
            </CardDescription>
          </CardHeader>

          {showVaultForm && (
            <CardContent className="border-t border-white/10 pt-4">
              <form onSubmit={handleAddVaultEntry} className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label className="text-slate-300 text-xs">Type</Label>
                    <select
                      value={vaultForm.entry_type}
                      onChange={(e) => setVaultForm((f) => ({ ...f, entry_type: e.target.value as EntryType }))}
                      className="w-full rounded-md border border-white/20 bg-white/10 px-3 py-2 text-sm text-white"
                    >
                      {ENTRY_TYPES.map((t) => (
                        <option key={t} value={t} className="bg-slate-900">{t}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-slate-300 text-xs">Title</Label>
                    <Input
                      placeholder="e.g. Letter to family"
                      value={vaultForm.title}
                      onChange={(e) => setVaultForm((f) => ({ ...f, title: e.target.value }))}
                      required
                      className="bg-white/10 border-white/20 text-white placeholder:text-slate-500 text-sm"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <Label className="text-slate-300 text-xs">
                    Sensitive Information <span className="text-purple-400">(encrypted before saving)</span>
                  </Label>
                  <textarea
                    placeholder="Write your message, password, or secret here…"
                    value={vaultForm.sensitive_data}
                    onChange={(e) => setVaultForm((f) => ({ ...f, sensitive_data: e.target.value }))}
                    required
                    rows={4}
                    className="w-full rounded-md border border-white/20 bg-white/10 px-3 py-2 text-sm text-white placeholder:text-slate-500 resize-none focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-slate-300 text-xs">
                    Notes <span className="text-slate-500">(optional, also encrypted)</span>
                  </Label>
                  <Input
                    placeholder="Any additional context…"
                    value={vaultForm.notes ?? ""}
                    onChange={(e) => setVaultForm((f) => ({ ...f, notes: e.target.value }))}
                    className="bg-white/10 border-white/20 text-white placeholder:text-slate-500 text-sm"
                  />
                </div>

                <Button
                  type="submit"
                  className="w-full bg-purple-600 hover:bg-purple-500"
                  disabled={vaultLoading}
                >
                  {vaultLoading ? (
                    <><Loader2 className="w-4 h-4 animate-spin mr-2" />Encrypting & Saving…</>
                  ) : (
                    <><Lock className="w-4 h-4 mr-2" />Save Encrypted Entry</>
                  )}
                </Button>
              </form>
            </CardContent>
          )}

          <CardContent className={showVaultForm ? "pt-0" : ""}>
            {vaultEntries.length === 0 ? (
              <p className="text-slate-500 text-sm text-center py-4">
                No entries yet. Add your first encrypted message.
              </p>
            ) : (
              <ul className="space-y-2">
                {vaultEntries.map((entry) => (
                  <li
                    key={entry.entry_id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Badge variant="secondary" className="shrink-0 text-xs capitalize">
                        {entry.entry_type}
                      </Badge>
                      <span className="text-white text-sm truncate">{entry.title}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-slate-500 text-xs hidden sm:block">
                        {new Date(entry.created_at).toLocaleDateString()}
                      </span>
                      <button
                        onClick={() => handleDeleteVaultEntry(entry.entry_id)}
                        className="text-slate-600 hover:text-red-400 transition-colors"
                        aria-label="Delete entry"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* ── Family Guide ──────────────────────────────────────────────── */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2 text-base">
              <Heart className="w-4 h-4 text-pink-400" /> Family Guide
            </CardTitle>
            <CardDescription className="text-slate-400">
              {userData?.status === "RELEASED"
                ? "Generate a human-readable guide from the encrypted vault contents."
                : "Available after the vault has been released by the nominee."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {userData?.status !== "RELEASED" ? (
              <p className="text-slate-500 text-sm text-center py-2">
                Status: <span className="font-medium text-slate-400">{userData?.status ?? "—"}</span>
                {" "}— Guide generation is locked until the vault reaches RELEASED status.
              </p>
            ) : (
              <>
                {!guide ? (
                  <Button
                    className="w-full bg-pink-600 hover:bg-pink-500"
                    onClick={handleGenerateGuide}
                    disabled={guideLoading}
                  >
                    {guideLoading ? (
                      <><Loader2 className="w-4 h-4 animate-spin mr-2" />Generating Guide…</>
                    ) : (
                      <><Heart className="w-4 h-4 mr-2" />Generate Family Guide</>
                    )}
                  </Button>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-slate-400 text-xs">
                        Generated {formatDate(guide.generated_at)}
                        {guide.source === "gemini" && (
                          <span className="ml-2 text-blue-400">· AI-powered</span>
                        )}
                      </span>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-white/20 text-white hover:bg-white/10 text-xs"
                          onClick={handleCopyGuide}
                        >
                          {guideCopied ? <CheckCircle2 className="w-3 h-3 mr-1 text-green-400" /> : null}
                          {guideCopied ? "Copied" : "Copy"}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-white/20 text-white hover:bg-white/10 text-xs"
                          onClick={() => window.print()}
                        >
                          Print
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-white/20 text-white hover:bg-white/10 text-xs"
                          onClick={() => setGuide(null)}
                        >
                          Regenerate
                        </Button>
                      </div>
                    </div>
                    <pre className="bg-black/30 border border-white/10 rounded-lg p-4 text-slate-300 text-xs leading-relaxed whitespace-pre-wrap overflow-auto max-h-96 font-mono">
                      {guide.guide}
                    </pre>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Nominee info */}
        {userData?.nominee_email && (
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2 text-base">
                <Heart className="w-4 h-4 text-pink-400" /> Nominee
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-slate-300 text-sm">
                If your check-in window expires, your legacy will be delivered to:
              </p>
              <p className="text-white font-medium mt-1">{userData.nominee_email}</p>
            </CardContent>
          </Card>
        )}

        {/* Footer */}
        <div className="text-center space-y-2">
          <p className="text-slate-500 text-xs">
            Vault created {userData ? formatDate(userData.created_at) : "—"}
          </p>
          <button
            onClick={() => { setView("landing"); setUserData(null); setLastCheckIn(null); setEmail(""); setGuide(null); }}
            className="text-slate-600 hover:text-slate-400 text-xs transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
