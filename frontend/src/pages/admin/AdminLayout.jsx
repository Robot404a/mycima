import { Suspense, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Armchair,
  ArrowLeft,
  CalendarRange,
  Clapperboard,
  LayoutDashboard,
  LogOut,
  Menu,
  TicketCheck,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { initials } from "../../lib/format";
import { PageLoader } from "../../components/Feedback";

const LINKS = [
  { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/admin/movies", label: "Films", icon: Clapperboard },
  { to: "/admin/showtimes", label: "Screenings", icon: CalendarRange },
  { to: "/admin/halls", label: "Halls & seats", icon: Armchair },
  { to: "/admin/bookings", label: "Bookings", icon: TicketCheck },
  { to: "/admin/users", label: "Guests", icon: Users },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  const signOut = () => {
    logout();
    navigate("/");
  };

  return (
    <div className={`admin-shell ${open ? "is-open" : ""}`}>
      <aside className="admin-sidebar" aria-label="Control room navigation">
        <div className="admin-sidebar-head">
          <Link to="/" className="brand" aria-label="MyCima home">
            <span className="brand-mark" aria-hidden="true">
              <span />
            </span>
            <span className="brand-word">
              MYCIMA
              <small>Control room</small>
            </span>
          </Link>
          <button
            type="button"
            className="icon-btn admin-sidebar-close"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="admin-nav">
          {LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) => `admin-nav-link ${isActive ? "is-active" : ""}`}
              >
                <Icon size={17} />
                <span>{link.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="admin-sidebar-foot">
          <Link to="/" className="admin-back-site">
            <ArrowLeft size={15} /> Back to the site
          </Link>
          <div className="admin-user">
            <span className="avatar">{initials(user?.full_name)}</span>
            <div>
              <strong>{user?.full_name}</strong>
              <small>{user?.email}</small>
            </div>
            <button type="button" className="icon-btn" onClick={signOut} title="Sign out">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {open ? <div className="admin-backdrop" onClick={() => setOpen(false)} /> : null}

      <div className="admin-main">
        <header className="admin-topbar">
          <button
            type="button"
            className="icon-btn admin-menu-toggle"
            onClick={() => setOpen((value) => !value)}
            aria-label="Open menu"
            aria-expanded={open}
          >
            <Menu size={19} />
          </button>
          <div className="admin-topbar-copy">
            <span className="eyebrow">MyCima operations</span>
            <span className="admin-topbar-date">
              {new Intl.DateTimeFormat("en-GB", {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
                timeZone: "Africa/Casablanca",
              }).format(new Date())}
            </span>
          </div>
          <div className="admin-topbar-actions">
            <span className="admin-live">
              <span className="pulse-dot" /> Live
            </span>
            <span className="admin-role-chip">Admin</span>
          </div>
        </header>
        <main className="admin-content">
          <Suspense fallback={<PageLoader label="Opening the control room" />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
