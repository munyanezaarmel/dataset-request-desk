"use client";
import { FormEvent, useState } from "react";
import Shell from "@/components/Shell";
import { api, ImportReport } from "@/lib/api";

function ImportView() {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const form = new FormData();
      form.append("file", file);
      setReport(await api<ImportReport>("/episodes/import", { method: "POST", form }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Import episodes</h1>
      <form onSubmit={upload} className="card stack">
        <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <button type="submit" disabled={!file || busy}>{busy ? "Importing…" : "Import CSV"}</button>
        <p className="muted">Safe to upload the same file again: existing episodes are skipped, never duplicated.</p>
      </form>
      {error && <p className="error">{error}</p>}
      {report && (
        <>
          <div className="card">
            <p><strong>{report.imported}</strong> imported, <strong>{report.skipped}</strong> skipped, {report.rows_read} rows read.</p>
            <table><tbody>
              {Object.entries(report.skipped_by_reason).map(([reason, n]) => (
                <tr key={reason}><td>{reason}</td><td>{n}</td></tr>
              ))}
            </tbody></table>
          </div>
          {report.skipped_rows.length > 0 && (
            <div className="scroll">
              <table>
                <thead><tr><th>Line</th><th>Episode</th><th>Reason</th><th>Detail</th></tr></thead>
                <tbody>
                  {report.skipped_rows.map((s) => (
                    <tr key={s.line}><td>{s.line}</td><td>{s.episode_id ?? "—"}</td><td>{s.reason}</td><td>{s.detail}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {report.skipped_rows_truncated && <p className="muted">Only the first rows are listed above.</p>}
        </>
      )}
    </>
  );
}

export default function ImportPage() {
  return <Shell>{() => <ImportView />}</Shell>;
}
