# Plano: Extensão RTK para pi

**Data:** 2026-04-11
**Autor:** agente-plan
**Status:** aprovado

---

## Objetivo

Criar `.pi/extensions/rtk.ts` que integra o RTK ao pi com cobertura
total de ferramentas (exceto `read`, mantido nativo por qualidade), e
exibe notificação de instalação com URL quando o binário não está
disponível no PATH, oferecendo recarga via `/rtk-reload`.

---

## Escopo

**Dentro do escopo:**
- Hook `tool_call` no `bash` → reescrita via `rtk rewrite` (LLM chamando bash)
- Override de `grep`, `find`, `ls` → versões RTK comprimidas
- `read` **nativo** (sem override — preserva qualidade)
- Verificação de disponibilidade do binário `rtk` no `session_start`
- Notificação com URL de instalação quando rtk não está instalado
- Comando `/rtk-reload` que re-verifica e chama `ctx.reload()`
- Cache da verificação para não chamar `which rtk` em cada tool call

**Fora do escopo:**
- Override do `read` nativo
- Configuração de nível de compressão (`-l aggressive`, `rtk smart`)
- Analytics de tokens economizados (`rtk gain`)
- Instalação automática do binário

---

## Arquivos Afetados

| Arquivo | Ação | Motivo |
|---|---|---|
| `.pi/extensions/rtk.ts` | criar | única entrega da feature |

---

## Sequência de Execução

### 1. Estrutura base e verificação de disponibilidade

**Arquivo:** `.pi/extensions/rtk.ts`

**O que fazer:**

```typescript
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { isToolCallEventType } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { execSync } from "node:child_process";
import { resolve } from "node:path";

// Cache — resetado a cada reload do módulo
let rtkAvailable: boolean | null = null;

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
```

**Dependências:** nenhuma

---

### 2. Notificação de instalação + comando `/rtk-reload`

**Arquivo:** `.pi/extensions/rtk.ts`

**O que fazer:**

Registrar o comando `/rtk-reload` **antes** do guard de disponibilidade,
para que fique acessível mesmo quando o rtk não está instalado.
No `session_start`, se rtk ausente, exibir notificação informativa.

```typescript
export default function (pi: ExtensionAPI) {

  // Sempre disponível — mesmo sem rtk instalado
  pi.registerCommand("rtk-reload", {
    description: "Re-verifica se rtk está instalado e recarrega o pi",
    handler: async (_args, ctx) => {
      rtkAvailable = null; // limpa cache para re-verificar
      if (!checkRtk()) {
        ctx.ui.notify(
          "rtk ainda não encontrado no PATH.\n" +
          "Instale com: brew install rtk\n" +
          "Ou: curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh | sh\n" +
          "Depois execute /rtk-reload novamente.",
          "warning",
        );
        return;
      }
      ctx.ui.notify("rtk encontrado! Recarregando...", "success");
      await ctx.reload();
    },
  });

  // Notificação no início de sessão
  pi.on("session_start", async (_event, ctx) => {
    if (!checkRtk()) {
      ctx.ui.notify(
        "⚠️  RTK não instalado — saída de comandos não será comprimida.\n" +
        "Instale em: https://github.com/rtk-ai/rtk#installation\n" +
        "  brew install rtk\n" +
        "  curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh | sh\n" +
        "Após instalar, execute /rtk-reload para ativar.",
        "warning",
      );
      return;
    }
    ctx.ui.notify("RTK ativo — bash, grep, find, ls comprimidos", "info");
  });

  // Guard: features abaixo só registradas se rtk disponível
  if (!checkRtk()) return;
```

**Dependências:** passo 1

---

### 3. Hook `tool_call` no `bash`

**Arquivo:** `.pi/extensions/rtk.ts` (dentro do `if (checkRtk())` / após o guard)

**O que fazer:**

Interceptar chamadas do LLM à ferramenta `bash` e reescrever o comando
via `rtk rewrite`. Mutação direta em `event.input.command` — o pi aplica
antes de executar, sem re-validação de schema.

```typescript
  pi.on("tool_call", async (event, _ctx) => {
    if (!isToolCallEventType("bash", event)) return;

    const command = event.input.command;
    if (typeof command !== "string") return;

    try {
      const rewritten = execSync(`rtk rewrite ${JSON.stringify(command)}`, {
        encoding: "utf-8",
        timeout: 2_000,
      }).trim();

      // rtk retorna o mesmo comando se não souber reescrever
      if (rewritten && rewritten !== command) {
        event.input.command = rewritten;
      }
    } catch {
      // Falha silenciosa — executa o comando original
    }
  });
```

**Dependências:** passo 2

---

### 4. Override de `grep`

**Arquivo:** `.pi/extensions/rtk.ts`

**O que fazer:**

Substituir o built-in `grep` pelo equivalente RTK. Parâmetros espelham
o schema nativo do pi para não quebrar chamadas existentes do LLM.

