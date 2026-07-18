import Link from "next/link";

export default function ProjectsPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6">
        <Link href="/" className="text-xl font-bold">
          CreatorOps <span className="text-violet-400">AI</span>
        </Link>

        <div className="flex items-center gap-4">
          <Link
            href="/dashboard"
            className="text-sm text-slate-300 transition hover:text-white"
          >
            Dashboard
          </Link>
          <Link
            href="/create"
            className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold transition hover:bg-violet-500"
          >
            New project
          </Link>
        </div>
      </nav>

      <section className="mx-auto max-w-7xl px-6 py-14">
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-violet-400">
          Your library
        </p>
        <div className="mt-3 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Projects
            </h1>
            <p className="mt-4 text-slate-400">
              Find every script, voiceover, and video in one place.
            </p>
          </div>
          <span className="w-fit rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs text-slate-400">
            0 projects
          </span>
        </div>

        <div className="mt-10 rounded-2xl border border-dashed border-slate-700 bg-slate-900/30 px-6 py-20 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-violet-500/15 text-xl text-violet-300">
            ◫
          </div>
          <h2 className="mt-5 text-xl font-semibold">Your library is empty</h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-400">
            Create a project to begin turning your ideas into polished,
            publication-ready videos.
          </p>
          <Link
            href="/create"
            className="mt-6 inline-flex rounded-xl bg-violet-600 px-5 py-3 text-sm font-semibold transition hover:bg-violet-500"
          >
            Start a new project
          </Link>
        </div>
      </section>
    </main>
  );
}
