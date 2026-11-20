import { Link } from "react-router-dom";
import { ArrowUpRight, Clock3, Star } from "lucide-react";
import { Poster } from "./Feedback";
import { duration, money } from "../lib/format";

export function MovieCard({ movie, index = 0, compact = false }) {
  return (
    <Link
      to={`/movies/${movie.id}`}
      className={`movie-card ${compact ? "movie-card--compact" : ""}`}
      style={{ "--card-index": index }}
    >
      <div className="movie-card-art">
        <Poster src={movie.poster_url} title={movie.title} />
        <div className="movie-card-shade" />
        {movie.rating ? (
          <span className="rating-badge">
            <Star size={12} fill="currentColor" /> {Number(movie.rating).toFixed(1)}
          </span>
        ) : null}
        {movie.status === "coming_soon" ? <span className="movie-status">Coming soon</span> : null}
        <span className="movie-card-cta">
          Book <ArrowUpRight size={15} />
        </span>
      </div>
      <div className="movie-card-copy">
        <h3>{movie.title}</h3>
        <p className="movie-card-meta">
          {(movie.genres || []).slice(0, 2).join(" · ")}
          {movie.duration_min ? (
            <>
              <span className="dot" />
              <Clock3 size={13} /> {duration(movie.duration_min)}
            </>
          ) : null}
        </p>
        <div className="movie-card-foot">
          <span className="age-chip">{movie.age_rating}</span>
          {movie.starting_price ? (
            <span className="from-price">
              from <strong>{money(movie.starting_price)}</strong>
            </span>
          ) : (
            <span className="from-price">{movie.release_date?.slice(0, 4) || "Soon"}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
