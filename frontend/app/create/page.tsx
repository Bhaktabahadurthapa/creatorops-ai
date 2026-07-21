"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

import { BRAND_DESCRIPTION } from "@/lib/brand";
import {
  getLocalProject,
  saveLocalProject,
  type LocalProject,
  type ProjectStatus,
} from "@/lib/projects";

type Scene = {
  scene_number: number;
  visual_description: string;
  narration: string;
  subtitle: string;
  duration_seconds: number;
};

type ScriptResult = {
  title: string;
  hook: string;
  narration: string;
  call_to_action: string;
  scenes: Scene[];
};

type VoiceResult = {
  audio_id: string;
  audio_url: string;
};

type VoiceReferenceStatus = {
  ready: boolean;
  filename: string | null;
};

type UploadedMedia = {
  project_id: string;
  media_id: string;
  filename: string;
  media_type: "image" | "video" | "audio";
  media_role: "scene" | "logo" | "background_music";
  media_path: string;
};

type FitMode = "cover" | "contain";
type SceneSource = "text" | "media";
type MotionType =
  | "automatic"
  | "zoom_in"
  | "zoom_out"
  | "pan_left"
  | "pan_right"
  | "pan_up"
  | "pan_down"
  | "none";
type MotionStrength = "subtle" | "medium" | "strong";
type VideoResolution = "720p" | "1080p";

const resolutionLabels: Record<VideoResolution, string> = {
  "720p": "720p HD",
  "1080p": "1080p Full HD",
};

type VideoResult = {
  video_id: string;
  status: "completed";
  video_url: string;
  subtitle_url: string;
  subtitles_burned: boolean;
  resolution: VideoResolution;
};

type JobStatus = "queued" | "processing" | "completed" | "failed";

type JobSubmission = {
  job_id: string;
  job_type: "voice" | "video";
  status: "queued";
  status_url: string;
};

type JobResponse = {
  job_id: string;
  job_type: "voice" | "video";
  status: JobStatus;
  result: Record<string, unknown> | null;
  error: string | null;
};

const apiUrl = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");
const jobPollIntervalMs = 1500;
const jobPollLimit = 1200;

type ProjectSavePatch = {
  title?: string;
  audio_url?: string | null;
  video_url?: string | null;
  subtitle_url?: string | null;
};

