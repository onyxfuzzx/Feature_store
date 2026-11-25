import React from "react";
import { Route, Routes, Navigate } from "react-router-dom";
import { getAuthToken, getActiveUser } from "./api";

import Sidebar from "./components/Sidebar.jsx";
import TopBar from "./components/TopBar.jsx";
import Admin from "./pages/Admin.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import FeatureCatalog from "./pages/FeatureCatalog.jsx";
import FeatureDetail from "./pages/FeatureDetail.jsx";
import Jobs from "./pages/Jobs.jsx";
import Login from "./pages/Login.jsx";
import ModelDetail from "./pages/ModelDetail.jsx";
import ModelRegistry from "./pages/ModelRegistry.jsx";
import NotFound from "./pages/NotFound.jsx";

function ProtectedLayout() {
  const token = getAuthToken();
  if (!token) return <Navigate to="/login" replace />;

  const user = getActiveUser();
  const jobAccess = user?.roles?.some((role) => ["admin", "ml_engineer", "data_scientist"].includes(role));
  const denied = <p role="alert">You do not have permission to access this page.</p>;
  return (
    <div className="flex min-h-screen bg-zinc-950 text-zinc-100">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 p-8 max-w-7xl w-full mx-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/features" element={<FeatureCatalog />} />
            <Route path="/features/:id" element={<FeatureDetail />} />
            <Route path="/models" element={<ModelRegistry />} />
            <Route path="/models/:id" element={<ModelDetail />} />
            <Route path="/jobs" element={jobAccess ? <Jobs /> : denied} />
            <Route path="/admin" element={user?.roles?.includes("admin") ? <Admin /> : denied} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<ProtectedLayout />} />
    </Routes>
  );
}
