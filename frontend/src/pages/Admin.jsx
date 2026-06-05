import { useEffect, useState } from "react";
import { fetchApi } from "../api";
import { IconClose, IconUsers, IconAudit, IconRefresh, IconKey } from "../components/Icons";

const ROLES = ["admin", "ml_engineer", "data_scientist", "analyst"];

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

function TabButton({ active, onClick, children }) {
  return (
    <button className={`tab-btn${active ? " active" : ""}`} onClick={onClick}>{children}</button>
  );
}

export default function Admin() {
  const [tab, setTab] = useState("users");
  const [users, setUsers] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [loadingKeys, setLoadingKeys] = useState(false);

  const [showUserModal, setShowUserModal] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);

  const [userForm, setUserForm] = useState({ name: "", email: "", password: "", roles: ["analyst"] });
  const [keyForm, setKeyForm] = useState({ name: "" });
  const [createdKeyPlain, setCreatedKeyPlain] = useState(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [logFilter, setLogFilter] = useState("");

  const loadUsers = async () => {
    setLoadingUsers(true);
    try {
      const data = await fetchApi("/users");
      setUsers(data);
    } catch {
      // ignore
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadLogs = async () => {
    setLoadingLogs(true);
    try {
      const data = await fetchApi("/users/audit-logs");
      setAuditLogs(data);
    } catch {
      // ignore
    } finally {
      setLoadingLogs(false);
    }
  };

  const loadKeys = async () => {
    setLoadingKeys(true);
    try {
      const data = await fetchApi("/api-keys");
      setApiKeys(data);
    } catch {
      // ignore
    } finally {
      setLoadingKeys(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  useEffect(() => {
    if (tab === "audit") loadLogs();
    if (tab === "keys") loadKeys();
  }, [tab]);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      await fetchApi("/users", { method: "POST", body: JSON.stringify(userForm) });
      setShowUserModal(false);
      setUserForm({ name: "", email: "", password: "", roles: ["analyst"] });
      await loadUsers();
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateKey = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      const data = await fetchApi("/api-keys", { method: "POST", body: JSON.stringify(keyForm) });
      setCreatedKeyPlain(data.plain_key);
      setKeyForm({ name: "" });
      await loadKeys();
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevokeKey = async (keyId) => {
    if (!window.confirm("Are you sure you want to revoke this API key? Scripts using it will fail.")) return;
    try {
      await fetchApi(`/api-keys/${keyId}`, { method: "DELETE" });
      await loadKeys();
    } catch (err) {
      alert("Failed to revoke key: " + err.message);
    }
  };

  const filteredLogs = auditLogs.filter((l) => {
    if (!logFilter) return true;
    return (
      l.action.toLowerCase().includes(logFilter.toLowerCase()) ||
      l.entity_type.toLowerCase().includes(logFilter.toLowerCase())
    );
  });

  const actionColor = (action) => {
    if (action.startsWith("CREATE")) return "#0d7a66";
    if (action.startsWith("PROMOTE") || action.startsWith("LINK")) return "#b06000";
    if (action.startsWith("MATERIALIZE") || action.startsWith("RUN")) return "#5b21b6";
    if (action.startsWith("REVOKE")) return "#be123c";
    return "#444";
  };

  return (
    <section>
      <div className="page-header">
        <div>
          <h1 className="page-title">Administration</h1>
          <p className="subtle">Manage users, programmatic API keys, and review the complete audit trail.</p>
        </div>
      </div>

      <div className="tab-bar">
        <TabButton active={tab === "users"} onClick={() => setTab("users")}>
          <IconUsers /> Users
        </TabButton>
        <TabButton active={tab === "keys"} onClick={() => setTab("keys")}>
          <IconKey /> API Keys
        </TabButton>
        <TabButton active={tab === "audit"} onClick={() => setTab("audit")}>
          <IconAudit /> Audit Logs
        </TabButton>
      </div>

      {tab === "users" && (
        <div style={{ marginTop: 16 }}>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
            <button className="button" onClick={() => setShowUserModal(true)}>+ Add User</button>
          </div>
          {loadingUsers && <div className="loading-pulse">Loading users…</div>}
          {!loadingUsers && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Roles</th>
                    <th>Status</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td><strong>{u.name}</strong></td>
                      <td className="subtle">{u.email}</td>
                      <td>
                        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                          {u.roles.map((r) => (
                            <span key={r} className="badge" style={{ fontSize: "0.75rem" }}>{r}</span>
                          ))}
                        </div>
                      </td>
                      <td>
                        <span className="badge" style={u.is_active
                          ? { background: "rgba(90,219,195,0.18)", color: "#0d7a66" }
                          : { background: "rgba(200,200,200,0.2)", color: "#666" }
                        }>
                          {u.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="subtle">{u.created_at?.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "keys" && (
        <div style={{ marginTop: 16 }}>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
            <button className="button" onClick={() => { setCreatedKeyPlain(null); setShowKeyModal(true); }}>+ Generate API Key</button>
          </div>
          {loadingKeys && <div className="loading-pulse">Loading API keys…</div>}
          {!loadingKeys && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Key Name</th>
                    <th>Status</th>
                    <th>Created At</th>
                    <th style={{ textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {apiKeys.length === 0 && (
                    <tr><td colSpan={4} style={{ textAlign: "center", padding: 32, color: "#888" }}>No active API keys. Generate one for CI/CD or scripts.</td></tr>
                  )}
                  {apiKeys.map((k) => (
                    <tr key={k.id}>
                      <td><strong>{k.name}</strong></td>
                      <td>
                        <span className="badge" style={{ background: "rgba(90,219,195,0.18)", color: "#0d7a66" }}>
                          Active
                        </span>
                      </td>
                      <td className="subtle">{k.created_at?.slice(0, 16).replace("T", " ")}</td>
                      <td style={{ textAlign: "right" }}>
                        <button className="button button-sm" style={{ background: "#f43f5e" }} onClick={() => handleRevokeKey(k.id)}>
                          Revoke
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "audit" && (
        <div style={{ marginTop: 16 }}>
          <div className="filter-bar" style={{ marginBottom: 12 }}>
            <input
              className="filter-input"
              placeholder="Filter by action or entity type…"
              value={logFilter}
              onChange={(e) => setLogFilter(e.target.value)}
            />
            <span className="subtle">{filteredLogs.length} entries</span>
            <button className="button button-sm" onClick={loadLogs}>
              <IconRefresh /> Refresh
            </button>
          </div>
          {loadingLogs && <div className="loading-pulse">Loading audit logs…</div>}
          {!loadingLogs && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Entity Type</th>
                    <th>Entity ID</th>
                    <th>Payload</th>
                    <th>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLogs.length === 0 && (
                    <tr><td colSpan={5} style={{ textAlign: "center", padding: 32, color: "#888" }}>No audit logs found.</td></tr>
                  )}
                  {filteredLogs.map((log) => (
                    <tr key={log.id}>
                      <td>
                        <span style={{ color: actionColor(log.action), fontWeight: 700, fontSize: "0.82rem" }}>
                          {log.action}
                        </span>
                      </td>
                      <td><code className="code-tag">{log.entity_type}</code></td>
                      <td><code style={{ fontSize: "0.72rem", color: "#888" }}>{log.entity_id.slice(0, 8)}…</code></td>
                      <td>
                        {log.payload_json ? (
                          <span className="subtle" style={{ fontSize: "0.78rem" }}>
                            {log.payload_json.slice(0, 60)}{log.payload_json.length > 60 ? "…" : ""}
                          </span>
                        ) : "—"}
                      </td>
                      <td className="subtle">{log.created_at?.slice(0, 16).replace("T", " ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {showUserModal && (
        <Modal title="Add Platform User" onClose={() => setShowUserModal(false)}>
          <form onSubmit={handleCreateUser} className="modal-form">
            {submitError && <div className="error-alert">{submitError}</div>}
            <div className="form-row">
              <div className="form-group">
                <label>Full Name *</label>
                <input value={userForm.name} onChange={(e) => setUserForm({ ...userForm, name: e.target.value })} required placeholder="Jane Smith" />
              </div>
              <div className="form-group">
                <label>Email *</label>
                <input type="email" value={userForm.email} onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} required placeholder="jane@company.com" />
              </div>
            </div>
            <div className="form-group">
              <label>Password *</label>
              <input type="password" value={userForm.password} onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} required placeholder="min 8 characters" />
            </div>
            <div className="form-group">
              <label>Roles</label>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 6 }}>
                {ROLES.map((r) => (
                  <label key={r} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={userForm.roles.includes(r)}
                      onChange={(e) => {
                        const newRoles = e.target.checked
                          ? [...userForm.roles, r]
                          : userForm.roles.filter((x) => x !== r);
                        setUserForm({ ...userForm, roles: newRoles });
                      }}
                    />
                    {r}
                  </label>
                ))}
              </div>
            </div>
            <div className="modal-actions">
              <button type="button" className="button button-outline" onClick={() => setShowUserModal(false)}>Cancel</button>
              <button type="submit" className="button" disabled={submitting}>{submitting ? "Creating…" : "Add User"}</button>
            </div>
          </form>
        </Modal>
      )}

      {showKeyModal && (
        <Modal title="Generate Programmatic API Key" onClose={() => setShowKeyModal(false)}>
          {!createdKeyPlain ? (
            <form onSubmit={handleCreateKey} className="modal-form">
              {submitError && <div className="error-alert">{submitError}</div>}
              <div className="form-group">
                <label>API Key Name *</label>
                <input
                  value={keyForm.name}
                  onChange={(e) => setKeyForm({ name: e.target.value })}
                  required
                  placeholder="e.g. CI-CD-Deployment-Key"
                />
                <span className="subtle" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                  Use a clear description indicating where this key will be used.
                </span>
              </div>
              <div className="modal-actions">
                <button type="button" className="button button-outline" onClick={() => setShowKeyModal(false)}>Cancel</button>
                <button type="submit" className="button" disabled={submitting}>{submitting ? "Generating…" : "Generate"}</button>
              </div>
            </form>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ background: "rgba(22, 101, 52, 0.1)", border: "1px solid #16a34a", padding: 12, borderRadius: 6, color: "#16a34a", fontSize: "0.88rem" }}>
                <strong>API Key generated successfully!</strong> Make sure to copy it now. You will not be able to see it again.
              </div>
              <div className="form-group">
                <label>API Key</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    readOnly
                    value={createdKeyPlain}
                    style={{ fontFamily: "monospace", flex: 1, padding: "8px 12px", background: "#1e1e1e", color: "#e0e0e0", border: "1px solid #333" }}
                  />
                  <button
                    className="button"
                    onClick={() => {
                      navigator.clipboard.writeText(createdKeyPlain);
                      alert("Copied to clipboard!");
                    }}
                  >
                    Copy
                  </button>
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" className="button" onClick={() => setShowKeyModal(false)}>Done</button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </section>
  );
}
