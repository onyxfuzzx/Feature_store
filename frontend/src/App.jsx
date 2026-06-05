import { Route, Routes, Navigate } from "react-router-dom";
import { getAuthToken } from "./api";

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
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <TopBar />
        <div className="page">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/features" element={<FeatureCatalog />} />
            <Route path="/features/:id" element={<FeatureDetail />} />
            <Route path="/models" element={<ModelRegistry />} />
            <Route path="/models/:id" element={<ModelDetail />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </div>
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
