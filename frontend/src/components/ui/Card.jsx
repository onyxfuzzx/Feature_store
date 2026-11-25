export function Card({ children, className = "", hover = false, ...props }) {
  return (
    <div
      className={`bg-zinc-900/80 border border-zinc-800/80 rounded-xl p-5 ${hover ? "hover:border-zinc-700/80 transition-colors" : ""} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, description, action }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div>
        <h3 className="text-sm font-semibold text-zinc-100 tracking-tight">
          {title}
        </h3>
        {description && (
          <p className="text-xs text-zinc-400 mt-0.5">{description}</p>
        )}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
