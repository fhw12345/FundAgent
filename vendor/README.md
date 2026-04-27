# vendor/

Local-only third-party artifacts that FundAgent depends on at runtime.

## `agent-maestro-2.8.5-fundagent-patched.vsix`

Patched build of the [Agent Maestro](https://github.com/Joouis/agent-maestro)
VS Code extension (v2.8.5) with two upstream-bound fixes applied:

1. **`src/server/utils/gemini.ts`** — pair `functionResponse` parts without
   explicit `id` via a per-name FIFO queue. Without this, multi-turn tool
   calls through `langchain-google-genai` 4.x fail with
   `"the number of function response parts is equal to the number of
   function call parts of the function call turn"`.

2. **`src/server/utils/openaiChat.ts`** — wrap system/developer message text
   blocks in `LanguageModelTextPart`. Without this, any OpenAI client that
   sends an array-shaped system message (deepagents, langchain-openai, etc.)
   fails with `"Unexpected chat message content type llm 2"`.

Both patches are committed on the
[`fix/lm-message-conversion`](https://github.com/Joouis/agent-maestro/compare/main...fix/lm-message-conversion)
branch of our local fork and submitted upstream as a PR. Once merged and a
new release is cut, delete this vsix and install the marketplace version.

### Install

```bash
code --install-extension vendor/agent-maestro-2.8.5-fundagent-patched.vsix --force
```

Then reload VS Code so the extension restarts on `localhost:23333`.
