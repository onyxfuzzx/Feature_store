import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchApi } from "../api";
import { IconClose, IconArrowRight, IconLightning, IconCheck } from "../components/Icons";

const STAGES = ["Staging", "Production", "Archived"];

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

function stagePillStyle(stage) {
  if (stage === "Production") return { background: "rgba(90,219,195,0.18)", color: "#0d7a66" };
  if (stage === "Staging") return { background: "rgba(255,176,103,0.2)", color: "#b06000" };
  return { background: "rgba(200,200,200,0.2)", color: "#666" };
}

function TabButton({ active, onClick, children }) {
  return (
    <button className={`tab-btn${active ? " active" : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}

function DriftChart({ history, thresholdNo, thresholdMod }) {
  const maxPsi = 0.3;
  const points = history.map((h, index) => {
    const x = (index / (history.length - 1)) * 260 + 20;
    const y = 100 - (h.psi / maxPsi) * 80 - 10;
    return { x, y, psi: h.psi, date: h.date };
  });

  const pathD = points.reduce((acc, p, i) => {
    return i === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`;
  }, "");

  const areaD = pathD ? `${pathD} L ${points[points.length - 1].x} 90 L ${points[0].x} 90 Z` : "";

  const yNo = 100 - (thresholdNo / maxPsi) * 80 - 10;
  const yMod = 100 - (thresholdMod / maxPsi) * 80 - 10;

  return (
    <div style={{ width: "100%", position: "relative" }}>
      <svg viewBox="0 0 300 100" style={{ width: "100%", height: 120, background: "#1b1b1f", borderRadius: 6 }}>
        <line x1="10" y1={yNo} x2="290" y2={yNo} stroke="rgba(217, 119, 6, 0.3)" strokeDasharray="3,3" strokeWidth={1} />
        <line x1="10" y1={yMod} x2="290" y2={yMod} stroke="rgba(225, 29, 72, 0.3)" strokeDasharray="3,3" strokeWidth={1} />
        
        {areaD && <path d={areaD} fill="url(#driftGradient)" opacity={0.15} />}
        {pathD && <path d={pathD} fill="none" stroke="#6366f1" strokeWidth={2} />}

        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={3} fill="#a5b4fc" />
        ))}

        <defs>
          <linearGradient id="driftGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
          </linearGradient>
        </defs>
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68rem", color: "#888", marginTop: 4, padding: "0 6px" }}>
        <span>{history[0].date}</span>
        <span>{history[history.length - 1].date}</span>
      </div>
    </div>
  );
}

