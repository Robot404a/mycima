import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Clock3,
  MapPin,
  Play,
  Sparkles,
  Star,
  Ticket,
} from "lucide-react";
import { api } from "../lib/api";
import { useApi, useDocumentTitle } from "../lib/hooks";
import {
  dayParts,
  duration,
  formatDateLong,
  formatDateShort,
  money,
  relativeDayLabel,
} from "../lib/format";
import { ErrorState, PageLoader, Poster } from "../components/Feedback";

const FORMAT_COPY = {
  STANDARD: "The classic. Warm picture, generous screen, every seat in the room.",
  THREE_D: "Depth without the headache. A more immersive way into the story.",
  IMAX: "Wall-to-wall image and sound you feel in the floor.",
};

function openConcierge(prompt) {
  window.dispatchEvent(new CustomEvent("nocturne:assistant-open", { detail: { prompt } }));
}

function FilmHero({ movie }) {
  return (
    <section className="film-hero">
      <div
        className="film-hero-backdrop"
        style={{ "--film-image": `url(${movie.backdrop_url || movie.poster_url})` }}
      />
      <div className="film-hero-inner">
        <Link to="/" className="back-link">
          <ArrowLeft size={15} /> Back to the programme
        </Link>
        <div className="film-hero-grid">
          <div className="film-poster-panel">
            <Poster src={movie.poster_url} title={movie.title} loading="eager" />
            <span className="film-poster-edge" />
          </div>
          <div className="film-copy">
            <div className="film-kicker">
              <span className="eyebrow">{movie.status === "coming_soon" ? "Coming soon" : "Now showing"}</span>
              {movie.rating ? (
                <span className="film-rating">
                  <Star size={13} fill="currentColor" /> {Number(movie.rating).toFixed(1)}
                </span>
              ) : null}
              <span className="age-chip">{movie.age_rating}</span>
            </div>
            <h1>{movie.title}</h1>
            {movie.tagline ? <p className="film-tagline">“{movie.tagline}”</p> : null}
            <p className="film-synopsis">{movie.synopsis}</p>
            <div className="film-meta">
              <span>
                <Clock3 size={15} /> {duration(movie.duration_min)}
              </span>
              <span>
                <CalendarDays size={15} /> {movie.release_date ? formatDateShort(movie.release_date) : "2027"}
              </span>
              {movie.director ? <span>Directed by {movie.director}</span> : null}
            </div>
            <div className="film-genres">
              {(movie.genres || []).map((genre) => (
                <span key={genre}>{genre}</span>
              ))}
            </div>
            <div className="film-actions">
              {movie.status !== "coming_soon" ? (
                <a href="#showtimes" className="btn btn--gold">
                  <Ticket size={16} /> Choose a screening
                </a>
              ) : (
                <button
                  type="button"
                  className="btn btn--gold"
                  onClick={() => openConcierge(`Tell me about ${movie.title}`)}
                >
                  <Sparkles size={16} /> Ask the concierge
                </button>
              )}
              {movie.trailer_url ? (
                <a
                  href={movie.trailer_url}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn--ghost"
                >
                  <Play size={15} /> Watch trailer
                </a>
              ) : null}
            </div>
            {movie.cast?.length ? (
              <p className="film-cast">
                <span>With</span> {movie.cast.join(" · ")}
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function MovieDetail() {
  const { movieId } = useParams();
  const navigate = useNavigate();
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedFormat, setSelectedFormat] = useState(null);
  const scheduleRef = useRef(null);

  const movieLoader = useCallback(() => api(`/movies/${movieId}`, { auth: false }), [movieId]);
  const showtimesLoader = useCallback(
    () => api(`/movies/${movieId}/showtimes`, { auth: false }),
    [movieId],
  );
  const movieApi = useApi(movieLoader, [movieId]);
  const showtimesApi = useApi(showtimesLoader, [movieId]);
  useDocumentTitle(movieApi.data?.title || "Film");

  const movie = movieApi.data;
  const schedule = showtimesApi.data;
  const dates = schedule?.dates || [];
  const formats = schedule?.formats || [];

  useEffect(() => {
    if (!dates.length) return;
    setSelectedDate((current) => current || dates[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schedule]);

  useEffect(() => {
    if (!formats.length) return;
    setSelectedFormat((current) => current || formats[0]?.value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schedule]);

  const filteredShowtimes = useMemo(() => {
    return (schedule?.showtimes || []).filter(
      (item) => item.date === selectedDate && (!selectedFormat || item.format === selectedFormat),
    );
  }, [schedule, selectedDate, selectedFormat]);

  const groups = useMemo(() => {
    const byCinema = new Map();
    for (const showtime of filteredShowtimes) {
      const cinemaName = showtime.cinema?.name || "Nocturne";
      if (!byCinema.has(cinemaName)) {
        byCinema.set(cinemaName, { cinema: showtime.cinema, halls: new Map() });
      }
      const entry = byCinema.get(cinemaName);
      const hallName = showtime.hall?.name || "Screen";
      if (!entry.halls.has(hallName)) {
        entry.halls.set(hallName, { hall: showtime.hall, times: [] });
      }
      entry.halls.get(hallName).times.push(showtime);
    }
    return [...byCinema.values()].map((entry) => ({
      ...entry,
      halls: [...entry.halls.values()],
    }));
  }, [filteredShowtimes]);

  if (movieApi.loading) return <PageLoader label="Loading the film" />;
  if (movieApi.error) {
    return (
      <div className="page page--narrow">
        <ErrorState error={movieApi.error} onRetry={() => movieApi.reload(true)} title="This film slipped away" />
      </div>
    );
  }
  if (!movie) return null;

  const noSchedule = movie.status === "coming_soon" || !dates.length;

  return (
    <div className="film-page">
      <FilmHero movie={movie} />

      {noSchedule ? (
        <section className="section section--narrow">
          <div className="coming-panel">
            <span className="eyebrow">Not yet in the room</span>
            <h2>
              In the <em>distance</em>
            </h2>
            <p>
              {movie.title} arrives{" "}
              {movie.release_date ? formatDateLong(movie.release_date) : "soon"}. Ask the concierge to
              remember it for you, or explore what is on screen tonight.
            </p>
            <div className="coming-panel-actions">
              <button
                type="button"
                className="btn btn--gold"
                onClick={() => openConcierge(`Tell me about ${movie.title}`)}
              >
                <Sparkles size={16} /> Ask the concierge
              </button>
              <Link to="/#now-showing" className="btn btn--ghost">
                Explore now showing
              </Link>
            </div>
          </div>
        </section>
      ) : (
        <section className="section schedule-section" id="showtimes" ref={scheduleRef}>
          <div className="section-head">
            <div>
              <span className="eyebrow">Choose your evening</span>
              <h2>
                Pick a <em>screening</em>
              </h2>
            </div>
            <p className="section-note">
              Three steps: the day, the format, then the room. We'll take care of the seat.
            </p>
          </div>

          {showtimesApi.error ? (
            <ErrorState
              error={showtimesApi.error}
              onRetry={() => showtimesApi.reload(true)}
              title="The schedule is hiding"
            />
          ) : showtimesApi.loading ? (
            <PageLoader label="Finding screenings" />
          ) : (
            <div className="schedule-flow">
              <div className="schedule-step">
                <div className="schedule-step-head">
                  <span className="step-number">01</span>
                  <div>
                    <h3>Select a day</h3>
                    <p>{formatDateLong(selectedDate || dates[0])}</p>
                  </div>
                </div>
                <div className="date-strip" role="group" aria-label="Choose a date">
                  {dates.map((day) => {
                    const parts = dayParts(day);
                    const active = day === selectedDate;
                    return (
                      <button
                        key={day}
                        type="button"
                        className={`date-card ${active ? "is-active" : ""}`}
                        onClick={() => setSelectedDate(day)}
                        aria-pressed={active}
                      >
                        <small>{relativeDayLabel(day)}</small>
                        <strong>{parts.day}</strong>
                        <span>{parts.month}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="schedule-step">
                <div className="schedule-step-head">
                  <span className="step-number">02</span>
                  <div>
                    <h3>Select a format</h3>
                    <p>Each screen has its own character.</p>
                  </div>
                </div>
                <div className="format-grid" role="group" aria-label="Choose a format">
                  {formats.map((format) => {
                    const active = format.value === selectedFormat;
                    return (
                      <button
                        key={format.value}
                        type="button"
                        className={`format-card ${active ? "is-active" : ""}`}
                        onClick={() => setSelectedFormat(format.value)}
                        aria-pressed={active}
                      >
                        <span className="format-label">{format.label}</span>
                        <span className="format-count">{format.count} screenings</span>
                        <span className="format-description">
                          {FORMAT_COPY[format.value] || "A different way to see it."}
                        </span>
                        <span className="format-check">{active ? "Selected" : "Choose"}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="schedule-step">
                <div className="schedule-step-head">
                  <span className="step-number">03</span>
                  <div>
                    <h3>Choose a time</h3>
                    <p>
                      {selectedDate ? relativeDayLabel(selectedDate) : ""} ·{" "}
                      {formats.find((format) => format.value === selectedFormat)?.label || "All formats"}
                    </p>
                  </div>
                </div>

                {filteredShowtimes.length ? (
                  <div className="screening-groups">
                    {groups.map((group) => (
                      <div className="screening-group" key={group.cinema?.id || group.cinema?.name}>
                        <div className="screening-cinema">
                          <MapPin size={15} />
                          <div>
                            <strong>{group.cinema?.name}</strong>
                            <small>{group.cinema?.address}</small>
                          </div>
                        </div>
                        {group.halls.map((hall) => (
                          <div className="screening-hall" key={hall.hall?.id || hall.hall?.name}>
                            <div className="screening-hall-name">
                              <span>{hall.hall?.name}</span>
                              <small>{hall.hall?.screen_type}</small>
                            </div>
                            <div className="time-buttons">
                              {hall.times.map((showtime) => (
                                <Link
                                  key={showtime.id}
                                  to={`/booking/${showtime.id}`}
                                  className="time-button"
                                  aria-label={`Book ${showtime.format_label} at ${showtime.time} in ${hall.hall?.name}`}
                                >
                                  <strong>{showtime.time}</strong>
                                  <small>
                                    {showtime.format_label} · {money(showtime.base_price)} from
                                  </small>
                                </Link>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="state-card state-card--empty">
                    <span className="state-icon">
                      <CalendarDays size={22} />
                    </span>
                    <h3>No screenings for this combination</h3>
                    <p>Try another day or format — the programme changes daily.</p>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      onClick={() => setSelectedFormat(formats[0]?.value)}
                    >
                      Reset format
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      )}

      <section className="film-footer-note">
        <p>
          <Clock3 size={15} /> Doors open 20 minutes before each screening. Latecomers are seated at
          the house's discretion.
        </p>
        <button
          type="button"
          className="text-btn"
          onClick={() => openConcierge(`Find me seats for ${movie.title}`)}
        >
          Let the concierge choose <ArrowRight size={13} />
        </button>
      </section>
    </div>
  );
}
