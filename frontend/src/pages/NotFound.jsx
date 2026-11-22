import React from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { AlertCircle, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="py-24 text-center space-y-4">
      <div className="inline-flex p-3 rounded-2xl bg-zinc-900 border border-zinc-800 text-zinc-400 mb-2">
        <AlertCircle className="w-8 h-8" />
      </div>
      <h1 className="text-3xl font-bold tracking-tight text-zinc-100">404 — Page Not Found</h1>
      <p className="text-sm text-zinc-400 max-w-sm mx-auto">
        The feature or page you requested could not be located in the platform registry.
      </p>
      <div className="pt-2">
        <Link to="/">
          <Button variant="secondary">
            <ArrowLeft className="w-4 h-4" /> Back to Mission Control
          </Button>
        </Link>
      </div>
    </div>
  );
}
