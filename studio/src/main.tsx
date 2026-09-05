import React, { Component, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { configure } from "./data";
import "./styles.css";
class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    return this.state.error ? (
      <div className="error-state" role="alert">
        <h1>Studio unavailable</h1>
        <p>{this.state.error.message}</p>
        <button onClick={() => location.reload()}>
          {"Reload / \u91cd\u65b0\u52a0\u8f7d"}
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
const client = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: true, staleTime: 10_000 },
  },
});
const root = createRoot(document.getElementById("root")!);
configure()
  .then(() =>
    root.render(
      <React.StrictMode>
        <ErrorBoundary>
          <QueryClientProvider client={client}>
            <App />
          </QueryClientProvider>
        </ErrorBoundary>
      </React.StrictMode>,
    ),
  )
  .catch((e) =>
    root.render(
      <div className="error-state" role="alert">
        <h1>Studio configuration unavailable</h1>
        <p>{String(e.message)}</p>
        <button onClick={() => location.reload()}>Retry</button>
      </div>,
    ),
  );
