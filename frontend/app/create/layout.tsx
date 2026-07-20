import type { Metadata } from "next";

export const metadata: Metadata = {
  description:
    "Create a structured video script, authorized narration, animated scenes, subtitles, and a final MP4 with CreatorOps AI.",
};

export default function CreateLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}
