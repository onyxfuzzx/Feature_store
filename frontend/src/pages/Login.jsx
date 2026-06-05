import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginApi } from "../api";
import { IconFeatures, IconArrowRight, IconLightning } from "../components/Icons";

export default function Login() {
  const [email, setEmail] = useState("admin@featureops.local");
  const [password, setPassword] = useState("ChangeMe123!");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginApi(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Invalid email or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-logo">
          <IconFeatures className="login-logo-svg" />
          <span className="brand-title">FeatureOps</span>
        </div>
        <p className="login-subtitle">Enterprise Feature Store &amp; Model Registry</p>

        {error && <div className="error-alert">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="login-email">Email Address</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="name@company.com"
            />
          </div>
          <div className="form-group">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••"
            />
          </div>
          <button type="submit" className="button login-button" disabled={loading}>
            {loading ? (
              "Authenticating…"
            ) : (
              <>
                Sign In <IconArrowRight style={{ marginLeft: 6 }} />
              </>
            )}
          </button>
        </form>

        <div className="login-demo">
          <p className="demo-title">
            <IconLightning className="inline-svg" /> Quick Demo Credentials
          </p>
          <div className="demo-row">
            <span><strong>Email:</strong> admin@featureops.local</span>
            <span><strong>Password:</strong> ChangeMe123!</span>
          </div>
          <span className="badge" style={{ marginTop: "8px", display: "inline-block" }}>Admin · All Roles</span>
        </div>
      </div>
    </div>
  );
}
