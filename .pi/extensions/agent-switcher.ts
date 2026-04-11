/**
 * Agent Switcher Extension
 *
 * Carrega dinamicamente todas as skills de .agents/agents/ e permite alternar
 * entre elas via Alt+A ou /agent. O ciclo nunca inclui "sem agente".
 *
 * Agentes somente-leitura (sem bash, write/edit bloqueados):
 *   - agent-ask
 *   - agent-plan
 *
 * Agentes de auditoria (bash liberado, write/edit bloqueados):
 *   - agent-quality
 *
 * Todos os demais agentes têm acesso completo (read, bash, edit, write).
 *
 * Por padrão, o agente "agent-build" é ativado ao iniciar.
 *
 * Atalhos:
 *   Alt+A  → cicla entre todos os agentes carregados
 *   /agent → mostra seletor visual
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type {
  ExtensionAPI,
  ExtensionContext,
} from "@mariozechner/pi-coding-agent";
import { DynamicBorder } from "@mariozechner/pi-coding-agent";
import {
  Container,
  Key,
  type SelectItem,
  SelectList,
  Text,
} from "@mariozechner/pi-tui";

// ─── agentes somente-leitura ──────────────────────────────────────────────────

/** Nomes de skill (nome do diretório) que operam em modo somente-leitura (sem bash). */
const READ_ONLY_AGENTS = new Set(["ask"]);

/**
 * Agentes de planejamento: podem usar write/edit APENAS em `.pi/plans/`.
 * Bash restrito a comandos de leitura.
 */
const PLAN_AGENTS = new Set(["plan"]);

/**
 * Agentes de auditoria: têm bash para rodar linters/testes,
 * mas não podem modificar arquivos (write/edit bloqueados).
 */
const AUDIT_AGENTS = new Set(["quality", "qa"]);

/** Ferramentas liberadas para agentes somente-leitura (sem bash). */
const READ_ONLY_TOOLS = ["read", "grep", "find", "ls"];

/** Ferramentas liberadas para agentes de planejamento (write/edit apenas em .pi/plans/). */
const PLAN_TOOLS = ["read", "bash", "write", "edit"];

/** Ferramentas liberadas para agentes de auditoria (bash sim, write/edit não). */
const AUDIT_TOOLS = ["read", "bash", "grep", "find", "ls"];

/** Ferramentas liberadas para agentes com acesso completo. */
const FULL_TOOLS = ["read", "bash", "edit", "write"];

/** Agente padrão ao iniciar (nome do diretório). */
const DEFAULT_AGENT = "build";

/** Cores do status bar, rotacionadas por índice de agente. */
const COLOR_TOKENS = [
  "success",
  "warning",
  "accent",
  "borderAccent",
  "mdCode",
  "mdHeading",
  "mdLink",
  "syntaxKeyword",
  "syntaxFunction",
  "syntaxString",
  "syntaxNumber",
  "syntaxType",
] as const;

// ─── comandos bash permitidos em agentes somente-leitura ────────────────────

const SAFE_BASH_PREFIXES = [
  "ls",
  "find",
  "grep",
  "cat",
  "head",
  "tail",
  "wc",
  "diff",
  "echo",
  "pwd",
  "git log",
  "git diff",
  "git status",
  "git show",
  "git blame",
  "git branch",
  "git remote",
  "git stash list",
  "python3 -c",
  "python -c",
  "jq",
  "sort",
  "uniq",
  "awk",
  "sed -n", // sed somente para leitura (flag -n sem output de arquivo)
  "tr",
  "cut",
  "xargs",
];

/**
 * Verifica se um comando bash é seguro para agentes somente-leitura.
 */
function isSafeBashCommand(command: string): boolean {
  const trimmed = command.trim().replace(/^(sudo\s+)/, "");
  return SAFE_BASH_PREFIXES.some((prefix) => trimmed.startsWith(prefix));
}

// ─── skill: tipos e carregamento ─────────────────────────────────────────────

const MAX_SKILL_CHARS = 8_000;

interface Skill {
  /** Nome do diretório (ex: "agent-ask") */
  dirName: string;
  /** Nome legível do frontmatter ou fallback para dirName */
  label: string;
  /** Descrição curta do frontmatter */
  description: string;
  /** Conteúdo do SKILL.md (truncado se necessário) */
  content: string;
  /** Token de cor baseado no índice */
  colorToken: string;
  /** Somente-leitura? */
  readOnly: boolean;
}

