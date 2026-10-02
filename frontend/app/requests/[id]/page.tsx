"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import StatusBadge from "@/components/StatusBadge";
import { api, EpisodeListItem, fmtDate, Me, nextActions, RequestDetail, Status } from "@/lib/api";

function AssignPanel({ requestId, onChanged, onError }: {
  requestId: number;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const [taskNames, setTaskNames] = useState<string[]>([]);
  const [task, setTask] = useState("");
  const [quality, setQuality] = useState("");
  const [availableOnly, setAvailableOnly] = useState(true);
  const [items, setItems] = useState<EpisodeListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    api<string[]>("/episodes/task-names").then(setTaskNames).catch(() => undefined);
  }, []);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ limit: "100" });
    if (task) params.set("task_name", task);
    if (quality) params.set("quality", quality);
    if (availableOnly) params.set("available_only", "true");
    try {
      const data = await api<{ items: EpisodeListItem[]; total: number }>(`/episodes?${params}`);
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      onError((e as Error).message);
    }
  }, [task, quality, availableOnly, onError]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  async function assign() {
    try {
      await api(`/requests/${requestId}/assignments`, {
        method: "POST",
        json: { episode_ids: Array.from(selected) },
      });
      setSelected(new Set());
      onChanged();
      load();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  return (
    <div className="card stack">
      <h2>Assign episodes</h2>
      <div className="row">
        <label>
          Task
          <select value={task} onChange={(e) => setTask(e.target.value)}>
            <option value="">all</option>
            {taskNames.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label>
          Quality
          <select value={quality} onChange={(e) => setQuality(e.target.value)}>
            <option value="">all</option>
            <option value="good">good</option>
            <option value="usable">usable</option>
            <option value="bad">bad</option>
          </select>
        </label>
        <label className="inline">
          <input type="checkbox" checked={availableOnly} onChange={(e) => setAvailableOnly(e.target.checked)} />
          unassigned only
        </label>
      </div>
      <p className="muted">Showing {items.length} of {total}. Bad episodes cannot be assigned.</p>
      <div className="scroll">
        <table>
          <thead>
            <tr><th></th><th>Episode</th><th>Task</th><th>Robot</th><th>Quality</th><th>Duration</th><th>Assigned to</th></tr>
          </thead>
          <tbody>
            {items.map((ep) => {
              const blocked = ep.quality === "bad" || ep.assigned_request_id !== null;
              return (
                <tr key={ep.episode_id} className={blocked ? "dim" : ""}>
                  <td>
                    <input type="checkbox" disabled={blocked} checked={selected.has(ep.episode_id)}
                           onChange={() => toggle(ep.episode_id)} />
                  </td>
                  <td>{ep.episode_id}</td>
                  <td>{ep.task_name}</td>
                  <td>{ep.robot_id}</td>
                  <td>{ep.quality}</td>
                  <td>{ep.duration_seconds}s</td>
                  <td>{ep.assigned_request_id ? `#${ep.assigned_request_id}` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button disabled={selected.size === 0} onClick={assign}>Assign {selected.size} selected</button>
    </div>
  );
}

function DetailView({ me, id }: { me: Me; id: number }) {
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setDetail(await api<RequestDetail>(`/requests/${id}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function move(to: Status) {
    setError(null);
    try {
      await api(`/requests/${id}/transition`, { method: "POST", json: { to_status: to } });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function unassign(episodeId: string) {
    setError(null);
    try {
      await api(`/requests/${id}/assignments/${episodeId}`, { method: "DELETE" });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!detail) return error ? <p className="error">{error}</p> : <p className="muted">Loading…</p>;
  const staff = me.role !== "client";
  const editable = staff && detail.status === "in_progress";

  return (
    <>
      <p><Link href="/requests">← All requests</Link></p>
      <h1>Request #{detail.id} <StatusBadge status={detail.status} /></h1>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <p><strong>Client:</strong> {detail.organisation ?? detail.client_name}</p>
        <p><strong>Task:</strong> {detail.task_name}</p>
        <p><strong>Episodes:</strong> {detail.assigned_count} assigned / {detail.episodes_requested} requested</p>
        <p><strong>Deadline:</strong> {detail.deadline}</p>
        {detail.notes && <p><strong>Notes:</strong> {detail.notes}</p>}
        <div className="actions">
          {nextActions(me.role, detail.status).map((a) => (
            <button key={a.to} className={a.danger ? "danger" : ""} onClick={() => move(a.to)}>{a.label}</button>
          ))}
        </div>
      </div>

      {editable && <AssignPanel requestId={id} onChanged={load} onError={setError} />}

      <h2>Assigned episodes ({detail.episodes.length})</h2>
      <table>
        <thead><tr><th>Episode</th><th>Task</th><th>Robot</th><th>Quality</th><th>Recorded</th>{editable && <th></th>}</tr></thead>
        <tbody>
          {detail.episodes.map((ep) => (
            <tr key={ep.episode_id}>
              <td>{ep.episode_id}</td><td>{ep.task_name}</td><td>{ep.robot_id}</td>
              <td>{ep.quality}</td><td>{fmtDate(ep.recorded_at)}</td>
              {editable && <td><button className="secondary" onClick={() => unassign(ep.episode_id)}>Remove</button></td>}
            </tr>
          ))}
          {detail.episodes.length === 0 && <tr><td colSpan={6} className="muted">None yet.</td></tr>}
        </tbody>
      </table>

      <h2>History</h2>
      <table>
        <thead><tr><th>When</th><th>Change</th><th>By</th></tr></thead>
        <tbody>
          {detail.history.map((h, i) => (
            <tr key={i}>
              <td>{fmtDate(h.changed_at)}</td>
              <td>{h.from_status ?? "—"} → {h.to_status}</td>
              <td>{h.changed_by_name}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export default function RequestPage() {
  const params = useParams<{ id: string }>();
  return <Shell>{(me) => <DetailView me={me} id={Number(params.id)} />}</Shell>;
}
