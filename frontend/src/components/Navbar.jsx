import { useCallback, useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Bell,
  CalendarDays,
  ChevronDown,
  LogOut,
  Menu,
  Moon,
  Settings2,
  Sun,
  Ticket,
  UserRound,
  X,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useCurrency } from "../context/CurrencyContext";
import { useTheme } from "../context/ThemeContext";
import { useApi } from "../lib/hooks";
import { api } from "../lib/api";
import { initials, relativeTime } from "../lib/format";
import { useClickOutside } from "../lib/hooks";

function NotificationBell() {
  const { isAuthenticated, user } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const location = useLocation();
  useClickOutside(ref, () => setOpen(false));

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  const loader = useCallback(
    () => (isAuthenticated ? api("/notifications/me", { params: { limit: 5 } }) : Promise.resolve(null)),
    [isAuthenticated, user?.id],
  );
  const { data, reload } = useApi(loader, [isAuthenticated, user?.id], {
    enabled: isAuthenticated,
    interval: 30000,
  });

  if (!isAuthenticated) return null;
  const unread = data?.unread || 0;
  const items = data?.items || [];

  const markRead = async (id) => {
    try {
      await api(`/notifications/${id}/read`, { method: "PATCH" });
      reload();
    } catch {
      /* non-critical */
    }
  };

  const markAll = async () => {
    try {
      await api("/notifications/read-all", { method: "POST" });
      reload();
    } catch {
      /* non-critical */
    }
  };

  return (
    <div className="nav-popover-wrap" ref={ref}>
      <button
        type="button"
        className={`icon-btn nav-bell ${open ? "is-active" : ""}`}
        onClick={() => setOpen((value) => !value)}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
        aria-expanded={open}
      >
        <Bell size={18} />
        {unread > 0 ? <span className="badge-dot">{unread > 9 ? "9+" : unread}</span> : null}
      </button>
      {open ? (
        <div className="popover notification-popover">
          <div className="popover-head">
            <span>Notifications</span>
            {unread > 0 ? (
              <button type="button" className="text-btn" onClick={markAll}>
                Mark all read
              </button>
            ) : null}
          </div>
          {items.length ? (
            <div className="notification-mini-list">
              {items.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={`notification-mini ${item.is_read ? "" : "is-unread"}`}
                  onClick={() => markRead(item.id)}
                >
                  <span className="notification-dot" />
                  <span>
                    <strong>{item.title}</strong>
                    <small>{relativeTime(item.created_at)}</small>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="popover-empty">
              <Bell size={20} />
              <p>No notifications yet.</p>
            </div>
          )}
          <Link className="popover-foot" to="/notifications">
            View all <span aria-hidden="true">→</span>
          </Link>
        </div>
      ) : null}
    </div>
  );
}

export function Navbar() {
  const { isAuthenticated, isAdmin, user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { currency, label: currencyLabel, name: currencyName, toggleCurrency } = useCurrency();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const isHome = location.pathname === "/";
  useClickOutside(accountRef, () => setAccountOpen(false));

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
    setAccountOpen(false);
  }, [location.pathname, location.hash]);

  const solid = scrolled || !isHome;

  const doLogout = () => {
    logout();
    setAccountOpen(false);
    navigate("/");
  };

  return (
    <header className={`navbar ${solid ? "is-solid" : ""} ${mobileOpen ? "is-open" : ""}`}>
      <div className="navbar-inner">
        <Link to="/" className="brand" aria-label="Nocturne home">
          <span className="brand-mark" aria-hidden="true">
            <span />
          </span>
          <span className="brand-word">
            NOCTURNE
            <small>Cinema, after dark</small>
          </span>
        </Link>

        <nav className="nav-links" aria-label="Main navigation">
          <NavLink to="/#now-showing" className="nav-link">
            Programme
          </NavLink>
          <NavLink to="/#cinemas" className="nav-link">
            The houses
          </NavLink>
          <NavLink to="/bookings" className="nav-link">
            My bookings
          </NavLink>
        </nav>

        <div className="nav-actions">
          <div className="nav-prefs">
            <button
              type="button"
              className="pref-toggle"
              onClick={toggleCurrency}
              aria-label={`Displayed prices are in ${currencyName}. Switch currency`}
              title="Switch currency — DH or €"
            >
              {currencyLabel}
            </button>
            <button
              type="button"
              className="icon-btn"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              title={theme === "dark" ? "Light mode" : "Dark mode"}
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
          </div>
          <NotificationBell />
          {isAuthenticated ? (
            <div className="nav-popover-wrap" ref={accountRef}>
              <button
                type="button"
                className="account-button"
                onClick={() => setAccountOpen((value) => !value)}
                aria-expanded={accountOpen}
              >
                <span className="avatar">{initials(user?.full_name)}</span>
                <span className="account-name">{user?.full_name?.split(" ")[0]}</span>
                <ChevronDown size={14} />
              </button>
              {accountOpen ? (
                <div className="popover account-popover">
                  <div className="account-head">
                    <span className="avatar avatar--lg">{initials(user?.full_name)}</span>
                    <div>
                      <strong>{user?.full_name}</strong>
                      <small>{user?.email}</small>
                    </div>
                  </div>
                  <div className="popover-links">
                    <Link to="/profile">
                      <UserRound size={16} /> Profile
                    </Link>
                    <Link to="/bookings">
                      <Ticket size={16} /> My bookings
                    </Link>
                    <Link to="/notifications">
                      <CalendarDays size={16} /> Notifications
                    </Link>
                    {isAdmin ? (
                      <Link to="/admin">
                        <Settings2 size={16} /> Control room
                      </Link>
                    ) : null}
                  </div>
                  <button type="button" className="logout-link" onClick={doLogout}>
                    <LogOut size={16} /> Sign out
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="guest-actions">
              <Link to="/login" className="text-link">
                Sign in
              </Link>
              <Link to="/register" className="btn btn--gold btn--sm">
                Join Nocturne
              </Link>
            </div>
          )}
          <button
            type="button"
            className="icon-btn mobile-toggle"
            onClick={() => setMobileOpen((value) => !value)}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {mobileOpen ? (
        <div className="mobile-menu">
          <nav aria-label="Mobile navigation">
            <Link to="/#now-showing">Programme</Link>
            <Link to="/#cinemas">The houses</Link>
            <Link to="/bookings">My bookings</Link>
            <Link to="/notifications">Notifications</Link>
            {isAdmin ? <Link to="/admin">Control room</Link> : null}
          </nav>
          <div className="mobile-prefs">
            <button type="button" className="btn btn--ghost btn--sm" onClick={toggleCurrency}>
              Prices in {currencyLabel}
            </button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={toggleTheme}>
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
          </div>
          {isAuthenticated ? (
            <div className="mobile-account">
              <span className="avatar">{initials(user?.full_name)}</span>
              <div>
                <strong>{user?.full_name}</strong>
                <small>{user?.email}</small>
              </div>
              <button type="button" className="btn btn--ghost btn--sm" onClick={doLogout}>
                Sign out
              </button>
            </div>
          ) : (
            <div className="mobile-auth">
              <Link to="/login" className="btn btn--ghost">
                Sign in
              </Link>
              <Link to="/register" className="btn btn--gold">
                Join Nocturne
              </Link>
            </div>
          )}
        </div>
      ) : null}
    </header>
  );
}
