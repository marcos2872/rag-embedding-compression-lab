/**
 * Extensão RTK para pi
 *
 * Integra o RTK (Rust Token Killer) ao pi para reduzir o consumo de tokens
 * em 60-90% nos comandos bash, grep, find e ls.
 *
 * O `read` nativo do pi é preservado intencionalmente — o RTK trunca
 * arquivos grandes de forma opaca, o que prejudica a qualidade do agente.
 *
 * Pré-requisito: rtk instalado e disponível no PATH.
 *   brew install rtk
 *   curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh | sh
 *
 * Se não estiver instalado, uma notificação é exibida ao iniciar a sessão.
 * Após instalar, execute /rtk-reload para ativar sem reiniciar o pi.
 */

import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { isToolCallEventType } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { execSync, spawnSync } from "node:child_process";

// Cache da verificação — resetado a cada reload do módulo (jiti re-executa o arquivo)
let rtkAvailable: boolean | null = null;

// Rastreamento in-memory dos rewrites desta sessão
interface RewriteEntry {
  original: string;
  rewritten: string;
  timestamp: number;
}

// Snapshot das estatísticas globais no início da sessão
// Subtraído do valor atual para calcular a economia da sessão
interface GainSummary {
  total_commands: number;
  total_saved: number;
  total_input: number;
  avg_savings_pct: number;
}

const sessionStart = Date.now();
const sessionRewrites: RewriteEntry[] = [];
let sessionSnapshot: GainSummary | null = null;

function getGainSummary(): GainSummary | null {
  const result = spawnSync("rtk", ["gain", "--all", "--format", "json"], {
    encoding: "utf-8",
  });
  try {
    return JSON.parse(result.stdout ?? "").summary as GainSummary;
  } catch {
    return null;
  }
}

function checkRtk(): boolean {
  if (rtkAvailable !== null) return rtkAvailable;
  try {
    execSync("which rtk", { stdio: "ignore" });
    rtkAvailable = true;
  } catch {
    rtkAvailable = false;
  }
  return rtkAvailable;
}

function rtkExec(args: string[], cwd: string): string {
  return execSync(["rtk", ...args].join(" "), {
    encoding: "utf-8",
    timeout: 10_000,
    cwd,
  }).trim();
}

