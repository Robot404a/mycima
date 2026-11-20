import { Component, Suspense, lazy } from "react";
import { Link, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { Footer } from "./components/Footer";
import { AssistantWidget } from "./components/AssistantWidget";
import { PageLoader } from "./components/Feedback";
import { RequireAdmin, RequireAuth } from "./components/ProtectedRoute";
import { useCurrency } from "./context/CurrencyContext";

const Home = lazy(() => import("./pages/Home"));
const MovieDetail = lazy(() => import("./pages/MovieDetail"));
const SeatSelection = lazy(() => import("./pages/SeatSelection"));
const Checkout = lazy(() => import("./pages/Checkout"));
const BookingDetail = lazy(() => import("./pages/BookingDetail"));
const Bookings = lazy(() => import("./pages/Bookings"));
const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const Profile = lazy(() => import("./pages/Profile"));
const Notifications = lazy(() => import("./pages/Notifications"));
const NotFound = lazy(() => import("./pages/NotFound"));
const AdminLayout = lazy(() => import("./pages/admin/AdminLayout"));
const AdminDashboard = lazy(() => import("./pages/admin/Dashboard"));
const AdminMovies = lazy(() => import("./pages/admin/AdminMovies"));
const AdminShowtimes = lazy(() => import("./pages/admin/AdminShowtimes"));
const AdminHalls = lazy(() => import("./pages/admin/AdminHalls"));
const AdminBookings = lazy(() => import("./pages/admin/AdminBookings"));
const AdminUsers = lazy(() => import("./pages/admin/AdminUsers"));

class AppBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="page page--narrow">
          <div className="state-card state-card--error">
            <span className="state-icon">!</span>
            <h3>The projector stopped</h3>
            <p>Something unexpected happened. Reload the page to start the reel again.</p>
            <Link to="/" className="btn btn--gold btn--sm">
              Back to the programme
            </Link>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function SiteLayout() {
  const location = useLocation();
  return (
    <div className="site-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <Navbar />
      <main id="main-content" className="site-main" key={location.pathname}>
        <Suspense fallback={<PageLoader label="Opening the house" />}>
          <Outlet />
        </Suspense>
      </main>
      <Footer />
      <AssistantWidget />
    </div>
  );
}

export default function App() {
  // Subscribing here makes every price re-render when the currency changes;
  // money() reads the active currency synchronously during that render.
  const { currency } = useCurrency();

  return (
    <AppBoundary currency={currency}>
      <Suspense fallback={<PageLoader label="Dusting off the projector" />}>
        <Routes>
        <Route element={<SiteLayout />}>
          <Route index element={<Home />} />
          <Route path="movies/:movieId" element={<MovieDetail />} />
          <Route
            path="booking/:showtimeId"
            element={
              <RequireAuth>
                <SeatSelection />
              </RequireAuth>
            }
          />
          <Route
            path="checkout/:holdId"
            element={
              <RequireAuth>
                <Checkout />
              </RequireAuth>
            }
          />
          <Route
            path="bookings"
            element={
              <RequireAuth>
                <Bookings />
              </RequireAuth>
            }
          />
          <Route
            path="bookings/:bookingId"
            element={
              <RequireAuth>
                <BookingDetail />
              </RequireAuth>
            }
          />
          <Route
            path="profile"
            element={
              <RequireAuth>
                <Profile />
              </RequireAuth>
            }
          />
          <Route
            path="notifications"
            element={
              <RequireAuth>
                <Notifications />
              </RequireAuth>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Route>

        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <AdminLayout />
            </RequireAdmin>
          }
        >
          <Route index element={<AdminDashboard />} />
          <Route path="movies" element={<AdminMovies />} />
          <Route path="showtimes" element={<AdminShowtimes />} />
          <Route path="halls" element={<AdminHalls />} />
          <Route path="bookings" element={<AdminBookings />} />
          <Route path="users" element={<AdminUsers />} />
        </Route>
        </Routes>
      </Suspense>
    </AppBoundary>
  );
}