async function getResponseError(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const errorBody: { detail?: unknown } = await response.json();
    if (typeof errorBody.detail === "string") {
      return errorBody.detail;
    }
  } catch {
    // Keep the fallback when the backend does not return JSON.
  }

  return fallback;
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function countSpokenWords(text: string): number {
  const withoutPauseMarkers = text.replace(/\[pause\s+[\d.]+s\]/gi, " ");
  return withoutPauseMarkers.match(/[\p{L}\p{N}]+(?:['’\-][\p{L}\p{N}]+)*/gu)
    ?.length ?? 0;
}

function formatTimestamp(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

async function pollForJob(
  submission: JobSubmission,
  onStatus: (status: JobStatus) => void,
): Promise<JobResponse> {
  for (let attempt = 0; attempt < jobPollLimit; attempt += 1) {
    const response = await fetch(`${apiUrl}${submission.status_url}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(
        await getResponseError(response, "Could not check rendering progress."),
      );
    }

    const job: JobResponse = await response.json();
    onStatus(job.status);
    if (job.status === "completed") {
      return job;
    }
    if (job.status === "failed") {
      throw new Error(job.error ?? "The background job failed.");
    }
    await wait(jobPollIntervalMs);
  }

  throw new Error("The background job timed out. Please try again.");
}

function readVoiceResult(job: JobResponse): VoiceResult {
  const audioId = job.result?.audio_id;
  const audioPath = job.result?.audio_url;
  if (typeof audioId !== "string" || typeof audioPath !== "string") {
    throw new Error("Voice generation completed without an audio result.");
  }
  return { audio_id: audioId, audio_url: audioPath };
}

function readVideoResult(job: JobResponse): VideoResult {
  const result = job.result;
  if (
    typeof result?.video_id !== "string" ||
    result.status !== "completed" ||
    typeof result.video_url !== "string" ||
    typeof result.subtitle_url !== "string" ||
    typeof result.subtitles_burned !== "boolean" ||
    (result.resolution !== "720p" && result.resolution !== "1080p")
  ) {
    throw new Error("Video rendering completed without a video result.");
  }
  return {
    video_id: result.video_id,
    status: "completed",
    video_url: result.video_url,
    subtitle_url: result.subtitle_url,
    subtitles_burned: result.subtitles_burned,
    resolution: result.resolution,
  };
}

export default function CreatePage() {
  const [idea, setIdea] = useState("");
  const [platform, setPlatform] = useState("YouTube");
  const [tone, setTone] = useState("Professional");
  const [duration, setDuration] = useState(30);
  const [result, setResult] = useState<ScriptResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [voiceJobStatus, setVoiceJobStatus] = useState<JobStatus | null>(null);
  const [voiceError, setVoiceError] = useState("");
  const [audioId, setAudioId] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [voiceFile, setVoiceFile] = useState<File | null>(null);
  const [voiceUploadLoading, setVoiceUploadLoading] = useState(false);
  const [voiceUploadError, setVoiceUploadError] = useState("");
  const [voiceReferenceReady, setVoiceReferenceReady] = useState(false);
  const [voiceStatusLoading, setVoiceStatusLoading] = useState(true);
  const projectId = useRef("");
  const [sceneMedia, setSceneMedia] = useState<Record<number, UploadedMedia>>(
    {},
  );
  const [sceneSources, setSceneSources] = useState<Record<number, SceneSource>>(
    {},
  );
  const [sceneTextPrompts, setSceneTextPrompts] = useState<
    Record<number, string>
  >({});
  const [sceneFitModes, setSceneFitModes] = useState<Record<number, FitMode>>(
    {},
  );
  const [sceneMotionTypes, setSceneMotionTypes] = useState<
    Record<number, MotionType>
  >({});
  const [sceneMotionStrengths, setSceneMotionStrengths] = useState<
    Record<number, MotionStrength>
  >({});
  const [sceneUploadLoading, setSceneUploadLoading] = useState<
    Record<number, boolean>
  >({});
  const [logoMedia, setLogoMedia] = useState<UploadedMedia | null>(null);
  const [backgroundMusic, setBackgroundMusic] = useState<UploadedMedia | null>(
    null,
  );
  const [optionalUploadLoading, setOptionalUploadLoading] = useState("");
  const [mediaError, setMediaError] = useState("");
  const [videoLoading, setVideoLoading] = useState(false);
  const [videoJobStatus, setVideoJobStatus] = useState<JobStatus | null>(null);
  const [videoError, setVideoError] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [subtitleUrl, setSubtitleUrl] = useState("");
  const [subtitlesBurned, setSubtitlesBurned] = useState(false);
  const [videoResolution, setVideoResolution] =
    useState<VideoResolution>("1080p");
  const [renderedResolution, setRenderedResolution] =
    useState<VideoResolution | null>(null);

  function persistProject(
    status: ProjectStatus,
    patch: ProjectSavePatch = {},
  ): void {
    if (!projectId.current) {
      projectId.current = crypto.randomUUID();
    }

    const existing = getLocalProject(projectId.current);
    const now = new Date().toISOString();
    const fallbackTitle =
      idea.trim().split(/\s+/).slice(0, 8).join(" ") || "Untitled project";
    const project: LocalProject = {
      project_id: projectId.current,
      title: patch.title ?? existing?.title ?? result?.title ?? fallbackTitle,
      idea: idea.trim(),
      platform,
      tone,
      duration,
      status,
      created_at: existing?.created_at ?? now,
      updated_at: now,
    };
    const nextAudioUrl =
      patch.audio_url === null
        ? undefined
        : (patch.audio_url ?? existing?.audio_url);
    const nextVideoUrl =
      patch.video_url === null
        ? undefined
        : (patch.video_url ?? existing?.video_url);
    const nextSubtitleUrl =
      patch.subtitle_url === null
        ? undefined
        : (patch.subtitle_url ?? existing?.subtitle_url);

    if (nextAudioUrl) project.audio_url = nextAudioUrl;
    if (nextVideoUrl) project.video_url = nextVideoUrl;
    if (nextSubtitleUrl) project.subtitle_url = nextSubtitleUrl;
    saveLocalProject(project);
  }

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const requestedProjectId = new URLSearchParams(
        window.location.search,
      ).get("project_id");
      if (!requestedProjectId) {
        return;
      }

      const savedProject = getLocalProject(requestedProjectId);
      if (!savedProject) {
        return;
      }

      projectId.current = savedProject.project_id;
      setIdea(savedProject.idea);
      setPlatform(savedProject.platform);
      setTone(savedProject.tone);
      setDuration(savedProject.duration);
      setAudioUrl(savedProject.audio_url ?? "");
      setVideoUrl(savedProject.video_url ?? "");
      setSubtitleUrl(savedProject.subtitle_url ?? "");

      const audioIdMatch = savedProject.audio_url?.match(
        /\/api\/voice\/audio\/([0-9a-f-]{36})(?:\?|$)/i,
      );
      if (audioIdMatch) {
        setAudioId(audioIdMatch[1]);
      }
    });

    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadVoiceReferenceStatus() {
      try {
        const response = await fetch(`${apiUrl}/api/voice/reference/status`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(
            await getResponseError(
              response,
              "Could not check the voice reference.",
            ),
          );
        }

        const status: VoiceReferenceStatus = await response.json();
        setVoiceReferenceReady(status.ready);
      } catch (requestError) {
        if (
          requestError instanceof Error &&
          requestError.name === "AbortError"
        ) {
          return;
        }

        setVoiceUploadError(
          requestError instanceof Error
            ? requestError.message
            : "Could not check the voice reference.",
        );
      } finally {
        setVoiceStatusLoading(false);
      }
    }

    loadVoiceReferenceStatus();
    return () => controller.abort();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!idea.trim()) {
      setError("Please enter your content idea.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    setVoiceError("");
    setVoiceJobStatus(null);
    setAudioId("");
    setAudioUrl("");
    if (!projectId.current) {
      projectId.current = crypto.randomUUID();
    }
    setSceneMedia({});
    setSceneSources({});
    setSceneTextPrompts({});
    setSceneFitModes({});
    setSceneMotionTypes({});
    setSceneMotionStrengths({});
    setLogoMedia(null);
    setBackgroundMusic(null);
    setMediaError("");
    setVideoError("");
    setVideoJobStatus(null);
    setVideoUrl("");
    setSubtitleUrl("");
    setSubtitlesBurned(false);
    setRenderedResolution(null);
    persistProject("Draft", {
      audio_url: null,
      video_url: null,
      subtitle_url: null,
    });

    try {
      const response = await fetch(`${apiUrl}/api/generate-script`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          idea,
          platform,
          tone,
          duration,
        }),
      });

      if (!response.ok) {
        throw new Error(
          await getResponseError(
            response,
            "The backend could not generate the script.",
          ),
        );
      }

      const data: ScriptResult = await response.json();
      setResult(data);
      persistProject("Script Ready", {
        title: data.title,
        audio_url: null,
        video_url: null,
        subtitle_url: null,
      });
    } catch (requestError) {
      persistProject("Failed");
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not connect to the backend. Make sure FastAPI is running on port 8000.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateVoice() {
    if (!result) {
      return;
    }

    setVoiceLoading(true);
    setVoiceJobStatus("queued");
    setVoiceError("");
    setAudioId("");
    setAudioUrl("");
    setVideoUrl("");
    setSubtitleUrl("");
    setSubtitlesBurned(false);
    setRenderedResolution(null);
    persistProject("Script Ready", {
      audio_url: null,
      video_url: null,
      subtitle_url: null,
    });

    try {
      const response = await fetch(`${apiUrl}/api/voice/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: result.narration,
        }),
      });

      if (!response.ok) {
        throw new Error(
          await getResponseError(
            response,
            "The backend could not generate the narration audio.",
          ),
        );
      }

      const submission: JobSubmission = await response.json();
      const job = await pollForJob(submission, setVoiceJobStatus);
      const data = readVoiceResult(job);
      const generatedAudioUrl = `${apiUrl}${data.audio_url}`;
      setAudioId(data.audio_id);
      setAudioUrl(generatedAudioUrl);
      persistProject("Voice Ready", {
        audio_url: generatedAudioUrl,
        video_url: null,
        subtitle_url: null,
      });
    } catch (requestError) {
      persistProject("Failed");
      setVoiceError(
        requestError instanceof Error
          ? requestError.message
          : "Could not generate narration audio.",
      );
    } finally {
      setVoiceLoading(false);
    }
  }

  async function handleVoiceUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!voiceFile) {
      setVoiceUploadError("Choose an authorized audio recording first.");
      return;
    }

    const uploadForm = event.currentTarget;
    setVoiceUploadLoading(true);
    setVoiceUploadError("");

    try {
      const formData = new FormData();
      formData.append("file", voiceFile);

      const response = await fetch(`${apiUrl}/api/voice/reference`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(
          await getResponseError(
            response,
            "The backend could not save the voice reference.",
          ),
        );
      }

      const status: VoiceReferenceStatus = await response.json();
      setVoiceReferenceReady(status.ready);
      setVoiceFile(null);
      setVoiceError("");
      uploadForm.reset();
    } catch (requestError) {
      setVoiceUploadError(
        requestError instanceof Error
          ? requestError.message
          : "Could not upload the voice reference.",
      );
    } finally {
      setVoiceUploadLoading(false);
    }
  }

  async function uploadMedia(
    file: File,
    mediaRole: "scene" | "logo" | "background_music",
  ): Promise<UploadedMedia> {
    if (!projectId.current) {
      projectId.current = crypto.randomUUID();
    }

    const formData = new FormData();
    formData.append("project_id", projectId.current);
    formData.append("media_role", mediaRole);
    formData.append("file", file);

    const response = await fetch(`${apiUrl}/api/media/upload`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(
        await getResponseError(
          response,
          "The media file could not be uploaded.",
        ),
      );
    }
    return response.json();
  }

  async function handleSceneMediaUpload(sceneNumber: number, file: File) {
    setSceneUploadLoading((current) => ({ ...current, [sceneNumber]: true }));
    setMediaError("");
    setVideoUrl("");
    setSubtitleUrl("");
    setRenderedResolution(null);

    try {
      const uploaded = await uploadMedia(file, "scene");
      setSceneMedia((current) => ({ ...current, [sceneNumber]: uploaded }));
      setSceneSources((current) => ({ ...current, [sceneNumber]: "media" }));
    } catch (requestError) {
      setMediaError(
        requestError instanceof Error
          ? requestError.message
          : "The scene media could not be uploaded.",
      );
    } finally {
      setSceneUploadLoading((current) => ({
        ...current,
        [sceneNumber]: false,
      }));
    }
  }

  async function handleOptionalMediaUpload(
    mediaRole: "logo" | "background_music",
    file: File,
  ) {
    setOptionalUploadLoading(mediaRole);
    setMediaError("");
    setVideoUrl("");
    setSubtitleUrl("");
    setRenderedResolution(null);

    try {
      const uploaded = await uploadMedia(file, mediaRole);
      if (mediaRole === "logo") {
        setLogoMedia(uploaded);
      } else {
        setBackgroundMusic(uploaded);
      }
    } catch (requestError) {
      setMediaError(
        requestError instanceof Error
          ? requestError.message
          : "The optional media could not be uploaded.",
      );
    } finally {
      setOptionalUploadLoading("");
    }
  }

  async function handleRenderVideo() {
    if (!result || !audioId) {
      setVideoError("Generate the narration voice before rendering video.");
      return;
    }
    const sceneMissingMedia = result.scenes.find(
      (scene) =>
        (sceneSources[scene.scene_number] ?? "text") === "media" &&
        !sceneMedia[scene.scene_number],
    );
    if (sceneMissingMedia) {
      setVideoError(
        `Choose an image or video for scene ${sceneMissingMedia.scene_number}, or switch it to Generate AI Visual.`,
      );
      return;
    }
    setVideoLoading(true);
    setVideoJobStatus("queued");
    setVideoError("");
    setVideoUrl("");
    setSubtitleUrl("");
    setRenderedResolution(null);
    persistProject("Rendering", {
      video_url: null,
      subtitle_url: null,
    });

    try {
      const response = await fetch(`${apiUrl}/api/video/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audio_id: audioId,
          resolution: videoResolution,
          scenes: result.scenes.map((scene) => {
            const source = sceneSources[scene.scene_number] ?? "text";
            const media =
              source === "media" ? sceneMedia[scene.scene_number] : undefined;
            return {
              scene_number: scene.scene_number,
              duration_seconds: scene.duration_seconds,
              media_path: media?.media_path ?? null,
              media_type: media?.media_type ?? "generated",
              subtitle: scene.subtitle,
              visual_description:
                sceneTextPrompts[scene.scene_number] ??
                scene.visual_description,
              fit_mode: sceneFitModes[scene.scene_number] ?? "cover",
              motion_type: sceneMotionTypes[scene.scene_number] ?? "automatic",
              motion_strength:
                sceneMotionStrengths[scene.scene_number] ?? "subtle",
            };
          }),
          logo_path: logoMedia?.media_path ?? null,
          background_music_path: backgroundMusic?.media_path ?? null,
        }),
      });
      if (!response.ok) {
        throw new Error(
          await getResponseError(
            response,
            "The backend could not render the final video.",
          ),
        );
      }

      const submission: JobSubmission = await response.json();
      const job = await pollForJob(submission, setVideoJobStatus);
      const video = readVideoResult(job);
      const generatedVideoUrl = `${apiUrl}${video.video_url}`;
      const generatedSubtitleUrl = `${apiUrl}${video.subtitle_url}`;
      setVideoUrl(generatedVideoUrl);
      setSubtitleUrl(generatedSubtitleUrl);
      setSubtitlesBurned(video.subtitles_burned);
      setRenderedResolution(video.resolution);
      persistProject("Completed", {
        video_url: generatedVideoUrl,
        subtitle_url: generatedSubtitleUrl,
      });
    } catch (requestError) {
      persistProject("Failed");
      setVideoError(
        requestError instanceof Error
          ? requestError.message
          : "The final video could not be rendered.",
      );
    } finally {
      setVideoLoading(false);
    }
  }

  const selectedMediaCount =
    result?.scenes.filter(
      (scene) => (sceneSources[scene.scene_number] ?? "text") === "media",
    ).length ?? 0;
  const hasMissingSelectedMedia =
    result?.scenes.some(
      (scene) =>
        (sceneSources[scene.scene_number] ?? "text") === "media" &&
        !sceneMedia[scene.scene_number],
    ) ?? false;
  const narrationWordCount = result ? countSpokenWords(result.narration) : 0;
  const estimatedRuntimeSeconds = Math.round(narrationWordCount / 2.3);
  let elapsedSceneSeconds = 0;
  const sceneTimings =
    result?.scenes.map((scene) => {
      const start = elapsedSceneSeconds;
      elapsedSceneSeconds += scene.duration_seconds;
      return { start, end: elapsedSceneSeconds };
    }) ?? [];

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-white">
      <div className="mx-auto max-w-6xl">
        <Link
          href="/"
          aria-label="CreatorOps AI home"
          className="inline-flex cursor-pointer rounded-md text-sm font-semibold uppercase tracking-widest text-violet-400 outline-none transition hover:text-violet-300 focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-4 focus-visible:ring-offset-slate-950"
        >
          CreatorOps AI
        </Link>

        <h1 className="mt-3 text-4xl font-bold">Create a New Video</h1>

        <p className="mt-3 text-slate-400">
          {BRAND_DESCRIPTION}
        </p>

        <form
          onSubmit={handleSubmit}
          className="mt-10 space-y-6 rounded-2xl border border-slate-800 bg-slate-900 p-6"
        >
          <div>
            <label htmlFor="idea" className="mb-2 block text-sm font-medium">
              Content idea
            </label>

            <textarea
              id="idea"
              value={idea}
              onChange={(event) => setIdea(event.target.value)}
              placeholder="Example: Help small businesses automate customer support"
              rows={5}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 p-4 outline-none focus:border-violet-500"
            />
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            <div>
              <label
                htmlFor="platform"
                className="mb-2 block text-sm font-medium"
              >
                Platform
              </label>

              <select
                id="platform"
                value={platform}
                onChange={(event) => setPlatform(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3"
              >
                <option>YouTube</option>
                <option>LinkedIn</option>
                <option>TikTok</option>
                <option>Instagram</option>
              </select>
            </div>

            <div>
              <label htmlFor="tone" className="mb-2 block text-sm font-medium">
                Tone
              </label>

              <select
                id="tone"
                value={tone}
                onChange={(event) => setTone(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3"
              >
                <option>Professional</option>
                <option>Friendly</option>
                <option>Educational</option>
                <option>Energetic</option>
              </select>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between gap-3">
                <label htmlFor="duration" className="text-sm font-medium">
                  Duration
                </label>
                <output
                  htmlFor="duration"
                  className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 font-mono text-xs font-semibold text-cyan-200"
                >
                  {duration < 60
                    ? `${duration} seconds`
                    : `${Math.floor(duration / 60)}m${
                        duration % 60 ? ` ${duration % 60}s` : ""
                      }`}
                </output>
              </div>

              <div className="rounded-xl border border-slate-700 bg-slate-950/80 px-4 py-3">
                <input
                  id="duration"
                  type="range"
                  min={5}
                  max={120}
                  step={5}
                  value={duration}
                  onChange={(event) => setDuration(Number(event.target.value))}
                  aria-valuetext={`${duration} seconds`}
                  className="h-2 w-full cursor-pointer accent-cyan-400"
                />
                <div className="mt-2 flex justify-between font-mono text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <span>5 sec</span>
                  <span>30 sec</span>
                  <span>1 min</span>
                  <span>2 min</span>
                </div>
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="rounded-xl bg-violet-600 px-6 py-3 font-semibold hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Generating..." : "Generate Script"}
          </button>
        </form>

        <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/70 p-5 sm:p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-slate-500">
                  Voice reference
                </p>
                <span
                  className={`rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] ${
                    voiceReferenceReady
                      ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
                      : "border-amber-400/30 bg-amber-400/10 text-amber-200"
                  }`}
                >
                  {voiceStatusLoading
                    ? "Checking"
                    : voiceReferenceReady
                      ? "Ready for later"
                      : "Upload required"}
                </span>
              </div>
              <h2 className="mt-3 text-xl font-bold text-white">
                Save your authorized voice for narration
              </h2>
            </div>
            <p className="max-w-md text-sm leading-6 text-slate-400">
              The recording stays in the private backend folder and remains
              available for future scripts on this installation.
            </p>
          </div>

          <form
            onSubmit={handleVoiceUpload}
            className="mt-5 grid gap-4 rounded-xl border border-slate-800 bg-slate-950/70 p-4 lg:grid-cols-[1fr_auto] lg:items-end"
          >
            <div>
              <label
                htmlFor="voice-reference"
                className="text-sm font-semibold text-slate-200"
              >
                {voiceReferenceReady
                  ? "Replace voice reference"
                  : "Upload your voice reference"}
              </label>
              <input
                id="voice-reference"
                name="voice-reference"
                type="file"
                onChange={(event) =>
                  setVoiceFile(event.target.files?.[0] ?? null)
                }
                className="mt-3 block w-full text-sm text-slate-400 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-800 file:px-4 file:py-2.5 file:font-semibold file:text-slate-100 hover:file:bg-slate-700"
              />
              <p className="mt-2 text-xs leading-5 text-slate-500">
                Most audio formats are accepted, including WAV, MP3, M4A, AAC,
                FLAC, OGG/Opus, WebM, MP4/MOV audio, AIFF, CAF, and WMA · 25 MB
                max · 6–20 clear seconds recommended. Upload only a voice you
                own or are authorized to use.
              </p>
            </div>

            <button
              type="submit"
              disabled={voiceUploadLoading || !voiceFile}
              className="w-fit rounded-lg bg-slate-100 px-5 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              {voiceUploadLoading
                ? "Saving…"
                : voiceReferenceReady
                  ? "Replace WAV"
                  : "Save voice"}
            </button>
          </form>

          {voiceUploadError && (
            <p className="mt-4 rounded-xl border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {voiceUploadError}
            </p>
          )}
        </section>

        {error && (
          <div className="mt-6 rounded-xl border border-red-800 bg-red-950/40 p-4 text-red-300">
            {error}
          </div>
        )}

        {result && (
          <section
            aria-live="polite"
            className="mt-8 overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/80 shadow-2xl shadow-black/20"
          >
            <header className="border-b border-slate-800 bg-[radial-gradient(circle_at_top_right,_rgba(139,92,246,0.18),_transparent_45%)] p-6 sm:p-8">
              <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.24em] text-violet-400">
                    Production blueprint
                  </p>
                  <h2 className="mt-3 max-w-3xl text-3xl font-bold tracking-tight sm:text-4xl">
                    {result.title}
                  </h2>
                </div>

                <div className="w-fit rounded-full border border-slate-700 bg-slate-950/70 px-4 py-2 font-mono text-xs text-slate-300">
                  {result.scenes.length} scenes ·{" "}
                  {result.scenes.reduce(
                    (total, scene) => total + scene.duration_seconds,
                    0,
                  )}
                  s total
                </div>
              </div>
            </header>

            <div className="grid gap-px bg-slate-800 lg:grid-cols-2">
              <article className="bg-slate-900 p-6 sm:p-8">
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-amber-300">
                  Opening hook
                </p>
                <p className="mt-4 text-xl font-semibold leading-8 text-white">
                  “{result.hook}”
                </p>
              </article>

              <article className="bg-slate-900 p-6 sm:p-8">
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-emerald-300">
                  Call to action
                </p>
                <p className="mt-4 text-lg leading-8 text-slate-200">
                  {result.call_to_action}
                </p>
              </article>
            </div>

            <article className="border-b border-slate-800 bg-slate-950/40 p-6 sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-slate-500">
                  Audio script
                </p>
                <p className="rounded-full border border-slate-800 bg-slate-950 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-400">
                  {narrationWordCount} words · ~{estimatedRuntimeSeconds}s spoken
                </p>
              </div>
              <p className="mt-4 max-w-4xl whitespace-pre-wrap leading-8 text-slate-300">
                {result.narration}
              </p>

              <div className="mt-7 border-t border-slate-800 pt-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-3">
                      <p className="font-mono text-xs uppercase tracking-[0.2em] text-slate-500">
                        Voice track
                      </p>
                      <span
                        className={`rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] ${
                          voiceReferenceReady
                            ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
                            : "border-amber-400/30 bg-amber-400/10 text-amber-200"
                        }`}
                      >
                        {voiceStatusLoading
                          ? "Checking reference"
                          : voiceReferenceReady
                            ? "Reference ready"
                            : "Reference required"}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-slate-400">
                      Render this narration with your authorized reference
                      voice.
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={handleGenerateVoice}
                    disabled={
                      voiceLoading || voiceStatusLoading || !voiceReferenceReady
                    }
                    className="w-fit rounded-xl border border-emerald-400/40 bg-emerald-400/10 px-5 py-3 text-sm font-bold text-emerald-200 transition hover:border-emerald-300 hover:bg-emerald-400/15 disabled:cursor-wait disabled:opacity-60"
                  >
                    {voiceLoading
                      ? voiceJobStatus === "queued"
                        ? "Voice queued…"
                        : "Generating Voice…"
                      : "Generate Voice"}
                  </button>
                </div>

                {voiceLoading && (
                  <p className="mt-4 text-sm text-emerald-300/80" role="status">
                    {voiceJobStatus === "queued"
                      ? "Your voice job is queued on the voice worker."
                      : "Chatterbox is generating narration. This page will update automatically."}
                  </p>
                )}

                {voiceError && (
                  <p className="mt-4 rounded-xl border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">
                    {voiceError}
                  </p>
                )}

                {audioUrl && (
                  <div className="mt-5 rounded-2xl border border-emerald-500/25 bg-emerald-500/5 p-4 sm:p-5">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                      <div className="flex items-center gap-3">
                        <span className="relative flex h-3 w-3">
                          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-50" />
                          <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-400" />
                        </span>
                        <div>
                          <p className="font-semibold text-emerald-100">
                            Narration ready
                          </p>
                          <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-300/60">
                            WAV · Authorized voice
                          </p>
                        </div>
                      </div>

                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                        <audio
                          controls
                          preload="metadata"
                          src={audioUrl}
                          className="h-10 max-w-full"
                        >
                          Play audio
                        </audio>
                        <a
                          href={`${audioUrl}?download=true`}
                          className="rounded-lg border border-slate-700 px-4 py-2 text-center text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:bg-slate-800"
                        >
                          Download WAV
                        </a>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </article>

            <div className="p-6 sm:p-8">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.24em] text-violet-400">
                    Scene plan
                  </p>
                  <h3 className="mt-2 text-2xl font-bold">Shot by shot</h3>
                </div>
                <div className="h-px flex-1 bg-slate-800" />
              </div>

              <ol className="mt-8 space-y-4">
                {result.scenes.map((scene, sceneIndex) => {
                  const source = sceneSources[scene.scene_number] ?? "text";
                  const selectedMedia =
                    source === "media"
                      ? sceneMedia[scene.scene_number]
                      : undefined;

                  return (
                    <li
                      key={scene.scene_number}
                      className="grid overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/60 transition-colors hover:border-slate-700 lg:grid-cols-[8rem_1fr]"
                    >
                      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900 px-5 py-4 lg:block lg:border-r lg:border-b-0 lg:px-6 lg:py-6">
                        <div>
                          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">
                            Scene
                          </p>
                          <p className="mt-1 text-3xl font-bold text-violet-300">
                            {String(scene.scene_number).padStart(2, "0")}
                          </p>
                        </div>
                        <p className="rounded-full bg-slate-950 px-3 py-1 font-mono text-xs text-slate-400 lg:mt-5 lg:w-fit">
                          {scene.duration_seconds}s
                        </p>
                        <p className="mt-2 font-mono text-[10px] text-slate-500">
                          {formatTimestamp(sceneTimings[sceneIndex].start)}–
                          {formatTimestamp(sceneTimings[sceneIndex].end)}
                        </p>
                      </div>

                      <div className="grid gap-6 p-5 sm:p-6 xl:grid-cols-2">
                        <div>
                          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">
                            Avatar video prompt
                          </p>
                          <p className="mt-2 leading-7 text-slate-200">
                            {scene.visual_description}
                          </p>
                        </div>

                        <div>
                          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">
                            Dialogue
                          </p>
                          <p className="mt-2 leading-7 text-slate-300">
                            {scene.narration}
                          </p>
                          <p className="mt-4 border-l-2 border-amber-300/70 pl-3 text-sm font-medium text-amber-100">
                            {scene.subtitle}
                          </p>
                        </div>

                        <div className="border-t border-slate-800 pt-5 xl:col-span-2">
                          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-300">
                            Choose scene source
                          </p>
                          <div className="mt-3 grid gap-3 sm:grid-cols-2">
                            <button
                              type="button"
                              aria-pressed={source === "text"}
                              onClick={() => {
                                setSceneSources((current) => ({
                                  ...current,
                                  [scene.scene_number]: "text",
                                }));
                                setVideoError("");
                                setVideoUrl("");
                                setSubtitleUrl("");
                                setRenderedResolution(null);
                              }}
                              className={`rounded-xl border p-4 text-left transition ${
                                source === "text"
                                  ? "border-violet-400/70 bg-violet-400/10 ring-1 ring-violet-400/30"
                                  : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                              }`}
                            >
                              <span className="block text-sm font-bold text-white">
                                Generate AI Visual
                              </span>
                              <span className="mt-1 block text-xs leading-5 text-slate-400">
                                Create a text-free AI scene image, then add
                                camera motion without an upload.
                              </span>
                            </button>
                            <button
                              type="button"
                              aria-pressed={source === "media"}
                              onClick={() => {
                                setSceneSources((current) => ({
                                  ...current,
                                  [scene.scene_number]: "media",
                                }));
                                setVideoError("");
                                setVideoUrl("");
                                setSubtitleUrl("");
                                setRenderedResolution(null);
                              }}
                              className={`rounded-xl border p-4 text-left transition ${
                                source === "media"
                                  ? "border-cyan-400/70 bg-cyan-400/10 ring-1 ring-cyan-400/30"
                                  : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                              }`}
                            >
                              <span className="block text-sm font-bold text-white">
                                Upload Image / Video
                              </span>
                              <span className="mt-1 block text-xs leading-5 text-slate-400">
                                Use your own photo or clip with fit, pan, and
                                zoom controls.
                              </span>
                            </button>
                          </div>

                          {source === "text" ? (
                            <div className="mt-4 rounded-xl border border-violet-400/20 bg-violet-400/5 p-4">
                              <label
                                htmlFor={`scene-text-${scene.scene_number}`}
                                className="font-mono text-[10px] uppercase tracking-[0.2em] text-violet-300"
                              >
                                AI visual prompt
                              </label>
                              <textarea
                                id={`scene-text-${scene.scene_number}`}
                                rows={3}
                                value={
                                  sceneTextPrompts[scene.scene_number] ??
                                  scene.visual_description
                                }
                                onChange={(event) => {
                                  setSceneTextPrompts((current) => ({
                                    ...current,
                                    [scene.scene_number]: event.target.value,
                                  }));
                                  setVideoUrl("");
                                  setSubtitleUrl("");
                                }}
                                className="mt-3 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-3 py-3 text-sm leading-6 text-slate-200 outline-none focus:border-violet-400"
                              />
                              <p className="mt-2 text-xs text-slate-500">
                                OpenAI creates a text-free scene image from this
                                prompt. CreatorOps then adds motion and syncs it
                                with the narration and subtitles.
                              </p>
                            </div>
                          ) : (
                            <div className="mt-4 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4">
                              <label
                                htmlFor={`scene-media-${scene.scene_number}`}
                                className="font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-300"
                              >
                                Scene media · image or video
                              </label>
                              <input
                                id={`scene-media-${scene.scene_number}`}
                                type="file"
                                accept="image/*,video/*,.mkv,.m4v,.avi"
                                onChange={(event) => {
                                  const file = event.target.files?.[0];
                                  event.target.value = "";
                                  if (file) {
                                    void handleSceneMediaUpload(
                                      scene.scene_number,
                                      file,
                                    );
                                  }
                                }}
                                className="mt-3 block w-full text-sm text-slate-400 file:mr-4 file:rounded-lg file:border-0 file:bg-cyan-400/10 file:px-4 file:py-2 file:font-semibold file:text-cyan-200 hover:file:bg-cyan-400/15"
                              />
                              <p className="mt-2 text-xs text-slate-500">
                                {sceneUploadLoading[scene.scene_number]
                                  ? "Uploading and validating…"
                                  : selectedMedia
                                    ? `${selectedMedia.filename} is ready.`
                                    : "Choose one image or video, or switch back to Generate AI Visual."}
                              </p>
                            </div>
                          )}

                          <div className="mt-4 grid gap-4 md:grid-cols-3 md:items-end">
                            <div>
                              <label
                                htmlFor={`fit-mode-${scene.scene_number}`}
                                className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500"
                              >
                                Frame mode
                              </label>
                              <select
                                id={`fit-mode-${scene.scene_number}`}
                                value={
                                  sceneFitModes[scene.scene_number] ?? "cover"
                                }
                                disabled={source === "text"}
                                onChange={(event) =>
                                  setSceneFitModes((current) => ({
                                    ...current,
                                    [scene.scene_number]: event.target
                                      .value as FitMode,
                                  }))
                                }
                                className="mt-3 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
                              >
                                <option value="cover">Cover</option>
                                <option value="contain">Contain</option>
                              </select>
                            </div>

                            <div>
                              <label
                                htmlFor={`motion-type-${scene.scene_number}`}
                                className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500"
                              >
                                Motion
                              </label>
                              <select
                                id={`motion-type-${scene.scene_number}`}
                                value={
                                  sceneMotionTypes[scene.scene_number] ??
                                  "automatic"
                                }
                                disabled={
                                  source === "text" ||
                                  selectedMedia?.media_type === "video"
                                }
                                onChange={(event) =>
                                  setSceneMotionTypes((current) => ({
                                    ...current,
                                    [scene.scene_number]: event.target
                                      .value as MotionType,
                                  }))
                                }
                                className="mt-3 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
                              >
                                <option value="automatic">Automatic</option>
                                <option value="zoom_in">Slow Zoom In</option>
                                <option value="zoom_out">Slow Zoom Out</option>
                                <option value="pan_left">Pan Left</option>
                                <option value="pan_right">Pan Right</option>
                                <option value="pan_up">Pan Up</option>
                                <option value="pan_down">Pan Down</option>
                                <option value="none">No Motion</option>
                              </select>
                            </div>

                            <div>
                              <label
                                htmlFor={`motion-strength-${scene.scene_number}`}
                                className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500"
                              >
                                Strength
                              </label>
                              <select
                                id={`motion-strength-${scene.scene_number}`}
                                value={
                                  sceneMotionStrengths[scene.scene_number] ??
                                  "subtle"
                                }
                                disabled={
                                  source === "text" ||
                                  selectedMedia?.media_type === "video" ||
                                  sceneMotionTypes[scene.scene_number] ===
                                    "none"
                                }
                                onChange={(event) =>
                                  setSceneMotionStrengths((current) => ({
                                    ...current,
                                    [scene.scene_number]: event.target
                                      .value as MotionStrength,
                                  }))
                                }
                                className="mt-3 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
                              >
                                <option value="subtle">Subtle</option>
                                <option value="medium">Balanced</option>
                                <option value="strong">Strong</option>
                              </select>
                            </div>
                          </div>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>

              <section className="mt-8 overflow-hidden rounded-2xl border border-cyan-500/20 bg-slate-950/70">
                <div className="border-b border-slate-800 bg-[linear-gradient(110deg,_rgba(34,211,238,0.08),_transparent_55%)] p-5 sm:p-6">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-cyan-300">
                        Final assembly
                      </p>
                      <h4 className="mt-2 text-xl font-bold text-white">
                        Render the scene plan
                      </h4>
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                        Mix AI-generated visuals with your uploaded images and video
                        clips in one narration-synced MP4.
                      </p>
                    </div>
                    <div className="rounded-full border border-slate-700 px-3 py-1.5 font-mono text-xs text-slate-400">
                      {selectedMediaCount} media ·{" "}
                      {result.scenes.length - selectedMediaCount} text
                    </div>
                  </div>
                </div>

                <div className="grid gap-px bg-slate-800 md:grid-cols-2">
                  <label className="block bg-slate-950 p-5 sm:p-6">
                    <span className="text-sm font-semibold text-slate-200">
                      Optional logo
                    </span>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        event.target.value = "";
                        if (file) {
                          void handleOptionalMediaUpload("logo", file);
                        }
                      }}
                      className="mt-3 block w-full text-sm text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-slate-200"
                    />
                    <span className="mt-2 block text-xs text-slate-500">
                      {optionalUploadLoading === "logo"
                        ? "Uploading logo…"
                        : (logoMedia?.filename ?? "PNG, JPG, or WebP")}
                    </span>
                  </label>

                  <label className="block bg-slate-950 p-5 sm:p-6">
                    <span className="text-sm font-semibold text-slate-200">
                      Optional background music
                    </span>
                    <input
                      type="file"
                      accept="audio/*"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        event.target.value = "";
                        if (file) {
                          void handleOptionalMediaUpload(
                            "background_music",
                            file,
                          );
                        }
                      }}
                      className="mt-3 block w-full text-sm text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-slate-200"
                    />
                    <span className="mt-2 block text-xs text-slate-500">
                      {optionalUploadLoading === "background_music"
                        ? "Uploading music…"
                        : (backgroundMusic?.filename ??
                          "Mixed quietly beneath narration")}
                    </span>
                  </label>
                </div>

                <div className="p-5 sm:p-6">
                  <fieldset className="mb-5">
                    <legend className="text-sm font-semibold text-slate-200">
                      Final video quality
                    </legend>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Choose the resolution for the preview and downloaded MP4.
                    </p>
                    <div className="mt-3 grid max-w-xl gap-3 sm:grid-cols-2">
                      {(
                        [
                          {
                            value: "720p",
                            title: "720p HD",
                            detail: "Smaller file and faster export",
                          },
                          {
                            value: "1080p",
                            title: "1080p Full HD",
                            detail: "Best detail for final delivery",
                          },
                        ] as const
                      ).map((option) => {
                        const selected = videoResolution === option.value;
                        return (
                          <button
                            key={option.value}
                            type="button"
                            aria-pressed={selected}
                            onClick={() => {
                              setVideoResolution(option.value);
                              setVideoUrl("");
                              setSubtitleUrl("");
                              setRenderedResolution(null);
                            }}
                            className={`rounded-xl border p-4 text-left transition ${
                              selected
                                ? "border-cyan-300 bg-cyan-300/10 shadow-[0_0_0_1px_rgba(103,232,249,0.2)]"
                                : "border-slate-700 bg-slate-900/70 hover:border-slate-600"
                            }`}
                          >
                            <span
                              className={`block text-sm font-bold ${
                                selected ? "text-cyan-100" : "text-slate-200"
                              }`}
                            >
                              {option.title}
                            </span>
                            <span className="mt-1 block text-xs text-slate-500">
                              {option.detail}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </fieldset>

                  {mediaError && (
                    <p className="mb-4 rounded-xl border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">
                      {mediaError}
                    </p>
                  )}
                  {videoError && (
                    <p className="mb-4 rounded-xl border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">
                      {videoError}
                    </p>
                  )}

                  <button
                    type="button"
                    onClick={handleRenderVideo}
                    disabled={
                      videoLoading || !audioId || hasMissingSelectedMedia
                    }
                    className="rounded-xl bg-cyan-300 px-6 py-3 font-bold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {videoLoading
                      ? videoJobStatus === "queued"
                        ? `${resolutionLabels[videoResolution]} render queued…`
                        : `Rendering ${resolutionLabels[videoResolution]}…`
                      : `Create ${resolutionLabels[videoResolution]} Video`}
                  </button>

                  {videoLoading && (
                    <p className="mt-3 text-sm text-cyan-200/80" role="status">
                      {videoJobStatus === "queued"
                        ? "Your render is queued. The page will begin tracking it automatically."
                        : "OpenAI is creating scene visuals, then FFmpeg will animate and render the final video. You can keep this page open."}
                    </p>
                  )}

                  {!audioId && (
                    <p className="mt-3 text-xs text-slate-500">
                      Generate the narration voice before the final render.
                    </p>
                  )}
                  {audioId && hasMissingSelectedMedia && (
                    <p className="mt-3 text-xs text-amber-300/80">
                      Upload media for each scene set to Image / Video, or
                      switch that scene to Generate AI Visual.
                    </p>
                  )}

                  {videoUrl && (
                    <div className="mt-6 rounded-2xl border border-cyan-400/25 bg-cyan-400/5 p-4 sm:p-5">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                          <p className="font-semibold text-cyan-100">
                            Final{" "}
                            {
                              resolutionLabels[
                                renderedResolution ?? videoResolution
                              ]
                            }{" "}
                            MP4 ready
                          </p>
                          <p className="mt-1 text-xs text-cyan-300/60">
                            Narration synced ·{" "}
                            {subtitlesBurned
                              ? "subtitles burned in"
                              : "SRT provided separately"}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {subtitleUrl && (
                            <a
                              href={`${subtitleUrl}?download=true`}
                              className="w-fit rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-800"
                            >
                              Download SRT
                            </a>
                          )}
                          <a
                            href={`${videoUrl}?download=true`}
                            className="w-fit rounded-lg border border-cyan-300/30 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/10"
                          >
                            Download{" "}
                            {
                              resolutionLabels[
                                renderedResolution ?? videoResolution
                              ]
                            }{" "}
                            MP4
                          </a>
                        </div>
                      </div>
                      <video
                        controls
                        preload="metadata"
                        src={videoUrl}
                        className="mt-5 aspect-video w-full rounded-xl bg-black"
                      >
                        Preview final video
                      </video>
                    </div>
                  )}
                </div>
              </section>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
