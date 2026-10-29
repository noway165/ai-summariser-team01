Node.js teams adding AI to their own project: copy ai.js next to app.js and
test/ai.test.js into test/. Edit PROMPT for your feature. No package to install
(Node 22 has fetch). Call ai.summarizeSafe(text) from ONE server endpoint and return
503 with a friendly message when it throws AIUnavailable.
