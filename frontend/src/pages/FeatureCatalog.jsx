import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchApi } from "../api";
import { IconClose, IconArrowRight } from "../components/Icons";
import { exportToCsv, exportToJson } from "../utils/export";

function statusBadgeStyle(s) {
  if (s === "active") return { background: "rgba(90,219,195,0.18)", color: "#0d7a66" };
  if (s === "draft") return { background: "rgba(255,176,103,0.2)", color: "#b06000" };
  return { background: "rgba(200,200,200,0.2)", color: "#444" };
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

export default function FeatureCatalog() {
  const [groups, setGroups] = useState([]);
  const [features, setFeatures] = useState([]);
  const [filterGroup, setFilterGroup] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterEnv, setFilterEnv] = useState("all");
  const [filterSearch, setFilterSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [showGroupModal, setShowGroupModal] = useState(false);
  const [showFeatureModal, setShowFeatureModal] = useState(false);
  const [groupForm, setGroupForm] = useState({ name: "", description: "", tags_json: "", environment: "dev" });
  const [featureForm, setFeatureForm] = useState({
    group_id: "", name: "", dtype: "float", description: "", source_sql: "", refresh_interval: "daily", status: "draft"
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const load = async () => {
    try {
      const [g, f] = await Promise.all([
        fetchApi("/features/groups"),
        fetchApi("/features"),
      ]);
      setGroups(g);
      setFeatures(f);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const filtered = features.filter((f) => {
    const groupOfFeature = groups.find((g) => g.id === f.group_id);
    const envMatch = filterEnv === "all" || (groupOfFeature && groupOfFeature.environment === filterEnv);
    const gMatch = filterGroup === "all" || f.group_id === filterGroup;
    const sMatch = filterStatus === "all" || f.status === filterStatus;
    const qMatch = !filterSearch || f.name.toLowerCase().includes(filterSearch.toLowerCase());
    return envMatch && gMatch && sMatch && qMatch;
  });

  const groupById = Object.fromEntries(groups.map((g) => [g.id, g.name]));
  const groupEnvMap = Object.fromEntries(groups.map((g) => [g.id, g.environment]));

  const handleCreateGroup = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      await fetchApi("/features/groups", {
        method: "POST",
        body: JSON.stringify({
          ...groupForm,
          tags_json: groupForm.tags_json || null,
        }),
      });
      setShowGroupModal(false);
      setGroupForm({ name: "", description: "", tags_json: "", environment: "dev" });
      await load();
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateFeature = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      await fetchApi("/features", {
        method: "POST",
        body: JSON.stringify(featureForm),
      });
      setShowFeatureModal(false);
      setFeatureForm({ group_id: "", name: "", dtype: "float", description: "", source_sql: "", refresh_interval: "daily", status: "draft" });
      await load();
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const exportCatalog = (format) => {
    const dataToExport = filtered.map(f => ({
      id: f.id,
      name: f.name,
      group: groupById[f.group_id] || "—",
      environment: groupEnvMap[f.group_id] || "dev",
      dtype: f.dtype,
      status: f.status,
      refresh_interval: f.refresh_interval,
      created_at: f.created_at,
    }));
    if (format === "csv") {
      exportToCsv(
        "feature_catalog.csv",
        ["ID", "Name", "Group", "Environment", "Data Type", "Status", "Refresh Interval", "Created At"],
        dataToExport,
        row => [row.id, row.name, row.group, row.environment, row.dtype, row.status, row.refresh_interval, row.created_at]
      );
    } else {
      exportToJson("feature_catalog.json", dataToExport);
    }
  };

  return (
    <section>
      <div className="page-header">
        <div>
          <h1 className="page-title">Feature Catalog</h1>
          <p className="subtle">Define, track, and govern ML features across your platform.</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="button button-outline" onClick={() => exportCatalog("csv")} style={{ background: "transparent", border: "1px solid #444", color: "#e0e0e0" }}>Export CSV</button>
          <button className="button button-outline" onClick={() => exportCatalog("json")} style={{ background: "transparent", border: "1px solid #444", color: "#e0e0e0" }}>Export JSON</button>
          <button className="button button-outline" onClick={() => setShowGroupModal(true)}>+ Group</button>
          <button className="button" onClick={() => setShowFeatureModal(true)}>+ Feature</button>
        </div>
      </div>

      {loading && <div className="loading-pulse">Loading features…</div>}
      {error && <div className="error-alert">{error}</div>}

      {!loading && (
        <>
          <div className="filter-bar">
            <input
              className="filter-input"
              placeholder="Search by name…"
              value={filterSearch}
              onChange={(e) => setFilterSearch(e.target.value)}
            />
            <select className="filter-select" value={filterGroup} onChange={(e) => setFilterGroup(e.target.value)}>
              <option value="all">All Groups</option>
              {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
            <select className="filter-select" value={filterEnv} onChange={(e) => setFilterEnv(e.target.value)}>
              <option value="all">All Environments</option>
              <option value="dev">Development</option>
              <option value="staging">Staging</option>
              <option value="prod">Production</option>
            </select>
            <select className="filter-select" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="draft">Draft</option>
              <option value="deprecated">Deprecated</option>
            </select>
            <span className="subtle">{filtered.length} result{filtered.length !== 1 ? "s" : ""}</span>
          </div>

          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Group</th>
                  <th>Environment</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Refresh</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr><td colSpan={8} style={{ textAlign: "center", padding: "32px", color: "#888" }}>No features found.</td></tr>
                )}
                {filtered.map((f) => {
                  const env = groupEnvMap[f.group_id] || "dev";
                  const envDetails = envText(env);
                  return (
                    <tr key={f.id} className="table-row-hover">
                      <td><strong>{f.name}</strong></td>
                      <td>{groupById[f.group_id] || "—"}</td>
                      <td>
                        <span className="badge" style={{ background: envColor(env), color: envDetails.color }}>
                          {envDetails.text}
                        </span>
                      </td>
                      <td><code className="code-tag">{f.dtype}</code></td>
                      <td><span className="badge" style={statusBadgeStyle(f.status)}>{f.status}</span></td>
                      <td>{f.refresh_interval}</td>
                      <td>{f.created_at?.slice(0, 10)}</td>
                      <td><Link to={`/features/${f.id}`} className="table-link" style={{ display: "inline-flex", alignItems: "center" }}>View <IconArrowRight style={{ marginLeft: 4 }} /></Link></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {showGroupModal && (
        <Modal title="Create Feature Group" onClose={() => setShowGroupModal(false)}>
          <form onSubmit={handleCreateGroup} className="modal-form">
            {submitError && <div className="error-alert">{submitError}</div>}
            <div className="form-group">
              <label>Group Name *</label>
              <input value={groupForm.name} onChange={(e) => setGroupForm({ ...groupForm, name: e.target.value })} required placeholder="e.g. Payments" />
            </div>
            <div className="form-group">
              <label>Environment *</label>
              <select value={groupForm.environment} onChange={(e) => setGroupForm({ ...groupForm, environment: e.target.value })}>
                <option value="dev">Development</option>
                <option value="staging">Staging</option>
                <option value="prod">Production</option>
              </select>
            </div>
            <div className="form-group">
              <label>Description</label>
              <textarea value={groupForm.description} onChange={(e) => setGroupForm({ ...groupForm, description: e.target.value })} placeholder="What features belong to this group?" rows={3} />
            </div>
            <div className="form-group">
              <label>Tags (JSON array, e.g. ["payments","core"])</label>
              <input value={groupForm.tags_json} onChange={(e) => setGroupForm({ ...groupForm, tags_json: e.target.value })} placeholder='["tag1","tag2"]' />
            </div>
            <div className="modal-actions">
              <button type="button" className="button button-outline" onClick={() => setShowGroupModal(false)}>Cancel</button>
              <button type="submit" className="button" disabled={submitting}>{submitting ? "Creating…" : "Create Group"}</button>
            </div>
          </form>
        </Modal>
      )}

      {showFeatureModal && (
        <Modal title="Define New Feature" onClose={() => setShowFeatureModal(false)}>
          <form onSubmit={handleCreateFeature} className="modal-form">
            {submitError && <div className="error-alert">{submitError}</div>}
            <div className="form-row">
              <div className="form-group">
                <label>Feature Name *</label>
                <input value={featureForm.name} onChange={(e) => setFeatureForm({ ...featureForm, name: e.target.value })} required placeholder="e.g. customer_30d_spend" />
              </div>
              <div className="form-group">
                <label>Group *</label>
                <select value={featureForm.group_id} onChange={(e) => setFeatureForm({ ...featureForm, group_id: e.target.value })} required>
                  <option value="">Select group</option>
                  {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Data Type *</label>
                <select value={featureForm.dtype} onChange={(e) => setFeatureForm({ ...featureForm, dtype: e.target.value })}>
                  <option value="float">float</option>
                  <option value="int">int</option>
                  <option value="string">string</option>
                  <option value="bool">bool</option>
                </select>
              </div>
              <div className="form-group">
                <label>Refresh Interval *</label>
                <select value={featureForm.refresh_interval} onChange={(e) => setFeatureForm({ ...featureForm, refresh_interval: e.target.value })}>
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Description</label>
              <input value={featureForm.description} onChange={(e) => setFeatureForm({ ...featureForm, description: e.target.value })} placeholder="What does this feature measure?" />
            </div>
            <div className="form-group">
              <label>Source SQL * (must return: entity_key, value, event_time)</label>
              <textarea
                value={featureForm.source_sql}
                onChange={(e) => setFeatureForm({ ...featureForm, source_sql: e.target.value })}
                required
                rows={4}
                placeholder="SELECT customer_id AS entity_key, SUM(amount) AS value, MAX(event_time) AS event_time FROM feature_store.sample_events GROUP BY customer_id"
                className="code-textarea"
              />
            </div>
            <div className="form-group">
              <label>Status</label>
              <select value={featureForm.status} onChange={(e) => setFeatureForm({ ...featureForm, status: e.target.value })}>
                <option value="draft">Draft</option>
                <option value="active">Active</option>
              </select>
            </div>
            <div className="modal-actions">
              <button type="button" className="button button-outline" onClick={() => setShowFeatureModal(false)}>Cancel</button>
              <button type="submit" className="button" disabled={submitting}>{submitting ? "Creating…" : "Create Feature"}</button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
