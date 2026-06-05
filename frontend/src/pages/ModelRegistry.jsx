import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchApi } from "../api";
import { IconClose, IconArrowRight } from "../components/Icons";
import { exportToCsv, exportToJson } from "../utils/export";

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

function envColor(env) {
  if (env === "prod" || env === "production") return "rgba(225, 29, 72, 0.15)";
  if (env === "staging") return "rgba(217, 119, 6, 0.15)";
  return "rgba(2, 132, 199, 0.15)";
}

function envText(env) {
  if (env === "prod" || env === "production") return { color: "#e11d48", text: "Production" };
  if (env === "staging") return { color: "#d97706", text: "Staging" };
  return { color: "#0284c7", text: "Development" };
}

export default function ModelRegistry() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", environment: "dev" });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [filterEnv, setFilterEnv] = useState("all");
  const [filterSearch, setFilterSearch] = useState("");

  const load = async () => {
    try {
      const data = await fetchApi("/models");
      setModels(data);
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
    setSubmitError(null);
    try {
      await fetchApi("/models", { method: "POST", body: JSON.stringify(form) });
      setShowModal(false);
      setForm({ name: "", description: "", environment: "dev" });
      await load();
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const filtered = models.filter((m) => {
    const envMatch = filterEnv === "all" || m.environment === filterEnv;
    const qMatch = !filterSearch || m.name.toLowerCase().includes(filterSearch.toLowerCase());
    return envMatch && qMatch;
  });

  const exportRegistry = (format) => {
    const dataToExport = filtered.map(m => ({
      id: m.id,
      name: m.name,
      environment: m.environment || "dev",
      description: m.description || "—",
      created_at: m.created_at,
    }));
    if (format === "csv") {
      exportToCsv(
        "model_registry.csv",
        ["ID", "Name", "Environment", "Description", "Created At"],
        dataToExport,
        row => [row.id, row.name, row.environment, row.description, row.created_at]
      );
    } else {
      exportToJson("model_registry.json", dataToExport);
    }
  };

  return (
    <section>
      <div className="page-header">
        <div>
          <h1 className="page-title">Model Registry</h1>
          <p className="subtle">Register, version, and promote your ML models.</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="button button-outline" onClick={() => exportRegistry("csv")} style={{ background: "transparent", border: "1px solid #444", color: "#e0e0e0" }}>Export CSV</button>
          <button className="button button-outline" onClick={() => exportRegistry("json")} style={{ background: "transparent", border: "1px solid #444", color: "#e0e0e0" }}>Export JSON</button>
          <button className="button" onClick={() => setShowModal(true)}>+ Register Model</button>
        </div>
      </div>

      {loading && <div className="loading-pulse">Loading models…</div>}

      {!loading && (
        <>
          <div className="filter-bar" style={{ marginBottom: 16 }}>
            <input
              className="filter-input"
              placeholder="Search models…"
              value={filterSearch}
              onChange={(e) => setFilterSearch(e.target.value)}
            />
            <select className="filter-select" value={filterEnv} onChange={(e) => setFilterEnv(e.target.value)}>
              <option value="all">All Environments</option>
              <option value="dev">Development</option>
              <option value="staging">Staging</option>
              <option value="prod">Production</option>
            </select>
            <span className="subtle">{filtered.length} model{filtered.length !== 1 ? "s" : ""}</span>
          </div>

          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Model Name</th>
                  <th>Environment</th>
                  <th>Description</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: "center", padding: 32, color: "#888" }}>No models found.</td></tr>
                )}
                {filtered.map((m) => {
                  const envDetails = envText(m.environment || "dev");
                  return (
                    <tr key={m.id} className="table-row-hover">
                      <td><strong>{m.name}</strong></td>
                      <td>
                        <span className="badge" style={{ background: envColor(m.environment || "dev"), color: envDetails.color }}>
                          {envDetails.text}
                        </span>
                      </td>
                      <td className="subtle">{m.description || "—"}</td>
                      <td className="subtle">{m.created_at?.slice(0, 10)}</td>
                      <td><Link to={`/models/${m.id}`} className="table-link" style={{ display: "inline-flex", alignItems: "center" }}>Versions <IconArrowRight style={{ marginLeft: 4 }} /></Link></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {showModal && (
        <Modal title="Register Model" onClose={() => setShowModal(false)}>
          <form onSubmit={handleCreate} className="modal-form">
            {submitError && <div className="error-alert">{submitError}</div>}
            <div className="form-group">
              <label>Model Name *</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder="e.g. Churn Predictor" />
            </div>
            <div className="form-group">
              <label>Environment *</label>
              <select value={form.environment} onChange={(e) => setForm({ ...form, environment: e.target.value })}>
                <option value="dev">Development</option>
                <option value="staging">Staging</option>
                <option value="prod">Production</option>
              </select>
            </div>
            <div className="form-group">
              <label>Description</label>
              <textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What does this model do?" />
            </div>
            <div className="modal-actions">
              <button type="button" className="button button-outline" onClick={() => setShowModal(false)}>Cancel</button>
              <button type="submit" className="button" disabled={submitting}>{submitting ? "Registering…" : "Register Model"}</button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
