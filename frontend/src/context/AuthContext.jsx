import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  api,
  clearAuthStorage,
  getStoredUser,
  getToken,
  setStoredUser,
  setToken,
} from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => getToken());
  const [user, setUserState] = useState(() => getStoredUser());
  const [ready, setReady] = useState(false);

  const persist = useCallback((nextToken, nextUser) => {
    setToken(nextToken);
    setStoredUser(nextUser);
    setTokenState(nextToken);
    setUserState(nextUser);
  }, []);

  const logout = useCallback(() => {
    clearAuthStorage();
    setTokenState(null);
    setUserState(null);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!getToken()) {
      setReady(true);
      return null;
    }
    try {
      const profile = await api("/users/me");
      setStoredUser(profile);
      setUserState(profile);
      return profile;
    } catch (error) {
      if (error.status === 401) {
        logout();
      }
      return null;
    } finally {
      setReady(true);
    }
  }, [logout]);

  useEffect(() => {
    refreshUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handler = () => logout();
    window.addEventListener("mycima:unauthorized", handler);
    return () => window.removeEventListener("mycima:unauthorized", handler);
  }, [logout]);

  const login = useCallback(
    async (email, password) => {
      const result = await api("/auth/login", {
        method: "POST",
        auth: false,
        body: { email, password },
      });
      persist(result.access_token, result.user);
      setReady(true);
      return result.user;
    },
    [persist],
  );

  // Registration is one step: the user service creates the account and returns a
  // JWT, so the visitor is signed in straight away.
  const register = useCallback(
    async (payload) => {
      const result = await api("/auth/register", {
        method: "POST",
        auth: false,
        body: payload,
      });
      persist(result.access_token, result.user);
      setReady(true);
      return result.user;
    },
    [persist],
  );

  const updateUser = useCallback((nextUser) => {
    setStoredUser(nextUser);
    setUserState(nextUser);
  }, []);

  const value = useMemo(
    () => ({
      token,
      user,
      ready,
      isAuthenticated: Boolean(token && user),
      isAdmin: user?.role === "admin",
      login,
      register,
      logout,
      refreshUser,
      updateUser,
    }),
    [
      token,
      user,
      ready,
      login,
      register,
      logout,
      refreshUser,
      updateUser,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
