"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  readLocalProjects,
  withDownloadParameter,
  type LocalProject,
  type ProjectStatus,
} from "@/lib/projects";

const statusStyles: Record<ProjectStatus, string> = {
  Draft: "border-slate-600/60 bg-slate-700/25 text-slate-300",
  "Script Ready": "border-violet-400/30 bg-violet-400/10 text-violet-200",
  "Voice Ready": "border-amber-300/30 bg-amber-300/10 text-amber-200",
  Rendering: "border-cyan-300/35 bg-cyan-300/10 text-cyan-200",
  Completed: "border-emerald-300/35 bg-emerald-300/10 text-emerald-200",
  Failed: "border-rose-400/35 bg-rose-400/10 text-rose-200",
};

const pipeline: Array<{ label: string; statuses: ProjectStatus[] }> = [
  { label: "Ideas", statuses: ["Draft"] },
  { label: "Scripts", statuses: ["Script Ready"] },
  { label: "Voices", statuses: ["Voice Ready"] },
  { label: "Renders", statuses: ["Rendering"] },
  { label: "Finished", statuses: ["Completed"] },
];

function formatDate(value: string): string {
  return new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
    Math.round((new Date(value).getTime() - Date.now()) / 86_400_000),
    "day",
  );
}

function StatIcon({
  type,
}: {
  type: "projects" | "active" | "video" | "time";
}) {
  const paths = {
    projects: "M5 7h14v12H5V7Zm3-3h8v3H8V4Z",
    active: "M4 12h4l2-6 4 12 2-6h4",
    video: "M5 7h10v10H5V7Zm10 3 4-2v8l-4-2",
    time: "M12 6v6l4 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z",
  };
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
      <path
        d={paths[type]}
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function DashboardClient() {
  const [projects, setProjects] = useState<LocalProject[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setProjects(readLocalProjects());
      setHydrated(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const completedProjects = useMemo(
    () => projects.filter((project) => project.status === "Completed"),
    [projects],
  );
  const activeProjects = projects.filter((project) =>
    ["Draft", "Script Ready", "Voice Ready", "Rendering"].includes(
      project.status,
    ),
  );
  const completedDuration = completedProjects.reduce(
    (total, project) => total + project.duration,
    0,
  );
  const latestVideo = completedProjects.find((project) => project.video_url);

  return (
    <main className="relative min-h-screen overflow-hidden bg-slate-950 text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_8%_4%,_rgba(139,92,246,0.14),_transparent_28%),radial-gradient(circle_at_92%_8%,_rgba(34,211,238,0.11),_transparent_24%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.035] [background-image:linear-gradient(rgba(255,255,255,.7)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.7)_1px,transparent_1px)] [background-size:64px_64px]" />

      <div className="relative mx-auto max-w-7xl px-5 py-6 sm:px-8 lg:px-10">
        <nav className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
          <Link
            href="/"
            aria-label="CreatorOps AI home"
            className="group flex cursor-pointer items-center gap-3 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-4 focus-visible:ring-offset-slate-950"
          >
            <span className="grid h-9 w-9 place-items-center rounded-xl border border-violet-400/30 bg-violet-400/10 font-mono text-sm font-black text-violet-200 transition group-hover:border-violet-300/60">
              CO
            </span>
            <span className="text-sm font-bold tracking-wide text-slate-100">
              CreatorOps <span className="text-violet-300">AI</span>
            </span>
          </Link>
          <div className="flex items-center gap-2">
            <Link
              href="/projects"
              className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-300 transition hover:bg-slate-900 hover:text-white"
            >
              Projects
            </Link>
            <Link
              href="/create"
              className="rounded-xl bg-violet-500 px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-violet-950/30 transition hover:bg-violet-400"
            >
              Create New Project
            </Link>
          </div>
        </nav>

        <header className="grid gap-8 py-12 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.24em] text-cyan-300">
              Production command center
            </p>
            <h1 className="mt-4 max-w-3xl text-4xl font-black tracking-[-0.045em] text-white sm:text-6xl">
              Keep every video moving.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">
              A local overview of scripts, voice tracks, and finished exports
              saved in this browser.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/create"
              className="rounded-xl bg-cyan-300 px-5 py-3 text-sm font-black text-slate-950 transition hover:bg-cyan-200"
            >
              Start a Video
            </Link>
            <Link
              href="/projects"
              className="rounded-xl border border-slate-700 bg-slate-900/60 px-5 py-3 text-sm font-bold text-slate-200 transition hover:border-slate-600 hover:bg-slate-900"
            >
              View All Projects
            </Link>
          </div>
        </header>

        {!hydrated ? (
          <div
            className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
            aria-label="Loading dashboard"
          >
            {[0, 1, 2, 3].map((item) => (
              <div
                key={item}
                className="h-32 animate-pulse rounded-2xl border border-slate-800 bg-slate-900/50"
              />
            ))}
          </div>
        ) : (
          <>
            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {[
                {
                  label: "Total projects",
                  value: projects.length,
                  icon: "projects" as const,
                  accent: "text-violet-300",
                },
                {
                  label: "In production",
                  value: activeProjects.length,
                  icon: "active" as const,
                  accent: "text-cyan-300",
                },
                {
                  label: "Completed videos",
                  value: completedProjects.length,
                  icon: "video" as const,
                  accent: "text-emerald-300",
                },
                {
                  label: "Finished runtime",
                  value: `${Math.floor(completedDuration / 60)}m ${completedDuration % 60}s`,
                  icon: "time" as const,
                  accent: "text-amber-300",
                },
              ].map((stat) => (
                <article
                  key={stat.label}
                  className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-black/10 backdrop-blur"
                >
                  <div
                    className={`grid h-10 w-10 place-items-center rounded-xl border border-current/20 bg-current/5 ${stat.accent}`}
                  >
                    <StatIcon type={stat.icon} />
                  </div>
                  <p className="mt-5 text-3xl font-black tracking-tight text-white">
                    {stat.value}
                  </p>
                  <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
                    {stat.label}
                  </p>
                </article>
              ))}
            </section>

            <section className="mt-6 grid gap-6 xl:grid-cols-[1.15fr_.85fr]">
              <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70 shadow-xl shadow-black/10">
                <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4 sm:px-6">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-violet-300">
                      Production flow
                    </p>
                    <h2 className="mt-1 text-lg font-black">
                      Projects by stage
                    </h2>
                  </div>
                  <span className="text-xs text-slate-500">
                    Local browser data
                  </span>
                </div>
                <div className="grid gap-px bg-slate-800 sm:grid-cols-5">
                  {pipeline.map((stage, index) => {
                    const count = projects.filter((project) =>
                      stage.statuses.includes(project.status),
                    ).length;
                    return (
                      <div
                        key={stage.label}
                        className="relative bg-slate-950/80 p-5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-slate-600">
                            0{index + 1}
                          </span>
                          <span
                            className={`h-2 w-2 rounded-full ${count ? "bg-cyan-300 shadow-[0_0_12px_rgba(103,232,249,.65)]" : "bg-slate-700"}`}
                          />
                        </div>
                        <p className="mt-8 text-3xl font-black text-white">
                          {count}
                        </p>
                        <p className="mt-1 text-xs font-semibold text-slate-400">
                          {stage.label}
                        </p>
                      </div>
                    );
                  })}
                </div>
                {projects.some((project) => project.status === "Failed") && (
                  <div className="border-t border-rose-400/15 bg-rose-400/5 px-5 py-3 text-sm text-rose-200 sm:px-6">
                    {
                      projects.filter((project) => project.status === "Failed")
                        .length
                    }{" "}
                    project needs attention. Open Projects to retry it.
                  </div>
                )}
              </div>

              <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70 shadow-xl shadow-black/10">
                <div className="border-b border-slate-800 px-5 py-4 sm:px-6">
                  <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-emerald-300">
                    Latest export
                  </p>
                  <h2 className="mt-1 text-lg font-black">Ready to review</h2>
                </div>
                {latestVideo?.video_url ? (
                  <div className="p-5 sm:p-6">
                    <video
                      controls
                      preload="metadata"
                      src={latestVideo.video_url}
                      className="aspect-video w-full rounded-xl border border-slate-800 bg-black"
                    >
                      Preview latest generated video
                    </video>
                    <h3 className="mt-4 line-clamp-1 font-bold text-white">
                      {latestVideo.title}
                    </h3>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Link
                        href={`/create?project_id=${encodeURIComponent(latestVideo.project_id)}`}
                        className="rounded-lg bg-slate-100 px-3 py-2 text-xs font-bold text-slate-950 hover:bg-white"
                      >
                        Open
                      </Link>
                      <a
                        href={withDownloadParameter(latestVideo.video_url)}
                        className="rounded-lg border border-emerald-400/25 px-3 py-2 text-xs font-bold text-emerald-200 hover:bg-emerald-400/10"
                      >
                        Download MP4
                      </a>
                    </div>
                  </div>
                ) : (
                  <div className="grid min-h-64 place-items-center p-6 text-center">
                    <div>
                      <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl border border-slate-700 bg-slate-800/60 text-slate-400">
                        ▶
                      </div>
                      <p className="mt-4 font-bold text-slate-200">
                        No completed video yet
                      </p>
                      <p className="mt-2 max-w-xs text-sm leading-6 text-slate-500">
                        Finish a project and its latest MP4 will be ready to
                        preview here.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </section>

            <section className="mt-6 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70">
              <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4 sm:px-6">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-300">
                    Recent activity
                  </p>
                  <h2 className="mt-1 text-lg font-black">Latest projects</h2>
                </div>
                <Link
                  href="/projects"
                  className="text-sm font-bold text-cyan-300 hover:text-cyan-200"
                >
                  View all →
                </Link>
              </div>

              {projects.length === 0 ? (
                <div className="px-6 py-16 text-center">
                  <h3 className="text-xl font-black">
                    Your dashboard is ready
                  </h3>
                  <p className="mx-auto mt-3 max-w-md leading-7 text-slate-400">
                    Create your first project and its progress will appear here
                    automatically.
                  </p>
                  <Link
                    href="/create"
                    className="mt-6 inline-flex rounded-xl bg-violet-500 px-5 py-3 text-sm font-bold hover:bg-violet-400"
                  >
                    Create Your First Video
                  </Link>
                </div>
              ) : (
                <div className="divide-y divide-slate-800">
                  {projects.slice(0, 5).map((project) => (
                    <article
                      key={project.project_id}
                      className="grid gap-4 px-5 py-4 transition hover:bg-slate-800/25 sm:grid-cols-[1fr_auto] sm:items-center sm:px-6"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-3">
                          <h3 className="truncate font-bold text-slate-100">
                            {project.title}
                          </h3>
                          <span
                            className={`inline-flex rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] ${statusStyles[project.status]}`}
                          >
                            {project.status}
                          </span>
                        </div>
                        <p className="mt-1 truncate text-sm text-slate-500">
                          {project.platform} · {project.tone} · updated{" "}
                          {formatDate(project.updated_at)}
                        </p>
                      </div>
                      <Link
                        href={`/create?project_id=${encodeURIComponent(project.project_id)}`}
                        className="w-fit rounded-lg border border-slate-700 px-3 py-2 text-xs font-bold text-slate-300 transition hover:border-violet-400/50 hover:text-violet-200"
                      >
                        Open Project
                      </Link>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )}

        <footer className="mt-14 border-t border-slate-800 py-6 text-xs leading-5 text-slate-600">
          Dashboard data stays in this browser and contains project metadata
          only.
        </footer>
      </div>
    </main>
  );
}
