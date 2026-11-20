import { Link } from "react-router-dom";
import { ArrowLeft, Film } from "lucide-react";
import { useDocumentTitle } from "../lib/hooks";

export default function NotFound() {
  useDocumentTitle("Reel not found");
  return (
    <div className="notfound page">
      <div className="notfound-grain" aria-hidden="true" />
      <div className="notfound-inner">
        <span className="notfound-code">404</span>
        <span className="eyebrow">
          <Film size={14} /> Reel not found
        </span>
        <h1>
          This scene was <em>cut</em>.
        </h1>
        <p>
          The page you're looking for is not in this cut of the film. It may have moved, or the
          projector simply skipped a frame.
        </p>
        <div className="notfound-actions">
          <Link to="/" className="btn btn--gold">
            <ArrowLeft size={15} /> Back to the programme
          </Link>
          <Link to="/bookings" className="btn btn--ghost">
            My bookings
          </Link>
        </div>
      </div>
    </div>
  );
}
