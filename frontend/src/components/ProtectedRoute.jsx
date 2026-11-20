import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { PageLoader } from "./Feedback";

export function RequireAuth({ children }) {
  const { isAuthenticated, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <PageLoader label="Checking your ticket" />;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return children;
}

export function RequireAdmin({ children }) {
  const { user, isAuthenticated, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <PageLoader label="Opening the control room" />;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (user?.role !== "admin") {
    return (
      <div className="page page--narrow">
        <div className="state-card state-card--error">
          <span className="state-icon">403</span>
          <h3>This room is for staff</h3>
          <p>Your account does not have administrator access.</p>
          <a className="btn btn--ghost btn--sm" href="/">
            Back to the programme
          </a>
        </div>
      </div>
    );
  }
  return children;
}
