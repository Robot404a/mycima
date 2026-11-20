import { useCallback, useMemo, useState } from "react";
import {
  CheckCheck,
  ShieldCheck,
  ShieldOff,
  UserCheck,
  UserRound,
  UserX,
  Users,
} from "lucide-react";
import { api, apiErrorMessage } from "../../lib/api";
import { useApi, useDocumentTitle } from "../../lib/hooks";
import { formatDateLong, initials, relativeTime } from "../../lib/format";
import { ErrorState, PageLoader } from "../../components/Feedback";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import {
  AdminEmpty,
  AdminPageHead,
  AdminSearch,
  ConfirmDialog,
  MiniStat,
  StatusPill,
} from "./ui";

export default function AdminUsers() {
  useDocumentTitle("Guests · Control room");
  const { user: currentUser } = useAuth();
  const { pushToast } = useToast();
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("all");
  const [confirm, setConfirm] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const loader = useCallback(() => api("/admin/users", { params: { limit: 200 } }), []);
  const { data, error, loading, reload } = useApi(loader, []);

  const users = data?.items || [];
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return users.filter((user) => {
      const roleMatch = role === "all" || user.role === role || (role === "inactive" && !user.is_active);
      const queryMatch =
        !needle ||
        user.full_name.toLowerCase().includes(needle) ||
        user.email.toLowerCase().includes(needle) ||
        (user.phone || "").toLowerCase().includes(needle);
      return roleMatch && queryMatch;
    });
  }, [users, query, role]);

  const stats = useMemo(() => {
    const month = new Date();
    return {
      total: users.length,
      admins: users.filter((user) => user.role === "admin").length,
      active: users.filter((user) => user.is_active).length,
      newThisMonth: users.filter((user) => {
        const created = new Date(user.created_at);
        return created.getMonth() === month.getMonth() && created.getFullYear() === month.getFullYear();
      }).length,
    };
  }, [users]);

  const applyChange = async (target, patch, message) => {
    setBusyId(target.id);
    try {
      await api(`/admin/users/${target.id}`, { method: "PATCH", body: patch });
      pushToast(message, "success");
      setConfirm(null);
      reload();
    } catch (err) {
      pushToast(apiErrorMessage(err), "error");
    } finally {
      setBusyId(null);
    }
  };

  const confirmAction = async () => {
    if (!confirm) return;
    const { target, patch, message } = confirm;
    await applyChange(target, patch, message);
  };

  if (loading) return <PageLoader label="Loading the guest book" />;
  if (error) return <ErrorState error={error} onRetry={() => reload(true)} title="The guest book is hiding" />;

  return (
    <div className="admin-page">
      <AdminPageHead
        eyebrow="People"
        title="Guests & staff"
        description="Accounts, roles and access. Every change is protected by the gateway's admin guard."
      />

      <div className="venue-stats">
        <MiniStat label="Accounts" value={stats.total} hint="Registered in the platform" />
        <MiniStat label="Administrators" value={stats.admins} hint="Control room access" />
        <MiniStat label="Active" value={stats.active} hint="Can sign in and book" />
        <MiniStat label="New this month" value={stats.newThisMonth} hint="Recent arrivals" />
      </div>

      <div className="admin-toolbar">
        <div className="segmented" role="tablist" aria-label="Role filters">
          {[
            ["all", "All"],
            ["user", "Guests"],
            ["admin", "Admins"],
            ["inactive", "Inactive"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={role === value}
              className={role === value ? "is-active" : ""}
              onClick={() => setRole(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <AdminSearch value={query} onChange={setQuery} placeholder="Name, email or phone" />
      </div>

      {filtered.length ? (
        <div className="admin-table-wrap">
          <table className="admin-table admin-table--users">
            <thead>
              <tr>
                <th>Guest</th>
                <th>Contact</th>
                <th>Role</th>
                <th>Status</th>
                <th>Joined</th>
                <th className="align-right">Access</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((user) => {
                const isSelf = user.id === currentUser?.id;
                const isAdmin = user.role === "admin";
                return (
                  <tr key={user.id} className={!user.is_active ? "is-muted" : ""}>
                    <td>
                      <div className="table-user-cell">
                        <span className={`avatar ${isAdmin ? "avatar--gold" : ""}`}>
                          {initials(user.full_name)}
                        </span>
                        <div>
                          <strong>
                            {user.full_name}
                            {isSelf ? <span className="self-tag">you</span> : null}
                          </strong>
                          <small>Joined {formatDateLong(user.created_at)}</small>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="table-email">{user.email}</span>
                      <small className="table-sub">{user.phone || "No phone"}</small>
                    </td>
                    <td>
                      <span className={`role-chip ${isAdmin ? "is-admin" : ""}`}>
                        {isAdmin ? <ShieldCheck size={13} /> : <UserRound size={13} />}
                        {isAdmin ? "Administrator" : "Guest"}
                      </span>
                    </td>
                    <td>
                      <span className={`status-pill status-pill--${user.is_active ? "active" : "inactive"}`}>
                        {user.is_active ? <CheckCheck size={12} /> : <UserX size={12} />}
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>{relativeTime(user.created_at)}</td>
                    <td>
                      <div className="table-actions">
                        <button
                          type="button"
                          className="role-toggle"
                          disabled={isSelf || busyId === user.id}
                          onClick={() =>
                            setConfirm({
                              target: user,
                              patch: { role: isAdmin ? "user" : "admin" },
                              message: isAdmin
                                ? `${user.full_name} will lose access to the control room.`
                                : `${user.full_name} will gain full administrator access.`,
                              title: isAdmin ? "Remove admin access?" : "Grant admin access?",
                              confirmLabel: isAdmin ? "Remove access" : "Grant access",
                              danger: isAdmin,
                            })
                          }
                          title={isSelf ? "You cannot change your own role" : "Toggle admin role"}
                        >
                          {isAdmin ? <ShieldOff size={14} /> : <UserCheck size={14} />}
                          {isAdmin ? "Demote" : "Promote"}
                        </button>
                        <button
                          type="button"
                          className={`status-toggle ${user.is_active ? "is-on" : ""}`}
                          disabled={isSelf || busyId === user.id}
                          onClick={() =>
                            setConfirm({
                              target: user,
                              patch: { is_active: !user.is_active },
                              message: user.is_active
                                ? `${user.full_name} will no longer be able to sign in or book. Existing bookings are unaffected.`
                                : `${user.full_name} will be able to sign in and book again.`,
                              title: user.is_active ? "Deactivate account?" : "Reactivate account?",
                              confirmLabel: user.is_active ? "Deactivate" : "Reactivate",
                              danger: user.is_active,
                            })
                          }
                          title={isSelf ? "You cannot deactivate yourself" : "Toggle account status"}
                          aria-label={`${user.is_active ? "Deactivate" : "Reactivate"} ${user.full_name}`}
                        >
                          <span className="status-toggle-track">
                            <span className="status-toggle-thumb" />
                          </span>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <AdminEmpty
          icon={Users}
          title="No accounts match"
          message="Change the filter or search for another guest."
        />
      )}

      <div className="admin-note-row">
        <ShieldCheck size={15} />
        <span>
          Passwords are hashed with bcrypt. Roles and account status are enforced by the API gateway
          on every admin request.
        </span>
        <span className="admin-note-price">
          {stats.total} accounts · {stats.admins} admins
        </span>
      </div>

      <ConfirmDialog
        open={Boolean(confirm)}
        onClose={() => setConfirm(null)}
        onConfirm={confirmAction}
        busy={busyId === confirm?.target?.id}
        title={confirm?.title || "Confirm change"}
        message={confirm?.message || ""}
        confirmLabel={confirm?.confirmLabel || "Confirm"}
        danger={confirm?.danger ?? true}
      />
    </div>
  );
}
