import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginApi } from "../api";
import { Button } from "../components/ui/Button";
import { Database, Lock, Mail, AlertCircle, ArrowRight } from "lucide-react";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await loginApi(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Failed to log in");
    } finally {
      setLoading(false);
    }
  };

  const handleFillDemo = () => {
    setEmail("admin@featureops.local");
    setPassword("ChangeMe123!");
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col justify-center items-center px-4 relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute w-[500px] h-[500px] bg-emerald-500/5 rounded-full blur-3xl pointer-events-none -top-40 -right-20" />
      <div className="absolute w-[500px] h-[500px] bg-indigo-500/5 rounded-full blur-3xl pointer-events-none -bottom-40 -left-20" />

      <div className="w-full max-w-md z-10">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 mb-4 shadow-inner">
            <Database className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Sign in to FeatureOps</h1>
          <p className="text-sm text-zinc-400 mt-1">Enterprise Feature Store & Model Registry Platform</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 sm:p-8 shadow-2xl">
          {error && (
            <div className="mb-5 p-3 rounded-lg bg-rose-950/50 border border-rose-800/60 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5" htmlFor="email">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-zinc-500 absolute left-3 top-3 pointer-events-none" />
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@featureops.local"
                  className="w-full bg-zinc-950 border border-zinc-800 text-sm text-zinc-100 pl-9 pr-3 py-2.5 rounded-lg focus:outline-none focus:border-zinc-700 focus:ring-1 focus:ring-emerald-500/40 transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5" htmlFor="password">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-zinc-500 absolute left-3 top-3 pointer-events-none" />
                <input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-zinc-950 border border-zinc-800 text-sm text-zinc-100 pl-9 pr-3 py-2.5 rounded-lg focus:outline-none focus:border-zinc-700 focus:ring-1 focus:ring-emerald-500/40 transition"
                />
              </div>
            </div>

            <Button type="submit" variant="primary" size="lg" className="w-full mt-2" loading={loading}>
              Sign In <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </form>

          {/* Quick Demo Fill button */}
          <div className="mt-6 pt-5 border-t border-zinc-800/80 text-center">
            <button
              type="button"
              onClick={handleFillDemo}
              className="text-xs text-zinc-400 hover:text-emerald-400 transition font-mono underline underline-offset-4"
            >
              Fill default admin credentials
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
