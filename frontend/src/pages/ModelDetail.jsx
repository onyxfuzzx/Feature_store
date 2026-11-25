import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchAllApi, fetchApi, getActiveUser } from "../api";
import { Card, CardHeader } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import LineageGraph from "../components/LineageGraph";
import ModelDriftPanel from "../components/ModelDriftPanel";
import ModelVersionAssets from "../components/ModelVersionAssets";
import { Plus, Send } from "lucide-react";

export default function ModelDetail() {
  const { id } = useParams();
  const [model, setModel] = useState(null);
  const [versions, setVersions] = useState([]);
  const [lineageGraph, setLineageGraph] = useState(null);
  const [history, setHistory] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("versions");

  // Promote Modal
  const [showPromoteModal, setShowPromoteModal] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [promoteStage, setPromoteStage] = useState("Production");
  const [promoting, setPromoting] = useState(false);

  // New Version Modal
  const [showVersionModal, setShowVersionModal] = useState(false);
  const [versionForm, setVersionForm] = useState({
    version: "",
    stage: "Staging",
    metrics_json: '{"roc_auc": 0.92, "precision": 0.88}',
    params_json: '{"n_estimators": 200, "max_depth": 6}',
  });
  const [submittingVersion, setSubmittingVersion] = useState(false);

  // Inference Proxy Bench
  const [predictKey, setPredictKey] = useState("cust_001");
  const [predictResult, setPredictResult] = useState(null);
  const [predicting, setPredicting] = useState(false);
  const [runtimeInput, setRuntimeInput] = useState("{}");
  const [predictVersion, setPredictVersion] = useState("");

  const user = getActiveUser();
  const canEdit = user?.roles?.some((r) =>
    ["admin", "ml_engineer"].includes(r),
  );
  const canRegister = user?.roles?.some((r) =>
    ["admin", "ml_engineer", "data_scientist"].includes(r),
  );

  const loadData = useCallback(async () => {
    try {
      setError(null);
      setLoading(true);
      const [m, v, lin] = await Promise.all([
        fetchApi(`/models/${id}`),
        fetchAllApi(`/models/${id}/versions`),
        fetchApi(`/models/${id}/lineage-graph`).catch(() => null),
      ]);
      setModel(m);
      setVersions(v);
      setLineageGraph(lin);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  const showHistory = async (version) => {
    try {
      const detail = await fetchApi(`/models/versions/${version.id}/detail`);
      setHistory({ version: version.version, rows: detail.stage_history });
    } catch (err) {
      setError(err.message);
    }
  };

  const handlePredict = async () => {
    if (!predictKey.trim()) return;
    setPredicting(true);
    setPredictResult(null);
    try {
      const res = await fetchApi(`/models/${id}/predict`, {
        method: "POST",
        body: JSON.stringify({
          entity_key: predictKey,
          runtime_features: JSON.parse(runtimeInput),
          version: predictVersion || undefined,
        }),
      });
      setPredictResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setPredicting(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handlePromote = async (e) => {
    e.preventDefault();
    if (!selectedVersion) return;
    setPromoting(true);
    try {
      await fetchApi(`/models/${id}/versions/${selectedVersion.id}/stage`, {
        method: "POST",
        body: JSON.stringify({ to_stage: promoteStage }),
      });
      setShowPromoteModal(false);
      await loadData();
      await showHistory(selectedVersion);
    } catch (err) {
      setError(err.message);
    } finally {
      setPromoting(false);
    }
  };

  const handleCreateVersion = async (e) => {
    e.preventDefault();
    setSubmittingVersion(true);
    try {
      await fetchApi(`/models/${id}/versions`, {
        method: "POST",
        body: JSON.stringify(versionForm),
      });
      setShowVersionModal(false);
      setVersionForm({
        version: "",
        stage: "Staging",
        metrics_json: '{"roc_auc": 0.92, "precision": 0.88}',
        params_json: '{"n_estimators": 200, "max_depth": 6}',
      });
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmittingVersion(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-sm text-zinc-500">
        Loading model details…
      </div>
    );
  }

  if (!model) {
    return (
      <div className="py-20 text-center text-sm text-zinc-500">
        <span role="alert">{error || "Model not found."}</span>{" "}
        <Button onClick={loadData}>Retry</Button>{" "}
        <Link to="/models" className="text-emerald-400">
          Back to Registry
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-zinc-800/80">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              to="/models"
              className="text-xs text-zinc-400 hover:text-zinc-200 transition"
            >
              Model Registry
            </Link>
            <span className="text-zinc-600">/</span>
            <span className="text-xs font-mono text-indigo-400">
              {model.name}
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100 flex items-center gap-3">
            <span>{model.name}</span>
            <Badge
              variant={
                model.environment === "production" ? "success" : "default"
              }
            >
              {model.environment}
            </Badge>
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            {model.description || "No description provided."}
          </p>
        </div>

        {canRegister && (
          <Button variant="primary" onClick={() => setShowVersionModal(true)}>
            <Plus className="w-4 h-4" /> New Version
          </Button>
        )}
      </div>

      {/* Tabs */}
      {error && (
        <div role="alert" className="text-rose-300 text-sm">
          {error}
        </div>
      )}
      <Modal
        isOpen={history !== null}
        title={`Stage History - v${history?.version || ""}`}
        onClose={() => setHistory(null)}
      >
        {history?.rows.length === 0 && <p>No stage transitions recorded.</p>}
        <ul className="space-y-2 text-xs">
          {history?.rows.map((row) => (
            <li key={row.id}>
              {row.from_stage} → {row.to_stage}{" "}
              <span className="text-zinc-400">{row.changed_at}</span>
            </li>
          ))}
        </ul>
      </Modal>
      <div className="flex gap-2 border-b border-zinc-800/80">
        {[
          { key: "versions", label: `Versions (${versions.length})` },
          { key: "lineage", label: "Lineage DAG" },
          { key: "predict", label: "Real-Time Inference Bench" },
          { key: "drift", label: "Population Stability & Drift (PSI)" },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition -mb-px ${
              activeTab === t.key
                ? "border-emerald-500 text-emerald-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab: Versions Table */}
      {activeTab === "versions" && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/50 text-zinc-400 font-mono text-[11px] uppercase">
                <th className="py-3 px-4 font-semibold">Version</th>
                <th className="py-3 px-4 font-semibold">Stage</th>
                <th className="py-3 px-4 font-semibold">Performance Metrics</th>
                <th className="py-3 px-4 font-semibold">Registered</th>
                <th className="py-3 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {versions.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-zinc-500">
                    No versions created yet.
                  </td>
                </tr>
              ) : (
                versions.map((v) => (
                  <tr key={v.id} className="hover:bg-zinc-800/30">
                    <td className="py-3 px-4 font-bold text-zinc-200 font-mono">
                      v{v.version}
                    </td>
                    <td className="py-3 px-4">
                      <Badge
                        variant={
                          v.stage === "Production"
                            ? "success"
                            : v.stage === "Staging"
                              ? "warning"
                              : "default"
                        }
                      >
                        {v.stage}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-300">
                      {v.metrics_json ? (
                        <span className="text-[11px] text-zinc-400">
                          {v.metrics_json}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-400">
                      {v.created_at ? v.created_at.slice(0, 10) : "N/A"}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <ModelVersionAssets
                        model={model}
                        version={v}
                        canEdit={canEdit}
                        canLink={user?.roles?.some((role) =>
                          ["admin", "ml_engineer", "data_scientist"].includes(
                            role,
                          ),
                        )}
                        onChanged={loadData}
                      />
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => showHistory(v)}
                      >
                        History
                      </Button>
                      {canEdit && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            setSelectedVersion(v);
                            setShowPromoteModal(true);
                          }}
                        >
                          Promote Stage
                        </Button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      )}

      {activeTab === "drift" && (
        <ModelDriftPanel
          modelId={id}
          versions={versions}
          canMeasure={user?.roles?.some((role) =>
            ["admin", "ml_engineer", "data_scientist"].includes(role),
          )}
        />
      )}

      {/* Tab: Lineage */}
      {activeTab === "lineage" && (
        <Card>
          <CardHeader
            title="Model Lineage & Feature Dependency DAG"
            description="End-to-end dependency graph showing features and source tables feeding this model."
          />
          <LineageGraph graph={lineageGraph} />
        </Card>
      )}

      {/* Tab: Inference Proxy Bench */}
      {activeTab === "predict" && (
        <Card>
          <CardHeader
            title="Real-Time Model Inference Proxy"
            description="Automated feature hydration from online store combined with real-time scoring."
          />
          <div className="space-y-4">
            <label className="block text-xs">
              Inference version{" "}
              <select
                aria-label="Inference version"
                className="bg-zinc-900 p-2"
                value={predictVersion}
                onChange={(event) => setPredictVersion(event.target.value)}
              >
                <option value="">Current Production</option>
                {versions.map((version) => (
                  <option key={version.id} value={version.version}>
                    {version.version}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs">
              Runtime features (JSON)
              <textarea
                aria-label="Runtime features (JSON)"
                className="block w-full bg-zinc-900 p-2 font-mono"
                value={runtimeInput}
                onChange={(event) => setRuntimeInput(event.target.value)}
              />
            </label>
            <div className="flex flex-col sm:flex-row items-center gap-3">
              <input
                type="text"
                placeholder="Entity primary key (e.g. cust_001)"
                value={predictKey}
                onChange={(e) => setPredictKey(e.target.value)}
                className="w-full sm:w-80 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-100 font-mono focus:outline-none focus:border-zinc-700"
              />
              <Button
                variant="primary"
                onClick={handlePredict}
                loading={predicting}
              >
                <Send className="w-3.5 h-3.5" /> Run Prediction
              </Button>
            </div>

            {predictResult && (
              <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-950 space-y-3">
                <div className="flex items-center justify-between text-xs font-mono pb-2 border-b border-zinc-800">
                  <span className="text-zinc-400">Inference Latency</span>
                  <span className="text-emerald-400 font-semibold">
                    {predictResult.latency_ms} ms
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800">
                    <span className="text-[10px] text-zinc-500 uppercase font-mono">
                      Prediction Class
                    </span>
                    <p className="text-lg font-bold font-mono text-zinc-100 mt-1">
                      {predictResult.prediction?.prediction_class}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800">
                    <span className="text-[10px] text-zinc-500 uppercase font-mono">
                      Probability / Score
                    </span>
                    <p className="text-lg font-bold font-mono text-indigo-400 mt-1">
                      {predictResult.prediction?.probability ??
                        predictResult.prediction?.value}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800">
                    <span className="text-[10px] text-zinc-500 uppercase font-mono">
                      Classification Label
                    </span>
                    <p className="text-xs font-semibold text-emerald-400 mt-2 truncate">
                      {predictResult.prediction?.label}
                    </p>
                  </div>
                </div>

                <div>
                  <span className="text-[11px] font-mono text-zinc-400 block mb-1.5">
                    Hydrated Online Feature Vector:
                  </span>
                  <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800/80 font-mono text-xs text-zinc-300">
                    <pre>
                      {JSON.stringify(predictResult.features_used, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Modal: Promote Stage */}
      <Modal
        isOpen={showPromoteModal}
        title="Promote Model Stage"
        onClose={() => setShowPromoteModal(false)}
      >
        <form onSubmit={handlePromote} className="space-y-4 text-xs">
          {error && (
            <p role="alert" className="text-rose-300">
              {error}
            </p>
          )}
          <div>
            <label
              className="block font-medium text-zinc-300 mb-1"
              htmlFor="modeldetail-field-1"
            >
              Target Stage
            </label>
            <select
              id="modeldetail-field-1"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              value={promoteStage}
              onChange={(e) => setPromoteStage(e.target.value)}
            >
              <option value="Production">Production</option>
              <option value="Staging">Staging</option>
              <option value="Archived">Archived</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
            <Button
              variant="secondary"
              onClick={() => setShowPromoteModal(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={promoting}>
              Confirm Promotion
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: New Version */}
      <Modal
        isOpen={showVersionModal}
        title="Register New Version"
        onClose={() => setShowVersionModal(false)}
      >
        <form onSubmit={handleCreateVersion} className="space-y-4 text-xs">
          {error && (
            <p role="alert" className="text-rose-300">
              {error}
            </p>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                className="block font-medium text-zinc-300 mb-1"
                htmlFor="modeldetail-field-2"
              >
                Version String
              </label>
              <input
                id="modeldetail-field-2"
                type="text"
                required
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
                placeholder="e.g. 1.1"
                value={versionForm.version}
                onChange={(e) =>
                  setVersionForm({ ...versionForm, version: e.target.value })
                }
              />
            </div>
            <div>
              <label
                className="block font-medium text-zinc-300 mb-1"
                htmlFor="modeldetail-field-3"
              >
                Initial Stage
              </label>
              <select
                id="modeldetail-field-3"
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
                value={versionForm.stage}
                onChange={(e) =>
                  setVersionForm({ ...versionForm, stage: e.target.value })
                }
              >
                <option value="Staging">Staging</option>
                <option value="Production">Production</option>
              </select>
            </div>
          </div>
          <div>
            <label
              className="block font-medium text-zinc-300 mb-1"
              htmlFor="modeldetail-field-4"
            >
              Metrics (JSON)
            </label>
            <input
              id="modeldetail-field-4"
              type="text"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 font-mono text-xs focus:outline-none focus:border-zinc-700"
              value={versionForm.metrics_json}
              onChange={(e) =>
                setVersionForm({ ...versionForm, metrics_json: e.target.value })
              }
            />
          </div>
          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
            <Button
              variant="secondary"
              onClick={() => setShowVersionModal(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={submittingVersion}>
              Register Version
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
