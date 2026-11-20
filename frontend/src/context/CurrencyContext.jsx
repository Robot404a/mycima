import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { setDisplayCurrency } from "../lib/format";

const STORAGE_KEY = "mycima.currency";

// The programme is priced in MAD; EUR is a display conversion for guests.
export const CURRENCY_OPTIONS = [
  { code: "MAD", label: "DH", name: "Moroccan dirham" },
  { code: "EUR", label: "€", name: "Euro" },
];

const CurrencyContext = createContext(null);

function initialCurrency() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "MAD" || stored === "EUR") return stored;
  } catch {
    /* storage unavailable */
  }
  return "MAD";
}

export function CurrencyProvider({ children }) {
  const [currency, setCurrency] = useState(initialCurrency);

  // Applied during render so every price in this render already uses the
  // selected currency (an effect would run after the children rendered).
  setDisplayCurrency(currency);

  useEffect(() => {
    setDisplayCurrency(currency);
    try {
      localStorage.setItem(STORAGE_KEY, currency);
    } catch {
      /* storage unavailable */
    }
  }, [currency]);

  const toggleCurrency = useCallback(() => {
    setCurrency((current) => (current === "MAD" ? "EUR" : "MAD"));
  }, []);

  const value = useMemo(() => {
    const option = CURRENCY_OPTIONS.find((item) => item.code === currency) || CURRENCY_OPTIONS[0];
    return { currency, label: option.label, name: option.name, setCurrency, toggleCurrency };
  }, [currency, toggleCurrency]);

  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useCurrency() {
  const context = useContext(CurrencyContext);
  if (!context) throw new Error("useCurrency must be used inside CurrencyProvider");
  return context;
}