export default function (pi: ExtensionAPI) {
  // Sempre registrado — precisa estar disponível antes do rtk ser instalado
  pi.registerCommand("rtk-reload", {
    description: "Re-verifica se rtk está instalado e recarrega o pi",
    handler: async (_args, ctx) => {
      rtkAvailable = null; // limpa cache para re-verificar
      if (!checkRtk()) {
        ctx.ui.notify(
          "rtk ainda não encontrado no PATH.\n" +
            "Instale com:\n" +
            "  brew install rtk\n" +
            "  curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh | sh\n" +
            "\nDepois execute /rtk-reload novamente.",
          "warning",
        );
        return;
      }
      ctx.ui.notify("rtk encontrado! Recarregando...", "success");
      await ctx.reload();
    },
  });

  // Notificação ao iniciar sessão
  pi.on("session_start", async (_event, ctx) => {
    if (!checkRtk()) {
      ctx.ui.notify(
        "⚠️  RTK não instalado — saída de comandos não será comprimida.\n" +
          "Instale em: https://github.com/rtk-ai/rtk#installation\n" +
          "  brew install rtk\n" +
          "  curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh | sh\n" +
          "\nApós instalar, execute /rtk-reload para ativar.",
        "warning",
      );
      return;
    }
    ctx.ui.notify("RTK ativo — bash, grep, find, ls comprimidos (-80% tokens)", "info");
    // Snapshot inicial para calcular economia da sessão
    sessionSnapshot = getGainSummary();
  });

  // Guard: ferramentas e hooks abaixo só ativos quando rtk disponível
  if (!checkRtk()) return;

  // ── Hook bash: reescreve comandos via `rtk rewrite` antes da execução ────

  pi.on("tool_call", async (event, _ctx) => {
    if (!isToolCallEventType("bash", event)) return;

    const command = event.input.command;
    if (typeof command !== "string") return;

    // spawnSync evita exceção em exit codes não-zero.
    // rtk rewrite sai com código 3 quando encontra reescrita (v0.35+),
    // e com código 1 quando não há equivalente RTK.
    const result = spawnSync("rtk", ["rewrite", command], {
      encoding: "utf-8",
      timeout: 2_000,
    });

    if (result.error) return; // rtk não encontrado ou timeout

    const rewritten = result.stdout?.trim();
    if (rewritten && rewritten !== command) {
      event.input.command = rewritten;
      sessionRewrites.push({ original: command, rewritten, timestamp: Date.now() });
    }
  });

  // ── Comando /rtk-logs: economia da sessão atual ───────────────────────────

  pi.registerCommand("rtk-logs", {
    description: "Mostra economia de tokens RTK na sessão atual",
    handler: async (_args, ctx) => {
      const duracaoMin = Math.round((Date.now() - sessionStart) / 60_000);
      const count = sessionRewrites.length;

      // Calcula economia da sessão via delta snapshot
      const current = getGainSummary();
      let sessionLine = "";
      let globalLine = "";

      if (current && sessionSnapshot) {
        const saved = current.total_saved - sessionSnapshot.total_saved;
        const cmds = current.total_commands - sessionSnapshot.total_commands;
        const input = current.total_input - sessionSnapshot.total_input;
        const pct = input > 0 ? ((saved / input) * 100).toFixed(1) : "0.0";
        sessionLine =
          saved > 0
            ? `💰 ${saved} tokens salvos · ${pct}% economia · ${cmds} cmd RTK`
            : `Nenhuma economia registrada ainda`;
        globalLine =
          `Global — ${current.total_commands} cmd · ` +
          `${current.total_saved} tokens salvos · ` +
          `${current.avg_savings_pct.toFixed(1)}% média`;
      } else {
        sessionLine = "Snapshot indisponível — reinicie o pi para habilitar";
        globalLine = "Estatísticas globais indisponíveis";
      }

      // Cabeçalho da sessão
      const header = `Sessão (${duracaoMin}min) — ${count} rewrite${count !== 1 ? "s" : ""}`;

      // Lista de rewrites com horário
      const rewriteLines = sessionRewrites.map((r, i) => {
        const hora = new Date(r.timestamp).toLocaleTimeString("pt-BR", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
        return `  ${String(i + 1).padStart(2)}. [${hora}] ${r.original}\n        → ${r.rewritten}`;
      });

      const msg = [
        `RTK Token Savings`,
        `${"-".repeat(42)}`,
        header,
        sessionLine,
        ...(rewriteLines.length > 0 ? ["", ...rewriteLines] : []),
        "",
        `${"-".repeat(42)}`,
        globalLine,
      ].join("\n");

      ctx.ui.notify(msg, "info");
    },
  });

  // ── Override grep ─────────────────────────────────────────────────────────

  pi.registerTool({
    name: "grep",
    label: "grep (rtk)",
    description:
      "Search file contents for a pattern. Returns grouped, token-optimized results (~80% fewer tokens).",
    parameters: Type.Object({
      pattern: Type.String({ description: "Search pattern (regex)" }),
      path: Type.Optional(
        Type.String({ description: "Directory or file to search" }),
      ),
      glob: Type.Optional(
        Type.String({ description: "File glob filter (e.g. '*.ts')" }),
      ),
      ignoreCase: Type.Optional(
        Type.Boolean({ description: "Case-insensitive search" }),
      ),
      context: Type.Optional(
        Type.Number({ description: "Lines of context around matches" }),
      ),
    }),
    async execute(_id, params, _signal, _update, ctx) {
      const args = ["grep", params.pattern, params.path ?? "."];
      if (params.glob) args.push("--glob", params.glob);
      if (params.ignoreCase) args.push("--ignore-case");
      if (params.context) args.push("--context", String(params.context));

      try {
        const text = rtkExec(args, ctx.cwd);
        return { content: [{ type: "text", text }], details: {} };
      } catch (e: any) {
        return {
          content: [{ type: "text", text: e.message }],
          isError: true,
          details: {},
        };
      }
    },
  });

  // ── Override find ─────────────────────────────────────────────────────────

  pi.registerTool({
    name: "find",
    label: "find (rtk)",
    description:
      "Search for files by glob pattern. Returns compact, token-optimized results (~80% fewer tokens).",
    parameters: Type.Object({
      pattern: Type.String({
        description: "Glob pattern to match files (e.g. '*.ts')",
      }),
      path: Type.Optional(
        Type.String({ description: "Directory to search in" }),
      ),
    }),
    async execute(_id, params, _signal, _update, ctx) {
      const args = ["find", params.pattern, params.path ?? "."];
      try {
        const text = rtkExec(args, ctx.cwd);
        return { content: [{ type: "text", text }], details: {} };
      } catch (e: any) {
        return {
          content: [{ type: "text", text: e.message }],
          isError: true,
          details: {},
        };
      }
    },
  });

  // ── Override ls ───────────────────────────────────────────────────────────

  pi.registerTool({
    name: "ls",
    label: "ls (rtk)",
    description:
      "List directory contents. Returns compact, token-optimized tree (~80% fewer tokens).",
    parameters: Type.Object({
      path: Type.Optional(Type.String({ description: "Directory to list" })),
    }),
    async execute(_id, params, _signal, _update, ctx) {
      const args = ["ls", params.path ?? "."];
      try {
        const text = rtkExec(args, ctx.cwd);
        return { content: [{ type: "text", text }], details: {} };
      } catch (e: any) {
        return {
          content: [{ type: "text", text: e.message }],
          isError: true,
          details: {},
        };
      }
    },
  });
}
