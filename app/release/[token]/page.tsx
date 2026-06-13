"use client";

import { useState, useEffect } from "react";
import { Shield, Heart, AlertCircle, CheckCircle2, Clock, Loader2, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { validateReleaseToken, approveRelease, type ReleaseValidationResponse } from "@/lib/api";

type PageState = "loading" | "valid" | "approved" | "expired" | "used" | "invalid";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ReleasePortalPage({
  params,
}: {
  params: { token: string };
}) {
  const { token } = params;

  const [pageState, setPageState] = useState<PageState>("loading");
  const [validation, setValidation] = useState<ReleaseValidationResponse | null>(null);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    validateReleaseToken(token)
      .then((data) => {
        if (cancelled) return;
        setValidation(data);
        if (!data.valid) {
          setPageState(data.status === "USED" ? "used" : "expired");
        } else {
          setPageState("valid");
        }
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "Unknown error";
        if (msg.includes("404") || msg.toLowerCase().includes("not found")) {
          setPageState("invalid");
        } else {
          setError(msg);
          setPageState("invalid");
        }
      });
    return () => { cancelled = true; };
  }, [token]);

  async function handleApprove() {
    setApproving(true);
    setError(null);
    try {
      await approveRelease(token);
      setPageState("approved");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Approval failed.";
      setError(msg);
      if (msg.toLowerCase().includes("expired")) setPageState("expired");
      else if (msg.toLowerCase().includes("already")) setPageState("used");
    } finally {
      setApproving(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex flex-col items-center justify-center p-6">
      <div className="max-w-lg w-full space-y-6">

        {/* Header */}
        <div className="text-center space-y-3">
          <div className="flex justify-center">
            <div className="relative">
              <div className="w-20 h-20 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
                <Shield className="w-10 h-10 text-blue-400" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full bg-pink-500/20 border border-pink-400/30 flex items-center justify-center">
                <Heart className="w-4 h-4 text-pink-400" />
              </div>
            </div>
          </div>
          <h1 className="text-3xl font-bold text-white">Aethelgard</h1>
          <p className="text-slate-400">Legacy Release Portal</p>
        </div>

        {/* Loading */}
        {pageState === "loading" && (
          <Card className="bg-white/5 border-white/10 text-center">
            <CardContent className="py-12">
              <Loader2 className="w-8 h-8 animate-spin text-blue-400 mx-auto mb-3" />
              <p className="text-slate-400">Validating your release link…</p>
            </CardContent>
          </Card>
        )}

        {/* Invalid / not found */}
        {pageState === "invalid" && (
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-red-400" /> Invalid Link
              </CardTitle>
              <CardDescription className="text-slate-400">
                This release link does not exist or was never issued.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <p className="text-slate-400 text-sm mt-3">
                If you believe you received this link in error, please contact the vault owner.
              </p>
            </CardContent>
          </Card>
        )}

        {/* Expired */}
        {pageState === "expired" && (
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Clock className="w-5 h-5 text-yellow-400" /> Link Expired
              </CardTitle>
              <CardDescription className="text-slate-400">
                This release link has expired.
                {validation?.expires_at && (
                  <> It was valid until {formatDate(validation.expires_at)}.</>
                )}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-slate-400 text-sm">
                Please ask the vault administrator to generate a new release link.
              </p>
            </CardContent>
          </Card>
        )}

        {/* Already used */}
        {pageState === "used" && (
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-400" /> Already Approved
              </CardTitle>
              <CardDescription className="text-slate-400">
                This release has already been approved. The vault has been released.
              </CardDescription>
            </CardHeader>
            {validation && (
              <CardContent>
                <p className="text-slate-400 text-sm">
                  Vault owner: <span className="text-white font-medium">{validation.owner_email}</span>
                </p>
              </CardContent>
            )}
          </Card>
        )}

        {/* Valid — awaiting approval */}
        {pageState === "valid" && validation && (
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Lock className="w-5 h-5 text-purple-400" /> Legacy Release Request
              </CardTitle>
              <CardDescription className="text-slate-400">
                You have been designated as the nominee for the following vault.
                Approving this release will grant access to the vault contents.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-3 rounded-lg border border-white/10 bg-white/5 p-4">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Vault owner</span>
                  <span className="text-white font-medium">{validation.owner_email}</span>
                </div>
                {validation.nominee_email && (
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Designated nominee</span>
                    <span className="text-white font-medium">{validation.nominee_email}</span>
                  </div>
                )}
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Link expires</span>
                  <span className="text-white font-medium">{formatDate(validation.expires_at)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Status</span>
                  <Badge variant="warning">Awaiting approval</Badge>
                </div>
              </div>

              {error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>This action is irreversible</AlertTitle>
                <AlertDescription>
                  Approving this release permanently transitions the vault to RELEASED status.
                  The vault owner&apos;s legacy will become accessible.
                  Only proceed if you are the designated nominee and you are certain.
                </AlertDescription>
              </Alert>

              <Button
                className="w-full bg-purple-600 hover:bg-purple-500 py-6 text-lg font-semibold"
                onClick={handleApprove}
                disabled={approving}
              >
                {approving ? (
                  <><Loader2 className="w-5 h-5 animate-spin mr-2" /> Approving Release…</>
                ) : (
                  <><Heart className="w-5 h-5 mr-2" /> Approve Legacy Release</>
                )}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Approved — success */}
        {pageState === "approved" && (
          <Card className="bg-white/5 border-white/10 text-center">
            <CardHeader>
              <div className="flex justify-center mb-2">
                <div className="w-16 h-16 rounded-full bg-green-500/20 border border-green-400/30 flex items-center justify-center">
                  <CheckCircle2 className="w-8 h-8 text-green-400" />
                </div>
              </div>
              <CardTitle className="text-white text-xl">Legacy Released</CardTitle>
              <CardDescription className="text-slate-400">
                The vault has been successfully released.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {validation && (
                <p className="text-slate-300 text-sm">
                  The legacy of{" "}
                  <span className="text-white font-medium">{validation.owner_email}</span>{" "}
                  is now accessible to their designated nominee.
                </p>
              )}
              <p className="text-slate-500 text-xs">
                Vault content access (Step 5) is coming in a future release.
              </p>
            </CardContent>
          </Card>
        )}

        <p className="text-center text-slate-600 text-xs">
          Aethelgard — AI-Powered Digital Legacy Vault
        </p>
      </div>
    </div>
  );
}
