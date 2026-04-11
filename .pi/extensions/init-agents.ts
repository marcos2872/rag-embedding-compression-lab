/**
 * Init Agents Extension (v2 — LLM-driven)
 *
 * O comando /init spawna um sub-agente pi com ferramentas de leitura + escrita.
 * O LLM descobre a stack, módulos, arquitetura e convenções do projeto por conta
 * própria e escreve o AGENTS.md diretamente.
 *
 * Feedback visual:
 *   - setWidget  → log de passos acima do editor (tool calls em tempo real)
 *   - setStatus  → spinner animado no rodapé
 *
 * Uso:
 *   /init  →  confirma, spawna sub-agente, exibe progresso, notifica resultado
 */

import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Container, Text } from "@mariozechner/pi-tui";
import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

// ─── system prompt do sub-agente ─────────────────────────────────────────────

const INIT_SYSTEM_PROMPT = `
# Papel

Você é um especialista em análise de projetos de software.
Sua única tarefa: analisar o projeto no diretório de trabalho atual e gerar
um arquivo AGENTS.md completo e preciso usando a ferramenta write.

## Passos de descoberta (execute nesta ordem)

1. **ls .** — liste a raiz para identificar manifesto principal e estrutura geral
2. **Leia o README.md** (se existir) — extraia nome, descrição e propósito do projeto
3. **Leia o manifesto principal** — pyproject.toml, package.json, go.mod, Cargo.toml ou pom.xml
4. **Liste src/** (ou equivalente) — mapeie todos os módulos e subpastas presentes
5. **Leia .env.example** (se existir) — extraia todas as variáveis de ambiente por grupo
6. **Verifique tests/** — confirme se existe e entenda o padrão de testes usado
7. **Leia o Makefile** (se existir) — extraia targets úteis como comandos
8. **Leia 2-3 arquivos de src/** — entenda a arquitetura pelo código real
   - Prefira __init__.py, main.py, app.py, index.ts, main.ts
   - Observe os imports para inferir camadas e dependências entre módulos

## Template do AGENTS.md

Gere o arquivo com EXATAMENTE esta estrutura.
Preencha cada campo com o que encontrar — não invente nada.

---

\`\`\`markdown
# AGENTS.md

> Arquivo gerado por \`/init\` com análise automática. Edite manualmente para ajustar convenções.

## Projeto

- **Nome:** {nome real do projeto}
- **Descrição:** {descrição de 1-2 linhas extraída do README ou manifesto}

## Stack

- **Linguagem(s):** {linguagem e versão — ex: Python 3.12, TypeScript 5}
- **Frameworks:** {apenas os que estiverem explicitamente nas dependências — omita a linha se nenhum}

## Gerenciamento de Dependências

- **Instalar tudo:** \`{comando exato}\`
- **Adicionar pacote:** \`{comando exato}\`
- **Remover pacote:** \`{comando exato}\`

## Comandos Essenciais

{Inclua apenas comandos que existam de fato no manifesto, Makefile ou scripts}
- **Testes:** \`{comando}\`
- **Cobertura:** \`{comando}\`
- **Lint:** \`{comando}\`
- **Formato:** \`{comando}\`
- **Dev server:** \`{comando}\`
- **Build:** \`{comando}\`

## Estrutura de Diretórios

- **Código principal:** \`{src/ ou equivalente}\`
- **Testes:** \`{tests/ ou equivalente — marque "(não encontrado)" se ausente}\`

## Módulos

{Para cada subpasta ou módulo relevante encontrado em src/, uma linha:}
- **\`src/nome_modulo/\`** — {o que o módulo faz em 1 linha, baseado no código lido}

## Arquitetura

- **Estilo:** {ex: Pipeline modular, Hexagonal, MVC, Flat, Monorepo, CLI}
- **Descrição:** {1-2 linhas descrevendo como os módulos se relacionam}

## Variáveis de Ambiente

{Inclua esta seção APENAS se .env.example existir}
> Copie \`.env.example\` para \`.env\` e ajuste os valores.

{grupos de variáveis encontrados — ex:}
- **{Grupo}:** \`VAR_1\`, \`VAR_2\`, \`VAR_3\`

## Testes

- **Framework:** {pytest / jest / vitest / go test / etc}
- **Diretório:** \`{tests/}\` {adicione "⚠️ não encontrado" se o diretório não existir}
- **Executar todos:** \`{comando}\`
- **Com cobertura:** \`{comando}\`

## Convenções de Código

- **Tamanho máximo de função:** 40 linhas
- **Tamanho máximo de arquivo:** 300 linhas
- **Aninhamento máximo:** 3 níveis
- **Docstrings / comentários:** Português brasileiro
- **Identificadores (variáveis, funções, classes):** Inglês
{adicione notas específicas da linguagem detectada — ex para Python:}
- Python: \`X | None\`, \`list[str]\` — nunca \`Optional\`/\`Union\` de \`typing\`
- Pydantic v2: \`.model_dump()\`, \`field_validator\`, \`model_json_schema()\`

## Commits

Este projeto segue o padrão **Conventional Commits**.
Antes de commitar, carregue a skill de commit:

\`\`\`
/skill:git-commit-push
\`\`\`

Ou siga diretamente as regras em \`.agents/skills/git-commit-push/SKILL.md\`.

## Agentes e Skills

| Agente    | Função                                         | Modo                   |
|-----------|------------------------------------------------|------------------------|
| \`build\`   | Implementa funcionalidades e corrige bugs      | escrita completa       |
| \`ask\`     | Responde perguntas somente-leitura             | somente-leitura        |
| \`plan\`    | Cria planos detalhados em \`.pi/plans/\`         | escrita em .pi/plans/  |
| \`quality\` | Auditoria de qualidade de código               | bash + leitura         |
| \`qa\`      | Análise de bugs e edge cases                   | bash + leitura         |
| \`test\`    | Cria e mantém testes automatizados             | escrita em tests/      |
| \`doc\`     | Cria documentação técnica em \`docs/\`           | escrita em docs/       |
\`\`\`

---

## Regras absolutas

- **NUNCA invente comandos** — use somente o que encontrar nos arquivos lidos
- Se um campo não puder ser determinado com certeza, escreva \`(preencher manualmente)\`
- Omita linhas/seções inteiras se a informação simplesmente não existir no projeto
- Use a ferramenta **write** para criar/sobrescrever o AGENTS.md no diretório atual
- Após escrever, confirme com uma linha: "✅ AGENTS.md gerado."
`.trim();

