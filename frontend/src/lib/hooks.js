import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Small async data hook with optional polling.
 * `loader` should be a stable function that returns a promise.
 */
export function useApi(loader, deps = [], options = {}) {
  const { interval = 0, enabled = true, initial = null } = options;
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const [data, setData] = useState(initial);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(Boolean(enabled && initial === null));
  const [refreshing, setRefreshing] = useState(false);
  const mounted = useRef(true);
  const requestId = useRef(0);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = useCallback(async (spinner = false) => {
    if (!enabled) return;
    const id = ++requestId.current;
    if (spinner) setLoading(true);
    else setRefreshing(true);
    try {
      const result = await loaderRef.current();
      if (mounted.current && id === requestId.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (mounted.current && id === requestId.current) setError(err);
    } finally {
      if (mounted.current && id === requestId.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    const run = async () => {
      const id = ++requestId.current;
      try {
        const result = await loaderRef.current();
        if (!cancelled && id === requestId.current) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (!cancelled && id === requestId.current) setError(err);
      } finally {
        if (!cancelled && id === requestId.current) setLoading(false);
      }
    };
    run();
    let timer = null;
    if (interval > 0) {
      timer = setInterval(() => {
        if (document.visibilityState === "visible") run();
      }, interval);
    }
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, interval, ...deps]);

  return { data, error, loading, refreshing, reload: load, setData, setError };
}

export function useCountdown(expiresAt) {
  const parsed = expiresAt ? new Date(expiresAt).getTime() : NaN;
  const target = Number.isFinite(parsed) ? parsed : null;
  const compute = () => (target ? Math.max(0, Math.round((target - Date.now()) / 1000)) : 0);
  const [seconds, setSeconds] = useState(compute);

  useEffect(() => {
    if (!target) {
      setSeconds(0);
      return undefined;
    }
    setSeconds(compute());
    const timer = setInterval(() => setSeconds(compute()), 1000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  return { seconds, expired: Boolean(target && seconds <= 0), active: Boolean(target && seconds > 0) };
}

export function useClickOutside(ref, handler) {
  useEffect(() => {
    const listener = (event) => {
      if (!ref.current || ref.current.contains(event.target)) return;
      handler(event);
    };
    document.addEventListener("mousedown", listener);
    document.addEventListener("touchstart", listener);
    return () => {
      document.removeEventListener("mousedown", listener);
      document.removeEventListener("touchstart", listener);
    };
  }, [ref, handler]);
}

export function useMediaQuery(query) {
  const [matches, setMatches] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false,
  );
  useEffect(() => {
    const mql = window.matchMedia(query);
    const handler = (event) => setMatches(event.matches);
    mql.addEventListener("change", handler);
    setMatches(mql.matches);
    return () => mql.removeEventListener("change", handler);
  }, [query]);
  return matches;
}

export function useDebounced(value, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function useDocumentTitle(title) {
  useEffect(() => {
    const base = "MYCIMA — Cinema, after dark.";
    document.title = title ? `${title} · MYCIMA` : base;
    return () => {
      document.title = base;
    };
  }, [title]);
}

export function useLockBody(locked) {
  useEffect(() => {
    if (!locked) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [locked]);
}
