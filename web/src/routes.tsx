import { lazy, Suspense } from "react";
import { createBrowserRouter, Outlet, useLocation } from "react-router-dom";
import { AppSidebar } from "@/components/app-sidebar";
import { Loading } from "@/components/loading";

// Lazy per-route chunks: Recharts (heavy) loads only with the chart pages, and
// chart-free pages (Transactions, Settings, Import…) no longer carry it. Keeps
// the initial bundle small and navigation chunks focused.
const Overview = lazy(() => import("@/pages/Overview"));
const Transactions = lazy(() => import("@/pages/Transactions"));
const Analysis = lazy(() => import("@/pages/Analysis"));
const Budgets = lazy(() => import("@/pages/Budgets"));
const Recurring = lazy(() => import("@/pages/Recurring"));
const Goals = lazy(() => import("@/pages/Goals"));
const NetWorth = lazy(() => import("@/pages/NetWorth"));
const Settings = lazy(() => import("@/pages/Settings"));
const Insights = lazy(() => import("@/pages/Insights"));
const Import = lazy(() => import("@/pages/Import"));
const Events = lazy(() => import("@/pages/Events"));
const Studio = lazy(() => import("@/pages/Studio"));
const Guide = lazy(() => import("@/pages/Guide"));

function AppLayout() {
  const loc = useLocation();
  return (
    // Full-bleed shell: the app fills the window (no floating card frame). The
    // sidebar and the main content are independent scroll regions, so scrolling
    // a long page never moves the nav rail and vice-versa.
    <div className="frosted-canvas" style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <AppSidebar />
      <main style={{ flex: 1, minWidth: 0, height: "100vh", overflowY: "auto", padding: "18px 24px 28px" }}>
        {/* minWidth:0 lets wide children (tables) shrink + scroll inside instead
            of forcing the page wider than the window. maxWidth keeps line lengths
            sane on very wide monitors. */}
        <div className="fl-page" key={loc.pathname} style={{ minWidth: 0, maxWidth: 1200, margin: "0 auto" }}>
          <Suspense fallback={<Loading rows={4} />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "transactions", element: <Transactions /> },
      { path: "analysis", element: <Analysis /> },
      { path: "budgets", element: <Budgets /> },
      { path: "recurring", element: <Recurring /> },
      { path: "goals", element: <Goals /> },
      { path: "networth", element: <NetWorth /> },
      { path: "events", element: <Events /> },
      { path: "studio", element: <Studio /> },
      { path: "import", element: <Import /> },
      { path: "insights", element: <Insights /> },
      { path: "settings", element: <Settings /> },
      { path: "guide", element: <Guide /> },
    ],
  },
]);
