---
name: doc-backend
description: Guide for documenting backend systems — stack-agnostic, with examples for FastAPI and Express. Covers endpoint tables, data-flow diagrams via Excalidraw, and when to write ADRs. Database models and ER diagrams are handled by the doc-db skill. Instructions are in English; all generated documentation must be written in Brazilian Portuguese.
---

# Backend Documentation — Reference Guide

## When to Activate This Skill

Produce or update backend documentation when:

- A new endpoint is added or an existing one changes signature / behavior
- A new database model or migration is created
- A new external service or third-party API is integrated
- Authentication or authorization rules change
- A new background job, queue, or scheduled task is introduced
- Error handling strategy changes globally

---

## Artifact 1: Endpoint Table

Every public API surface must have a corresponding endpoint table in `docs/api.md` or inline in a module README.

### Template

```markdown
## Endpoints — <Módulo ou Recurso>

| Método | Caminho | Autenticação | Corpo da Requisição | Resposta de Sucesso | Erros Comuns |
|---|---|---|---|---|---|
| `GET` | `/recursos` | Token JWT | — | `200` lista paginada de `Recurso` | `401`, `403` |
| `POST` | `/recursos` | Token JWT | `CriarRecursoSchema` | `201` `Recurso` criado | `400`, `422` |
| `GET` | `/recursos/{id}` | Token JWT | — | `200` `Recurso` | `404` |
| `PATCH` | `/recursos/{id}` | Token JWT + dono | `AtualizarRecursoSchema` | `200` `Recurso` atualizado | `400`, `403`, `404` |
| `DELETE` | `/recursos/{id}` | Token JWT + admin | — | `204` sem corpo | `403`, `404` |
```

### Naming Conventions

- Paths use **plural nouns in kebab-case**: `/usuarios`, `/session-tokens`
- No verbs in paths: `/usuarios/{id}/desativar` not `/desativar-usuario`
- Nested resources only when the child cannot exist without the parent: `/projetos/{id}/tarefas`
- Version prefix when breaking changes are expected: `/v1/recursos`

### FastAPI Example (docstring format)

```python
@router.post("/recursos", response_model=RecursoSchema, status_code=201)
async def criar_recurso(
    payload: CriarRecursoSchema,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> RecursoSchema:
    """Cria um novo recurso para o usuário autenticado.

    Args:
        payload: Dados do recurso a ser criado.

    Returns:
        O recurso criado com seu ID gerado.

    Raises:
        HTTPException 400: Se os dados forem inválidos semanticamente.
        HTTPException 403: Se o usuário não tiver permissão.
    """
```

### Express Example (JSDoc format)

```js
/**
 * POST /recursos
 * Cria um novo recurso para o usuário autenticado.
 *
 * @param {Object} req.body - { nome: string, descricao: string }
 * @returns {201} { id, nome, descricao, criadoEm }
 * @throws {400} Dados inválidos
 * @throws {401} Não autenticado
 */
router.post('/recursos', authenticate, async (req, res) => { … });
```

---

## Artifact 2: Data Flow Diagram (via Excalidraw)

Use this for documenting request/response flows, async jobs, and webhook chains.  
Always use the `excalidraw` skill to generate `.excalidraw` files.

### Swimlane Layout Convention

Organize horizontally by actor (left → right). Standard actors:

```
Cliente / Browser | API Gateway | Serviço | Banco de Dados | Serviço Externo
```

### Color Palette for Flow Diagrams

```python
CLIENT_BG      = "#dbeafe"   # blue-100   — cliente/browser
CLIENT_STROKE  = "#1d4ed8"   # blue-700

SERVICE_BG     = "#dcfce7"   # green-100  — serviços internos
SERVICE_STROKE = "#15803d"   # green-700

DB_BG          = "#fef9c3"   # yellow-100 — banco de dados
DB_STROKE      = "#a16207"   # yellow-700

EXTERNAL_BG    = "#f1f5f9"   # slate-100  — serviços externos
EXTERNAL_STROKE= "#475569"   # slate-600

DECISION_BG    = "#ede9fe"   # violet-100 — decisão / condicional
DECISION_STROKE= "#6d28d9"   # violet-700

ERROR_BG       = "#fee2e2"   # red-100    — caminho de erro
ERROR_STROKE   = "#b91c1c"   # red-700

ARROW_COLOR    = "#374151"   # gray-700
```

### What to Show in Each Flow Diagram

- **Happy path** in the main lane — always include
- **Error paths** branching down or to a separate lane — use `ERROR_*` colors
- **Auth checks** as diamond decision shapes
- **Async steps** (queues, jobs) as dashed arrows
- Protocol label on every arrow: `HTTPS/REST`, `SQL`, `AMQP`, `WebSocket`
- Sequence numbers on arrows when order matters: `1.`, `2.`, `3.`

---

## Artifact 3: ADRs for Backend Decisions

Create an ADR (see skill **`doc-architecture`** for the MADR template) when deciding:

| Trigger | Example ADR title |
|---|---|
| ORM / query builder choice | `0004 — Uso de SQLModel sobre SQLAlchemy puro` |
| Auth strategy | `0005 — Autenticação via JWT com refresh token rotativo` |
| Error handling pattern | `0006 — Erros de negócio retornam 422 com código de erro estruturado` |
| Caching strategy | `0007 — Cache de sessões no Redis com TTL de 1 hora` |
| Async vs sync handlers | `0008 — Handlers FastAPI assíncronos por padrão` |
| Pagination strategy | `0009 — Paginação cursor-based para listagens grandes` |

---

## Review Checklist

Before closing a backend task, confirm:

- [ ] Todo endpoint novo tem entrada na tabela de endpoints de `docs/api.md`
- [ ] Toda migration tem docstring explicando contexto e rollback
- [ ] Mudanças de autenticação/autorização têm diagrama de fluxo atualizado
- [ ] Breaking changes em endpoints públicos têm ADR
- [ ] Erros HTTP retornam corpo de erro com mensagem descritiva (conforme convenção do framework)
- [ ] Campos sensíveis (tokens, senhas) nunca aparecem em logs ou respostas

---

## Cross-References

- Geração de diagramas de fluxo: ver skill **`excalidraw`**
- Modelos de banco e diagramas ER: ver skill **`doc-db`**
- ADRs e C4: ver skill **`doc-architecture`**
- Documentação de componentes UI: ver skill **`doc-frontend`**
