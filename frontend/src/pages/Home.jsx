import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Clock3, MapPin, Search, Sparkles, Ticket, Volume2 } from "lucide-react";
import { api } from "../lib/api";
import { useApi, useDocumentTitle } from "../lib/hooks";
import { formatDateShort, money } from "../lib/format";
import { MovieCard } from "../components/MovieCard";
import FilmShowcase from "../components/FilmShowcase";
import { EmptyState, ErrorState, Poster, Skeleton } from "../components/Feedback";

const GENRES = ["All", "Sci-Fi", "Drama", "Thriller", "Comedy", "Romance", "Animation", "Crime"];

function openConcierge(prompt) {
  window.dispatchEvent(new CustomEvent("nocturne:assistant-open", { detail: { prompt } }));
}

function Hero({ featured, nowShowing }) {
  const movie = featured?.[0] || nowShowing?.[0];
  if (!movie) {
    return (
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">Casablanca · Cinema after dark</span>
          <h1>
            Stories that <em>stay</em> after the credits.
          </h1>
          <p className="hero-lede">
            An independent house for big screens, deep seats and the kind of films you keep
            thinking about on the walk home.
          </p>
        </div>
        <div className="hero-shelf">
          <Skeleton className="hero-skeleton" />
        </div>
      </section>
    );
  }
  return (
    <section className="hero">
      <div className="hero-atmosphere" style={{ "--hero-image": `url(${movie.backdrop_url || movie.poster_url})` }} />
      <div className="hero-copy">
        <span className="eyebrow">
          <span className="eyebrow-line" /> Casablanca · Cinema after dark
        </span>
        <h1>
          Stories that <em>stay</em> after the credits.
        </h1>
        <p className="hero-lede">
          Big screens, deep seats and a programme chosen for the way it makes you feel. Tonight,
          the lights go down on something worth remembering.
        </p>
        <div className="hero-actions">
          <Link to={`/movies/${movie.id}`} className="btn btn--gold btn--lg">
            <Ticket size={17} /> Book tonight's film
          </Link>
          <a href="#now-showing" className="btn btn--ghost btn--lg">
            Explore the programme <ArrowRight size={16} />
          </a>
        </div>
        <div className="hero-meta">
          <span>
            <strong>{nowShowing?.length || 8}</strong> films on screen
          </span>
          <span className="hero-meta-divider" />
          <span>
            <strong>3</strong> houses in Casablanca
          </span>
          <span className="hero-meta-divider" />
          <span>
            IMAX <span className="dot" /> Dolby Atmos
          </span>
        </div>
      </div>

      <div className="hero-shelf">
        <FilmShowcase movies={featured?.length ? featured : nowShowing} label="Casablanca programme" />
      </div>

      <div className="hero-scroll">
        <span>Scroll to explore</span>
        <span className="scroll-line" />
      </div>
    </section>
  );
}

function ComingCard({ movie, index }) {
  return (
    <article className="coming-card" style={{ "--card-index": index }}>
      <Link to={`/movies/${movie.id}`} className="coming-art">
        <Poster src={movie.poster_url} title={movie.title} />
        <span className="coming-year">{movie.release_date?.slice(0, 4) || "Soon"}</span>
      </Link>
      <div className="coming-copy">
        <span className="eyebrow">In the distance</span>
        <h3>{movie.title}</h3>
        <p>{movie.tagline}</p>
        <button
          type="button"
          className="text-btn"
          onClick={() => openConcierge(`Tell me about ${movie.title}`)}
        >
          Ask the concierge <ArrowRight size={13} />
        </button>
      </div>
    </article>
  );
}

