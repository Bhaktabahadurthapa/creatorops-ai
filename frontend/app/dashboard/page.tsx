import type { Metadata } from "next";

import { BRAND_TAGLINE } from "@/lib/brand";

import DashboardClient from "./dashboard-client";

export const metadata: Metadata = {
  description: `${BRAND_TAGLINE} Monitor local CreatorOps AI projects from first draft through completed video.`,
};

export default function DashboardPage() {
  return <DashboardClient />;
}
