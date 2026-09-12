import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Landing } from "./pages/Landing";
import { Overview } from "./pages/Overview";
import { AgentExplorer } from "./pages/AgentExplorer";
import { AgentPassportPage } from "./pages/AgentPassportPage";
import {
  AuditCenter, DelegationCenter, PolicyCenter, SecurityCenter, TrustGraphPage,
} from "./pages/Centers";
import { DemoPage } from "./pages/Demo";

function NotFound() {
  return (
    <div className="py-24 text-center">
      <p className="num mono text-5xl font-semibold text-(--color-ink-faint)">404</p>
      <p className="mt-3 text-sm text-(--color-ink-dim)">
        No page at this route — and AgentPassport never guesses.
      </p>
      <div className="mt-6 flex items-center justify-center gap-4 text-[13px]">
        <Link to="/overview" className="link-draw font-medium text-(--color-accent)">Console</Link>
        <Link to="/" className="link-draw text-(--color-ink-dim)">Home</Link>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* public editorial layer */}
        <Route index element={<Landing />} />
        {/* application console — instrument-panel layer */}
        <Route element={<Layout />}>
          <Route path="/overview" element={<Overview />} />
          <Route path="/agents" element={<AgentExplorer />} />
          <Route path="/agents/:id" element={<AgentPassportPage />} />
          <Route path="/graph" element={<TrustGraphPage />} />
          <Route path="/delegations" element={<DelegationCenter />} />
          <Route path="/security" element={<SecurityCenter />} />
          <Route path="/policies" element={<PolicyCenter />} />
          <Route path="/audit" element={<AuditCenter />} />
          <Route path="/demo" element={<DemoPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
