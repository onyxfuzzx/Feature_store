import { useEffect, useState } from "react";
import { fetchApi } from "../api";
import { IconRefresh } from "../components/Icons";

function StatCard({ label, value, note, color }) {
  return (
    <div className="card stat-card">
      <div className="stat-dot" style={{ background: color }} />
      <div className="card-title">{label}</div>
      <div className="card-kpi">{value}</div>
      {note && <div className="subtle">{note}</div>}
    </div>
  );
}

function statusColor(s) {
  if (s === "success") return "var(--mint)";
  if (s === "failed") return "var(--coral)";
  return "var(--sun)";
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    try {
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

  return (
    <section>
      <div className="page-header">
        <div>
          <h1 className="page-title">Mission Control</h1>
          <p className="subtle">Real-time platform health and activity.</p>
        </div>
        <button className="button" onClick={load}>
          <IconRefresh /> Refresh
        </button>
      </div>

      {loading && <div className="loading-pulse">Loading…</div>}
      {error && <div className="error-alert">{error}</div>}

      {data && (
        <>
          <div className="stat-grid">
            {data.stats.map((s, i) => (
              <StatCard
                key={s.label}
                label={s.label}
                value={s.value}
                note={s.note}
                color={["var(--mint)", "var(--sun)", "var(--coral)", "#a78bfa"][i % 4]}
              />
            ))}
          </div>

          <div className="grid-two">
            <div className="card">
              <h3 className="card-title">Recent Materializations</h3>
              {data.recent_materializations.length === 0 ? (
                <p className="subtle" style={{ marginTop: 8 }}>No materializations yet.</p>
              ) : (
                <div className="list">
                  {data.recent_materializations.map((item, i) => (
                    <div className="list-item" key={i}>
                      <div>
                        <strong>{item.name.slice(0, 8)}…</strong>
                        <div className="subtle">{item.time.slice(0, 16).replace("T", " ")}</div>
                      </div>
                      <span
                        className="badge"
                        style={{ background: `${statusColor(item.status)}33`, color: statusColor(item.status) }}
                      >
                        {item.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="card">
              <h3 className="card-title">Model Stage Promotions</h3>
              {data.recent_promotions.length === 0 ? (
                <p className="subtle" style={{ marginTop: 8 }}>No promotions yet.</p>
              ) : (
                <div className="list">
                  {data.recent_promotions.map((item, i) => (
                    <div className="list-item" key={i}>
                      <div>
                        <strong>{item.model.slice(0, 8)}…</strong>
                        <div className="subtle">{item.time.slice(0, 16).replace("T", " ")}</div>
                      </div>
                      <span className="badge">{item.stage}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
