import type { Metadata } from "next";

import ProjectsClient from "./projects-client";

export const metadata: Metadata = {
  description:
    "Review locally generated CreatorOps AI scripts, narration, and completed videos.",
};

export default function ProjectsPage() {
  return <ProjectsClient />;
}
