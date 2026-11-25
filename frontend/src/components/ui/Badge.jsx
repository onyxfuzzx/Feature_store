export function Badge({ children, variant = "default", className = "" }) {
  const styles = {
    default: "bg-zinc-800/70 text-zinc-300 border-zinc-700/60",
    success: "bg-emerald-950/60 text-emerald-400 border-emerald-800/40",
    warning: "bg-amber-950/60 text-amber-400 border-amber-800/40",
    danger: "bg-rose-950/60 text-rose-400 border-rose-800/40",
    info: "bg-sky-950/60 text-sky-400 border-sky-800/40",
    purple: "bg-purple-950/60 text-purple-400 border-purple-800/40",
  };

  let resolvedVariant = variant;
  const str = String(children).toLowerCase();
  if (str === "active" || str === "success" || str === "production")
    resolvedVariant = "success";
  else if (str === "running" || str === "staging" || str === "moderate_drift")
    resolvedVariant = "warning";
  else if (str === "failed" || str === "error" || str === "danger")
    resolvedVariant = "danger";
  else if (str === "draft" || str === "archived") resolvedVariant = "default";

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${styles[resolvedVariant] || styles.default} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />
      {children}
    </span>
  );
}
