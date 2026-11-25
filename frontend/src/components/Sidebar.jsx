import { NavLink, useNavigate } from "react-router-dom";
import { getActiveUser, logoutApi } from "../api";
import {
  LayoutDashboard,
  Layers,
  Cpu,
  Clock,
  Shield,
  LogOut,
  Database,
} from "lucide-react";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/features", label: "Feature Catalog", icon: Layers },
  { to: "/models", label: "Model Registry", icon: Cpu },
  {
    to: "/jobs",
    label: "Scheduler & Jobs",
    icon: Clock,
    roles: ["admin", "ml_engineer", "data_scientist"],
  },
  { to: "/admin", label: "Administration", icon: Shield, adminOnly: true },
];

export default function Sidebar() {
  const user = getActiveUser();
  const navigate = useNavigate();
  const isAdmin = user?.roles?.includes("admin");

  const handleLogout = () => {
    logoutApi();
    navigate("/login");
  };

  return (
    <aside className="w-64 bg-zinc-950 border-r border-zinc-800/80 flex flex-col h-screen sticky top-0 shrink-0 select-none">
      {/* Brand Header */}
      <div className="h-16 flex items-center gap-3 px-5 border-b border-zinc-800/80">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
          <Database className="w-4 h-4" />
        </div>
        <div>
          <span className="font-semibold text-sm tracking-tight text-zinc-100">
            FeatureOps
          </span>
          <span className="block text-[10px] text-zinc-500 tracking-wider uppercase font-mono">
            Platform
          </span>
        </div>
      </div>

      {/* Nav links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <div className="px-3 py-2 text-[11px] font-semibold tracking-wider text-zinc-500 uppercase font-mono">
          Core Engine
        </div>
        {navItems
          .filter(
            (item) =>
              (!item.adminOnly || isAdmin) &&
              (!item.roles ||
                item.roles.some((role) => user?.roles?.includes(role))),
          )
          .map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-zinc-900 text-emerald-400 border border-zinc-800"
                      : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/60"
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
      </nav>

      {/* User profile & Logout */}
      <div className="p-3 border-t border-zinc-800/80 bg-zinc-950/60">
        <div className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/60 border border-zinc-800/60">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-7 h-7 rounded-full bg-emerald-950 border border-emerald-700/50 flex items-center justify-center text-xs font-semibold text-emerald-400 shrink-0">
              {user?.name?.[0]?.toUpperCase() || "U"}
            </div>
            <div className="truncate">
              <div className="text-xs font-medium text-zinc-200 truncate">
                {user?.name || "Admin"}
              </div>
              <div className="text-[10px] font-mono text-zinc-500 uppercase">
                {user?.roles?.[0] || "user"}
              </div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="p-1.5 text-zinc-400 hover:text-rose-400 hover:bg-zinc-800 rounded-md transition"
            title="Log out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