```typescript
  pi.registerTool({
    name: "grep",
    label: "grep (rtk)",
    description:
      "Search file contents for a pattern. Returns grouped, token-optimized results.",
    parameters: Type.Object({
      pattern:    Type.String({ description: "Search pattern (regex)" }),
      path:       Type.Optional(Type.String({ description: "Directory or file to search" })),
      glob:       Type.Optional(Type.String({ description: "File glob filter (e.g. '*.ts')" })),
      ignoreCase: Type.Optional(Type.Boolean({ description: "Case-insensitive search" })),
      context:    Type.Optional(Type.Number({ description: "Lines of context around matches" })),
    }),
    async execute(_id, params, _signal, _update, ctx) {
      const args = ["grep", params.pattern, params.path ?? "."];
      if (params.glob)       args.push("--glob",    params.glob);
      if (params.ignoreCase) args.push("--ignore-case");
      if (params.context)    args.push("--context", String(params.context));

      try {
        const text = rtkExec(args, ctx.cwd);
        return { content: [{ type: "text", text }], details: {} };
      } catch (e: any) {
        return { content: [{ type: "text", text: e.message }], isError: true, details: {} };
      }
    },
  });
```

**Dependências:** passo 2

---

### 5. Override de `find`

**Arquivo:** `.pi/extensions/rtk.ts`

**O que fazer:**

```typescript
  pi.registerTool({
    name: "find",
    label: "find (rtk)",
    description:
      "Search for files by glob pattern. Returns compact, token-optimized results.",
    parameters: Type.Object({
      pattern: Type.String({ description: "Glob pattern to match files (e.g. '*.ts')" }),
      path:    Type.Optional(Type.String({ description: "Directory to search in" })),
    }),
    async execute(_id, params, _signal, _update, ctx) {
      const args = ["find", params.pattern, params.path ?? "."];
      try {
        const text = rtkExec(args, ctx.cwd);
        return { content: [{ type: "text", text }], details: {} };
      } catch (e: any) {
        return { content: [{ type: "text", text: e.message }], isError: true, details: {} };
      }
    },
  });
```

**Dependências:** passo 2

---

### 6. Override de `ls`

**Arquivo:** `.pi/extensions/rtk.ts`

```typescript
  pi.registerTool({
    name: "ls",
    label: "ls (rtk)",
    description: "List directory contents. Returns compact, token-optimized tree.",
    parameters: Type.Object({
      path: Type.Optional(Type.String({ description: "Directory to list" })),
    }),
    async execute(_id, params, _signal, _update, ctx) {
      const args = ["ls", params.path ?? "."];
      try {
        const text = rtkExec(args, ctx.cwd);
        return { content: [{ type: "text", text }], details: {} };
      } catch (e: any) {
        return { content: [{ type: "text", text: e.message }], isError: true, details: {} };
      }
    },
  });

} // fim do export default
```

**Dependências:** passos 3, 4, 5

---

## Cobertura resultante

| Ferramenta | Estratégia | Economia estimada |
|---|---|---|
| `bash` | hook `tool_call` + `rtk rewrite` | 75–92% nos comandos suportados |
| `grep` | override RTK | ~80% |
| `find` | override RTK | ~80% |
| `ls` | override RTK | ~80% |
| `read` | **nativo pi** (preservado) | — |

---

## Decisões de design

| Decisão | Justificativa |
|---|---|
| `read` nativo | RTK trunca arquivos grandes de forma opaca; o built-in do pi preserva conteúdo integral com offset/limit explícito — qualidade do agente é prioridade |
| `/rtk-reload` registrado antes do guard | O comando precisa estar disponível mesmo sem rtk instalado, pois é o mecanismo de ativação pós-instalação |
| Cache `rtkAvailable` | Evita fork de processo `which rtk` a cada tool call; é resetado a cada reload do módulo |
| Falha silenciosa no hook bash | `rtk rewrite` pode não suportar comandos compostos (pipes, heredocs); não bloquear execução caso falhe |
| Sem `rtkExec` no hook bash | Usa `execSync` direto para minimizar overhead no caminho crítico de cada chamada bash |

---

## Riscos e Mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| `rtk rewrite` lento (>2s) | baixa | timeout de 2s + fallback para comando original |
| Schema de `grep`/`find`/`ls` diverge do nativo | baixa | parâmetros espelham o schema dos built-ins documentados |
| `rtk` instalado após PATH diferente do pi | baixa | `/rtk-reload` reseta o cache e re-executa `which rtk` |
| Saída RTK diferente do esperado pelo LLM | baixa | RTK é projetado para outputs semânticos; tee salva saída original em falhas |

---

## Fora do escopo

- Override do `read` (decisão explícita de qualidade)
- Compressão agressiva (`-l aggressive`, `rtk smart`)
- Dashboard de tokens economizados no footer do pi
- Configuração por projeto (nível de compressão, comandos excluídos)

---

## Critérios de Conclusão

- [ ] Arquivo `.pi/extensions/rtk.ts` criado e carregado pelo pi
- [ ] Com rtk instalado: notificação "RTK ativo" ao iniciar sessão
- [ ] Sem rtk instalado: notificação de aviso com URL + instrução `/rtk-reload`
- [ ] `/rtk-reload` após instalar rtk: detecta binário e chama `ctx.reload()`
- [ ] LLM chamando `git status` via `bash` → executa `rtk git status`
- [ ] LLM chamando `grep` → usa ferramenta override RTK
- [ ] LLM chamando `find` → usa ferramenta override RTK
- [ ] LLM chamando `ls` → usa ferramenta override RTK
- [ ] LLM chamando `read` → usa built-in nativo do pi (não interceptado)