// ─── tipos ────────────────────────────────────────────────────────────────────

interface Step {
  icon: string;
  label: string;
  detail: string;
}

// ─── helpers ──────────────────────────────────────────────────────────────────

function getPiInvocation(args: string[]): { command: string; args: string[] } {
  const currentScript = process.argv[1];
  if (currentScript && fs.existsSync(currentScript)) {
    return { command: process.execPath, args: [currentScript, ...args] };
  }
  const execName = path.basename(process.execPath).toLowerCase();
  if (!/^(node|bun)(\.exe)?$/.test(execName)) {
    return { command: process.execPath, args };
  }
  return { command: "pi", args };
}

function writePromptToTemp(content: string): { dir: string; filePath: string } {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pi-init-"));
  const filePath = path.join(dir, "system-prompt.md");
  fs.writeFileSync(filePath, content, { encoding: "utf-8", mode: 0o600 });
  return { dir, filePath };
}

function cleanupTemp(dir: string): void {
  try { fs.rmSync(dir, { recursive: true, force: true }); } catch { /* ignora */ }
}

/** Retorna o caminho relativo ao cwd, ou só o basename se muito longo. */
function shortPath(filePath: string, cwd: string): string {
  if (!filePath) return "";
  try {
    const rel = path.relative(cwd, filePath);
    return rel.startsWith("..") ? path.basename(filePath) : rel;
  } catch {
    return path.basename(filePath);
  }
}

/** Extrai informações de display de um evento tool_execution_start. */
function parseStep(
  toolName: string,
  args: Record<string, unknown>,
  cwd: string,
): Step {
  const p = (args["file_path"] ?? args["path"] ?? "") as string;
  const short = shortPath(p, cwd);

  switch (toolName) {
    case "read":  return { icon: "📄", label: "lendo",     detail: short };
    case "ls":    return { icon: "📁", label: "listando",  detail: short || "." };
    case "grep":  return { icon: "🔍", label: "buscando",  detail: short };
    case "find":  return { icon: "🔎", label: "procurando",detail: short };
    case "write": return { icon: "✍️ ", label: "escrevendo",detail: short };
    default:      return { icon: "→ ", label: toolName,    detail: short };
  }
}

// ─── extensão principal ───────────────────────────────────────────────────────

const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
const MAX_VISIBLE_STEPS = 8;
const WIDGET_ID = "pi-init";
const STATUS_ID = "pi-init";

