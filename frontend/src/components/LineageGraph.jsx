import React, { useState } from 'react';
import { Database, Layers, Zap, Cpu, Send, ArrowRight } from 'lucide-react';

const typeConfig = {
  source_table: {
    icon: Database,
    color: 'text-sky-400 bg-sky-500/10 border-sky-500/30',
    badge: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
    title: 'Source Table',
  },
  feature_group: {
    icon: Layers,
    color: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
    badge: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    title: 'Feature Group',
  },
  feature: {
    icon: Zap,
    color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    title: 'Feature Definition',
  },
  model: {
    icon: Cpu,
    color: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    title: 'Model',
  },
  model_version: {
    icon: Cpu,
    color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/30',
    badge: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
    title: 'Model Version',
  },
  endpoint: {
    icon: Send,
    color: 'text-rose-400 bg-rose-500/10 border-rose-500/30',
    badge: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
    title: 'Inference Endpoint',
  },
};

export default function LineageGraph({ graph }) {
  const [selectedNode, setSelectedNode] = useState(null);

  if (!graph || !graph.nodes || graph.nodes.length === 0) {
    return (
      <div className="p-8 text-center border border-zinc-800 rounded-xl bg-zinc-900/40 text-zinc-500 text-sm">
        No lineage graph connections registered yet.
      </div>
    );
  }

  // Group nodes into stages for a horizontal flow
  const stageOrder = ['source_table', 'feature_group', 'feature', 'model', 'model_version', 'endpoint'];
  const columns = stageOrder
    .map((st) => ({
      type: st,
      nodes: graph.nodes.filter((n) => n.type === st),
    }))
    .filter((col) => col.nodes.length > 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-xs text-zinc-400 border-b border-zinc-800/80 pb-3">
        <div className="flex items-center gap-4">
          <span className="font-semibold text-zinc-200">Lineage Flow:</span>
          {columns.map((col, idx) => (
            <React.Fragment key={col.type}>
              <span className="capitalize">{typeConfig[col.type]?.title || col.type}</span>
              {idx < columns.length - 1 && <ArrowRight className="w-3.5 h-3.5 text-zinc-600" />}
            </React.Fragment>
          ))}
        </div>
        <span className="text-zinc-500">{graph.nodes.length} Nodes · {graph.edges?.length || 0} Connectors</span>
      </div>

      <div className="relative overflow-x-auto p-4 border border-zinc-800/80 rounded-xl bg-zinc-950/60 min-h-[220px]">
        <div className="flex items-start gap-8 min-w-max">
          {columns.map((col, cIdx) => (
            <div key={col.type} className="flex flex-col gap-3 w-56">
              <div className="text-[11px] font-semibold tracking-wider uppercase text-zinc-500 px-1">
                {typeConfig[col.type]?.title || col.type}
              </div>
              <div className="flex flex-col gap-2.5">
                {col.nodes.map((node) => {
                  const cfg = typeConfig[node.type] || typeConfig.feature;
                  const Icon = cfg.icon;
                  const isSelected = selectedNode?.id === node.id;

                  return (
                    <div
                      key={node.id}
                      onClick={() => setSelectedNode(node)}
                      className={`cursor-pointer p-3 rounded-lg border transition-all duration-150 ${
                        cfg.color
                      } ${isSelected ? 'ring-2 ring-emerald-500 ring-offset-2 ring-offset-zinc-950 scale-[1.02]' : 'hover:scale-[1.01]'}`}
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <Icon className="w-4 h-4 shrink-0" />
                        <span className="text-xs font-semibold text-zinc-100 truncate">{node.label}</span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${cfg.badge}`}>
                          {node.type}
                        </span>
                        {node.metadata &&
                          Object.entries(node.metadata).map(([k, v]) => (
                            <span
                              key={k}
                              className="text-[10px] px-1.5 py-0.5 rounded border bg-zinc-900 border-zinc-800 text-zinc-400"
                            >
                              {k}: {v}
                            </span>
                          ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {selectedNode && (
        <div className="p-3 border border-zinc-800 rounded-lg bg-zinc-900/60 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-zinc-200">Selected Node:</span>
            <span className="text-emerald-400 font-mono">{selectedNode.label}</span>
            <span className="text-zinc-500">({selectedNode.type})</span>
          </div>
          <button
            onClick={() => setSelectedNode(null)}
            className="text-zinc-500 hover:text-zinc-300 text-xs underline"
          >
            Clear selection
          </button>
        </div>
      )}
    </div>
  );
}
