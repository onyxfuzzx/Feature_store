import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { fetchApi } from "../api";
import { Search, Layers, Cpu, Database } from "lucide-react";

export default function TopBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setResults(null);
      setOpen(false);
      return;
    }
    const timeout = setTimeout(async () => {
      try {
        const data = await fetchApi(`/search?q=${encodeURIComponent(query)}`);
        setResults(data);
        setOpen(true);
      } catch {
        /* ignore */
      }
    }, 250);
    return () => clearTimeout(timeout);
  }, [query]);

  return (
    <header className="h-16 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md sticky top-0 z-30 px-6 flex items-center justify-between">
      {/* Search Input */}
      <div className="relative w-80 max-w-md" ref={ref}>
        <div className="relative flex items-center">
          <Search className="w-4 h-4 text-zinc-400 absolute left-3 pointer-events-none" />
          <input
            id="global-search"
            type="text"
            className="w-full bg-zinc-900/80 border border-zinc-800 text-xs text-zinc-100 pl-9 pr-3 py-2 rounded-lg placeholder:text-zinc-500 focus:outline-none focus:border-zinc-700 focus:ring-1 focus:ring-emerald-500/40 transition"
            placeholder="Search features, models, tags…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => results && setOpen(true)}
          />
        </div>

        {/* Search Results Dropdown */}
        {open && results && (
          <div className="absolute left-0 right-0 mt-2 bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl p-2 z-50 text-xs max-h-80 overflow-y-auto">
            {results.features.length === 0 && results.models.length === 0 && (
              <div className="p-3 text-center text-zinc-500">No results found for "{query}"</div>
            )}
            {results.features.length > 0 && (
              <div className="mb-2">
                <div className="px-2 py-1 text-[10px] font-mono uppercase text-zinc-500 font-semibold">Features</div>
                {results.features.map((f) => (
                  <div
                    key={f.id}
                    className="flex items-center gap-2 p-2 hover:bg-zinc-800 rounded-md cursor-pointer text-zinc-200 transition"
                    onClick={() => {
                      navigate(`/features/${f.id}`);
                      setOpen(false);
                      setQuery("");
                    }}
                  >
                    <Layers className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span className="truncate">{f.name}</span>
                  </div>
                ))}
              </div>
            )}
            {results.models.length > 0 && (
              <div>
                <div className="px-2 py-1 text-[10px] font-mono uppercase text-zinc-500 font-semibold">Models</div>
                {results.models.map((m) => (
                  <div
                    key={m.id}
                    className="flex items-center gap-2 p-2 hover:bg-zinc-800 rounded-md cursor-pointer text-zinc-200 transition"
                    onClick={() => {
                      navigate(`/models/${m.id}`);
                      setOpen(false);
                      setQuery("");
                    }}
                  >
                    <Cpu className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                    <span className="truncate">{m.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right status items */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/40 text-emerald-400 text-xs font-medium font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Supabase Connected</span>
        </div>
      </div>
    </header>
  );
}
