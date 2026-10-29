// test/ai.test.js — Lab 5, Task D: the failure policy is tested in CI, with NO key and
// NO network. A fake fetch plays the AI provider; we decide what it answers.
const { test, beforeEach } = require("node:test");
const assert = require("node:assert/strict");
const ai = require("../ai");

const OK = { choices: [{ message: { content: "A short summary." }, finish_reason: "stop" }] };

function fakeProvider(...statuses) {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    const status = statuses[Math.min(calls.length, statuses.length) - 1];
    return new Response(JSON.stringify(status === 200 ? OK : { error: "x" }), { status });
  };
  return { fetchImpl, calls };
}

beforeEach(() => {
  process.env.GEMINI_API_KEY = "test-key-not-real";
});

test("summary ok, key only in the header", async () => {
  const { fetchImpl, calls } = fakeProvider(200);
  assert.equal(await ai.summarizeSafe("some text", fetchImpl), "A short summary.");
  assert.equal(calls[0].options.headers.Authorization, "Bearer test-key-not-real");
  assert.ok(!calls[0].url.includes("test-key-not-real"));
});

test("429 is retried with backoff", async () => {
  const { fetchImpl, calls } = fakeProvider(429, 429, 200);
  const waits = [];
  const sleep = async (ms) => waits.push(ms);
  assert.equal(await ai.summarizeSafe("text", fetchImpl, sleep), "A short summary.");
  assert.equal(calls.length, 3);
  assert.deepEqual(waits, [1000, 2000]);
});

test("a bad key is not retried", async () => {
  const { fetchImpl, calls } = fakeProvider(403);
  await assert.rejects(ai.summarizeSafe("text", fetchImpl, async () => {}), ai.AIUnavailable);
  assert.equal(calls.length, 1);
});

test("a timeout gives up cleanly", async () => {
  const fetchImpl = async () => {
    throw new DOMException("slow", "TimeoutError");
  };
  await assert.rejects(ai.summarizeSafe("text", fetchImpl), ai.AIUnavailable);
});

test("an empty answer is a failure", async () => {
  const empty = { choices: [{ message: { content: "" }, finish_reason: "length" }] };
  const fetchImpl = async () => new Response(JSON.stringify(empty), { status: 200 });
  await assert.rejects(ai.summarizeSafe("text", fetchImpl), ai.AIUnavailable);
});

test("a missing key is a failure, not a crash", async () => {
  delete process.env.GEMINI_API_KEY;
  await assert.rejects(ai.summarizeSafe("text"), ai.AIUnavailable);
});

test("the input is capped", async () => {
  const { fetchImpl, calls } = fakeProvider(200);
  await ai.summarizeSafe("x".repeat(50_000), fetchImpl);
  assert.ok(calls[0].options.body.length < 10_000);
});
