import Link from "next/link";

import { BRAND_DESCRIPTION } from "@/lib/brand";

const features = [
  {
    title: "AI Script Writer",
    description:
      "Turn a simple idea into a structured and engaging video script.",
  },
  {
    title: "AI Voiceover",
    description: "Generate a natural voiceover from your approved script.",
  },
  {
    title: "Smart Media Matching",
    description: "Match images and video clips with every scene automatically.",
  },
  {
    title: "Automatic Subtitles",
    description:
      "Create synchronized subtitles for clear and accessible videos.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6">
        <Link
          href="/"
          aria-label="CreatorOps AI home"
          className="cursor-pointer rounded-md text-xl font-bold outline-none transition hover:text-white focus-visible:ring-2 focus-visible:ring-violet-400"
        >
          CreatorOps <span className="text-violet-400">AI</span>
        </Link>

        <div className="flex items-center gap-4">
          <Link
            href="/projects"
            className="text-sm text-slate-300 hover:text-white"
          >
            Projects
          </Link>

          <Link
            href="/create"
            className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold hover:bg-violet-500"
          >
            Start Creating
          </Link>
        </div>
      </nav>

      <section className="mx-auto flex max-w-5xl flex-col items-center px-6 py-24 text-center">
        <div className="mb-6 rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-sm text-violet-300">
          Built for OpenAI Build Week 2026
        </div>

        <h1 className="max-w-4xl text-5xl font-bold tracking-tight sm:text-7xl">
          Your idea. Your voice.{" "}
          <span className="text-violet-400">Your finished video.</span>
        </h1>

        <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
          {BRAND_DESCRIPTION}
        </p>

        <div className="mt-10 flex flex-col gap-4 sm:flex-row">
          <Link
            href="/create"
            className="rounded-xl bg-violet-600 px-6 py-3 font-semibold hover:bg-violet-500"
          >
            Create Your First Video
          </Link>
          <Link
            href="/dashboard"
            className="rounded-xl border border-slate-700 px-6 py-3 font-semibold hover:bg-slate-900"
          >
            Open Dashboard
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-24">
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => (
            <article
              key={feature.title}
              className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6"
            >
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-violet-500/15 text-violet-300">
                ✦
              </div>

              <h2 className="text-lg font-semibold">{feature.title}</h2>

              <p className="mt-3 text-sm leading-6 text-slate-400">
                {feature.description}
              </p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
