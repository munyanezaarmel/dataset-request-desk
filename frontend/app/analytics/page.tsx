"use client";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Analytics, api } from "@/lib/api";

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "no delivered requests in range";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

function AnalyticsView() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    if (from) params.set("from", from);
    if (to) params.set("to", to);
    try {
      setError(null);
      setData(await api<Analytics>(`/analytics?${params}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [from, to]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <h1>Analytics</h1>
      <div className="row">
        <label>From <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label>To <input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
      </div>
      <p className="muted">Empty dates = last 30 days. Days are UTC.</p>
      {error && <p className="error">{error}</p>}
      {data && (
        <>
          <p className="muted">Showing {data.from} to {data.to}</p>
          <div className="grid">
            <div className="card">
              <h2>Requests by status</h2>
              <table><tbody>
                {Object.entries(data.requests_by_status).map(([status, n]) => (
                  <tr key={status}><td>{status}</td><td>{n}</td></tr>
                ))}
              </tbody></table>
              <p><strong>Median submitted → delivered:</strong><br />
                {formatDuration(data.median_submitted_to_delivered.seconds)}
                {" "}({data.median_submitted_to_delivered.requests_counted} requests)</p>
            </div>
            <div className="card">
              <h2>Top 5 tasks (good episodes)</h2>
              <table><tbody>
                {data.top_tasks_by_good_episodes.map((t) => (
                  <tr key={t.task_name}><td>{t.task_name}</td><td>{t.good_episodes}</td></tr>
                ))}
              </tbody></table>
            </div>
          </div>
          <h2>Episodes per day per robot</h2>
          <div className="scroll">
            <table>
              <thead><tr><th>Day</th><th>Robot</th><th>Episodes</th></tr></thead>
              <tbody>
                {data.episodes_per_day_per_robot.map((r) => (
                  <tr key={r.day + r.robot_id}><td>{r.day}</td><td>{r.robot_id}</td><td>{r.episodes}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}

export default function AnalyticsPage() {
  return <Shell>{() => <AnalyticsView />}</Shell>;
}