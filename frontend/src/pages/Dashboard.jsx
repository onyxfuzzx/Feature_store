import React, { useEffect, useState } from "react";
import { fetchApi } from "../api";
import { Card, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import {
  Layers,
  Cpu,
  Clock,
  Activity,
  RefreshCw,
  ArrowUpRight,
  CheckCircle2,
  AlertCircle,
  Database,
} from "lucide-react";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    try {
      setError(null);
      const d = await fetchApi("/dashboard/summary");
      setData(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const statIcons = [Layers, Cpu, Clock, Activity];

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-zinc-800/80">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Mission Control</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Real-time feature store metrics, model registry tracking, and pipeline health.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" size="md" onClick={load} loading={loading}>
            <RefreshCw className="w-4 h-4" /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/50 text-rose-300 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Stats Grid */}
      {data && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {data.stats.map((s, idx) => {
            const Icon = statIcons[idx % statIcons.length];
            return (
              <Card key={s.label} hover className="relative overflow-hidden">
                <div className="flex items-center justify-between text-zinc-400 mb-3">
                  <span className="text-xs font-medium tracking-wide uppercase font-mono">{s.label}</span>
                  <div className="p-2 rounded-lg bg-zinc-800/60 border border-zinc-700/50 text-zinc-300">
                    <Icon className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-3xl font-bold text-zinc-100 tracking-tight">{s.value}</div>
                {s.note && (
                  <p className="text-xs text-zinc-500 mt-2 font-mono flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-emerald-500 inline-block" />
                    {s.note}
                  </p>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Activity Streams Grid */}
      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Materializations */}
          <Card>
            <CardHeader
              title="Recent Materialization Runs"
              description="Latest batch execution statuses and timestamps."
            />
            {data.recent_materializations.length === 0 ? (
              <div className="py-8 text-center text-sm text-zinc-500">No materializations recorded yet.</div>
            ) : (
              <div className="divide-y divide-zinc-800/60">
                {data.recent_materializations.map((item, i) => (
                  <div key={i} className="py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-emerald-400" />
                      <div>
                        <div className="text-sm font-medium text-zinc-200">{item.name}</div>
                        <div className="text-xs text-zinc-500 font-mono">
                          {item.time ? item.time.slice(0, 16).replace("T", " ") : "N/A"}
                        </div>
                      </div>
                    </div>
                    <Badge variant={item.status === "success" ? "success" : "danger"}>
                      {item.status}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Model Stage Promotions */}
          <Card>
            <CardHeader
              title="Model Stage Promotions"
              description="Recent lifecycle transitions in the Model Registry."
            />
            {data.recent_promotions.length === 0 ? (
              <div className="py-8 text-center text-sm text-zinc-500">No model stage promotions logged yet.</div>
            ) : (
              <div className="divide-y divide-zinc-800/60">
                {data.recent_promotions.map((item, i) => (
                  <div key={i} className="py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Cpu className="w-4 h-4 text-indigo-400 shrink-0" />
                      <div>
                        <div className="text-sm font-medium text-zinc-200">{item.model}</div>
                        <div className="text-xs text-zinc-500 font-mono">
                          {item.time ? item.time.slice(0, 16).replace("T", " ") : "N/A"}
                        </div>
                      </div>
                    </div>
                    <Badge variant={item.stage === "Production" ? "success" : "warning"}>
                      {item.stage}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
