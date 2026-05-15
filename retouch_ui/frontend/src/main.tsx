import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";
import { ErrorBoundary } from "./components/error-boundary";
import { ToastProvider } from "./components/toast-provider";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Root element not found. Ensure there is a <div id=\"root\"></div> in index.html.");
}

createRoot(rootEl).render(
  <StrictMode>
    <ErrorBoundary>
      <ToastProvider>
        <App />
      </ToastProvider>
    </ErrorBoundary>
  </StrictMode>,
);