function parseSkillFrontmatter(raw: string): {
  name?: string;
  description?: string;
} {
  const match = raw.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return {};
  const block = match[1]!;
  const nameMatch = block.match(/^name:\s*(.+)$/m);
  const descMatch = block.match(/^description:\s*["']?([^"'\n]+)["']?\s*$/m);
  return {
    name: nameMatch?.[1]?.trim(),
    description: descMatch?.[1]?.trim(),
  };
}

function loadAllSkills(cwd: string): Skill[] {
  const skillsDir = join(cwd, ".agents", "agents");
  if (!existsSync(skillsDir)) return [];

  const skills: Skill[] = [];

  try {
    const entries = readdirSync(skillsDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const skillFile = join(skillsDir, entry.name, "SKILL.md");
      if (!existsSync(skillFile)) continue;
      try {
        const raw = readFileSync(skillFile, "utf-8");
        const { name, description } = parseSkillFrontmatter(raw);
        const content =
          raw.length > MAX_SKILL_CHARS
            ? raw.slice(0, MAX_SKILL_CHARS) + "\n\n[... conteúdo truncado ...]"
            : raw;
        skills.push({
          dirName: entry.name,
          label: name ?? entry.name,
          description: description ?? "(sem descrição)",
          content,
          colorToken: "", // atribuído após sort
          readOnly: READ_ONLY_AGENTS.has(entry.name),
        });
      } catch (err) {
        console.error(`agent-switcher: falha ao ler ${skillFile}: ${err}`);
      }
    }
  } catch (err) {
    console.error(`agent-switcher: falha ao listar ${skillsDir}: ${err}`);
  }

  skills.sort((a, b) => a.dirName.localeCompare(b.dirName));
  skills.forEach((s, i) => {
    s.colorToken = COLOR_TOKENS[i % COLOR_TOKENS.length]!;
  });

  return skills;
}

// ─── extensão principal ───────────────────────────────────────────────────────

