import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchApi, getActiveUser } from "../api";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import { Cpu, Plus, ArrowRight, Activity, Calendar } from "lucide-react";

export default function ModelRegistry() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", environment: "dev" });
  const [submitting, setSubmitting] = useState(false);

  const user = getActiveUser();
  const canCreate = user?.roles?.some((r) => ["admin", "ml_engineer", "data_scientist"].includes(r));

  const loadModels = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchApi("/models");
      setModels(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadModels();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await fetchApi("/models", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setShowModal(false);
      setForm({ name: "", description: "", environment: "dev" });
      await loadModels();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {error && <div role="alert" className="text-rose-300">{error} <Button onClick={loadModels}>Retry</Button></div>}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-zinc-800/80">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Model Registry</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Track ML models, version performance metrics, lifecycle stages, and feature lineage.
          </p>
        </div>
        {canCreate && (
          <Button variant="primary" onClick={() => setShowModal(true)}>
            <Plus className="w-4 h-4" /> Register Model
          </Button>
        )}
      </div>

      {loading ? (
        <div className="py-20 text-center text-sm text-zinc-500">Loading models from registry…</div>
      ) : models.length === 0 ? (
        <div className="py-20 text-center text-sm text-zinc-500">
          No models registered yet. Click "Register Model" to add your first.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {models.map((m) => (
            <Card key={m.id} hover className="flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="p-2 rounded-lg bg-indigo-950/60 border border-indigo-800/40 text-indigo-400">
                    <Cpu className="w-5 h-5" />
                  </div>
                  <Badge variant={m.environment === "production" ? "success" : "default"}>
                    {m.environment}
                  </Badge>
                </div>
                <h3 className="text-base font-semibold text-zinc-100 tracking-tight">{m.name}</h3>
                <p className="text-xs text-zinc-400 mt-1.5 line-clamp-2">
                  {m.description || "No description specified."}
                </p>
              </div>

              <div className="mt-5 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs text-zinc-500">
                <span className="font-mono text-[11px]">
                  {m.created_at ? m.created_at.slice(0, 10) : "N/A"}
                </span>
                <Link
                  to={`/models/${m.id}`}
                  className="inline-flex items-center gap-1 font-medium text-emerald-400 hover:text-emerald-300 transition"
                >
                  Manage <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Modal: Register Model */}
      <Modal isOpen={showModal} title="Register New Model" onClose={() => setShowModal(false)}>
        <form onSubmit={handleCreate} className="space-y-4 text-xs">
          {error && <p role="alert" className="text-rose-300">{error}</p>}
          <div>
            <label className="block font-medium text-zinc-300 mb-1" htmlFor="modelregistry-field-1">Model Name</label>
            <input id="modelregistry-field-1"
              type="text"
              required
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              placeholder="e.g. Churn Risk Predictor"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="block font-medium text-zinc-300 mb-1" htmlFor="modelregistry-field-2">Description</label>
            <input id="modelregistry-field-2"
              type="text"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              placeholder="Model goal and prediction target"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div>
            <label className="block font-medium text-zinc-300 mb-1" htmlFor="modelregistry-field-3">Environment</label>
            <select id="modelregistry-field-3"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              value={form.environment}
              onChange={(e) => setForm({ ...form, environment: e.target.value })}
            >
              <option value="dev">Development (dev)</option>
              <option value="staging">Staging</option>
              <option value="production">Production</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
            <Button variant="secondary" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={submitting}>
              Register
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
