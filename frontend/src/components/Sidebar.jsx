import { NavLink, useNavigate } from "react-router-dom";
import { getActiveUser, logoutApi } from "../api";
import {
  IconDashboard,
  IconFeatures,
  IconModels,
  IconJobs,
  IconAdmin,
  IconLogout
} from "./Icons";

const iconMap = {
  dashboard: IconDashboard,
  features: IconFeatures,
  models: IconModels,
  jobs: IconJobs,
  admin: IconAdmin,
};

const navItems = [
  { to: "/", label: "Dashboard", iconKey: "dashboard", end: true },
  { to: "/features", label: "Features", iconKey: "features" },
  { to: "/models", label: "Models", iconKey: "models" },
  { to: "/jobs", label: "Jobs", iconKey: "jobs" },
  { to: "/admin", label: "Admin", iconKey: "admin", adminOnly: true },
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
    <aside className="sidebar">
      <div className="sidebar-brand">
        <IconFeatures className="brand-hex-svg" />
        <span className="brand-name">FeatureOps</span>
      </div>

      <nav className="nav">
        {navItems
          .filter((item) => !item.adminOnly || isAdmin)
          .map((item) => {
            const IconComp = iconMap[item.iconKey];
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive ? "nav-link active" : "nav-link"
                }
              >
                <span className="nav-icon">
                  {IconComp && <IconComp />}
                </span>
                {item.label}
              </NavLink>
            );
          })}
      </nav>

      <div className="sidebar-spacer" />

      <div className="sidebar-user-card">
        <div className="sidebar-user-avatar">
          {user?.name?.[0]?.toUpperCase() || "U"}
        </div>
        <div className="sidebar-user-info">
          <div className="sidebar-user-name">{user?.name || "User"}</div>
          <div className="sidebar-user-role">
            {user?.roles?.[0] || "viewer"}
          </div>
        </div>
        <button
          className="sidebar-logout-btn"
          onClick={handleLogout}
          title="Logout"
        >
          <IconLogout />
        </button>
      </div>
    </aside>
  );
}
