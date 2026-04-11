import { join } from "node:path";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

/**
 * Registra os caminhos canônicos de agentes e skills do diretório .agents/
 * para que o pi os descubra nativamente via resources_discover.
 *
 * Agentes (Alt+A, /agent): .agents/agents/
 * Skills de suporte (/skill:nome): .agents/skills/
 */
export default function (pi: ExtensionAPI) {
  pi.on("resources_discover", (event) => {
    return {
      skillPaths: [
        join(event.cwd, ".agents", "agents"),
        join(event.cwd, ".agents", "skills"),
      ],
    };
  });
}
