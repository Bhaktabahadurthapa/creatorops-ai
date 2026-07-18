"use client";

import { FormEvent, useState } from "react";

type ScriptResult = {
  title: string;
  script: string;
};

export default function CreatePage() {
  const [idea, setIdea] = useState("");
  const [platform, setPlatform] = useState("YouTube");
  const [tone, setTone] = useState("Professional");
  const [duration, setDuration] = useState(60);
  const [result, setResult] = useState<ScriptResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!idea.trim()) {
      setError("Please enter your content idea.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/generate-script",
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
        throw new Error("The backend could not generate the script.");
      }

      const data: ScriptResult = await response.json();
      setResult(data);
    } catch {
      setError(
        "Could not connect to the backend. Make sure FastAPI is running on port 8000.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-white">
      <div className="mx-auto max-w-4xl">
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

        {error && (
          <div className="mt-6 rounded-xl border border-red-800 bg-red-950/40 p-4 text-red-300">
            {error}
          </div>
        )}

        {result && (
          <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm font-semibold text-violet-400">
              Generated Script
            </p>

            <h2 className="mt-2 text-2xl font-bold">{result.title}</h2>

            <pre className="mt-5 whitespace-pre-wrap font-sans leading-7 text-slate-300">
              {result.script}
            </pre>
          </section>
        )}
      </div>
    </main>
  );
}