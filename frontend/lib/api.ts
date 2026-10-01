export type Role = "client" | "operator" | "admin";
export type Status = "submitted" | "in_progress" | "delivered" | "accepted" | "rejected";

export interface Me {
  id: number;
  email: string;
  name: string;
  role: Role;
  organisation: string | null;
}

export interface RequestItem {
  id: number;
  client_id: number;
  client_name: string;
  organisation: string | null;
  task_name: string;
  episodes_requested: number;
  assigned_count: number;
  deadline: string;
  notes: string | null;
  status: Status;
  created_at: string;
  updated_at: string;
}

export interface HistoryItem {
  from_status: Status | null;
  to_status: Status;
  changed_by: number;
  changed_by_name: string;
  changed_at: string;
}

export interface Episode {
  episode_id: string;
  robot_id: string;
  task_name: string;
  recorded_at: string;
  duration_seconds: number;
  operator_name: string;
  quality: "good" | "usable" | "bad";
}

export interface EpisodeListItem extends Episode {
  assigned_request_id: number | null;
}

export interface RequestDetail extends RequestItem {
  history: HistoryItem[];
  episodes: Episode[];
}

export interface ImportReport {
  rows_read: number;
  imported: number;
  skipped: number;
  skipped_by_reason: Record<string, number>;
  skipped_rows: { line: number; episode_id: string | null; reason: string; detail: string }[];
  skipped_rows_truncated: boolean;
}

export interface Analytics {
  from: string;
  to: string;
  episodes_per_day_per_robot: { day: string; robot_id: string; episodes: number }[];
  requests_by_status: Record<Status, number>;
  median_submitted_to_delivered: { seconds: number | null; requests_counted: number };
  top_tasks_by_good_episodes: { task_name: string; good_episodes: number }[];
}

// ---------------------------------------------------------------------------
const TOKEN_KEY = "token";

export function getToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function formatDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc: ["body","deadline"], msg: "..."}]
    return detail
      .map((d) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`)
      .join("; ");
  }
  return null;
}

export async function api<T>(
  path: string,
  init: { method?: string; json?: unknown; form?: FormData } = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  } else if (init.form) {
    body = init.form; // the browser sets the multipart Content-Type itself
  }

  const res = await fetch(`/api${path}`, { method: init.method ?? "GET", headers, body });
  if (res.status === 401 && !path.startsWith("/auth/login")) {
    setToken(null);
    window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, formatDetail(data?.detail) ?? res.statusText);
  return data as T;
}

// ---------------------------------------------------------------------------
// UI hint only: which buttons to SHOW. The server is what actually enforces
// who may do what (see backend/app/services/workflow.py).
export function nextActions(role: Role, status: Status): { to: Status; label: string; danger?: boolean }[] {
  if (role === "client") {
    return status === "delivered"
      ? [
          { to: "accepted", label: "Accept delivery" },
          { to: "rejected", label: "Reject delivery", danger: true },
        ]
      : [];
  }
  if (status === "submitted") return [{ to: "in_progress", label: "Start work" }];
  if (status === "in_progress") return [{ to: "delivered", label: "Mark delivered" }];
  if (status === "rejected") return [{ to: "in_progress", label: "Restart (rework)" }];
  return [];
}

export const fmtDate = (iso: string) => new Date(iso).toLocaleString();