import React from "react";
import { Loader2 } from "lucide-react";

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  className = "",
  type = "button",
  onClick,
  ...props
}) {
  const base = "inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:opacity-50 disabled:pointer-events-none";
  
  const sizes = {
    sm: "text-xs px-2.5 py-1.5 gap-1.5",
    md: "text-sm px-3.5 py-2 gap-2",
    lg: "text-sm px-4 py-2.5 gap-2",
  };

  const variants = {
    primary: "bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm shadow-emerald-950",
    secondary: "bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700/60",
    outline: "border border-zinc-800 hover:bg-zinc-800/60 text-zinc-300 hover:text-white",
    ghost: "hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100",
    danger: "bg-rose-600/90 hover:bg-rose-600 text-white shadow-sm shadow-rose-950",
  };

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
      {...props}
    >
      {loading && <Loader2 className="w-4 h-4 animate-spin" />}
      {children}
    </button>
  );
}
