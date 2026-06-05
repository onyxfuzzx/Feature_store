import { Link } from "react-router-dom";
import { IconFeatures, IconArrowLeft } from "../components/Icons";

export default function NotFound() {
  return (
    <section style={{ textAlign: "center", paddingTop: 80 }}>
      <div>
        <IconFeatures style={{ width: "5rem", height: "5rem", marginBottom: 16, color: "var(--mint)" }} />
      </div>
      <h1 className="page-title">404 — Not Found</h1>
      <p className="subtle" style={{ marginBottom: 24 }}>The page you're looking for doesn't exist.</p>
      <Link to="/" className="button" style={{ display: "inline-flex" }}>
        <IconArrowLeft style={{ marginRight: 6 }} /> Back to Dashboard
      </Link>
    </section>
  );
}