export default function Home() {
  useDocumentTitle();
  const [genre, setGenre] = useState("All");
  const [query, setQuery] = useState("");

  const nowLoader = useCallback(
    () => api("/movies", { params: { status: "now_showing", limit: 50 }, auth: false }),
    [],
  );
  const comingLoader = useCallback(
    () => api("/movies", { params: { status: "coming_soon", limit: 20 }, auth: false }),
    [],
  );
  const featuredLoader = useCallback(() => api("/movies/featured", { auth: false }), []);
  const cinemasLoader = useCallback(() => api("/cinemas", { auth: false }), []);

  const now = useApi(nowLoader, []);
  const coming = useApi(comingLoader, []);
  const featured = useApi(featuredLoader, []);
  const cinemas = useApi(cinemasLoader, []);

  const nowItems = now.data?.items || [];
  const comingItems = coming.data?.items || [];
  const featuredItems = featured.data?.items || [];
  const cinemaItems = cinemas.data?.items || [];

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return nowItems.filter((movie) => {
      const genreMatch =
        genre === "All" || (movie.genres || []).some((item) => item.toLowerCase() === genre.toLowerCase());
      const queryMatch =
        !needle ||
        movie.title.toLowerCase().includes(needle) ||
        (movie.genres || []).join(" ").toLowerCase().includes(needle) ||
        (movie.mood_tags || []).join(" ").toLowerCase().includes(needle);
      return genreMatch && queryMatch;
    });
  }, [nowItems, genre, query]);

  return (
    <div className="home">
      <Hero featured={featuredItems} nowShowing={nowItems} />

      <div className="ticker" aria-hidden="true">
        <div className="ticker-track">
          {Array.from({ length: 2 }).map((_, index) => (
            <span key={index}>
              Now showing <i>·</i> Casablanca <i>·</i> Late screenings every Thursday <i>·</i>{" "}
              IMAX &amp; Dolby Atmos <i>·</i> Curated by Nocturne <i>·</i>
            </span>
          ))}
        </div>
      </div>

      <section className="section" id="now-showing">
        <div className="section-head">
          <div>
            <span className="eyebrow">The programme</span>
            <h2>
              On our <em>screens</em>
            </h2>
          </div>
          <p className="section-note">
            This week's selection, from new releases to the films we couldn't stop thinking about.
          </p>
        </div>

        <div className="programme-tools">
          <div className="genre-chips" role="group" aria-label="Filter by genre">
            {GENRES.map((item) => (
              <button
                key={item}
                type="button"
                className={`chip ${genre === item ? "is-active" : ""}`}
                onClick={() => setGenre(item)}
              >
                {item}
              </button>
            ))}
          </div>
          <label className="search-field">
            <Search size={16} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search a film or a mood"
              aria-label="Search films"
            />
          </label>
        </div>

        {now.loading ? (
          <div className="movie-grid">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="movie-card movie-card--skeleton">
                <Skeleton className="skeleton-poster" />
                <div className="movie-card-copy">
                  <Skeleton style={{ width: "70%", height: 18 }} />
                  <Skeleton style={{ width: "45%", height: 12, marginTop: 10 }} />
                </div>
              </div>
            ))}
          </div>
        ) : now.error ? (
          <ErrorState error={now.error} onRetry={() => now.reload(true)} title="The programme is hiding" />
        ) : filtered.length ? (
          <div className="movie-grid">
            {filtered.map((movie, index) => (
              <MovieCard key={movie.id} movie={movie} index={index} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Search}
            title="No films match that mood"
            message="Try another genre or clear the search to see the full programme."
            action={
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => {
                  setGenre("All");
                  setQuery("");
                }}
              >
                Clear filters
              </button>
            }
          />
        )}
      </section>

      <section className="section section--split" id="coming-soon">
        <div className="section-head section-head--stacked">
          <span className="eyebrow">In the distance</span>
          <h2>
            Coming <em>soon</em>
          </h2>
          <p className="section-note">
            The films already casting a shadow on our calendar. Ask the concierge to tell you more.
          </p>
        </div>
        {coming.loading ? (
          <div className="coming-rail">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="coming-skeleton" />
            ))}
          </div>
        ) : (
          <div className="coming-rail">
            {comingItems.map((movie, index) => (
              <ComingCard key={movie.id} movie={movie} index={index} />
            ))}
          </div>
        )}
      </section>

      <section className="experience-band">
        <div className="experience-copy">
          <span className="eyebrow">The Nocturne standard</span>
          <h2>
            Built for the <em>dark</em>.
          </h2>
          <p>
            Three houses across Casablanca — Central on boulevard Mohammed V, Riviera on the
            Corniche, Anfa in the neighbourhood — each tuned for picture, sound and the distance
            between you and the screen.
          </p>
          <div className="experience-list">
            <div>
              <Volume2 size={17} />
              <span>Dolby Atmos sound</span>
            </div>
            <div>
              <Ticket size={17} />
              <span>Seats you sink into</span>
            </div>
            <div>
              <Clock3 size={17} />
              <span>Late screenings on Thursdays</span>
            </div>
          </div>
        </div>
        <div className="experience-image">
          <div className="experience-quote">
            <span>“</span>
            <p>
              Casablanca deserves a cinema that stays dark when the lights come up. That’s the
              room we built.
            </p>
            <small>The Nocturne standard</small>
            <small className="experience-credit">
              Cinema hall · Lichtburg Essen, photo by Tuxyso / Wikimedia Commons, CC BY-SA 4.0
            </small>
          </div>
        </div>
      </section>

      <section className="section" id="cinemas">
        <div className="section-head">
          <div>
            <span className="eyebrow">Three houses</span>
            <h2>
              Find your <em>room</em>
            </h2>
          </div>
          <p className="section-note">
            A flagship in the city, a coastal room with velvet seats, and an arthouse for the curious.
          </p>
        </div>
        <div className="cinema-grid">
          {(cinemaItems.length ? cinemaItems : [null, null, null]).map((cinema, index) =>
            cinema ? (
              <article
                key={cinema.id}
                className={`cinema-card ${index === 0 ? "cinema-card--featured" : ""}`}
              >
                <div className="cinema-index">0{index + 1}</div>
                <span className="eyebrow">{cinema.city}</span>
                <h3>{cinema.name}</h3>
                <p className="cinema-address">
                  <MapPin size={14} /> {cinema.address}
                </p>
                <p className="cinema-description">{cinema.description}</p>
                <div className="amenity-row">
                  {(cinema.amenities || []).slice(0, 3).map((amenity) => (
                    <span key={amenity}>{amenity}</span>
                  ))}
                </div>
                <span className="cinema-halls">
                  {cinema.halls?.length || 0} screen{cinema.halls?.length === 1 ? "" : "s"}
                </span>
              </article>
            ) : (
              <Skeleton key={index} className="cinema-skeleton" />
            ),
          )}
        </div>
      </section>

      <section className="concierge-band">
        <div className="concierge-glow" aria-hidden="true" />
        <div className="concierge-copy">
          <span className="eyebrow">
            <Sparkles size={14} /> The concierge
          </span>
          <h2>
            Not sure what to <em>see</em>?
          </h2>
          <p>
            Tell us the mood, the company or the number of seats. Our concierge finds the film,
            the screening and the best seats — then waits for your confirmation.
          </p>
          <button
            type="button"
            className="btn btn--gold"
            onClick={() => openConcierge("I want two seats together for something thoughtful tomorrow evening")}
          >
            Ask the concierge <Sparkles size={15} />
          </button>
        </div>
        <div className="concierge-preview" aria-hidden="true">
          <div className="concierge-preview-head">
            <span className="assistant-orb">
              <Sparkles size={15} />
            </span>
            <span>Two seats, something warm</span>
          </div>
          <div className="preview-bubble preview-bubble--user">
            I'm in the mood for a comedy tomorrow evening, 2 seats together.
          </div>
          <div className="preview-bubble preview-bubble--bot">
            I found <strong>Everything Everywhere All at Once</strong> at Nocturne Central, tomorrow
            at 21:30. Two seats in row F, 160 MAD total. Shall I hold them?
          </div>
          <div className="preview-tag">
            <span className="pulse-dot" /> Hold confirmed only after you say yes
          </div>
        </div>
      </section>
    </div>
  );
}
