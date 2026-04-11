---
name: doc-frontend
description: Guide for documenting frontend systems — generic with examples for React + Vite, Next.js. Covers component tables, route tables, global state tables, component tree and user-flow diagrams via Excalidraw, and when to write ADRs. Instructions are in English; all generated documentation must be written in Brazilian Portuguese.
---

# Frontend Documentation — Reference Guide

## When to Activate This Skill

Produce or update frontend documentation when:

- A new page or route is added
- A new reusable component is created
- Global state shape changes (new context key, new store slice)
- A new API integration is wired to the frontend
- Authentication or protected route logic changes
- A significant UX flow is added or redesigned

---

## Artifact 1: Component Table

Every reusable component must have an entry in `docs/components.md` or inline in the component file.

### Template

```markdown
## Componente: `<NomeDoComponente>`

**Arquivo:** `src/components/NomeDoComponente.tsx`  
**Descrição:** Descrição curta do propósito do componente.

### Props

| Prop | Tipo | Obrigatório | Padrão | Descrição |
|---|---|---|---|---|
| `titulo` | `string` | Sim | — | Texto exibido no cabeçalho |
| `itens` | `Item[]` | Sim | — | Lista de itens a renderizar |
| `onSelecionar` | `(item: Item) => void` | Não | `undefined` | Callback ao selecionar um item |
| `carregando` | `boolean` | Não | `false` | Exibe skeleton quando true |
| `className` | `string` | Não | `""` | Classes CSS adicionais |

### Estado interno

| Estado | Tipo | Valor inicial | Descrição |
|---|---|---|---|
| `aberto` | `boolean` | `false` | Controla visibilidade do dropdown |
| `busca` | `string` | `""` | Texto de filtro local |

### Eventos emitidos / Callbacks

| Evento | Assinatura | Quando dispara |
|---|---|---|
| `onSelecionar` | `(item: Item) => void` | Usuário clica em um item da lista |
| `onFechar` | `() => void` | Usuário pressiona Esc ou clica fora |

### Dependências

| Dependência | Tipo | Motivo |
|---|---|---|
| `useAuth` | Hook | Verifica se usuário está autenticado |
| `AppContext` | Context | Lê lista global de itens |
| `api/itens.ts` | Função de API | Busca itens do servidor |
```

### Naming Conventions

- Components: `PascalCase` — `UserCard`, `TemplateList`
- Custom hooks: `use` prefix — `useAuth`, `useChat`, `useDebounce`
- API functions: verb + noun — `fetchTemplates`, `createSession`, `deleteUser`
- Event handlers (props): `on` prefix — `onSubmit`, `onClose`, `onChange`
- Boolean props: `is`/`has`/`can` prefix — `isLoading`, `hasError`, `canEdit`

### React Component Docblock Example

```tsx
/**
 * Exibe a lista de templates disponíveis com suporte a busca e filtragem.
 *
 * @example
 * <ListaTemplates onSelecionar={(t) => setTemplate(t)} carregando={false} />
 */
export function ListaTemplates({ onSelecionar, carregando = false }: ListaTemplatesProps) {
```

### Next.js Page Component Example

```tsx
/**
 * Página de configurações do usuário.
 * Rota: /configuracoes
 * Autenticação: obrigatória — redireciona para /login se não autenticado.
 */
export default function ConfiguracoesPage() {
```

---

## Artifact 2: Route Table

Document all routes in `docs/routes.md` or in the router configuration file.

### Template

