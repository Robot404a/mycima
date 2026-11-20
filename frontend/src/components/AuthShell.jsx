import { useCallback } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Quote, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { Poster } from "./Feedback";

export function AuthShell({ eyebrow, title, subtitle, children, footer, side = "login" }) {
  const loader = useCallback(() => api("/movies/featured", { auth: false }), []);
  const { data } = useApi(loader, []);
  const movies = (data?.items || []).slice(0, 3);

  return (
    <div className="auth-page">
      <div className="auth-panel">
        <div className="auth-panel-top">
          <Link to="/" className="brand" aria-label="MyCima home">
            <span className="brand-mark" aria-hidden="true">
              <span />
            </span>
            <span className="brand-word">
              MYCIMA
              <small>Cinema, after dark</small>
            </span>
          </Link>
          <Link to="/" className="back-link">
            <ArrowLeft size={15} /> Back to the programme
          </Link>
        </div>
        <div className="auth-form-wrap">
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p className="auth-subtitle">{subtitle}</p>
          {children}
          {footer ? <div className="auth-footer">{footer}</div> : null}
        </div>
        <div className="auth-legal">
          <span>© {new Date().getFullYear()} MyCima Cinemas</span>
          <span>Casablanca · Morocco</span>
        </div>
      </div>

      <aside className="auth-visual" aria-hidden="true">
        <div className="auth-visual-glow" />
        <div className="auth-poster-stack">
          {movies.length
            ? movies.map((movie, index) => (
                <div key={movie.id} className={`auth-poster auth-poster--${index}`}>
                  <Poster src={movie.poster_url} title={movie.title} />
                </div>
              ))
            : [0, 1, 2].map((index) => (
                <div key={index} className={`auth-poster auth-poster--${index} auth-poster--empty`}>
                  <Sparkles size={18} />
                </div>
              ))}
        </div>
        <div className="auth-quote">
          <Quote size={22} />
          <p>
            {side === "login"
              ? "The room goes dark, the world falls away, and for two hours nothing else has to matter."
              : "Every great evening begins with a seat. Choose yours, and let the film do the rest."}
          </p>
          <small>The MyCima manifesto</small>
        </div>
        <div className="auth-visual-foot">
          <span className="pulse-dot" /> Three houses in Casablanca · IMAX &amp; Dolby Atmos
        </div>
      </aside>
    </div>
  );
}
