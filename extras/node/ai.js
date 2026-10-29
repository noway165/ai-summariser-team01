// ai.js — Lab 5: the ONLY file that knows which AI provider we call.
//
// It speaks the "OpenAI-compatible" chat-completions format, which Gemini, Groq and
// OpenRouter all accept. Changing provider = changing AI_BASE_URL, AI_MODEL and the key
// in the environment. No other file changes.
const crypto = require("node:crypto");

const AI_BASE_URL =
  process.env.AI_BASE_URL ?? "https://generativelanguage.googleapis.com/v1beta/openai";
const AI_MODEL = process.env.AI_MODEL ?? "gemini-3.5-flash-lite";
const PROMPT_VERSION = "v1"; // change it when you change the prompt (only matters if you cache)
// Lab 5, Step 2: PROMPT below is the only part you change — describe YOUR feature.
// Keep ${text}: it is replaced by the record from your database.
const PROMPT = (text) =>
  "Summarise the note below in at most three short sentences. " +
  "Use only facts that appear in the note. Reply in the language of the note.\n\n" +
  `NOTE:\n${text}`;
const MAX_INPUT_CHARS = 8000; // cap the input
const TIMEOUT_MS = 15_000; // never wait forever on the network

class AIUnavailable extends Error {} // message is for the logs, never for the browser

class HTTPStatusError extends Error {
  constructor(status) {
    super(`HTTP ${status}`);
    this.status = status;
  }
}

function cacheKey(text) {
  // Same model + same prompt + same text = same summary, so it can be stored and reused.
  const raw = `${AI_MODEL}\n${PROMPT_VERSION}\n${text}`;
  return crypto.createHash("sha256").update(raw).digest("hex");
}

async function summarize(text, fetchImpl = fetch) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) throw new AIUnavailable("GEMINI_API_KEY is not set");
  const prompt = PROMPT(text.slice(0, MAX_INPUT_CHARS));
  const r = await fetchImpl(`${AI_BASE_URL}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify({
      model: AI_MODEL,
      messages: [{ role: "user", content: prompt }],
      temperature: 0.2, // low randomness: this is a summary
      max_tokens: 1024, // caps cost; Gemini 3 "thinking" tokens count here too
      reasoning_effort: "low",
    }),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!r.ok) throw new HTTPStatusError(r.status);
  const data = await r.json();
  // Check the shape before trusting it: refusals and cut-off answers look different.
  const choice = data?.choices?.[0];
  const answer = (choice?.message?.content ?? "").trim();
  if (!answer) throw new AIUnavailable(`empty answer, finish_reason=${choice?.finish_reason}`);
  return answer;
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function summarizeSafe(text, fetchImpl = fetch, sleep = wait) {
  const attempts = 3;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await summarize(text, fetchImpl);
    } catch (err) {
      if (err instanceof HTTPStatusError) {
        if (err.status === 429 || err.status >= 500) {
          // temporary: wait, then try again
          if (attempt < attempts - 1) {
            await sleep(1000 * 2 ** attempt); // 1 s, then 2 s
            continue;
          }
          throw new AIUnavailable(`HTTP ${err.status} after ${attempts} attempts`);
        }
        throw new AIUnavailable(`HTTP ${err.status} (not retried)`); // 4xx never gets better
      }
      if (err.name === "TimeoutError") throw new AIUnavailable("timeout");
      if (err instanceof AIUnavailable) throw err;
      throw new AIUnavailable(`network error: ${err.name}`);
    }
  }
  throw new AIUnavailable("unreachable");
}

module.exports = { summarize, summarizeSafe, cacheKey, AIUnavailable, AI_MODEL };
