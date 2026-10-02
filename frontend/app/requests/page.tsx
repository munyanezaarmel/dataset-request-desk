"use client";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import StatusBadge from "@/components/StatusBadge";
import { api, Me, nextActions, RequestItem, Status } from "@/lib/api";

const STATUSES: Status[] = ["submitted", "in_progress", "delivered", "accepted", "rejected"];

function RequestsView({ me }: { me: Me }) {
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ task_name: "", episodes_requested: 10, deadline: "", notes: "" });

  const load = useCallback(async () => {
    try {
      const query = statusFilter ? `?status=${statusFilter}` : "";
      setRequests(await api<RequestItem[]>(`/requests${query}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/requests", { method: "POST", json: { ...form, notes: form.notes || null } });
      setForm({ task_name: "", episodes_requested: 10, deadline: "", notes: "" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function move(id: number, to: Status) {
    setError(null);
    try {
      await api(`/requests/${id}/transition`, { method: "POST", json: { to_status: to } });
      await load();
    } catch (err) {
      setError((err as Error).message); // e.g. "Cannot deliver: 5 episodes requested but only 2 assigned"
    }
  }

  return (
    <>
      <h1>{me.role === "client" ? "My requests" : "All requests"}</h1>
      {error && <p className="error">{error}</p>}

      {me.role === "client" && (
        <form onSubmit={create} className="card stack">
          <h2>New request</h2>
          <div className="row">
            <label>
              Task name
              <input value={form.task_name} onChange={(e) => setForm({ ...form, task_name: e.target.value })}
                     placeholder="e.g. pick cup" required />
            </label>
            <label>
              Episodes
              <input type="number" min={1} value={form.episodes_requested}
                     onChange={(e) => setForm({ ...form, episodes_requested: Number(e.target.value) })} required />
            </label>
            <label>
              Deadline
              <input type="date" value={form.deadline}
                     onChange={(e) => setForm({ ...form, deadline: e.target.value })} required />
            </label>
          </div>
          <label>
            Notes
            <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </label>
          <button type="submit">Submit request</button>
        </form>
      )}

      {me.role !== "client" && (
        <label className="inline">
          Filter by status{" "}
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">all</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
      )}

      <table>
        <thead>
          <tr>
            <th>#</th>
            {me.role !== "client" && <th>Client</th>}
            <th>Task</th>
            <th>Episodes</th>
            <th>Deadline</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((r) => (
            <tr key={r.id}>
              <td><Link href={`/requests/${r.id}`}>{r.id}</Link></td>
              {me.role !== "client" && <td>{r.organisation ?? r.client_name}</td>}
              <td>{r.task_name}</td>
              <td>{r.assigned_count} / {r.episodes_requested}</td>
              <td>{r.deadline}</td>
              <td><StatusBadge status={r.status} /></td>
              <td className="actions">
                {nextActions(me.role, r.status).map((a) => (
                  <button key={a.to} className={a.danger ? "danger" : ""} onClick={() => move(r.id, a.to)}>
                    {a.label}
                  </button>
                ))}
                <Link href={`/requests/${r.id}`}>Open</Link>
              </td>
            </tr>
          ))}
          {requests.length === 0 && (
            <tr><td colSpan={7} className="muted">No requests yet.</td></tr>
          )}
        </tbody>
      </table>
    </>
  );
}

export default function RequestsPage() {
  return <Shell>{(me) => <RequestsView me={me} />}</Shell>;
}
