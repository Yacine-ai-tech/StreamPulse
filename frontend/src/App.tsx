import UserGuidePage from './pages/UserGuidePage';
import BenchmarkPage from './pages/BenchmarkPage';
import ApiDocsPage from './pages/ApiDocsPage';
import { Component, ReactNode, lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Radio, ListTree, Send, Workflow, Split, Cable, Database, BellRing, BarChart3, Code2, BookOpen } from "lucide-react";
import { AppShell } from "./kit/AppShell";
import { WakingBackend } from "./kit/misc";
import { Skeleton } from "./kit/primitives";
import { api } from "./lib/api";
import Events from "./pages/Events";
import Playground from "./pages/Playground";
import Automation from "./pages/Automation";
import Classifier from "./pages/Classifier";
import Sources from "./pages/Sources";
import Destinations from "./pages/Destinations";
import Alerts from "./pages/Alerts";
import Analytics from "./pages/Analytics";

const Live = lazy(() => import("./pages/Live"));

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  resetKey?: string;
}

class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null, resetKey: this.props.resetKey };

  static getDerivedStateFromProps(props: { resetKey?: string }, state: ErrorBoundaryState) {
    if (props.resetKey !== state.resetKey) {
      return { hasError: false, error: null, resetKey: props.resetKey };
    }
    return null;
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error("StreamPulse UI Error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center text-red-400 bg-red-950/30 rounded-xl border border-red-800/50 m-4">
          <h2 className="text-xl font-bold mb-2">Component Error</h2>
          <p className="text-sm opacity-80 mb-4">{this.state.error?.message || "An unexpected error occurred."}</p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg text-sm transition"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>;
}

const NAV = [
  { to: "/", label: "Live Operations", icon: Radio },
  { to: "/events", label: "Events", icon: ListTree },
  { to: "/playground", label: "Ingest Playground", icon: Send },
  { to: "/sources", label: "Sources", icon: Cable },
  { to: "/destinations", label: "Destinations", icon: Database },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/alerts", label: "Alerts", icon: BellRing },
  { to: "/automation", label: "Automation", icon: Workflow },
  { to: "/classifier", label: "Classifier", icon: Split },
  { to: "/api-docs", label: "API Docs", icon: Code2 },
  { to: "/user-guide", label: "User Guide", icon: BookOpen }
];

export default function App() {
  const [health, setHealth] = useState<"ok" | "down" | "checking">("checking");
  const [attempts, setAttempts] = useState(0);
  const everConnected = useRef(false);

  const check = useCallback(() => {
    setHealth("checking");
    api.health().then(() => { everConnected.current = true; setHealth("ok"); }).catch(() => setHealth("down"));
  }, []);

  useEffect(() => { check(); }, [check, attempts]);

  useEffect(() => {
    if (health === "down" && attempts < 6) {
      const t = setTimeout(() => setAttempts((a) => a + 1), 8000);
      return () => clearTimeout(t);
    }
  }, [health, attempts]);

  return (
    <BrowserRouter>
      <AppShell product="StreamPulse" tagline="Real-Time Data Intelligence" nav={NAV} health={health}>
        {health === "down" && attempts >= 6 && !everConnected.current ? (
          <WakingBackend waking={attempts < 6} onRetry={() => setAttempts(0)} />
        ) : (
          <Suspense fallback={<Skeleton className="h-64 w-full" />}>
            <RouteErrorBoundary>
              <Routes>
                <Route path="/" element={<Live />} />
                <Route path="/events" element={<Events />} />
                <Route path="/playground" element={<Playground />} />
                <Route path="/sources" element={<Sources />} />
                <Route path="/destinations" element={<Destinations />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/alerts" element={<Alerts />} />
                <Route path="/automation" element={<Automation />} />
                <Route path="/classifier" element={<Classifier />} />
                <Route path="/api-docs" element={<ApiDocsPage />} />
                <Route path="/benchmark" element={<BenchmarkPage />} />
                <Route path="/user-guide" element={<UserGuidePage />} />
                <Route path="*" element={<Live />} />
              </Routes>
            </RouteErrorBoundary>
          </Suspense>
        )}
      </AppShell>
    </BrowserRouter>
  );
}
