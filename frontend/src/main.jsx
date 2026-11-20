import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { CurrencyProvider } from "./context/CurrencyContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ToastProvider } from "./context/ToastContext";
import { ScrollToTop } from "./components/ScrollToTop";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <CurrencyProvider>
          <AuthProvider>
            <ToastProvider>
              <ScrollToTop />
              <App />
            </ToastProvider>
          </AuthProvider>
        </CurrencyProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
);
