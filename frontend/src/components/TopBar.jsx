import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { fetchApi, getActiveUser } from "../api";
import { IconSearch, IconFeatures, IconModels } from "./Icons";

export default function TopBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [open, setOpen] = useState(false);
  const user = getActiveUser();
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
    }, 320);
    return () => clearTimeout(timeout);
  }, [query]);

  return (
    <header className="topbar">
      <div className="topbar-search-wrap" ref={ref}>
        <IconSearch className="topbar-search-icon" />
        <input
          id="global-search"
          className="search"
          placeholder="Search features, models, tags…"
          aria-label="Global search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results && setOpen(true)}
        />
        {open && results && (
          <div className="search-dropdown">
            {results.features.length === 0 && results.models.length === 0 && (
              <div className="search-empty">No results for "{query}"</div>
            )}
            {results.features.length > 0 && (
              <div className="search-section">
                <div className="search-section-label">Features</div>
                {results.features.map((f) => (
                  <div
                    key={f.id}
                    className="search-item"
                    onClick={() => {
                      navigate(`/features/${f.id}`);
                      setOpen(false);
                      setQuery("");
                    }}
                  >
                    <span className="search-icon"><IconFeatures /></span> {f.name}
                  </div>
                ))}
              </div>
            )}
            {results.models.length > 0 && (
              <div className="search-section">
                <div className="search-section-label">Models</div>
                {results.models.map((m) => (
                  <div
                    key={m.id}
                    className="search-item"
                    onClick={() => {
                      navigate(`/models/${m.id}`);
                      setOpen(false);
                      setQuery("");
                    }}
                  >
                    <span className="search-icon"><IconModels /></span> {m.name}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="topbar-right">
        <span className="tag">Live</span>
        <div className="topbar-user">
          <div className="topbar-avatar">
            {user?.name?.[0]?.toUpperCase() || "U"}
          </div>
          <div className="topbar-user-info">
            <span className="topbar-user-name">{user?.name || "User"}</span>
            <span className="topbar-user-role">{user?.roles?.[0] || ""}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
