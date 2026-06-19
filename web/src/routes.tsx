import { createBrowserRouter, Outlet } from "react-router-dom";
import { AppSidebar } from "@/components/app-sidebar";
import { PagePlaceholder } from "@/components/page-placeholder";
import Overview from "@/pages/Overview";
import Transactions from "@/pages/Transactions";
import Budgets from "@/pages/Budgets";

function AppLayout() {
  return (
    <div className="frosted-canvas" style={{ display: "flex", minHeight: "100vh" }}>
      <AppSidebar />
      <main style={{ flex: 1, padding: 24 }}><Outlet /></main>
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
      { path: "budgets", element: <Budgets /> },
      { path: "recurring", element: <PagePlaceholder title="Recurring" /> },
      { path: "goals", element: <PagePlaceholder title="Goals" /> },
      { path: "networth", element: <PagePlaceholder title="Net Worth" /> },
      { path: "import", element: <PagePlaceholder title="Import" /> },
      { path: "insights", element: <PagePlaceholder title="AI Insights" /> },
      { path: "settings", element: <PagePlaceholder title="Settings" /> },
    ],
  },
]);
