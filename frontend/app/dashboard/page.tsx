import type { Metadata } from "next";

import DashboardClient from "./dashboard-client";

export const metadata: Metadata = {
  description:
    "Monitor local CreatorOps AI projects from first draft through completed video.",
};

export default function DashboardPage() {
  return <DashboardClient />;
}
