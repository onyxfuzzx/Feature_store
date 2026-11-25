import { useId, useState } from "react";

const stages = [
  "source_table",
  "unknown_source",
  "feature_group",
  "feature",
  "model",
  "model_version",
  "endpoint",
];
export default function LineageGraph({ graph }) {
  const [selected, setSelected] = useState(null),
    marker = useId().replace(/:/g, "");
  if (!graph?.nodes?.length)
    return <p className="p-6 text-zinc-400">No registered lineage.</p>;
  const columns = stages
    .map((type) => graph.nodes.filter((node) => node.type === type))
    .filter((nodes) => nodes.length);
  const positions = Object.fromEntries(
    columns.flatMap((nodes, column) =>
      nodes.map((node, row) => [
        node.id,
        { x: 20 + column * 260, y: 30 + row * 100 },
      ]),
    ),
  );
  const height = Math.max(...columns.map((nodes) => nodes.length)) * 100 + 50;
  return (
    <section aria-label="Lineage dependency graph" className="space-y-3">
      <p className="text-xs text-zinc-400">
        {graph.nodes.length} nodes · {graph.edges.length} registered
        dependencies. Select a node for details.
      </p>
      <div className="overflow-auto border border-zinc-800 rounded-xl">
        <svg
          width={columns.length * 260}
          height={height}
          aria-label="Directed lineage dependencies"
        >
          <defs>
            <marker
              id={marker}
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="4"
              orient="auto"
            >
              <path d="M0,0 L8,4 L0,8 Z" fill="#71717a" />
            </marker>
          </defs>
          {graph.edges.map((edge) => {
            const from = positions[edge.source],
              to = positions[edge.target];
            if (!from || !to) return null;
            const x = from.x + 210,
              y = from.y + 30,
              endX = to.x,
              endY = to.y + 30,
              mid = (x + endX) / 2;
            return (
              <path
                key={`${edge.source}/${edge.target}`}
                data-source={edge.source}
                data-target={edge.target}
                d={`M${x},${y} C${mid},${y} ${mid},${endY} ${endX},${endY}`}
                stroke="#71717a"
                strokeWidth="1.5"
                fill="none"
                markerEnd={`url(#${marker})`}
              >
                <title>{edge.label}</title>
              </path>
            );
          })}
          {graph.nodes.map((node) => {
            const position = positions[node.id];
            if (!position) return null;
            return (
              <g
                key={node.id}
                transform={`translate(${position.x},${position.y})`}
                role="button"
                tabIndex="0"
                aria-label={node.label}
                onClick={() => setSelected(node)}
                onKeyDown={(event) => {
                  if (["Enter", " "].includes(event.key)) {
                    event.preventDefault();
                    setSelected(node);
                  }
                }}
                className="cursor-pointer"
              >
                <title>{node.label}</title>
                <rect
                  width="210"
                  height="60"
                  rx="8"
                  fill="#18181b"
                  stroke={selected?.id === node.id ? "#34d399" : "#52525b"}
                />
                <text x="10" y="24" fill="#f4f4f5" fontSize="12">
                  {node.label.length > 27
                    ? node.label.slice(0, 26) + "…"
                    : node.label}
                </text>
                <text x="10" y="45" fill="#a1a1aa" fontSize="10">
                  {node.type}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      {selected && (
        <div className="p-3 bg-zinc-900 rounded text-xs" role="status">
          <strong>{selected.label}</strong>
          <pre className="whitespace-pre-wrap">
            {JSON.stringify(selected.metadata, null, 2)}
          </pre>
          <button onClick={() => setSelected(null)}>Clear selection</button>
        </div>
      )}
    </section>
  );
}
