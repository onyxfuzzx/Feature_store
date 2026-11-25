import React, { useEffect, useState } from "react";
import { fetchApi, getActiveUser } from "../api";
import { Card, CardHeader } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import { Shield, Key, Users, History, Plus, Copy, Check, AlertCircle } from "lucide-react";

export default function Admin() {
  const [tab, setTab] = useState("users");
  const [users, setUsers] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // User creation modal
  const [showUserModal, setShowUserModal] = useState(false);
  const [userForm, setUserForm] = useState({ name: "", email: "", password: "", roles: ["analyst"] });
  const [submittingUser, setSubmittingUser] = useState(false);

  // Key creation modal
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState(null);
  const [copied, setCopied] = useState(false);
  const [submittingKey, setSubmittingKey] = useState(false);

  const currentUser = getActiveUser();

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      if (tab === "users") {
        const u = await fetchApi("/users");
        setUsers(u);
      } else if (tab === "keys") {
        const k = await fetchApi("/api-keys");
        setApiKeys(k);
      } else if (tab === "audit") {
        const a = await fetchApi("/users/audit-logs");
        setAuditLogs(a);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [tab]);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setSubmittingUser(true);
    try {
      await fetchApi("/users", {
        method: "POST",
        body: JSON.stringify(userForm),
      });
      setShowUserModal(false);
      setUserForm({ name: "", email: "", password: "", roles: ["analyst"] });
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmittingUser(false);
    }
  };

  const handleCreateKey = async (e) => {
    e.preventDefault();
    setSubmittingKey(true);
    try {
      const res = await fetchApi("/api-keys", {
        method: "POST",
        body: JSON.stringify({ name: keyName }),
      });
      setCreatedKey(res.plain_key);
      setKeyName("");
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmittingKey(false);
    }
  };

  const copyToClipboard = async (text) => {
    try { await navigator.clipboard.writeText(text); } catch (err) { setError(err.message); return; }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {error && <div role="alert" className="text-rose-300">{error} <Button onClick={loadData}>Retry</Button></div>}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-zinc-800/80">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Administration</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Manage users, RBAC permissions, programmatic API keys, and compliance audit logs.
          </p>
        </div>
        {tab === "users" && (
          <Button variant="primary" onClick={() => setShowUserModal(true)}>
            <Plus className="w-4 h-4" /> Add User
          </Button>
        )}
        {tab === "keys" && (
          <Button variant="primary" onClick={() => { setCreatedKey(null); setShowKeyModal(true); }}>
            <Plus className="w-4 h-4" /> Generate API Key
          </Button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-zinc-800/80">
        {[
          { key: "users", label: "Users & RBAC Roles", icon: Users },
          { key: "keys", label: "Programmatic API Keys", icon: Key },
          { key: "audit", label: "Audit Logs", icon: History },
        ].map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2 text-xs font-medium border-b-2 transition -mb-px ${
                tab === t.key
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab: Users */}
      {tab === "users" && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/50 text-zinc-400 font-mono text-[11px] uppercase">
                <th className="py-3 px-4 font-semibold">User Name</th>
                <th className="py-3 px-4 font-semibold">Email</th>
                <th className="py-3 px-4 font-semibold">Assigned Roles</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 font-semibold">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-zinc-800/30">
                  <td className="py-3 px-4 font-medium text-zinc-200">{u.name}</td>
                  <td className="py-3 px-4 text-zinc-400 font-mono">{u.email}</td>
                  <td className="py-3 px-4">
                    <div className="flex gap-1.5 flex-wrap">
                      {u.roles?.map((r) => (
                        <span key={r} className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono text-[10px]">
                          {r}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <Badge variant={u.is_active ? "success" : "default"}>
                      {u.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  <td className="py-3 px-4 font-mono text-zinc-400">
                    {u.created_at ? u.created_at.slice(0, 10) : "N/A"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Tab: API Keys */}
      {tab === "keys" && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/50 text-zinc-400 font-mono text-[11px] uppercase">
                <th className="py-3 px-4 font-semibold">Key Name</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 font-semibold">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {apiKeys.length === 0 ? (
                <tr>
                  <td colSpan={3} className="py-8 text-center text-zinc-500">
                    No active API keys created yet.
                  </td>
                </tr>
              ) : (
                apiKeys.map((k) => (
                  <tr key={k.id} className="hover:bg-zinc-800/30">
                    <td className="py-3 px-4 font-medium text-zinc-200 flex items-center gap-2">
                      <Key className="w-3.5 h-3.5 text-zinc-500" />
                      <span>{k.name}</span>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant={k.is_active ? "success" : "default"}>
                        {k.is_active ? "Active" : "Revoked"}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-400">
                      {k.created_at ? k.created_at.slice(0, 10) : "N/A"}
                      <Button size="sm" onClick={async () => { try { await fetchApi(`/api-keys/${k.id}`, { method: "DELETE" }); await loadData(); } catch (err) { setError(err.message); } }}>Revoke</Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      )}

      {/* Tab: Audit Logs */}
      {tab === "audit" && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-950/50 text-zinc-400 font-mono text-[11px] uppercase">
                <th className="py-3 px-4 font-semibold">Timestamp</th>
                <th className="py-3 px-4 font-semibold">Action</th>
                <th className="py-3 px-4 font-semibold">Entity</th>
                <th className="py-3 px-4 font-semibold">Payload Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {auditLogs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-zinc-500">
                    No audit records logged yet.
                  </td>
                </tr>
              ) : (
                auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-zinc-800/30 font-mono">
                    <td className="py-3 px-4 text-zinc-400 text-[11px]">
                      {log.created_at ? log.created_at.slice(0, 19).replace("T", " ") : "N/A"}
                    </td>
                    <td className="py-3 px-4 text-emerald-400 font-semibold">{log.action}</td>
                    <td className="py-3 px-4 text-zinc-300">{log.entity_type}</td>
                    <td className="py-3 px-4 text-zinc-400 text-[10px] truncate max-w-xs">
                      {log.payload_json || "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      )}

      {/* Modal: New User */}
      <Modal isOpen={showUserModal} title="Create User Account" onClose={() => setShowUserModal(false)}>
        <form onSubmit={handleCreateUser} className="space-y-4 text-xs">
          {error && <p role="alert" className="text-rose-300">{error}</p>}
          <div>
            <label className="block font-medium text-zinc-300 mb-1" htmlFor="admin-field-1">Full Name</label>
            <input id="admin-field-1"
              type="text"
              required
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              placeholder="e.g. Jane Doe"
              value={userForm.name}
              onChange={(e) => setUserForm({ ...userForm, name: e.target.value })}
            />
          </div>
          <div>
            <label className="block font-medium text-zinc-300 mb-1" htmlFor="admin-field-2">Email</label>
            <input id="admin-field-2"
              type="email"
              required
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              placeholder="jane@company.com"
              value={userForm.email}
              onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
            />
          </div>
          <div>
            <label className="block font-medium text-zinc-300 mb-1" htmlFor="admin-field-3">Password</label>
            <input id="admin-field-3"
              type="password"
              required
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              placeholder="••••••••••••"
              value={userForm.password}
              onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
            />
          </div>
          <div>
            <label className="block font-medium text-zinc-300 mb-1" htmlFor="admin-field-4">Role Assignment</label>
            <select id="admin-field-4"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
              value={userForm.roles[0]}
              onChange={(e) => setUserForm({ ...userForm, roles: [e.target.value] })}
            >
              <option value="analyst">Analyst (Read-only)</option>
              <option value="data_scientist">Data Scientist</option>
              <option value="ml_engineer">ML Engineer</option>
              <option value="admin">Admin (Full Control)</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
            <Button variant="secondary" onClick={() => setShowUserModal(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={submittingUser}>
              Create User
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: New API Key */}
      <Modal isOpen={showKeyModal} title="Generate API Key" onClose={() => setShowKeyModal(false)}>
        {createdKey ? (
          <div className="space-y-4 text-xs">
          {error && <p role="alert" className="text-rose-300">{error}</p>}
            <div className="p-3 bg-emerald-950/40 border border-emerald-800/60 rounded-lg text-emerald-300">
              <span className="font-semibold block mb-1">API Key Generated Successfully</span>
              <p className="text-[11px] text-zinc-400">
                Copy this key immediately. You will not be able to see it again.
              </p>
            </div>
            <div className="flex items-center gap-2 p-2.5 bg-zinc-950 border border-zinc-800 rounded-lg">
              <code className="flex-1 font-mono text-[11px] text-emerald-400 truncate">{createdKey}</code>
              <Button size="sm" variant="secondary" onClick={() => copyToClipboard(createdKey)}>
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
            <div className="flex justify-end pt-3 border-t border-zinc-800">
              <Button variant="secondary" onClick={() => setShowKeyModal(false)}>
                Done
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleCreateKey} className="space-y-4 text-xs">
          {error && <p role="alert" className="text-rose-300">{error}</p>}
            <div>
              <label className="block font-medium text-zinc-300 mb-1" htmlFor="admin-field-5">Descriptive Key Name</label>
              <input id="admin-field-5"
                type="text"
                required
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-100 focus:outline-none focus:border-zinc-700"
                placeholder="e.g. CI-CD-Inference-Key"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
              <Button variant="secondary" onClick={() => setShowKeyModal(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" loading={submittingKey}>
                Generate
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
