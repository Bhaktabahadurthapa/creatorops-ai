"use client";

import { FormEvent, useEffect, useState } from "react";

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

export default function CreatePage() {
  const [idea, setIdea] = useState("");
  const [platform, setPlatform] = useState("YouTube");
  const [tone, setTone] = useState("Professional");
  const [duration, setDuration] = useState(60);
  const [result, setResult] = useState<ScriptResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [voiceFile, setVoiceFile] = useState<File | null>(null);
  const [voiceUploadLoading, setVoiceUploadLoading] = useState(false);
  const [voiceUploadError, setVoiceUploadError] = useState("");
  const [voiceReferenceReady, setVoiceReferenceReady] = useState(false);
  const [voiceStatusLoading, setVoiceStatusLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    async function loadVoiceReferenceStatus() {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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
        if (requestError instanceof Error && requestError.name === "AbortError") {
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
    setAudioUrl("");

    try {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

      const response = await fetch(
        `${apiUrl}/api/generate-script`,
        {
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
        },
      );

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
    } catch (requestError) {
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
    setVoiceError("");
    setAudioUrl("");

    try {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
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

      const data: VoiceResult = await response.json();
      setAudioUrl(`${apiUrl}${data.audio_url}`);
    } catch (requestError) {
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
      setVoiceUploadError("Choose an authorized WAV recording first.");
      return;
    }

    const uploadForm = event.currentTarget;
    setVoiceUploadLoading(true);
    setVoiceUploadError("");

    try {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
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

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-white">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-violet-400">
          CreatorOps AI
        </p>

        <h1 className="mt-3 text-4xl font-bold">Create a New Video</h1>

        <p className="mt-3 text-slate-400">
          Enter your idea and generate the first version of your video script.
        </p>

        <form
          onSubmit={handleSubmit}
          className="mt-10 space-y-6 rounded-2xl border border-slate-800 bg-slate-900 p-6"
        >
          <div>
            <label
              htmlFor="idea"
              className="mb-2 block text-sm font-medium"
            >
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
              <label
                htmlFor="tone"
                className="mb-2 block text-sm font-medium"
              >
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
              <label
                htmlFor="duration"
                className="mb-2 block text-sm font-medium"
              >
                Duration
              </label>

              <select
                id="duration"
                value={duration}
                onChange={(event) =>
                  setDuration(Number(event.target.value))
                }
                className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3"
              >
                <option value={30}>30 seconds</option>
                <option value={60}>60 seconds</option>
                <option value={120}>2 minutes</option>
              </select>
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
                accept=".wav,audio/wav"
                onChange={(event) =>
                  setVoiceFile(event.target.files?.[0] ?? null)
                }
                className="mt-3 block w-full text-sm text-slate-400 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-800 file:px-4 file:py-2.5 file:font-semibold file:text-slate-100 hover:file:bg-slate-700"
              />
              <p className="mt-2 text-xs leading-5 text-slate-500">
                WAV only · 25 MB max · at least 1 second. Upload only a voice
                you own or are authorized to use.
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
                  {result.scenes.length} scenes · {" "}
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
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-slate-500">
                Full narration
              </p>
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
                      Render this narration with your authorized reference voice.
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
                    {voiceLoading ? "Generating Voice…" : "Generate Voice"}
                  </button>
                </div>

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
                {result.scenes.map((scene) => (
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
                    </div>

                    <div className="grid gap-6 p-5 sm:p-6 xl:grid-cols-2">
                      <div>
                        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">
                          Visual direction
                        </p>
                        <p className="mt-2 leading-7 text-slate-200">
                          {scene.visual_description}
                        </p>
                      </div>

                      <div>
                        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">
                          Narration
                        </p>
                        <p className="mt-2 leading-7 text-slate-300">
                          {scene.narration}
                        </p>
                        <p className="mt-4 border-l-2 border-amber-300/70 pl-3 text-sm font-medium text-amber-100">
                          {scene.subtitle}
                        </p>
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