export default function (pi: ExtensionAPI) {
  pi.registerCommand("init", {
    description:
      "Usa LLM para analisar o projeto e criar/atualizar o AGENTS.md automaticamente",

    handler: async (_args, ctx) => {
      const agentsPath = path.join(ctx.cwd, "AGENTS.md");
      const exists = fs.existsSync(agentsPath);
      const action = exists ? "Atualizar" : "Criar";

      // ── 1. Confirmação ────────────────────────────────────────────────────
      const ok = await ctx.ui.confirm(
        `${action} AGENTS.md via análise automática`,
        `Um sub-agente irá analisar o projeto usando ferramentas de leitura\n` +
        `e escreverá o AGENTS.md com base no que encontrar.\n\n` +
        (exists ? `⚠️  O AGENTS.md atual será sobrescrito.\n\n` : "") +
        `Deseja continuar?`,
      );
      if (!ok) {
        ctx.ui.notify("Operação cancelada.", "info");
        return;
      }

      // ── 2. System prompt em arquivo temporário ────────────────────────────
      const { dir: tmpDir, filePath: promptPath } = writePromptToTemp(INIT_SYSTEM_PROMPT);

      // ── 3. Estado do feedback visual ──────────────────────────────────────
      const steps: Step[] = [];
      let spinnerFrame = 0;
      let spinnerTimer: ReturnType<typeof setInterval> | null = null;

      const updateWidget = () => {
        if (!ctx.hasUI) return;
        ctx.ui.setWidget(WIDGET_ID, (_tui, theme) => {
          const box = new Container();

          box.addChild(new Text(
            theme.fg("accent", "⚙  /init") +
            theme.fg("muted", "  descobrindo projeto…"),
            0, 0,
          ));
          box.addChild(new Text(theme.fg("muted", "─".repeat(42)), 0, 0));

          const skipped = steps.length - MAX_VISIBLE_STEPS;
          if (skipped > 0) {
            box.addChild(new Text(
              theme.fg("dim", `   ↑ +${skipped} passo${skipped > 1 ? "s" : ""} anteriores`),
              0, 0,
            ));
          }

          for (const step of steps.slice(-MAX_VISIBLE_STEPS)) {
            box.addChild(new Text(
              `  ${step.icon} ` +
              theme.fg("default", step.label) +
              (step.detail ? theme.fg("dim", `  ${step.detail}`) : ""),
              0, 0,
            ));
          }

          if (steps.length === 0) {
            box.addChild(new Text(theme.fg("dim", "  aguardando primeiro passo…"), 0, 0));
          }

          return box;
        });
      };

      const startSpinner = () => {
        if (!ctx.hasUI) return;
        updateWidget();
        spinnerTimer = setInterval(() => {
          spinnerFrame = (spinnerFrame + 1) % SPINNER_FRAMES.length;
          ctx.ui.setStatus(
            STATUS_ID,
            ctx.ui.theme.fg("accent", SPINNER_FRAMES[spinnerFrame]!) +
            ctx.ui.theme.fg("dim", "  /init — analisando projeto…"),
          );
        }, 80);
      };

      const stopFeedback = () => {
        if (spinnerTimer) { clearInterval(spinnerTimer); spinnerTimer = null; }
        if (!ctx.hasUI) return;
        ctx.ui.setStatus(STATUS_ID, undefined);
        ctx.ui.setWidget(WIDGET_ID, undefined);
      };

      startSpinner();

      // ── 4. Spawn do sub-agente ────────────────────────────────────────────
      const spawnArgs = [
        "--mode", "json",
        "--no-session",
        "--tools", "read,grep,find,ls,write",
        "--append-system-prompt", promptPath,
        "Analise o projeto e gere o AGENTS.md seguindo as instruções do sistema.",
      ];

      const invocation = getPiInvocation(spawnArgs);
      const proc = spawn(invocation.command, invocation.args, {
        cwd: ctx.cwd,
        shell: false,
        stdio: ["ignore", "pipe", "pipe"],
      });

      // ── 5. Streaming de progresso ─────────────────────────────────────────
      let stdoutBuffer = "";
      let stderrOutput = "";

      proc.stdout.on("data", (data: Buffer) => {
        stdoutBuffer += data.toString();
        const lines = stdoutBuffer.split("\n");
        stdoutBuffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line) as Record<string, unknown>;
            if (event["type"] === "tool_execution_start") {
              const toolName = event["toolName"] as string;
              const args = (event["args"] ?? {}) as Record<string, unknown>;
              steps.push(parseStep(toolName, args, ctx.cwd));
              updateWidget();
            }
          } catch { /* linha não-JSON — ignora */ }
        }
      });

      proc.stderr.on("data", (data: Buffer) => {
        stderrOutput += data.toString();
      });

      // ── 6. Finalização ────────────────────────────────────────────────────
      const exitCode = await new Promise<number>((resolve) => {
        proc.on("close", (code) => resolve(code ?? 0));
        proc.on("error", () => resolve(1));
      });

      stopFeedback();
      cleanupTemp(tmpDir);

      if (exitCode === 0 && fs.existsSync(agentsPath)) {
        ctx.ui.notify(
          `✅ AGENTS.md ${exists ? "atualizado" : "gerado"} — ${agentsPath}`,
          "success",
        );
      } else {
        const hint = stderrOutput.trim()
          ? `\n\nDetalhe: ${stderrOutput.slice(0, 200)}`
          : "";
        ctx.ui.notify(
          `❌ Falha ao gerar AGENTS.md (exit ${exitCode}).${hint}`,
          "error",
        );
      }
    },
  });
}
