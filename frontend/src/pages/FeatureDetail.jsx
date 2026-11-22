import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchApi, getActiveUser } from "../api";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Card, CardHeader } from "../components/ui/Card";
import {
  Layers,
  Play,
  ArrowRight,
  Database,
  Code,
  ShieldCheck,
  Zap,
  Clock,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";

export default function FeatureDetail() {
  const { id } = useParams();
  const [feature, setFeature] = useState(null);
  const [materializations, setMaterializations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");

  // Materialize trigger
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);

  // Live Online Test Bench
  const [testKey, setTestKey] = useState("cust_001");
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  const user = getActiveUser();
  const canMaterialize = user?.roles?.some((r) => ["admin", "ml_engineer"].includes(r));

  const loadData = async () => {
    try {
      setLoading(true);
      const [fData, matData] = await Promise.all([
        fetchApi(`/features/${id}`),
        fetchApi(`/features/${id}/materializations`),
      ]);
      setFeature(fData);
      setMaterializations(matData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  const handleTriggerMaterialize = async () => {
    setRunning(true);
    setRunResult(null);
    try {
      const res = await fetchApi(`/features/${id}/materialize`, { method: "POST" });
      setRunResult(res);
      await loadData();
    } catch (err) {
      alert("Materialization failed: " + err.message);
    } finally {
      setRunning(false);
    }
  };

  const handleTestOnlineLookup = async () => {
    if (!testKey.trim() || !feature) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetchApi("/features/online/batch", {
        method: "POST",
        body: JSON.stringify({
          entity_keys: [testKey.trim()],
          features: [feature.name],
        }),
      });
      setTestResult(res);
    } catch (err) {
      alert("Online test lookup failed: " + err.message);
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return <div className="py-20 text-center text-sm text-zinc-500">Loading feature details…</div>;
  }

  if (!feature) {
    return (
      <div className="py-20 text-center text-sm text-zinc-500">
        Feature definition not found. <Link to="/features" className="text-emerald-400">Return to catalog</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-zinc-800/80">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link to="/features" className="text-xs text-zinc-400 hover:text-zinc-200 transition">
              Feature Catalog
            </Link>
            <span className="text-zinc-600">/</span>
            <span className="text-xs font-mono text-emerald-400">{feature.name}</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100 flex items-center gap-3">
            <span>{feature.name}</span>
            <Badge variant={feature.status === "active" ? "success" : "default"}>{feature.status}</Badge>
          </h1>
          <p className="text-sm text-zinc-400 mt-1">{feature.description || "No description provided."}</p>
        </div>

        {canMaterialize && (
          <Button variant="primary" onClick={handleTriggerMaterialize} loading={running}>
            <Play className="w-4 h-4 fill-current" /> Materialize Now
          </Button>
        )}
      </div>

      {runResult && (
        <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-800/50 text-emerald-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>
              Materialization finished with status: <strong>{runResult.status}</strong> ({runResult.row_count || 0} rows ingested)
            </span>
          </div>
          {runResult.error_message && (
            <span className="text-amber-400 text-[11px]">{runResult.error_message}</span>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-zinc-800/80">
        {[
          { key: "overview", label: "Overview & SQL" },
          { key: "test", label: "Online Serving Test Bench" },
          { key: "history", label: `Materialization Runs (${materializations.length})` },
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

      {/* Tab: Overview */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader title="Source SQL Transformation" description="Executed on source events table to extract values." />
              <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 font-mono text-xs text-zinc-300 overflow-x-auto">
                <pre>{feature.source_sql}</pre>
              </div>
            </Card>

            {feature.validation_rules_json && (
              <Card>
                <CardHeader title="Validation Rules" description="Active data quality constraints checked at runtime." />
                <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 font-mono text-xs text-emerald-400">
                  <pre>{JSON.stringify(JSON.parse(feature.validation_rules_json), null, 2)}</pre>
                </div>
              </Card>
            )}
          </div>

          <div className="space-y-6">
            <Card>
              <CardHeader title="Feature Metadata" />
              <div className="space-y-3 text-xs divide-y divide-zinc-800/60">
                <div className="pt-2 flex justify-between">
                  <span className="text-zinc-500">Data Type</span>
                  <span className="font-mono text-zinc-200">{feature.dtype}</span>
                </div>
                <div className="pt-2 flex justify-between">
                  <span className="text-zinc-500">Cadence</span>
                  <span className="font-mono text-zinc-200">{feature.refresh_interval}</span>
                </div>
                <div className="pt-2 flex justify-between">
                  <span className="text-zinc-500">Feature UUID</span>
                  <span className="font-mono text-zinc-400 text-[10px] truncate max-w-[140px]">{feature.id}</span>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Tab: Online Serving Test Bench */}
      {activeTab === "test" && (
        <Card className="max-w-2xl">
          <CardHeader
            title="Real-Time Online Serving Tester"
            description="Queries the low-latency feature_values_online table using the batch API."
          />
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1">Entity Key</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-100 font-mono focus:outline-none focus:border-zinc-700"
                  placeholder="e.g. cust_001"
                  value={testKey}
                  onChange={(e) => setTestKey(e.target.value)}
                />
                <Button variant="primary" size="md" onClick={handleTestOnlineLookup} loading={testing}>
                  <Zap className="w-3.5 h-3.5" /> Lookup
                </Button>
              </div>
            </div>

            {testResult && (
              <div className="mt-4 p-4 rounded-xl bg-zinc-950 border border-zinc-800">
                <div className="flex items-center justify-between text-xs text-zinc-400 mb-2 font-mono pb-2 border-b border-zinc-800">
                  <span>Serving Latency</span>
                  <span className="text-emerald-400 font-semibold">{testResult.read_latency_ms} ms</span>
                </div>
                <div className="font-mono text-xs text-zinc-300">
                  <pre>{JSON.stringify(testResult.values, null, 2)}</pre>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Tab: Materialization Runs */}
      {activeTab === "history" && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/50 text-zinc-400 font-mono text-[11px] uppercase">
                <th className="py-3 px-4 font-semibold">Started At</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 font-semibold">Rows Ingested</th>
                <th className="py-3 px-4 font-semibold">Message / Validation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {materializations.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-zinc-500">
                    No materialization runs recorded yet.
                  </td>
                </tr>
              ) : (
                materializations.map((m) => (
                  <tr key={m.id} className="hover:bg-zinc-800/30">
                    <td className="py-3 px-4 font-mono text-zinc-300">
                      {m.started_at ? m.started_at.slice(0, 19).replace("T", " ") : "N/A"}
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant={m.status === "success" ? "success" : "danger"}>{m.status}</Badge>
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-300">{m.row_count ?? "—"}</td>
                    <td className="py-3 px-4 text-zinc-400 text-[11px] max-w-xs truncate">
                      {m.error_message || "Completed with zero validation warnings"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
