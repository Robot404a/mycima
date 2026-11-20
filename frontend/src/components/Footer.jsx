import { Link } from "react-router-dom";
import { Instagram, MapPin, MoveUpRight } from "lucide-react";

export function Footer() {
  return (
    <footer className="footer">
      <div className="footer-top">
        <div className="footer-brand">
          <span className="brand-word">
            NOCTURNE
            <small>Cinema, after dark</small>
          </span>
          <p>
            An independent cinema house in Casablanca. Stories on large screens, seats worth
            staying in, and a little darkness to make the light matter.
          </p>
          <span className="footer-note">Casablanca · Morocco · Since 2026</span>
        </div>
        <div className="footer-col">
          <h4>Visit</h4>
          <p>
            <MapPin size={14} /> Nocturne Central
            <br />
            12 Boulevard Mohammed V
            <br />
            Casablanca
          </p>
          <a href="mailto:hello@nocturne.ma">
            hello@nocturne.ma <MoveUpRight size={13} />
          </a>
        </div>
        <div className="footer-col">
          <h4>Explore</h4>
          <Link to="/#now-showing">Now showing</Link>
          <Link to="/#coming-soon">Coming soon</Link>
          <Link to="/bookings">My bookings</Link>
          <Link to="/notifications">Notifications</Link>
        </div>
        <div className="footer-col">
          <h4>Follow</h4>
          <a href="https://instagram.com" target="_blank" rel="noreferrer">
            <Instagram size={14} /> Instagram
          </a>
          <a href="https://letterboxd.com" target="_blank" rel="noreferrer">
            Letterboxd <MoveUpRight size={13} />
          </a>
          <span className="footer-tag">Late screenings every Thursday.</span>
        </div>
      </div>
      <div className="footer-bottom">
        <span>© {new Date().getFullYear()} Nocturne Cinemas. All rights reserved.</span>
        <span>A distributed booking experience.</span>
      </div>
    </footer>
  );
}