export default function ModelDetail() {
  const { id } = useParams();
  const [model, setModel] = useState(null);
  const [versions, setVersions] = useState([]);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [versionDetail, setVersionDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  
  const [mainTab, setMainTab] = useState("details");
  const [driftData, setDriftData] = useState(null);
  const [loadingDrift, setLoadingDrift] = useState(false);

  const [showVersionModal, setShowVersionModal] = useState(false);
  const [showLineageModal, setShowLineageModal] = useState(false);
  const [promotingTo, setPromotingTo] = useState("");
  const [promoting, setPromoting] = useState(false);
  
  const [versionForm, setVersionForm] = useState({
    version: "", stage: "Staging", metrics_json: "", params_json: "", artifact_uri: ""
  });
  const [lineageForm, setLineageForm] = useState({ feature_ids_json: "", dataset_uri: "" });
  
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const load = async () => {
    try {
      const [m, v] = await Promise.all([
        fetchApi(`/models/${id}`),
        fetchApi(`/models/${id}/versions`),
      ]);
      setModel(m);
      setVersions(v);
      if (v.length > 0) {
        await selectVersion(v[0]);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const loadDrift = async () => {
    setLoadingDrift(true);
    try {
      const data = await fetchApi(`/models/${id}/drift`);
      setDriftData(data);
    } catch {
      // ignore
    } finally {
      setLoadingDrift(false);
    }
  };

  const selectVersion = async (ver) => {
    setSelectedVersion(ver);
    try {
      const detail = await fetchApi(`/models/versions/${ver.id}/detail`);
      setVersionDetail(detail);
      setPromotingTo(ver.stage);
    } catch {
      setVersionDetail(null);
    }
  };

  useEffect(() => { load(); }, [id]);

  useEffect(() => {
    if (mainTab === "monitoring") {
      loadDrift();
    }
  }, [mainTab]);

  const handleCreateVersion = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = {
        ...versionForm,
        metrics_json: versionForm.metrics_json || null,
        params_json: versionForm.params_json || null,
        artifact_uri: versionForm.artifact_uri || null,
      };
      await fetchApi(`/models/${id}/versions`, { method: "POST", body: JSON.stringify(payload) });
      setShowVersionModal(false);
      setVersionForm({ version: "", stage: "Staging", metrics_json: "", params_json: "", artifact_uri: "" });
      await load();
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handlePromote = async () => {
    if (!selectedVersion || !promotingTo) return;
    setPromoting(true);
    try {
      await fetchApi(`/models/${id}/versions/${selectedVersion.id}/stage`, {
        method: "POST",
        body: JSON.stringify({ to_stage: promotingTo }),
      });
      await load();
    } catch {
      // ignore
    } finally {
      setPromoting(false);
    }
  };

  const handleSaveLineage = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await fetchApi(`/models/versions/${selectedVersion.id}/lineage`, {
        method: "POST",
        body: JSON.stringify({
          feature_ids_json: lineageForm.feature_ids_json || null,
          dataset_uri: lineageForm.dataset_uri || null,
        }),
      });
      setShowLineageModal(false);
      await selectVersion(selectedVersion);
    } catch {
      // ignore
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="loading-pulse">Loading model…</div>;
  if (!model) return <div className="error-alert">Model not found.</div>;

  const envText = model.environment === "prod" ? "Production" : model.environment === "staging" ? "Staging" : "Development";

  return (
    <section>
      <div className="page-header">
        <div>
          <h1 className="page-title">{model.name}</h1>
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 4 }}>
            <span className="badge" style={
              model.environment === "prod"
                ? { background: "rgba(225,29,72,0.15)", color: "#e11d48" }
                : model.environment === "staging"
                ? { background: "rgba(217,119,6,0.15)", color: "#d97706" }
                : { background: "rgba(2,132,199,0.15)", color: "#0284c7" }
            }>
              {envText}
            </span>
            <span className="subtle">{model.description || "No description."}</span>
          </div>
        </div>
        {mainTab === "details" && (
          <button className="button" onClick={() => setShowVersionModal(true)}>+ Add Version</button>
        )}
      </div>

      <div className="tab-bar" style={{ marginBottom: 16 }}>
        <TabButton active={mainTab === "details"} onClick={() => setMainTab("details")}>Model Versions</TabButton>
        <TabButton active={mainTab === "monitoring"} onClick={() => setMainTab("monitoring")}>Drift Monitoring</TabButton>
      </div>

      {mainTab === "details" && (
        <div className="model-detail-layout">
          {/* Version Selector */}
          <div className="card version-list-card">
            <h3 className="card-title">Versions</h3>
            {versions.length === 0 && <p className="subtle">No versions yet.</p>}
            {versions.map((v) => (
              <div
                key={v.id}
                className={`version-item${selectedVersion?.id === v.id ? " selected" : ""}`}
                onClick={() => selectVersion(v)}
              >
                <div>
                  <strong>v{v.version}</strong>
                  <div className="subtle" style={{ fontSize: "0.78rem" }}>
                    {v.created_at?.slice(0, 10)}
                  </div>
                </div>
                <span className="badge" style={stagePillStyle(v.stage)}>{v.stage}</span>
              </div>
            ))}
          </div>

          {/* Version Detail Panel */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
            {!selectedVersion && (
              <div className="card">
                <p className="subtle">Select a version to inspect.</p>
              </div>
            )}

            {selectedVersion && versionDetail && (
              <>
                {/* Stage Promotion */}
                <div className="card">
                  <h3 className="card-title">Stage Promotion</h3>
                  <div className="promote-row">
                    <div>
                      <span className="subtle">Current: </span>
                      <span className="badge" style={stagePillStyle(selectedVersion.stage)}>{selectedVersion.stage}</span>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <select
                        className="filter-select"
                        value={promotingTo}
                        onChange={(e) => setPromotingTo(e.target.value)}
                      >
                        {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                      <button className="button" onClick={handlePromote} disabled={promoting || promotingTo === selectedVersion.stage}>
                        {promoting ? (
                          "Promoting…"
                        ) : (
                          <>
                            Promote <IconArrowRight style={{ marginLeft: 4 }} />
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Metrics & Params */}
                <div className="grid-two">
                  <div className="card">
                    <h3 className="card-title">Metrics</h3>
                    {versionDetail.metrics_json ? (
                      <pre className="sql-block">{JSON.stringify(JSON.parse(versionDetail.metrics_json), null, 2)}</pre>
                    ) : <p className="subtle">No metrics.</p>}
                  </div>
                  <div className="card">
                    <h3 className="card-title">Parameters</h3>
                    {versionDetail.params_json ? (
                      <pre className="sql-block">{JSON.stringify(JSON.parse(versionDetail.params_json), null, 2)}</pre>
                    ) : <p className="subtle">No parameters.</p>}
                  </div>
                </div>

                {/* Artifact URI */}
                {versionDetail.artifact_uri && (
                  <div className="card">
                    <h3 className="card-title">Artifact</h3>
                    <code className="code-tag">{versionDetail.artifact_uri}</code>
                  </div>
                )}

                {/* Lineage */}
                <div className="card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <h3 className="card-title" style={{ margin: 0 }}>Lineage</h3>
                    <button className="button button-sm" onClick={() => setShowLineageModal(true)}>Edit</button>
                  </div>
                  {versionDetail.lineage.length === 0 ? (
                    <p className="subtle">No lineage linked.</p>
                  ) : (
                    versionDetail.lineage.map((l) => (
                      <div key={l.id} className="lineage-card" style={{ marginBottom: 8 }}>
                        <div>
                          {l.dataset_uri && <div><span className="subtle">Dataset: </span><code>{l.dataset_uri}</code></div>}
                          {l.feature_ids_json && <div><span className="subtle">Features: </span><code>{l.feature_ids_json}</code></div>}
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Stage History */}
                <div className="card">
                  <h3 className="card-title">Stage History</h3>
                  {versionDetail.stage_history.length === 0 ? (
                    <p className="subtle">No stage changes recorded.</p>
                  ) : (
                    <table className="table">
                      <thead><tr><th>From</th><th>To</th><th>Changed At</th></tr></thead>
                      <tbody>
                        {versionDetail.stage_history.map((h) => (
                          <tr key={h.id}>
                            <td><span className="badge" style={stagePillStyle(h.from_stage)}>{h.from_stage}</span></td>
                            <td><span className="badge" style={stagePillStyle(h.to_stage)}>{h.to_stage}</span></td>
                            <td className="subtle">{h.changed_at?.slice(0, 16).replace("T", " ")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {mainTab === "monitoring" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {loadingDrift && <div className="loading-pulse">Calculating feature drift metrics…</div>}
          {!loadingDrift && driftData && (
            <>
              {/* Drift Summary Panel */}
              <div className="card" style={{ display: "flex", flexDirection: "row", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
                <div style={{ flex: 1, minWidth: 250 }}>
                  <h3 className="card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    Model Health Status:
                    {driftData.metrics.some(m => m.drift_detected) ? (
                      <span className="badge" style={{ background: "rgba(225,29,72,0.15)", color: "#e11d48", padding: "4px 12px" }}>Warning (Drift Detected)</span>
                    ) : (
                      <span className="badge" style={{ background: "rgba(90,219,195,0.18)", color: "#0d7a66", padding: "4px 12px" }}>Healthy</span>
                    )}
                  </h3>
                  <p className="subtle">
                    We track population distribution changes of model input features. Population Stability Index (PSI) values above 0.2 indicate significant feature drift.
                  </p>
                </div>
                <div style={{ display: "flex", gap: 16 }}>
                  <div style={{ padding: "12px 20px", background: "#1b1b1f", borderRadius: 8, textAlign: "center", border: "1px solid #333" }}>
                    <div className="subtle" style={{ fontSize: "0.75rem" }}>Moderate Threshold</div>
                    <strong style={{ color: "#d97706", fontSize: "1.2rem" }}>&gt; {driftData.thresholds.no_drift}</strong>
                  </div>
                  <div style={{ padding: "12px 20px", background: "#1b1b1f", borderRadius: 8, textAlign: "center", border: "1px solid #333" }}>
                    <div className="subtle" style={{ fontSize: "0.75rem" }}>High/Action Threshold</div>
                    <strong style={{ color: "#e11d48", fontSize: "1.2rem" }}>&gt; {driftData.thresholds.moderate_drift}</strong>
                  </div>
                </div>
              </div>

              {/* Drift Charts Grid */}
              <div className="grid-two">
                {driftData.metrics.map((m) => (
                  <div key={m.feature} className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <h4 style={{ margin: 0, fontSize: "0.95rem" }}><code>{m.feature}</code></h4>
                      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                        <span className="subtle" style={{ fontSize: "0.78rem" }}>PSI: <strong>{m.current_psi}</strong></span>
                        {m.drift_detected ? (
                          <span className="badge" style={{ background: "rgba(225,29,72,0.15)", color: "#e11d48", fontSize: "0.7rem" }}>DRIFTED</span>
                        ) : (
                          <span className="badge" style={{ background: "rgba(90,219,195,0.18)", color: "#0d7a66", fontSize: "0.7rem" }}>OK</span>
                        )}
                      </div>
                    </div>
                    
                    <DriftChart
                      history={m.history}
                      thresholdNo={driftData.thresholds.no_drift}
                      thresholdMod={driftData.thresholds.moderate_drift}
                    />
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {showVersionModal && (
        <Modal title="Add Model Version" onClose={() => setShowVersionModal(false)}>
          <form onSubmit={handleCreateVersion} className="modal-form">
            {submitError && <div className="error-alert">{submitError}</div>}
            <div className="form-row">
              <div className="form-group">
                <label>Version * (e.g. 1.0)</label>
                <input value={versionForm.version} onChange={(e) => setVersionForm({ ...versionForm, version: e.target.value })} required placeholder="1.0" />
              </div>
              <div className="form-group">
                <label>Initial Stage</label>
                <select value={versionForm.stage} onChange={(e) => setVersionForm({ ...versionForm, stage: e.target.value })}>
                  {STAGES.map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Metrics JSON (e.g. {`{"roc_auc": 0.92}`})</label>
              <textarea rows={2} value={versionForm.metrics_json} onChange={(e) => setVersionForm({ ...versionForm, metrics_json: e.target.value })} placeholder='{"roc_auc": 0.92, "precision": 0.88}' className="code-textarea" />
            </div>
            <div className="form-group">
              <label>Parameters JSON</label>
              <textarea rows={2} value={versionForm.params_json} onChange={(e) => setVersionForm({ ...versionForm, params_json: e.target.value })} placeholder='{"max_depth": 6, "n_estimators": 200}' className="code-textarea" />
            </div>
            <div className="form-group">
              <label>Artifact URI</label>
              <input value={versionForm.artifact_uri} onChange={(e) => setVersionForm({ ...versionForm, artifact_uri: e.target.value })} placeholder="s3://bucket/models/v1/model.pkl" />
            </div>
            <div className="modal-actions">
              <button type="button" className="button button-outline" onClick={() => setShowVersionModal(false)}>Cancel</button>
              <button type="submit" className="button" disabled={submitting}>{submitting ? "Saving…" : "Add Version"}</button>
            </div>
          </form>
        </Modal>
      )}

      {showLineageModal && (
        <Modal title="Edit Version Lineage" onClose={() => setShowLineageModal(false)}>
          <form onSubmit={handleSaveLineage} className="modal-form">
            <div className="form-group">
              <label>Feature IDs JSON (array of UUIDs)</label>
              <input value={lineageForm.feature_ids_json} onChange={(e) => setLineageForm({ ...lineageForm, feature_ids_json: e.target.value })} placeholder='["uuid1","uuid2"]' />
            </div>
            <div className="form-group">
              <label>Dataset URI</label>
              <input value={lineageForm.dataset_uri} onChange={(e) => setLineageForm({ ...lineageForm, dataset_uri: e.target.value })} placeholder="s3://bucket/dataset.csv" />
            </div>
            <div className="modal-actions">
              <button type="button" className="button button-outline" onClick={() => setShowLineageModal(false)}>Cancel</button>
              <button type="submit" className="button" disabled={submitting}>{submitting ? "Saving…" : "Save Lineage"}</button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