```markdown
## Rotas da Aplicação

| Caminho | Componente / Página | Autenticação | Parâmetros | Descrição |
|---|---|---|---|---|
| `/` | `HomePage` | Não | — | Página inicial pública |
| `/login` | `LoginPage` | Não (redireciona se autenticado) | `?redirect=` | Formulário de login |
| `/dashboard` | `DashboardPage` | Obrigatória | — | Painel principal do usuário |
| `/projetos/:id` | `ProjetoDetalhe` | Obrigatória | `id: string` | Detalhes de um projeto |
| `/projetos/:id/editar` | `EditarProjeto` | Obrigatória + dono | `id: string` | Edição do projeto |
| `/admin` | `AdminPage` | Obrigatória + admin | — | Painel administrativo |

### Rotas de API (proxy / BFF)

| Caminho | Destino | Descrição |
|---|---|---|
| `/api/*` | `<URL do backend>` | Proxy para o backend (conforme configuração do projeto) |
```

### React Router Example

```tsx
// Comentário obrigatório em cada rota protegida:
// Rota protegida: requer autenticação. Ver: ProtectedRoute.tsx
<Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
```

### Next.js App Router Example

```
app/
├── page.tsx              # / — pública
├── login/
│   └── page.tsx          # /login — redireciona se autenticado
├── dashboard/
│   └── page.tsx          # /dashboard — protegida
└── projetos/
    └── [id]/
        ├── page.tsx      # /projetos/:id — protegida
        └── editar/
            └── page.tsx  # /projetos/:id/editar — protegida + dono
```

---

## Artifact 3: Global State Table

Document every piece of shared state in `docs/state.md` or inline in the context/store file.

### Template (Context API)

```markdown
## Estado Global — `AppContext`

**Arquivo:** `src/context/AppContext.tsx`

| Chave | Tipo | Valor inicial | Quem atualiza | Quem consome | Descrição |
|---|---|---|---|---|---|
| `usuario` | `User \| null` | `null` | `useAuth` (login/logout) | Header, rotas protegidas | Usuário autenticado |
| `tema` | `"claro" \| "escuro"` | `"claro"` | `ConfiguracoesPage` | toda a árvore via CSS var | Tema da UI |
| `notificacoes` | `Notificacao[]` | `[]` | `useNotificacoes` | `NotificacaoBar` | Fila de toasts |

### Ações disponíveis

| Ação | Assinatura | Descrição |
|---|---|---|
| `setUsuario` | `(u: User \| null) => void` | Atualiza usuário após login/logout |
| `adicionarNotificacao` | `(n: Notificacao) => void` | Empilha uma nova notificação |
| `removerNotificacao` | `(id: string) => void` | Remove notificação por ID |
```

### Template (Zustand / Redux)

```markdown
## Store: `projetoStore`

**Arquivo:** `src/stores/projetoStore.ts`

| Slice | Tipo | Descrição |
|---|---|---|
| `projetos` | `Projeto[]` | Lista de projetos carregados |
| `projetoAtivo` | `Projeto \| null` | Projeto em edição |
| `status` | `"idle" \| "carregando" \| "erro"` | Estado de carregamento |

### Thunks / Actions assíncronas

| Ação | Descrição |
|---|---|
| `carregarProjetos()` | Busca lista do servidor e popula `projetos` |
| `salvarProjeto(p)` | POST/PATCH no servidor e atualiza `projetos` |
| `deletarProjeto(id)` | DELETE no servidor e remove de `projetos` |
```

---

## Artifact 4: Component Tree Diagram (via Excalidraw)

Use to show how components nest and communicate. Store at `docs/diagrams/componentes-<pagina>.excalidraw`.  
Always use the `excalidraw` skill to generate `.excalidraw` files.

### Color Palette for Component Trees

```python
PAGE_BG        = "#dbeafe"   # blue-100   — páginas / rotas
PAGE_STROKE    = "#1d4ed8"   # blue-700

LAYOUT_BG      = "#dcfce7"   # green-100  — layouts e wrappers
LAYOUT_STROKE  = "#15803d"   # green-700

COMPONENT_BG   = "#f1f5f9"   # slate-100  — componentes regulares
COMPONENT_STROKE = "#475569" # slate-600

HOOK_BG        = "#ede9fe"   # violet-100 — custom hooks
HOOK_STROKE    = "#6d28d9"   # violet-700

CONTEXT_BG     = "#fef9c3"   # yellow-100 — context providers
CONTEXT_STROKE = "#a16207"   # yellow-700

ARROW_PROPS    = "#374151"   # gray-700   — seta = props drilling
ARROW_CONTEXT  = "#a16207"   # yellow-700 — seta pontilhada = context
```

### Layout Conventions

- Root at the top; children below
- Horizontal siblings at the same Y level
- Props drilling: solid arrow with label `props: nomeDaProp`
- Context consumption: dashed arrow from Provider to consumer with label `context`
- Hook usage: dashed arrow from component to hook box (violet) with label `uses`
- Keep diagrams to one page per route/feature — don't try to map the entire app in one diagram

---

## Artifact 5: User Flow Diagram (via Excalidraw)

Use to map a specific user journey through the UI. Store at `docs/diagrams/fluxo-<jornada>.excalidraw`.

### User Flow Element Conventions

```python
SCREEN_BG      = "#dbeafe"   # blue-100   — tela / página
SCREEN_STROKE  = "#1d4ed8"   # blue-700

ACTION_BG      = "#dcfce7"   # green-100  — ação do usuário
ACTION_STROKE  = "#15803d"   # green-700

DECISION_BG    = "#ede9fe"   # violet-100 — decisão / condicional
DECISION_STROKE= "#6d28d9"   # violet-700 — use diamond shape

ERROR_BG       = "#fee2e2"   # red-100    — estado de erro
ERROR_STROKE   = "#b91c1c"   # red-700

LOADING_BG     = "#fef9c3"   # yellow-100 — estado de carregamento
LOADING_STROKE = "#a16207"   # yellow-700

SUCCESS_BG     = "#dcfce7"   # green-100
SUCCESS_STROKE = "#15803d"   # green-700
```

### What Every User Flow Must Show

- **Ponto de entrada** (onde o usuário começa): círculo preenchido
- **Happy path**: caminho principal, sem desvios
- **Estados de loading**: caixas amarelas entre ação e resultado
- **Estados de erro**: caixas vermelhas com mensagem de erro exibida
- **Ponto de saída / sucesso**: círculo preenchido com borda dupla
- Setas nomeadas com o gatilho: `"clica em Salvar"`, `"token expira"`, `"erro 422"`

---

## Artifact 6: ADRs for Frontend Decisions

Create an ADR (see skill **`doc-architecture`** for the MADR template) when deciding:

| Trigger | Exemplo de título |
|---|---|
| State management choice | `0010 — Uso de Context API em vez de Zustand para estado global` |
| Routing library | `0011 — React Router v6 como solução de roteamento` |
| SSR vs SPA | `0012 — SPA pura com Vite em vez de Next.js` |
| CSS strategy | `0013 — Tailwind v4 como sistema de estilos` |
| Form library | `0014 — React Hook Form para formulários complexos` |
| Data fetching | `0015 — Fetch nativo + AbortController em vez de React Query` |
| SSE strategy | `0016 — SSE via fetch + ReadableStream em vez de EventSource` |

---

## Review Checklist

Before closing a frontend task, confirm:

- [ ] Todo componente novo tem entrada na tabela de componentes
- [ ] Toda rota nova tem entrada na tabela de rotas
- [ ] Toda nova chave de estado global está documentada
- [ ] Props de componentes públicos estão tipadas com TypeScript (sem `any`)
- [ ] Hooks com efeitos colaterais têm função de cleanup no `useEffect`
- [ ] Funções de API ficam na camada de API dedicada (conforme estrutura declarada no AGENTS.md) — nenhum `fetch` direto em componentes
- [ ] Rotas protegidas têm componente de guarda explícito
- [ ] Textos exibidos ao usuário estão no idioma configurado no projeto

---

## Cross-References

- Geração de diagramas: ver skill **`excalidraw`**
- ADRs e C4: ver skill **`doc-architecture`**
- Documentação de endpoints consumidos: ver skill **`doc-backend`**
