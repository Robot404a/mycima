import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Star } from "lucide-react";
import { duration } from "../lib/format";

const SLIDE_MS = 3600;

function splitTitle(title) {
  const words = String(title || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length) return { lead: "", tail: "Untitled" };
  if (words.length === 1) return { lead: "", tail: words[0] };
  return { lead: words.slice(0, -1).join(" "), tail: words[words.length - 1] };
}

function FilmSlide({ movie, active, index, total }) {
  const { lead, tail } = splitTitle(movie.title);
  const genres = (movie.genres || []).slice(0, 2);
  const meta = [
    movie.duration_min ? duration(movie.duration_min) : null,
    movie.age_rating || null,
    ...genres,
  ].filter(Boolean);

  return (
    <article
      className={`showcase-slide ${active ? "is-active" : ""}`}
      aria-label={`${index + 1} of ${total}: ${movie.title}`}
      aria-hidden={active ? undefined : "true"}
    >
      <div
        className="showcase-art"
        style={{ backgroundImage: `url(${movie.backdrop_url || movie.poster_url})` }}
      />
      <div className="showcase-veil" />
      <div className="showcase-copy">
        <span className="showcase-kicker">On the programme</span>
        {movie.tagline ? <p className="showcase-tagline">{movie.tagline}</p> : null}
        <h2 className="showcase-title">
          {lead ? `${lead} ` : null}
          <em>{tail}</em>
        </h2>
        <div className="showcase-meta">
          {movie.rating ? (
            <span className="showcase-rating">
              <Star size={11} fill="currentColor" /> {Number(movie.rating).toFixed(1)}
            </span>
          ) : null}
          {meta.map((item, itemIndex) => (
            <span key={`${movie.id}-meta-${itemIndex}`} className="showcase-meta-item">
              {itemIndex > 0 || movie.rating ? <span className="dot" /> : null}
              {item}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}

export default function FilmShowcase({ movies = [], label = "The programme" }) {
  const items = useMemo(
    () => (movies || []).filter((movie) => movie && movie.id),
    [movies],
  );
  const total = items.length;
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (index >= total) setIndex(0);
  }, [index, total]);

  // Hold each film for a few seconds, then cut to the next one
  useEffect(() => {
    if (paused || total < 2) return undefined;
    const timer = window.setTimeout(() => {
      setIndex((current) => (current + 1) % total);
    }, SLIDE_MS);
    return () => window.clearTimeout(timer);
  }, [paused, total, index]);

  if (!total) {
    return (
      <div className="showcase showcase--empty">
        <div className="showcase-copy">
          <span className="showcase-kicker">The programme</span>
          <h2 className="showcase-title">
            <em>Loading</em> the reel
          </h2>
        </div>
      </div>
    );
  }

  const active = items[Math.min(index, total - 1)];

  return (
    <section
      className={`showcase ${paused ? "is-paused" : ""}`}
      style={{ "--showcase-duration": `${SLIDE_MS}ms` }}
      aria-roledescription="carousel"
      aria-label="Films now showing at Nocturne"
      onPointerEnter={() => setPaused(true)}
      onPointerLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
    >
      {items.map((movie, slideIndex) => (
        <FilmSlide
          key={movie.id}
          movie={movie}
          active={slideIndex === index}
          index={slideIndex}
          total={total}
        />
      ))}

      <div className="showcase-top">
        <span className="showcase-label">
          <span className="showcase-live" />
          {label}
        </span>
        <span className="showcase-badge">Now showing</span>
      </div>

      <div className="showcase-foot">
        <span className="showcase-count">
          <strong>{String(index + 1).padStart(2, "0")}</strong> / {String(total).padStart(2, "0")}
        </span>
        <span className="showcase-track">
          <span key={`${active.id}-progress`} />
        </span>
        <div className="showcase-dots" role="tablist" aria-label="Choose a film">
          {items.map((movie, dotIndex) => (
            <button
              key={movie.id}
              type="button"
              role="tab"
              aria-selected={dotIndex === index}
              aria-label={movie.title}
              className={dotIndex === index ? "is-active" : ""}
              onClick={() => setIndex(dotIndex)}
            />
          ))}
        </div>
        <Link to={`/movies/${active.id}`} className="showcase-link">
          View film <ArrowUpRight size={13} />
        </Link>
      </div>
    </section>
  );
}
