"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { BRAND_DESCRIPTION, BRAND_TAGLINE } from "@/lib/brand";
import {
  PROJECT_STATUSES,
  deleteLocalProject,
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

function formatDuration(duration: number): string {
  if (duration < 60) return `${duration}s`;
  const minutes = Math.floor(duration / 60);
  const seconds = duration % 60;
  return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function ActionIcon({
  name,
}: {
  name: "open" | "play" | "download" | "delete";
}) {
  const common = "h-4 w-4";
  if (name === "open") {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        className={common}
        aria-hidden="true"
      >
        <path
          d="M7 17 17 7M9 7h8v8"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (name === "play") {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        className={common}
        aria-hidden="true"
      >
        <path
          d="m9 7 8 5-8 5V7Z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (name === "download") {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        className={common}
        aria-hidden="true"
      >
        <path
          d="M12 4v11m0 0 4-4m-4 4-4-4M5 19h14"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" className={common} aria-hidden="true">
      <path
        d="M5 7h14m-9 4v5m4-5v5M9 7l1-2h4l1 2m2 0-1 12H8L7 7"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ProjectsClient() {
  const [projects, setProjects] = useState<LocalProject[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [statusFilter, setStatusFilter] = useState<"All" | ProjectStatus>(
    "All",
  );
  const [platformFilter, setPlatformFilter] = useState("All");
  const [previewProjectId, setPreviewProjectId] = useState<string | null>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setProjects(readLocalProjects());
      setHydrated(true);
    });

    return () => window.cancelAnimationFrame(frame);
  }, []);

  const platforms = useMemo(
    () => [...new Set(projects.map((project) => project.platform))].sort(),
    [projects],
  );
  const filteredProjects = useMemo(
    () =>
      projects.filter(
        (project) =>
          (statusFilter === "All" || project.status === statusFilter) &&
          (platformFilter === "All" || project.platform === platformFilter),
      ),
    [platformFilter, projects, statusFilter],
  );
  const completedCount = projects.filter(
    (project) => project.status === "Completed",
  ).length;
  const activeCount = projects.filter((project) =>
    ["Draft", "Script Ready", "Voice Ready", "Rendering"].includes(
      project.status,
    ),
  ).length;

  function handleDelete(project: LocalProject) {
    const confirmed = window.confirm(
      `Delete “${project.title}” from this browser? Generated backend files will not be deleted.`,
    );
    if (!confirmed) return;

    setProjects(deleteLocalProject(project.project_id));
    if (previewProjectId === project.project_id) {
      setPreviewProjectId(null);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-slate-950 text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_2%,_rgba(139,92,246,0.13),_transparent_28%),radial-gradient(circle_at_88%_12%,_rgba(34,211,238,0.1),_transparent_24%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.035] [background-image:linear-gradient(rgba(255,255,255,.7)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.7)_1px,transparent_1px)] [background-size:64px_64px]" />

      <div className="relative mx-auto max-w-7xl px-5 py-6 sm:px-8 lg:px-10">
        <nav className="flex items-center justify-between border-b border-slate-800/80 pb-5">
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
          <Link
            href="/create"
            className="rounded-xl bg-violet-500 px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-violet-950/30 transition hover:bg-violet-400"
          >
            Create New Project
          </Link>
        </nav>

        <header className="grid gap-8 py-12 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.24em] text-cyan-300">
              Local production library
            </p>
            <h1 className="mt-4 max-w-3xl text-4xl font-black tracking-[-0.04em] text-white sm:text-6xl">
              Your ideas, moving toward publish.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">
              {BRAND_TAGLINE} Scripts, narration, and final exports stay
              private in this browser. No account or cloud database required.
            </p>
          </div>

          <dl className="grid grid-cols-3 divide-x divide-slate-800 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/65 shadow-2xl shadow-black/20 backdrop-blur">
            {[
              ["Total", projects.length],
              ["Active", activeCount],
              ["Finished", completedCount],
            ].map(([label, value]) => (
              <div
                key={label}
                className="min-w-24 px-4 py-4 text-center sm:min-w-28"
              >
                <dd className="text-2xl font-black text-white">{value}</dd>
                <dt className="mt-1 font-mono text-[9px] uppercase tracking-[0.2em] text-slate-500">
                  {label}
                </dt>
              </div>
            ))}
          </dl>
        </header>

        {projects.length > 0 && (
          <section className="mb-6 flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur sm:flex-row sm:items-end sm:justify-between">
            <div className="flex flex-1 flex-col gap-3 sm:flex-row">
              <label className="block sm:max-w-56 sm:flex-1">
                <span className="mb-2 block font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
                  Status
                </span>
                <select
                  value={statusFilter}
                  onChange={(event) =>
                    setStatusFilter(event.target.value as "All" | ProjectStatus)
                  }
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-violet-400"
                >
                  <option value="All">All statuses</option>
                  {PROJECT_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {status}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block sm:max-w-56 sm:flex-1">
                <span className="mb-2 block font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
                  Platform
                </span>
                <select
                  value={platformFilter}
                  onChange={(event) => setPlatformFilter(event.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"
                >
                  <option value="All">All platforms</option>
                  {platforms.map((platform) => (
                    <option key={platform} value={platform}>
                      {platform}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="text-sm text-slate-500">
              Showing {filteredProjects.length} of {projects.length}
            </p>
          </section>
        )}

        {!hydrated ? (
          <section
            className="grid gap-5 md:grid-cols-2 xl:grid-cols-3"
            aria-label="Loading projects"
          >
            {[0, 1, 2].map((item) => (
              <div
                key={item}
                className="h-72 animate-pulse rounded-2xl border border-slate-800 bg-slate-900/50"
              />
            ))}
          </section>
        ) : projects.length === 0 ? (
          <section className="rounded-3xl border border-dashed border-slate-700 bg-slate-900/45 px-6 py-20 text-center backdrop-blur">
            <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl border border-violet-400/25 bg-violet-400/10 text-2xl text-violet-200">
              ✦
            </div>
            <h2 className="mt-6 text-2xl font-black text-white">
              No projects yet
            </h2>
            <p className="mx-auto mt-3 max-w-md leading-7 text-slate-400">
              {BRAND_DESCRIPTION} Your project will appear here as it moves
              through production.
            </p>
            <Link
              href="/create"
              className="mt-7 inline-flex rounded-xl bg-violet-500 px-5 py-3 text-sm font-bold text-white transition hover:bg-violet-400"
            >
              Create New Project
            </Link>
          </section>
        ) : filteredProjects.length === 0 ? (
          <section className="rounded-2xl border border-slate-800 bg-slate-900/50 px-6 py-14 text-center">
            <h2 className="text-xl font-bold">
              No projects match these filters
            </h2>
            <button
              type="button"
              onClick={() => {
                setStatusFilter("All");
                setPlatformFilter("All");
              }}
              className="mt-4 text-sm font-semibold text-cyan-300 hover:text-cyan-200"
            >
              Clear filters
            </button>
          </section>
        ) : (
          <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {filteredProjects.map((project, index) => {
              const previewOpen = previewProjectId === project.project_id;
              return (
                <article
                  key={project.project_id}
                  className="group relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80 shadow-xl shadow-black/10 transition duration-300 hover:-translate-y-1 hover:border-slate-700 hover:shadow-2xl hover:shadow-black/25"
                  style={{ animationDelay: `${Math.min(index, 8) * 50}ms` }}
                >
                  <div className="h-1 bg-gradient-to-r from-violet-500 via-cyan-400 to-emerald-400 opacity-65" />
                  <div className="p-5 sm:p-6">
                    <div className="flex items-start justify-between gap-4">
                      <span
                        className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] ${statusStyles[project.status]}`}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full bg-current ${project.status === "Rendering" ? "animate-pulse" : ""}`}
                        />
                        {project.status}
                      </span>
                      <span className="font-mono text-[10px] tracking-[0.14em] text-slate-600">
                        {project.project_id.slice(0, 8)}
                      </span>
                    </div>

                    <h2 className="mt-5 line-clamp-2 text-xl font-black leading-7 tracking-tight text-white">
                      {project.title}
                    </h2>
                    <p className="mt-3 line-clamp-3 min-h-[4.5rem] text-sm leading-6 text-slate-400">
                      {project.idea}
                    </p>

                    <dl className="mt-5 grid grid-cols-3 gap-2 border-y border-slate-800 py-4">
                      {[
                        ["Platform", project.platform],
                        ["Tone", project.tone],
                        ["Length", formatDuration(project.duration)],
                      ].map(([label, value]) => (
                        <div key={label} className="min-w-0">
                          <dt className="font-mono text-[9px] uppercase tracking-[0.16em] text-slate-600">
                            {label}
                          </dt>
                          <dd className="mt-1 truncate text-xs font-semibold text-slate-300">
                            {value}
                          </dd>
                        </div>
                      ))}
                    </dl>

                    <p className="mt-4 text-xs text-slate-500">
                      Updated {formatDate(project.updated_at)}
                    </p>

                    <div className="mt-5 flex flex-wrap gap-2">
                      <Link
                        href={`/create?project_id=${encodeURIComponent(project.project_id)}`}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-2 text-xs font-bold text-slate-950 transition hover:bg-white"
                      >
                        <ActionIcon name="open" /> Open
                      </Link>
                      <button
                        type="button"
                        disabled={!project.video_url}
                        onClick={() =>
                          setPreviewProjectId(
                            previewOpen ? null : project.project_id,
                          )
                        }
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-2 text-xs font-bold text-slate-200 transition hover:border-cyan-400/50 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-35"
                      >
                        <ActionIcon name="play" />{" "}
                        {previewOpen ? "Close Preview" : "Preview Video"}
                      </button>
                      {project.video_url && (
                        <a
                          href={withDownloadParameter(project.video_url)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-2 text-xs font-bold text-slate-300 transition hover:border-emerald-400/50 hover:text-emerald-200"
                        >
                          <ActionIcon name="download" /> Download MP4
                        </a>
                      )}
                      {project.subtitle_url && (
                        <a
                          href={withDownloadParameter(project.subtitle_url)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-2 text-xs font-bold text-slate-300 transition hover:border-violet-400/50 hover:text-violet-200"
                        >
                          <ActionIcon name="download" /> Download SRT
                        </a>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDelete(project)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-transparent px-3 py-2 text-xs font-bold text-slate-500 transition hover:border-rose-400/25 hover:bg-rose-400/5 hover:text-rose-300"
                      >
                        <ActionIcon name="delete" /> Delete
                      </button>
                    </div>

                    {previewOpen && project.video_url && (
                      <video
                        controls
                        preload="metadata"
                        src={project.video_url}
                        className="mt-5 aspect-video w-full rounded-xl border border-slate-800 bg-black"
                      >
                        Preview generated video
                      </video>
                    )}
                  </div>
                </article>
              );
            })}
          </section>
        )}

        <footer className="mt-14 border-t border-slate-800 py-6 text-xs leading-5 text-slate-600">
          Project metadata is stored only in this browser. Deleting browser
          storage removes this list but does not delete generated backend files.
        </footer>
      </div>
    </main>
  );
}
