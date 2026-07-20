import type { Metadata } from "next";

import { BRAND_TAGLINE } from "@/lib/brand";

import ProjectsClient from "./projects-client";

export const metadata: Metadata = {
  description: `${BRAND_TAGLINE} Review locally generated CreatorOps AI scripts, narration, and completed videos.`,
};

export default function ProjectsPage() {
  return <ProjectsClient />;
}
