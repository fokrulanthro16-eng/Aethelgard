const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export { API_BASE_URL };

export interface UserCreateData {
  email: string;
  nominee_email?: string;
}

export interface UserMetadata {
  PK: string;
  SK: string;
  email: string;
  nominee_email: string | null;
  created_at: string;
  updated_at: string;
  last_checkin_at: string;
  next_check_due_at: string | null;
  dead_man_switch_days: number;
  status: string;
  release_candidate_at: string | null;
}

export interface CheckInResponse {
  message: string;
  email: string;
  last_checkin_at: string;
  next_check_due: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  environment: string;
}

export interface VaultEntryCreateData {
  entry_type: string;
  title: string;
  sensitive_data: string;
  notes?: string;
}

/** Metadata-only — sensitive_data and notes are NOT included. */
export interface VaultEntryResponse {
  entry_id: string;
  entry_type: string;
  title: string;
  created_at: string;
  updated_at: string;
}

/** Full decrypted entry returned by the single-GET endpoint. */
export interface VaultEntryDecrypted {
  entry_id: string;
  entry_type: string;
  title: string;
  sensitive_data: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeleteEntryResponse {
  deleted: boolean;
  entry_id: string;
}

// ── Family Guide ──────────────────────────────────────────────────────────────

export interface FamilyGuideResponse {
  generated_at: string;
  guide: string;
  source: string; // "gemini" | "fallback"
}

// ── Release portal ────────────────────────────────────────────────────────────

export interface ReleaseValidationResponse {
  token: string;
  owner_email: string;
  nominee_email: string | null;
  expires_at: string;
  status: string; // PENDING | USED | EXPIRED
  valid: boolean;
}

export interface ReleaseApprovalResponse {
  token: string;
  owner_email: string;
  approved: boolean;
  released_at: string;
}

// ── Demo mode ─────────────────────────────────────────────────────────────────

export interface DemoVaultEntry {
  entry_id: string;
  entry_type: string;
  title: string;
}

export interface DemoSetupResponse {
  demo_email: string;
  nominee_email: string;
  vault_entries: DemoVaultEntry[];
  release_token: string;
  release_expires_at: string;
}

export interface DemoStatsResponse {
  test_count: number;
  steps_complete: number;
  encryption: {
    mode: string;
    algorithm: string;
    key_derivation: string;
  };
  gemini: {
    configured: boolean;
    model: string;
    fallback_available: boolean;
  };
  dead_man_switch: {
    threshold_days: number;
  };
  release_token: {
    expiry_hours: number;
  };
  dynamodb: {
    table: string;
    design: string;
    item_types: string[];
  };
}

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message =
      (errorBody as { detail?: string }).detail ??
      `API error ${response.status}`;
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function healthCheck(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

export async function createUser(data: UserCreateData): Promise<UserMetadata> {
  return apiFetch<UserMetadata>("/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getUser(email: string): Promise<UserMetadata> {
  return apiFetch<UserMetadata>(
    `/users/${encodeURIComponent(email)}`
  );
}

export async function checkIn(email: string): Promise<CheckInResponse> {
  return apiFetch<CheckInResponse>(
    `/users/${encodeURIComponent(email)}/check-in`,
    { method: "POST" }
  );
}

// ── Vault ─────────────────────────────────────────────────────────────────────

export async function createVaultEntry(
  email: string,
  data: VaultEntryCreateData
): Promise<VaultEntryResponse> {
  return apiFetch<VaultEntryResponse>(
    `/users/${encodeURIComponent(email)}/vault`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function listVaultEntries(
  email: string
): Promise<VaultEntryResponse[]> {
  return apiFetch<VaultEntryResponse[]>(
    `/users/${encodeURIComponent(email)}/vault`
  );
}

export async function getVaultEntry(
  email: string,
  entryId: string
): Promise<VaultEntryDecrypted> {
  return apiFetch<VaultEntryDecrypted>(
    `/users/${encodeURIComponent(email)}/vault/${encodeURIComponent(entryId)}`
  );
}

export async function deleteVaultEntry(
  email: string,
  entryId: string
): Promise<DeleteEntryResponse> {
  return apiFetch<DeleteEntryResponse>(
    `/users/${encodeURIComponent(email)}/vault/${encodeURIComponent(entryId)}`,
    { method: "DELETE" }
  );
}

// ── Release portal ────────────────────────────────────────────────────────────

export async function generateFamilyGuide(
  email: string
): Promise<FamilyGuideResponse> {
  return apiFetch<FamilyGuideResponse>(
    `/users/${encodeURIComponent(email)}/family-guide`,
    { method: "POST" }
  );
}

export async function getFamilyGuideDemo(
  email: string
): Promise<FamilyGuideResponse> {
  return apiFetch<FamilyGuideResponse>(
    `/users/${encodeURIComponent(email)}/family-guide/demo`
  );
}

export async function validateReleaseToken(
  token: string
): Promise<ReleaseValidationResponse> {
  return apiFetch<ReleaseValidationResponse>(`/release/${encodeURIComponent(token)}`);
}

export async function approveRelease(
  token: string
): Promise<ReleaseApprovalResponse> {
  return apiFetch<ReleaseApprovalResponse>(
    `/release/${encodeURIComponent(token)}/approve`,
    { method: "POST" }
  );
}

// ── Demo mode ─────────────────────────────────────────────────────────────────

export async function setupDemo(): Promise<DemoSetupResponse> {
  return apiFetch<DemoSetupResponse>("/demo/setup", { method: "POST" });
}

export async function getDemoStats(): Promise<DemoStatsResponse> {
  return apiFetch<DemoStatsResponse>("/demo/stats");
}
