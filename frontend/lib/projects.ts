export const PROJECT_STATUSES = [
  "Draft",
  "Script Ready",
  "Voice Ready",
  "Rendering",
  "Completed",
  "Failed",
] as const;

export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

export type LocalProject = {
  project_id: string;
  title: string;
  idea: string;
  platform: string;
  tone: string;
  duration: number;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
  audio_url?: string;
  video_url?: string;
  subtitle_url?: string;
};

const STORAGE_KEY = "creatorops-ai.projects.v1";
const MAX_PROJECTS = 100;

function cleanText(value: unknown, maxLength: number): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const cleaned = value.trim().slice(0, maxLength);
  return cleaned || null;
}

function cleanDate(value: unknown): string | null {
  if (typeof value !== "string" || Number.isNaN(Date.parse(value))) {
    return null;
  }

  return value;
}

function cleanMediaUrl(value: unknown): string | undefined {
  if (typeof value !== "string" || value.length > 2_000) {
    return undefined;
  }

  if (value.startsWith("/") && !value.startsWith("//")) {
    return value;
  }

  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? parsed.toString()
      : undefined;
  } catch {
    return undefined;
  }
}

function normalizeProject(value: unknown): LocalProject | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  const candidate = value as Record<string, unknown>;
  const projectId = cleanText(candidate.project_id, 100);
  const title = cleanText(candidate.title, 200);
  const idea = cleanText(candidate.idea, 2_000);
  const platform = cleanText(candidate.platform, 100);
  const tone = cleanText(candidate.tone, 100);
  const createdAt = cleanDate(candidate.created_at);
  const updatedAt = cleanDate(candidate.updated_at);
  const duration = Number(candidate.duration);
  const status = candidate.status;

  if (
    !projectId ||
    !title ||
    !idea ||
    !platform ||
    !tone ||
    !createdAt ||
    !updatedAt ||
    !Number.isInteger(duration) ||
    duration < 1 ||
    duration > 600 ||
    !PROJECT_STATUSES.includes(status as ProjectStatus)
  ) {
    return null;
  }

  const project: LocalProject = {
    project_id: projectId,
    title,
    idea,
    platform,
    tone,
    duration,
    status: status as ProjectStatus,
    created_at: createdAt,
    updated_at: updatedAt,
  };
  const audioUrl = cleanMediaUrl(candidate.audio_url);
  const videoUrl = cleanMediaUrl(candidate.video_url);
  const subtitleUrl = cleanMediaUrl(candidate.subtitle_url);

  if (audioUrl) project.audio_url = audioUrl;
  if (videoUrl) project.video_url = videoUrl;
  if (subtitleUrl) project.subtitle_url = subtitleUrl;

  return project;
}

export function readLocalProjects(): LocalProject[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = stored ? JSON.parse(stored) : [];
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .map(normalizeProject)
      .filter((project): project is LocalProject => project !== null)
      .sort((left, right) => right.updated_at.localeCompare(left.updated_at))
      .slice(0, MAX_PROJECTS);
  } catch {
    return [];
  }
}

export function getLocalProject(projectId: string): LocalProject | undefined {
  return readLocalProjects().find(
    (project) => project.project_id === projectId,
  );
}

export function saveLocalProject(project: LocalProject): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  const normalized = normalizeProject(project);
  if (!normalized) {
    return false;
  }

  const projects = readLocalProjects().filter(
    (existing) => existing.project_id !== normalized.project_id,
  );

  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([normalized, ...projects].slice(0, MAX_PROJECTS)),
    );
    return true;
  } catch {
    return false;
  }
}

export function deleteLocalProject(projectId: string): LocalProject[] {
  const projects = readLocalProjects().filter(
    (project) => project.project_id !== projectId,
  );

  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
    } catch {
      return readLocalProjects();
    }
  }

  return projects;
}

export function withDownloadParameter(url: string): string {
  return `${url}${url.includes("?") ? "&" : "?"}download=true`;
}
