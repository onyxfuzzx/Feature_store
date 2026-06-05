import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchApi, getActiveUser } from "../api";
import { IconFeatures, IconCircle, IconArrowRight, IconLightning, IconCheck } from "../components/Icons";

function TabButton({ active, onClick, children }) {
  return (
    <button className={`tab-btn${active ? " active" : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}

function LineageCard({ lineage }) {
  return (
    <div className="lineage-card">
      <div className="lineage-source">
        <span className="lineage-icon" style={{ display: "inline-flex", alignItems: "center" }}>
          <IconFeatures style={{ width: "1.1em", height: "1.1em" }} />
        </span>
        <div>
          <div className="lineage-table-name">{lineage.source_table}</div>
          {lineage.source_columns_json && (
            <div className="subtle" style={{ fontSize: "0.78rem" }}>
              Columns: {lineage.source_columns_json}
            </div>
          )}
        </div>
      </div>
      <div className="lineage-arrow" style={{ display: "inline-flex", alignItems: "center" }}>
        <IconArrowRight />
      </div>
      <div className="lineage-feature">
        <span className="lineage-icon" style={{ display: "inline-flex", alignItems: "center" }}>
          <IconCircle style={{ width: "1.1em", height: "1.1em" }} />
        </span>
        <span>This Feature</span>
      </div>
    </div>
  );
}

export default function FeatureDetail() {
  const { id } = useParams();
  const [feature, setFeature] = useState(null);
  const [materializations, setMaterializations] = useState([]);
  const [values, setValues] = useState(null);
  const [lineage, setLineage] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("info");
  const [materializeLoading, setMaterializeLoading] = useState(false);
  const [materializeResult, setMaterializeResult] = useState(null);
  const [lineageForm, setLineageForm] = useState({ source_table: "", source_columns_json: "" });
  const [lineageSubmitting, setLineageSubmitting] = useState(false);

  // Validation Rules State
  const [valRules, setValRules] = useState({ min_value: "", max_value: "", allow_null: true, required_type: "" });
  const [savingRules, setSavingRules] = useState(false);
  const [saveRulesSuccess, setSaveRulesSuccess] = useState(false);

  const load = async () => {
    try {
      const [f, mats, lin] = await Promise.all([
        fetchApi(`/features/${id}`),
        fetchApi(`/features/${id}/materializations`),
        fetchApi(`/features/${id}/lineage`),
      ]);
      setFeature(f);
      setMaterializations(mats);
      setLineage(lin);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const loadValues = async () => {
    const v = await fetchApi(`/features/${id}/values`);
    setValues(v);
  };

  useEffect(() => {
    load();
  }, [id]);

  useEffect(() => {
    if (tab === "values" && !values) {
      loadValues();
    }
  }, [tab]);

  useEffect(() => {
    if (feature) {
      let rules = {};
      try {
        rules = JSON.parse(feature.validation_rules_json || "{}");
      } catch (e) {
        // ignore
      }
      setValRules({
        min_value: rules.min_value !== undefined ? rules.min_value : "",
        max_value: rules.max_value !== undefined ? rules.max_value : "",
        allow_null: rules.allow_null !== undefined ? rules.allow_null : true,
        required_type: rules.required_type || "",
      });
    }
  }, [feature]);

  const handleMaterialize = async () => {
    setMaterializeLoading(true);
    setMaterializeResult(null);
    try {
      const result = await fetchApi(`/features/${id}/materialize`, { method: "POST" });
      setMaterializeResult(result);
      await load();
    } catch (e) {
      setMaterializeResult({ error: e.message });
    } finally {
      setMaterializeLoading(false);
    }
  };

  const handleAddLineage = async (e) => {
    e.preventDefault();
    setLineageSubmitting(true);
    try {
      await fetchApi(`/features/${id}/lineage`, {
        method: "POST",
        body: JSON.stringify({
          source_table: lineageForm.source_table,
          source_columns_json: lineageForm.source_columns_json || null,
        }),
      });
      setLineageForm({ source_table: "", source_columns_json: "" });
      const lin = await fetchApi(`/features/${id}/lineage`);
      setLineage(lin);
    } catch {
      // ignore
    } finally {
      setLineageSubmitting(false);
    }
  };

  const handleSaveRules = async (e) => {
    e.preventDefault();
    setSavingRules(true);
    setSaveRulesSuccess(false);
    try {
      const rules = {
        allow_null: valRules.allow_null,
      };
      if (valRules.min_value !== "") rules.min_value = Number(valRules.min_value);
      if (valRules.max_value !== "") rules.max_value = Number(valRules.max_value);
      if (valRules.required_type !== "") rules.required_type = valRules.required_type;

      await fetchApi(`/features/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          validation_rules_json: JSON.stringify(rules),
        }),
      });
      setSaveRulesSuccess(true);
      await load();
      setTimeout(() => setSaveRulesSuccess(false), 3000);
    } catch (err) {
      alert("Failed to save rules: " + err.message);
    } finally {
      setSavingRules(false);
    }
  };

  if (loading) return <div className="loading-pulse">Loading feature…</div>;
  if (!feature) return <div className="error-alert">Feature not found.</div>;

  const badgeColor = feature.status === "active"
    ? { background: "rgba(90,219,195,0.18)", color: "#0d7a66" }
    : { background: "rgba(255,176,103,0.2)", color: "#b06000" };

  const activeUser = getActiveUser();
  const canEditRules = activeUser && (activeUser.roles.includes("admin") || activeUser.roles.includes("ml_engineer") || activeUser.roles.includes("data_scientist"));

  return (
    <section>
      <div className="page-header">
        <div>
          <h1 className="page-title">{feature.name}</h1>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span className="badge" style={badgeColor}>{feature.status}</span>
            <span className="code-tag">{feature.dtype}</span>
            <span className="subtle">Refresh: {feature.refresh_interval}</span>
          </div>
        </div>
        <button className="button" onClick={handleMaterialize} disabled={materializeLoading}>
          {materializeLoading ? (
            "Running…"
          ) : (
            <>
              <IconLightning /> Materialize Now
            </>
          )}
        </button>
      </div>

      {materializeResult && (
        <div className={`alert-box ${materializeResult.error ? "alert-error" : "alert-success"}`}>
          {materializeResult.error ? (
            `Error: ${materializeResult.error}`
          ) : (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <IconCheck /> Materialization {materializeResult.status} — {materializeResult.row_count ?? 0} rows written
            </span>
          )}
        </div>
      )}

      <div className="tab-bar">
        {["info", "validation", "lineage", "values", "history"].map((t) => (
          <TabButton key={t} active={tab === t} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </TabButton>
        ))}
      </div>

      {tab === "info" && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3 className="card-title">Definition</h3>
          {feature.description && <p className="subtle">{feature.description}</p>}
          <div style={{ marginTop: 16 }}>
            <div className="subtle" style={{ marginBottom: 6, fontWeight: 600 }}>Source SQL</div>
            <pre className="sql-block">{feature.source_sql}</pre>
          </div>
          <div className="meta-row" style={{ marginTop: 16 }}>
            <span className="subtle">Feature ID: <code>{feature.id}</code></span>
            <span className="subtle">Created: {feature.created_at?.slice(0, 16).replace("T", " ")}</span>
          </div>
        </div>
      )}

      {tab === "validation" && (
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card">
            <h3 className="card-title">Data Quality Rules</h3>
            <p className="subtle" style={{ marginBottom: 16 }}>
              Enforce schema validation rules on feature values during materialization and ingestion.
            </p>

            <form onSubmit={handleSaveRules} className="modal-form" style={{ padding: 0 }}>
              {saveRulesSuccess && (
                <div style={{ background: "rgba(22, 101, 52, 0.1)", border: "1px solid #16a34a", padding: 12, borderRadius: 6, color: "#16a34a", marginBottom: 12, fontSize: "0.88rem" }}>
                  Validation rules saved successfully!
                </div>
              )}
              <div className="form-row">
                <div className="form-group">
                  <label>Required Data Type</label>
                  <select
                    disabled={!canEditRules}
                    value={valRules.required_type}
                    onChange={(e) => setValRules({ ...valRules, required_type: e.target.value })}
                    style={{ width: "100%", padding: 8, background: "#1e1e1e", color: "#e0e0e0", border: "1px solid #333", borderRadius: 4 }}
                  >
                    <option value="">None (Infer from Definition)</option>
                    <option value="int">Integer</option>
                    <option value="float">Float/Decimal</option>
                    <option value="string">String/Text</option>
                    <option value="bool">Boolean</option>
                  </select>
                </div>
                <div className="form-group" style={{ display: "flex", alignItems: "center", height: "100%", marginTop: 24 }}>
                  <label style={{ display: "inline-flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                    <input
                      disabled={!canEditRules}
                      type="checkbox"
                      checked={valRules.allow_null}
                      onChange={(e) => setValRules({ ...valRules, allow_null: e.target.checked })}
                    />
                    Allow NULL values
                  </label>
                </div>
              </div>

              <div className="form-row" style={{ marginTop: 12 }}>
                <div className="form-group">
                  <label>Minimum Value (Numeric)</label>
                  <input
                    disabled={!canEditRules}
                    type="number"
                    step="any"
                    value={valRules.min_value}
                    onChange={(e) => setValRules({ ...valRules, min_value: e.target.value })}
                    placeholder="e.g. 0"
                  />
                </div>
                <div className="form-group">
                  <label>Maximum Value (Numeric)</label>
                  <input
                    disabled={!canEditRules}
                    type="number"
                    step="any"
                    value={valRules.max_value}
                    onChange={(e) => setValRules({ ...valRules, max_value: e.target.value })}
                    placeholder="e.g. 100"
                  />
                </div>
              </div>

              {canEditRules ? (
                <button type="submit" className="button" style={{ marginTop: 16 }} disabled={savingRules}>
                  {savingRules ? "Saving…" : "Save Rules"}
                </button>
              ) : (
                <div className="subtle" style={{ fontSize: "0.78rem", marginTop: 12 }}>
                  * You do not have permissions to edit validation rules. Admins or ML Engineers only.
                </div>
              )}
            </form>
          </div>
        </div>
      )}

      {tab === "lineage" && (
        <div style={{ marginTop: 16 }}>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3 className="card-title">Data Lineage</h3>
            {lineage.length === 0 ? (
              <p className="subtle">No lineage entries. Add source tables below.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {lineage.map((l) => <LineageCard key={l.id} lineage={l} />)}
              </div>
            )}
          </div>
          <div className="card">
            <h3 className="card-title">Add Source Table</h3>
            <form onSubmit={handleAddLineage} className="modal-form" style={{ padding: 0 }}>
              <div className="form-row">
                <div className="form-group">
                  <label>Source Table *</label>
                  <input
                    value={lineageForm.source_table}
                    onChange={(e) => setLineageForm({ ...lineageForm, source_table: e.target.value })}
                    required
                    placeholder="e.g. feature_store.sample_events"
                  />
                </div>
                <div className="form-group">
                  <label>Source Columns (optional)</label>
                  <input
                    value={lineageForm.source_columns_json}
                    onChange={(e) => setLineageForm({ ...lineageForm, source_columns_json: e.target.value })}
                    placeholder='["customer_id","amount"]'
                  />
                </div>
              </div>
              <button type="submit" className="button" disabled={lineageSubmitting}>
                {lineageSubmitting ? "Adding…" : "Add Lineage"}
              </button>
            </form>
          </div>
        </div>
      )}

      {tab === "values" && (
        <div style={{ marginTop: 16 }}>
          {!values && <div className="loading-pulse">Loading values…</div>}
          {values && (
            <>
              <div className="card" style={{ marginBottom: 16 }}>
                <h3 className="card-title">Online Store (latest per entity)</h3>
                <table className="table">
                  <thead><tr><th>Entity Key</th><th>Value</th><th>Event Time</th><th>Updated At</th></tr></thead>
                  <tbody>
                    {values.online.length === 0 && (
                      <tr><td colSpan={4} style={{ textAlign: "center", padding: 24, color: "#888" }}>No online values. Trigger materialization first.</td></tr>
                    )}
                    {values.online.map((v, i) => (
                      <tr key={i}>
                        <td><code>{v.entity_key}</code></td>
                        <td>{v.value}</td>
                        <td>{v.event_time?.slice(0, 16)}</td>
                        <td>{v.updated_at?.slice(0, 16)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="card">
                <h3 className="card-title">Offline Store (historical)</h3>
                <table className="table">
                  <thead><tr><th>Entity Key</th><th>Value</th><th>Event Time</th></tr></thead>
                  <tbody>
                    {values.offline.length === 0 && (
                      <tr><td colSpan={3} style={{ textAlign: "center", padding: 24, color: "#888" }}>No offline values.</td></tr>
                    )}
                    {values.offline.map((v, i) => (
                      <tr key={i}>
                        <td><code>{v.entity_key}</code></td>
                        <td>{v.value}</td>
                        <td>{v.event_time?.slice(0, 16)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {tab === "history" && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3 className="card-title">Materialization History</h3>
          <table className="table">
            <thead><tr><th>Status</th><th>Started</th><th>Finished</th><th>Rows</th><th>Error</th></tr></thead>
            <tbody>
              {materializations.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: "center", padding: 24, color: "#888" }}>No history yet.</td></tr>
              )}
              {materializations.map((m) => (
                <tr key={m.id}>
                  <td><span className="badge" style={{ color: m.status === "success" ? "#0d7a66" : m.status === "failed" ? "#c00" : "#b06000" }}>{m.status}</span></td>
                  <td>{m.started_at?.slice(0, 16).replace("T", " ")}</td>
                  <td>{m.finished_at?.slice(0, 16).replace("T", " ")}</td>
                  <td>{m.row_count ?? "—"}</td>
                  <td style={{ color: "#c00", fontSize: "0.8rem" }}>{m.error_message || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