export default function agentSwitcherExtension(pi: ExtensionAPI): void {
  let skills: Skill[] = [];
  // Agente ativo — sempre um da lista (nunca undefined)
  let activeSkill: Skill | undefined;

  // ── helpers visuais ──────────────────────────────────────────────────────

  function updateStatus(ctx: ExtensionContext): void {
    if (!activeSkill) return;
    const icon = activeSkill.readOnly
      ? "▶"
      : AUDIT_AGENTS.has(activeSkill.dirName)
        ? "▶"
        : "▶";
    ctx.ui.setStatus(
      "agent-switcher",
      ctx.ui.theme.fg(activeSkill.colorToken, `${icon} ${activeSkill.label}`),
    );
  }

  // ── aplicação do agente ──────────────────────────────────────────────────

  function activateAgent(skill: Skill, ctx: ExtensionContext): void {
    activeSkill = skill;
    const tools = skill.readOnly
      ? READ_ONLY_TOOLS
      : PLAN_AGENTS.has(skill.dirName)
        ? PLAN_TOOLS
        : AUDIT_AGENTS.has(skill.dirName)
          ? AUDIT_TOOLS
          : FULL_TOOLS;
    pi.setActiveTools(tools);
    updateStatus(ctx);
    const mode = skill.readOnly
      ? "somente-leitura"
      : PLAN_AGENTS.has(skill.dirName)
        ? "planejamento (escrita apenas em .pi/plans/)"
        : AUDIT_AGENTS.has(skill.dirName)
          ? "auditoria (bash, sem escrita)"
          : "acesso completo";
    ctx.ui.notify(`Agente: ${skill.label} (${mode})`, "info");
  }

  // ── ciclo alt+A ──────────────────────────────────────────────────────────

  function cycleAgent(ctx: ExtensionContext): void {
    if (skills.length === 0) return;
    const currentIndex = activeSkill
      ? skills.findIndex((s) => s.dirName === activeSkill!.dirName)
      : -1;
    const nextIndex = (currentIndex + 1) % skills.length;
    activateAgent(skills[nextIndex]!, ctx);
  }

  // ── seletor visual /agent ────────────────────────────────────────────────

  async function showAgentSelector(ctx: ExtensionContext): Promise<void> {
    if (skills.length === 0) {
      ctx.ui.notify("Nenhuma skill encontrada em .agents/agents/", "warning");
      return;
    }

    const items: SelectItem[] = skills.map((s) => ({
      value: s.dirName,
      label:
        (s.dirName === activeSkill?.dirName ? `${s.label} (ativo)` : s.label) +
        (s.readOnly ? " 👁" : PLAN_AGENTS.has(s.dirName) ? " 📋" : AUDIT_AGENTS.has(s.dirName) ? " 🔍" : ""),
      description: s.description,
    }));

    const result = await ctx.ui.custom<string | null>(
      (tui, theme, _kb, done) => {
        const container = new Container();

        container.addChild(
          new DynamicBorder((s: string) => theme.fg("accent", s)),
        );
        container.addChild(
          new Text(theme.fg("accent", theme.bold(" Selecionar Agente"))),
        );

        const selectList = new SelectList(items, Math.min(items.length, 10), {
          selectedPrefix: (t) => theme.fg("accent", t),
          selectedText: (t) => theme.fg("accent", t),
          description: (t) => theme.fg("muted", t),
          scrollInfo: (t) => theme.fg("dim", t),
          noMatch: (t) => theme.fg("warning", t),
        });

        selectList.onSelect = (item) => done(item.value);
        selectList.onCancel = () => done(null);

        container.addChild(selectList);
        container.addChild(
          new Text(
            theme.fg(
              "dim",
              " ↑↓ navegar  •  enter selecionar  •  esc cancelar  •  👁 = somente-leitura  •  📋 = planejamento",
            ),
          ),
        );
        container.addChild(
          new DynamicBorder((s: string) => theme.fg("accent", s)),
        );

        return {
          render: (width: number) => container.render(width),
          invalidate: () => container.invalidate(),
          handleInput: (data: string) => {
            selectList.handleInput(data);
            tui.requestRender();
          },
        };
      },
    );

    if (result === null) return;
    const chosen = skills.find((s) => s.dirName === result);
    if (chosen) activateAgent(chosen, ctx);
  }

  // ── atalho e comando ─────────────────────────────────────────────────────

  pi.registerShortcut(Key.alt("a"), {
    description: "Alternar agente (ask ↔ build)",
    handler: async (ctx) => cycleAgent(ctx),
  });

  pi.registerCommand("agent", {
    description: "Selecionar agente ativo (ask | build)",
    handler: async (_args, ctx) => showAgentSelector(ctx),
  });

  // ── restrições para agentes somente-leitura ───────────────────────────────

  pi.on("tool_call", async (event, ctx) => {
    if (!activeSkill) return;

    const agentLabel = activeSkill.label;
    const isReadOnly = activeSkill.readOnly;
    const isAudit = AUDIT_AGENTS.has(activeSkill.dirName);
    const isPlan = PLAN_AGENTS.has(activeSkill.dirName);

    // Agente de planejamento: write/edit só em .pi/plans/
    if (isPlan && (event.toolName === "write" || event.toolName === "edit")) {
      const filePath = (event.input as { path?: string }).path ?? "";
      const normalized = filePath.replace(/\\/g, "/");
      if (
        normalized.startsWith(".pi/plans/") ||
        normalized.includes("/.pi/plans/")
      ) {
        return; // escrita autorizada para arquivos de plano
      }
      ctx.ui.notify(
        `[${agentLabel}] Escrita bloqueada fora de .pi/plans/. Troque para o agente build (Alt+A) para modificar código.`,
        "warning",
      );
      return {
        block: true,
        reason: `Agente ${agentLabel}: escrita permitida apenas em .pi/plans/. Caminho rejeitado: ${filePath}`,
      };
    }

    // Agentes somente-leitura e de auditoria: bloqueia write e edit
    if (isReadOnly || isAudit) {
      if (event.toolName === "write" || event.toolName === "edit") {
        // Agentes de auditoria podem salvar relatórios em .pi/audit/
        if (isAudit && event.toolName === "write") {
          const filePath = (event.input as { path?: string }).path ?? "";
          const normalized = filePath.replace(/\\/g, "/");
          if (
            normalized.startsWith(".pi/audit/") ||
            normalized.includes("/.pi/audit/")
          ) {
            return; // escrita autorizada para relatório de auditoria
          }
        }
        ctx.ui.notify(
          `[${agentLabel}] Escrita bloqueada. Troque para o agente build (Alt+A) para modificar arquivos.`,
          "warning",
        );
        return {
          block: true,
          reason: `Agente ${agentLabel}: ferramenta "${event.toolName}" bloqueada. Use o agente build para modificações.`,
        };
      }
    }

    // Agentes somente-leitura e de planejamento filtram comandos bash
    if ((isReadOnly || isPlan) && event.toolName === "bash") {
      const cmd = (event.input as { command: string }).command;
      if (!isSafeBashCommand(cmd)) {
        ctx.ui.notify(
          `[${agentLabel}] Comando bash bloqueado: "${cmd.slice(0, 60)}". Apenas leitura é permitida.`,
          "warning",
        );
        return {
          block: true,
          reason: `Agente ${agentLabel}: comando bash não permitido (modifica ou executa side-effects). Use o agente build.`,
        };
      }
    }
  });

  // ── injeção no system prompt ─────────────────────────────────────────────

  /**
   * Gera um prefácio declarativo de modo para ser injetado antes do conteúdo da skill.
   * Isso garante que o modelo saiba qual modo está ativo mesmo quando o histórico
   * da conversa contém instruções de agentes anteriores (ex: quality → build).
   */
  function buildModePreamble(skill: Skill): string {
    if (skill.readOnly) {
      return (
        `> **[MODO SOMENTE-LEITURA ATIVO — ${skill.label}]** ` +
        `Este agente usa APENAS \`read\` e comandos bash seguros de leitura. ` +
        `Quaisquer permissões de \`edit\`, \`write\` ou bash irrestrito de instruções anteriores estão **REVOGADAS**.\n\n`
      );
    }
    if (PLAN_AGENTS.has(skill.dirName)) {
      return (
        `> **[MODO PLANEJAMENTO ATIVO — ${skill.label}]** ` +
        `Este agente usa \`read\`, bash seguro de leitura, e **DEVE** usar \`write\`/\`edit\` para gravar planos em \`.pi/plans/\`. ` +
        `Escrita em qualquer caminho fora de \`.pi/plans/\` está **BLOQUEADA**. ` +
        `Quaisquer permissões de escrita em código-fonte de instruções anteriores estão **REVOGADAS**.\n\n`
      );
    }
    if (AUDIT_AGENTS.has(skill.dirName)) {
      return (
        `> **[MODO AUDITORIA ATIVO — ${skill.label}]** ` +
        `Este agente usa \`read\` e \`bash\`, e pode usar \`write\` APENAS para salvar relatórios em \`.pi/audit/\`. ` +
        `Quaisquer permissões de escrita em código-fonte de instruções anteriores estão **REVOGADAS**.\n\n`
      );
    }
    return (
      `> **[MODO DE ESCRITA COMPLETO ATIVO — ${skill.label}]** ` +
      `Este agente tem permissão total para usar \`read\`, \`bash\`, \`edit\` e \`write\`. ` +
      `Quaisquer restrições de escrita de instruções anteriores estão **REVOGADAS**.\n\n`
    );
  }

  pi.on("before_agent_start", async (event) => {
    if (!activeSkill?.content) return;
    const preamble = buildModePreamble(activeSkill);
    return {
      systemPrompt: `${event.systemPrompt}\n\n${preamble}${activeSkill.content}`,
    };
  });

  // ── ciclo de vida da sessão ──────────────────────────────────────────────

  pi.on("session_start", async (_event, ctx) => {
    skills = loadAllSkills(ctx.cwd);

    if (skills.length === 0) {
      ctx.ui.notify(
        "agent-switcher: nenhuma skill encontrada em .agents/agents/",
        "warning",
      );
      return;
    }

    // Restaura agente ativo da sessão anterior
    const entries = ctx.sessionManager.getEntries();
    const lastState = entries
      .filter(
        (e: { type: string; customType?: string }) =>
          e.type === "custom" && e.customType === "agent-switcher-state",
      )
      .pop() as { data?: { dirName: string } } | undefined;

    const restoredDirName = lastState?.data?.dirName;
    activeSkill =
      (restoredDirName
        ? skills.find((s) => s.dirName === restoredDirName)
        : undefined) ??
      skills.find((s) => s.dirName === DEFAULT_AGENT) ??
      skills[0]!;

    // Aplica ferramentas sem notificar (restore silencioso)
    const tools = activeSkill.readOnly
      ? READ_ONLY_TOOLS
      : PLAN_AGENTS.has(activeSkill.dirName)
        ? PLAN_TOOLS
        : AUDIT_AGENTS.has(activeSkill.dirName)
          ? AUDIT_TOOLS
          : FULL_TOOLS;
    pi.setActiveTools(tools);
    updateStatus(ctx);
  });

  // Persiste estado a cada turn para que session restore funcione
  pi.on("turn_start", async () => {
    if (activeSkill) {
      pi.appendEntry("agent-switcher-state", { dirName: activeSkill.dirName });
    }
  });
}
