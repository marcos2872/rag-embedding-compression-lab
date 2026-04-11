import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.registerProvider("openrouter", {
    baseUrl: "https://openrouter.ai/api/v1",
    apiKey:
      "!grep -m1 '^OPENROUTER_API_KEY=' $(git rev-parse --show-toplevel)/.env | cut -d= -f2-",
    api: "openai-completions",
    models: [
      {
        id: "qwen/qwen3.6-plus:free",
        name: "Qwen 3.6-plus (Free) via OpenRouter",
        reasoning: true,
        input: ["text"],
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 40960,
        maxTokens: 16384,
        compat: {
          supportsDeveloperRole: false,
          supportsReasoningEffort: false,
        },
      },
    ],
  });
}
