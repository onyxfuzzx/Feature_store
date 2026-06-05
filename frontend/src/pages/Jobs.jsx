import { useEffect, useState } from "react";
import { fetchApi } from "../api";
import { IconClose, IconPlay, IconDot } from "../components/Icons";

function Modal({ title, onClose, children }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{title}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close modal"><IconClose /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function statusColor(s) {
  if (s === "success") return "#0d7a66";
  if (s === "failed") return "#c00";
  if (s === "running") return "#b06000";
  return "#666";
}

export default function Jobs() {
  const [jobs, setJobs] = useState([]);
  const [runs, setRuns] = useState({});
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: "", type: "feature_materialization", cron: "0 * * * *", payload_json: "", is_active: true });
  const [submitting, setSubmitting] = useState(false);
  const [runningJob, setRunningJob] = useState(null);

  const load = async () => {
    try {
      const data = await fetchApi("/jobs");
      setJobs(data);
      const runsMap = {};
      await Promise.all(
        data.map(async (job) => {
          try {
            const r = await fetchApi(`/jobs/${job.id}/runs`);
            runsMap[job.id] = r.slice(0, 3);
          } catch {
            runsMap[job.id] = [];
          }
        })
      );
      setRuns(runsMap);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await fetchApi("/jobs", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          payload_json: form.payload_json || null,
        }),
      });
      setShowModal(false);
      setForm({ name: "", type: "feature_materialization", cron: "0 * * * *", payload_json: "", is_active: true });
      await load();
    } catch {
      // ignore
    } finally {
      setSubmitting(false);
    }
  };

  const handleRunNow = async (jobId) => {
    setRunningJob(jobId);
    try {
      await fetchApi(`/jobs/${jobId}/run`, { method: "POST" });
      await load();
    } catch {
      // ignore
    } finally {
      setRunningJob(null);
    }
  };

  return (
    <section>
      <div className="page-header">
        <div>
          <h1 className="page-title">Materialization Jobs</h1>
          <p className="subtle">Schedule, monitor, and trigger background feature jobs.</p>
        </div>
        <button className="button" onClick={() => setShowModal(true)}>+ Create Job</button>
      </div>

      {loading && <div className="loading-pulse">Loading jobs…</div>}

      {!loading && jobs.map((job) => (
        <div key={job.id} className="card" style={{ marginBottom: 16 }}>
          <div className="job-header">
            <div>
              <strong>{job.name}</strong>
              <div className="subtle">{job.type} · <code>{job.cron}</code></div>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <span className={`badge ${job.is_active ? "" : "badge-off"}`}>
                {job.is_active ? "Active" : "Inactive"}
              </span>
              <button
                className="button button-sm"
                onClick={() => handleRunNow(job.id)}
                disabled={runningJob === job.id}
                style={{ display: "inline-flex", alignItems: "center" }}
              >
                {runningJob === job.id ? (
                  "Running…"
                ) : (
                  <>
                    <IconPlay style={{ marginRight: 4 }} /> Run Now
                  </>
                )}
              </button>
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <div className="subtle" style={{ fontWeight: 600, marginBottom: 6 }}>Last Runs</div>
            {(runs[job.id] || []).length === 0 && <p className="subtle">No runs yet.</p>}
            <div className="list" style={{ gap: 8 }}>
              {(runs[job.id] || []).map((run) => (
                <div key={run.id} className="list-item" style={{ padding: "10px 14px" }}>
                  <div>
                    <span style={{ display: "inline-flex", alignItems: "center" }}>
                      <IconDot fill={statusColor(run.status)} style={{ marginRight: 6 }} />
                      <span style={{ color: statusColor(run.status), fontWeight: 600 }}>{run.status}</span>
                    </span>
                    {run.log && <div className="subtle" style={{ fontSize: "0.78rem", marginTop: 2 }}>{run.log.slice(0, 80)}</div>}
                  </div>
                  <div className="subtle" style={{ fontSize: "0.8rem" }}>
                    {run.started_at?.slice(0, 16).replace("T", " ")}
                    {run.finished_at && ` -> ${run.finished_at.slice(11, 16)}`}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ))}

      {!loading && jobs.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: 40, color: "#888" }}>
          No jobs configured. Create your first job to start scheduling materializations.
        </div>
      )}

      {showModal && (
        <Modal title="Create Job Definition" onClose={() => setShowModal(false)}>
          <form onSubmit={handleCreate} className="modal-form">
            <div className="form-group">
              <label>Job Name *</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder="Materialize Payments" />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Type *</label>
                <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                  <option value="feature_materialization">feature_materialization</option>
                </select>
              </div>
              <div className="form-group">
                <label>Cron Expression *</label>
                <input value={form.cron} onChange={(e) => setForm({ ...form, cron: e.target.value })} required placeholder="0 * * * *" />
              </div>
            </div>
            <div className="form-group">
              <label>Payload JSON (e.g. feature_id)</label>
              <input value={form.payload_json} onChange={(e) => setForm({ ...form, payload_json: e.target.value })} placeholder='{"feature_id":"<uuid>"}' />
            </div>
            <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
              <input type="checkbox" id="is_active" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              <label htmlFor="is_active">Active (schedule immediately)</label>
            </div>
            <div className="modal-actions">
              <button type="button" className="button button-outline" onClick={() => setShowModal(false)}>Cancel</button>
              <button type="submit" className="button" disabled={submitting}>{submitting ? "Creating…" : "Create Job"}</button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
