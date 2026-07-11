import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Radio, ListTree, Send, Workflow, Split, Cable, Database, BellRing, BarChart3 } from "lucide-react";
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
];

export default function App() {
  const [health, setHealth] = useState<"ok" | "down" | "checking">("checking");
  const [attempts, setAttempts] = useState(0);

  const check = useCallback(() => {
    setHealth("checking");
    api.health().then(() => setHealth("ok")).catch(() => setHealth("down"));
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
        {health !== "ok" && !(health === "checking" && attempts === 0) ? (
          <WakingBackend waking={attempts < 6} onRetry={() => setAttempts(0)} />
        ) : (
          <Suspense fallback={<Skeleton className="h-64 w-full" />}>
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
              <Route path="*" element={<Live />} />
            </Routes>
          </Suspense>
        )}
      </AppShell>
    </BrowserRouter>
  );
}
