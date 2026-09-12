import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Overview } from "./pages/Overview";
import { AgentExplorer } from "./pages/AgentExplorer";
import { AgentPassportPage } from "./pages/AgentPassportPage";
import {
  AuditCenter, DelegationCenter, PolicyCenter, SecurityCenter, TrustGraphPage,
} from "./pages/Centers";
import { DemoPage } from "./pages/Demo";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="/agents" element={<AgentExplorer />} />
          <Route path="/agents/:id" element={<AgentPassportPage />} />
          <Route path="/graph" element={<TrustGraphPage />} />
          <Route path="/delegations" element={<DelegationCenter />} />
          <Route path="/security" element={<SecurityCenter />} />
          <Route path="/policies" element={<PolicyCenter />} />
          <Route path="/audit" element={<AuditCenter />} />
          <Route path="/demo" element={<DemoPage />} />
          <Route
            path="*"
            element={
              <div className="py-20 text-center text-(--color-ink-faint)">
                <p className="mono text-4xl">404</p>
                <p className="mt-2 text-sm">No page at this route.</p>
              </div>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
