import React, { useEffect, useState } from "react";
import { fetchApi } from "../api";
import { Button } from "./ui/Button";

const time = (offset = 0) => new Date(Date.now() + offset).toISOString().slice(0, 16);
export default function ModelDriftPanel({ modelId, versions, canMeasure }) {
  const [selected, setSelected] = useState(versions.find((v) => v.stage === "Production")?.id || versions[0]?.id || "");
  const version = versions.find((v) => v.id === selected);
  const [data, setData] = useState(null), [error, setError] = useState(null), [busy, setBusy] = useState(false);
  const [samples, setSamples] = useState("{}"), [start, setStart] = useState(time(-86400000)), [end, setEnd] = useState(time(60000));
  const [minimum, setMinimum] = useState(20);
  const load = async () => {
    if (!version) return;
    try { setError(null); setData(await fetchApi(`/models/${modelId}/drift?version=${encodeURIComponent(version.version)}`)); }
    catch (err) { setError(err.message); }
  };
  useEffect(() => { setData(null); load(); }, [selected, modelId]);
  const act = async (baseline) => {
    setBusy(true); setError(null);
    try {
      const window = { window_start: new Date(start + "Z").toISOString(), window_end: new Date(end + "Z").toISOString() };
      await fetchApi(baseline ? `/models/${modelId}/versions/${selected}/drift-baseline` : `/models/${modelId}/drift/runs`, {
        method: "POST", body: JSON.stringify({ ...window, ...(baseline ? { samples: JSON.parse(samples) } : { version: version.version, min_samples: Number(minimum) }) }),
      });
      await load();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return <section className="space-y-4 p-5 border border-zinc-800 rounded-xl" aria-label="Recorded drift monitoring">
    <label className="block text-sm">Monitoring version <select aria-label="Monitoring version" className="bg-zinc-900 p-2 ml-3" value={selected} onChange={(e) => setSelected(e.target.value)}>
      {versions.map((v) => <option key={v.id} value={v.id}>{v.version} ({v.stage})</option>)}
    </select></label>
    {error && <div role="alert" className="text-rose-300">{error} <Button onClick={load}>Retry</Button></div>}
    <p className="text-sm text-zinc-400">Status: {data?.status || (version ? "Loading" : "No model version")}. Measurements use recorded inference values for this version, with a fixed training baseline.</p>
    {data?.baseline && <p className="text-xs text-zinc-400">Training window: {data.baseline.window_start} to {data.baseline.window_end}</p>}
    {canMeasure && version && <div className="space-y-3 border-y border-zinc-800 py-4">
      <div className="flex flex-wrap gap-4">
        <label>Window start (UTC)<input aria-label="Window start (UTC)" className="block bg-zinc-900 p-2" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label>Window end (UTC, exclusive)<input aria-label="Window end (UTC, exclusive)" className="block bg-zinc-900 p-2" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        <label>Minimum samples<input aria-label="Minimum samples" className="block bg-zinc-900 p-2 w-28" type="number" min="2" value={minimum} onChange={(e) => setMinimum(e.target.value)} /></label>
      </div>
      <label className="block">Training samples by linked feature ID (JSON)
        <textarea aria-label="Training samples by linked feature ID (JSON)" className="block w-full bg-zinc-900 p-3 font-mono text-xs" rows="4" value={samples} onChange={(e) => setSamples(e.target.value)} />
      </label>
      <p className="text-xs text-zinc-400">Capture freezes the supplied training distributions. Measure evaluates inference observations within the window above. Missing samples remain unknown.</p>
      <div className="flex gap-3"><Button onClick={() => act(true)} loading={busy}>Capture Training Baseline</Button><Button onClick={() => act(false)} loading={busy}>Measure Drift</Button></div>
    </div>}
    {data?.metrics.map((item) => <article key={item.feature_id} className="space-y-2 p-3 bg-zinc-900 rounded">
      <h3 className="font-semibold">{item.feature}</h3>
      <p className="text-sm">PSI: {item.current_psi ?? "Not measured"} · {item.status} · baseline {item.baseline_sample_count}, current {item.current_sample_count} samples</p>
      <p className="text-xs font-mono break-all">{item.feature_id}</p>
      {item.drift_detected && <p role="status" className="text-amber-300">Drift detected</p>}
      {item.history.length > 0 && <table className="w-full text-xs"><caption className="text-left text-zinc-400">Recorded measurements</caption><thead><tr><th>Recorded at</th><th>PSI</th><th>Status</th></tr></thead><tbody>
        {item.history.map((point) => <tr key={point.run_id}><td>{point.date}</td><td>{point.psi ?? "Unknown"}</td><td>{point.status}</td></tr>)}
      </tbody></table>}
    </article>)}
  </section>;
}
