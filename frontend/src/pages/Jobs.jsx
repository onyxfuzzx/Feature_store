import React, { useEffect, useState } from "react";
import { fetchApi, getActiveUser } from "../api";
import { Card, CardHeader } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import { Clock, Play, Plus, RefreshCw, AlertCircle, CheckCircle2 } from "lucide-react";

export default function Jobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [runningJobId, setRunningJobId] = useState(null);
  const [form, setForm] = useState({
    name: "",
    type: "feature_materialization",
    cron: "0 * * * *",
    payload_json: '{"feature_id": ""}',
    is_active: true,
  });
  const [submitting, setSubmitting] = useState(false);

  const user = getActiveUser();
  const canTrigger = user?.roles?.some((r) => ["admin", "ml_engineer"].includes(r));

  const loadJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      // Single aggregated request — zero N+1 waterfalls!
      const data = await fetchApi("/jobs/overview");
      setJobs(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const handleRun = async (jobId) => {
    setRunningJobId(jobId);
    try {
      await fetchApi(`/jobs/${jobId}/run`, { method: "POST" });
      await loadJobs();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningJobId(null);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await fetchApi(editingId ? `/jobs/${editingId}` : "/jobs", {
        method: editingId ? "PUT" : "POST",
        body: JSON.stringify(form),
      });
      setShowModal(false);
      setForm({
        name: "",
        type: "feature_materialization",
        cron: "0 * * * *",
        payload_json: '{"feature_id": ""}',
        is_active: true,
      });
      await loadJobs();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {error && <div role="alert" className="text-rose-300">{error} <Button onClick={loadJobs}>Retry</Button></div>}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-zinc-800/80">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Scheduler & Jobs</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Background APScheduler materialization workers and batch execution history.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={loadJobs} loading={loading}>
            <RefreshCw className="w-4 h-4" /> Refresh
          </Button>
          {canTrigger && (
            <Button variant="primary" onClick={() => { setEditingId(null); setForm({ name: "", type: "feature_materialization", cron: "0 * * * *", payload_json: '{"feature_id":""}', is_active: true }); setShowModal(true); }}>
              <Plus className="w-4 h-4" /> Create Schedule
            </Button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-sm text-zinc-500">Loading scheduled jobs…</div>
      ) : jobs.length === 0 ? (
        <div className="py-20 text-center text-sm text-zinc-500">No jobs configured in the scheduler.</div>
      ) : (
        <div className="space-y-4">
          {jobs.map((job) => (
            <Card key={job.id} className="p-5">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-base text-zinc-100">{job.name}</span>
                    <Badge variant={job.is_active ? "success" : "default"}>
                      {job.is_active ? "Active" : "Paused"}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-4 text-xs font-mono text-zinc-400">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-zinc-500" />
                      Cron (UTC): <code className="bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-200">{job.cron}</code>
                    </span>
                    <span>Type: {job.type}</span>
                  </div>
                </div>

                {canTrigger && <div className="flex gap-2">
                  <Button onClick={() => { setEditingId(job.id); setForm({ name: job.name, type: job.type, cron: job.cron, payload_json: job.payload_json, is_active: job.is_active }); setShowModal(true); }}>Edit Schedule</Button>
                  <Button onClick={async () => { try { await fetchApi(`/jobs/${job.id}`, { method: "PUT", body: JSON.stringify({ ...job, is_active: !job.is_active }) }); await loadJobs(); } catch (err) { setError(err.message); } }}>{job.is_active ? "Pause" : "Resume"}</Button>
                </div>}
                {canTrigger && (
                  <Button
                    variant="secondary"
                    size="md"
                    onClick={() => handleRun(job.id)}
                    loading={runningJobId === job.id}
                  >
                    <Play className="w-3.5 h-3.5 fill-current" /> Trigger Run
                  </Button>
                )}
              </div>

              {/* Recent runs list */}
              {job.recent_runs && job.recent_runs.length > 0 && (
                <div className="mt-4 pt-4 border-t border-zinc-800/80">
                  <span className="text-[10px] font-mono uppercase text-zinc-500 font-semibold mb-2 block">
                    Recent Runs ({job.recent_runs.length})
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    {job.recent_runs.map((r) => (
                      <div
                        key={r.id}
                        className="flex items-center justify-between p-2 rounded-lg bg-zinc-950 border border-zinc-800/80 text-xs"
                      >
                        <span className="font-mono text-zinc-400">
                          {r.started_at ? r.started_at.slice(11, 19) : "N/A"}
                        </span>
                        <Badge variant={r.status === "success" ? "success" : "danger"}>{r.status}</Badge>
                        {r.log && <span role="status" className="text-rose-300">{r.log}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Modal: Create Job */}
      <Modal isOpen={showModal} title={editingId ? "Edit Scheduled Job" : "Create Scheduled Job"} onClose={() => setShowModal(false)}>
        <form onSubmit={handleCreate} className="space-y-4 text-xs">
          {error && <p role="alert" className="text-rose-300">{error}</p>}
          <div>
            <label className="block font-medium text-zinc-300 mb-1" htmlFor="jobs-field-1">Job Name</label>
            <input id="jobs-field-1"
              type="text"
              required
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              placeholder="e.g. Hourly Payments Materialization"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="block font-medium text-zinc-300 mb-1" htmlFor="jobs-field-2">Cron Expression (UTC)</label>
            <input id="jobs-field-2"
              type="text"
              required
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 font-mono focus:outline-none focus:border-zinc-700"
              placeholder="0 * * * * (Hourly at :00)"
              value={form.cron}
              onChange={(e) => setForm({ ...form, cron: e.target.value })}
            />
          </div>
          <div>
            <label className="block font-medium text-zinc-300 mb-1" htmlFor="jobs-field-3">Payload (JSON)</label>
            <textarea id="jobs-field-3"
              rows={2}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 font-mono text-xs focus:outline-none focus:border-zinc-700"
              value={form.payload_json}
              onChange={(e) => setForm({ ...form, payload_json: e.target.value })}
            />
          </div>
          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
            <Button variant="secondary" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={submitting}>
              {editingId ? "Save Schedule" : "Create Job"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
