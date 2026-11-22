import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchApi, getActiveUser } from "../api";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Modal } from "../components/ui/Modal";
import {
  Layers,
  Plus,
  Search,
  Filter,
  ArrowRight,
  Database,
  CheckCircle2,
  AlertCircle,
  FileCode,
} from "lucide-react";

export default function FeatureCatalog() {
  const [features, setFeatures] = useState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedGroup, setSelectedGroup] = useState("all");
  const [selectedEnv, setSelectedEnv] = useState("all");

  // Modals
  const [showFeatureModal, setShowFeatureModal] = useState(false);
  const [showGroupModal, setShowGroupModal] = useState(false);

  // Forms
  const [featureForm, setFeatureForm] = useState({
    group_id: "",
    name: "",
    dtype: "float",
    description: "",
    source_sql: "SELECT customer_id AS entity_key, amount AS value, event_time FROM feature_store.sample_events",
    refresh_interval: "hourly",
    status: "active",
    min_value: "",
    max_value: "",
    allow_null: true,
  });

  const [groupForm, setGroupForm] = useState({
    name: "",
    description: "",
    environment: "dev",
    tags: "core,ml",
  });

  const [submitting, setSubmitting] = useState(false);
  const [dryRunning, setDryRunning] = useState(false);
  const [dryRunResult, setDryRunResult] = useState(null);
  const user = getActiveUser();
  const canEdit = user?.roles?.some((r) => ["admin", "ml_engineer", "data_scientist"].includes(r));

  const handleDryRun = async () => {
    if (!featureForm.source_sql.trim()) return;
    setDryRunning(true);
    setDryRunResult(null);
    try {
      const res = await fetchApi("/features/dry-run", {
        method: "POST",
        body: JSON.stringify({ query: featureForm.source_sql, limit: 3 }),
      });
      setDryRunResult(res);
    } catch (err) {
      setDryRunResult({ is_valid: false, error: err.message });
    } finally {
      setDryRunning(false);
    }
  };

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [fData, gData] = await Promise.all([
        fetchApi("/features"),
        fetchApi("/features/groups"),
      ]);
      setFeatures(fData);
      setGroups(gData);
      if (gData.length > 0 && !featureForm.group_id) {
        setFeatureForm((prev) => ({ ...prev, group_id: gData[0].id }));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateGroup = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await fetchApi("/features/groups", {
        method: "POST",
        body: JSON.stringify({
          name: groupForm.name,
          description: groupForm.description,
          environment: groupForm.environment,
          tags_json: JSON.stringify(groupForm.tags.split(",").map((t) => t.trim())),
        }),
      });
      setShowGroupModal(false);
      setGroupForm({ name: "", description: "", environment: "dev", tags: "core,ml" });
      await loadData();
    } catch (err) {
      alert(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateFeature = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const validationRules = {
        allow_null: featureForm.allow_null,
        min_value: featureForm.min_value ? parseFloat(featureForm.min_value) : null,
        max_value: featureForm.max_value ? parseFloat(featureForm.max_value) : null,
      };

      await fetchApi("/features", {
        method: "POST",
        body: JSON.stringify({
          group_id: featureForm.group_id,
          name: featureForm.name,
          dtype: featureForm.dtype,
          description: featureForm.description,
          source_sql: featureForm.source_sql,
          refresh_interval: featureForm.refresh_interval,
          status: featureForm.status,
          validation_rules_json: JSON.stringify(validationRules),
        }),
      });
      setShowFeatureModal(false);
      setFeatureForm({
        group_id: groups[0]?.id || "",
        name: "",
        dtype: "float",
        description: "",
        source_sql: "SELECT customer_id AS entity_key, amount AS value, event_time FROM feature_store.sample_events",
        refresh_interval: "hourly",
        status: "active",
        min_value: "",
        max_value: "",
        allow_null: true,
      });
      await loadData();
    } catch (err) {
      alert(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const filteredFeatures = features.filter((f) => {
    const matchesSearch =
      f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (f.description && f.description.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesGroup = selectedGroup === "all" || f.group_id === selectedGroup;
    return matchesSearch && matchesGroup;
  });

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-zinc-800/80">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Feature Catalog</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Discover, define, validate, and serve feature transformations across teams.
          </p>
        </div>
        {canEdit && (
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => setShowGroupModal(true)}>
              <Plus className="w-4 h-4" /> Feature Group
            </Button>
            <Button variant="primary" onClick={() => setShowFeatureModal(true)}>
              <Plus className="w-4 h-4" /> Define Feature
            </Button>
          </div>
        )}
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/50 text-rose-300 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-3 pointer-events-none" />
          <input
            type="text"
            className="w-full bg-zinc-900 border border-zinc-800 text-xs text-zinc-100 pl-9 pr-3 py-2 rounded-lg placeholder:text-zinc-500 focus:outline-none focus:border-zinc-700"
            placeholder="Filter features by name or description…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            className="bg-zinc-900 border border-zinc-800 text-xs text-zinc-300 px-3 py-2 rounded-lg focus:outline-none focus:border-zinc-700"
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
          >
            <option value="all">All Groups ({groups.length})</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Features Table */}
      <Card className="p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/50 text-zinc-400 font-mono text-[11px] uppercase">
                <th className="py-3 px-4 font-semibold">Feature Name</th>
                <th className="py-3 px-4 font-semibold">Group</th>
                <th className="py-3 px-4 font-semibold">Type</th>
                <th className="py-3 px-4 font-semibold">Refresh</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-zinc-500">
                    Loading feature catalog…
                  </td>
                </tr>
              ) : filteredFeatures.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-zinc-500">
                    No features found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredFeatures.map((f) => {
                  const grp = groups.find((g) => g.id === f.group_id);
                  return (
                    <tr key={f.id} className="hover:bg-zinc-800/30 transition-colors">
                      <td className="py-3 px-4 font-medium text-zinc-200">
                        <Link to={`/features/${f.id}`} className="hover:text-emerald-400 transition flex items-center gap-2">
                          <Layers className="w-3.5 h-3.5 text-emerald-400" />
                          <span>{f.name}</span>
                        </Link>
                      </td>
                      <td className="py-3 px-4 text-zinc-400">{grp?.name || "—"}</td>
                      <td className="py-3 px-4 font-mono text-zinc-400">
                        <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 text-[10px]">{f.dtype}</span>
                      </td>
                      <td className="py-3 px-4 font-mono text-zinc-400">{f.refresh_interval}</td>
                      <td className="py-3 px-4">
                        <Badge variant={f.status === "active" ? "success" : "default"}>{f.status}</Badge>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          to={`/features/${f.id}`}
                          className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-emerald-400 transition"
                        >
                          View <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Modal: New Feature Group */}
      <Modal isOpen={showGroupModal} title="Create Feature Group" onClose={() => setShowGroupModal(false)}>
        <form onSubmit={handleCreateGroup} className="space-y-4 text-xs">
          <div>
            <label className="block font-medium text-zinc-300 mb-1">Group Name</label>
            <input
              type="text"
              required
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              placeholder="e.g. Payments"
              value={groupForm.name}
              onChange={(e) => setGroupForm({ ...groupForm, name: e.target.value })}
            />
          </div>
          <div>
            <label className="block font-medium text-zinc-300 mb-1">Description</label>
            <input
              type="text"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              placeholder="Feature group purpose"
              value={groupForm.description}
              onChange={(e) => setGroupForm({ ...groupForm, description: e.target.value })}
            />
          </div>
          <div>
            <label className="block font-medium text-zinc-300 mb-1">Environment</label>
            <select
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              value={groupForm.environment}
              onChange={(e) => setGroupForm({ ...groupForm, environment: e.target.value })}
            >
              <option value="dev">Development (dev)</option>
              <option value="staging">Staging</option>
              <option value="production">Production</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
            <Button variant="secondary" onClick={() => setShowGroupModal(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={submitting}>
              Create Group
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Define Feature */}
      <Modal isOpen={showFeatureModal} title="Define New Feature" maxWidth="max-w-xl" onClose={() => setShowFeatureModal(false)}>
        <form onSubmit={handleCreateFeature} className="space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-zinc-300 mb-1">Feature Group</label>
              <select
                required
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
                value={featureForm.group_id}
                onChange={(e) => setFeatureForm({ ...featureForm, group_id: e.target.value })}
              >
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} ({g.environment})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-medium text-zinc-300 mb-1">Feature Name</label>
              <input
                type="text"
                required
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
                placeholder="e.g. customer_30d_spend"
                value={featureForm.name}
                onChange={(e) => setFeatureForm({ ...featureForm, name: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-zinc-300 mb-1">Data Type</label>
              <select
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
                value={featureForm.dtype}
                onChange={(e) => setFeatureForm({ ...featureForm, dtype: e.target.value })}
              >
                <option value="float">Float</option>
                <option value="int">Integer</option>
                <option value="string">String</option>
                <option value="boolean">Boolean</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-zinc-300 mb-1">Refresh Cadence</label>
              <select
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
                value={featureForm.refresh_interval}
                onChange={(e) => setFeatureForm({ ...featureForm, refresh_interval: e.target.value })}
              >
                <option value="hourly">Hourly</option>
                <option value="daily">Daily</option>
                <option value="streaming">Streaming / Realtime</option>
              </select>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block font-medium text-zinc-300">SQL Transformation</label>
              <button
                type="button"
                onClick={handleDryRun}
                disabled={dryRunning}
                className="text-[11px] text-emerald-400 hover:text-emerald-300 font-mono underline disabled:opacity-50"
              >
                {dryRunning ? "Testing SQL..." : "Test Query (Dry Run)"}
              </button>
            </div>
            <textarea
              required
              rows={3}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 font-mono text-[11px] focus:outline-none focus:border-zinc-700"
              value={featureForm.source_sql}
              onChange={(e) => setFeatureForm({ ...featureForm, source_sql: e.target.value })}
            />
            <p className="text-[10px] text-zinc-500 mt-1">Must alias entity_key and value.</p>

            {dryRunResult && (
              <div className="mt-2 p-2.5 rounded-lg border text-xs font-mono bg-zinc-950 border-zinc-800">
                {dryRunResult.is_valid ? (
                  <div>
                    <div className="flex items-center justify-between text-emerald-400 mb-1.5 text-[11px]">
                      <span>✓ Query Validated ({dryRunResult.execution_time_ms}ms)</span>
                      <span className="text-zinc-500">{dryRunResult.row_count} sample rows</span>
                    </div>
                    {dryRunResult.rows.length > 0 && (
                      <div className="overflow-x-auto max-h-28 text-[10px]">
                        <table className="w-full text-left text-zinc-400">
                          <thead>
                            <tr className="border-b border-zinc-800 text-zinc-300">
                              {dryRunResult.columns.map((c) => (
                                <th key={c} className="py-1 px-1.5">{c}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {dryRunResult.rows.map((r, idx) => (
                              <tr key={idx} className="border-b border-zinc-900">
                                {dryRunResult.columns.map((c) => (
                                  <td key={c} className="py-0.5 px-1.5 text-zinc-200">{r[c] ?? "null"}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-rose-400 text-[11px]">
                    ✕ Error: {dryRunResult.error}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Validation Rules Section */}
          <div className="p-3 bg-zinc-950/60 border border-zinc-800/80 rounded-lg space-y-2">
            <span className="text-[11px] font-semibold text-zinc-300 font-mono uppercase">Validation Rules</span>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] text-zinc-400 mb-1">Min Value</label>
                <input
                  type="number"
                  step="any"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded p-1.5 text-zinc-100 text-xs"
                  placeholder="e.g. 0"
                  value={featureForm.min_value}
                  onChange={(e) => setFeatureForm({ ...featureForm, min_value: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-[10px] text-zinc-400 mb-1">Max Value</label>
                <input
                  type="number"
                  step="any"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded p-1.5 text-zinc-100 text-xs"
                  placeholder="e.g. 100000"
                  value={featureForm.max_value}
                  onChange={(e) => setFeatureForm({ ...featureForm, max_value: e.target.value })}
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
            <Button variant="secondary" onClick={() => setShowFeatureModal(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={submitting}>
              Save Feature
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
