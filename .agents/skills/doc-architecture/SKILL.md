---
name: doc-architecture
description: "Guide for producing architecture documentation artifacts: ADRs (MADR compact format), C4 Model diagrams via Excalidraw, and service inventory tables. Instructions are in English; all generated documentation must be written in Brazilian Portuguese."
---

# Architecture Documentation — Reference Guide

## When to Activate This Skill

Produce or update architecture documentation when:

- A new external system, service, or integration is added
- A significant technology or framework decision is made
- The deployment topology changes (new infra, containers, databases)
- A feature crosses two or more bounded domains
- A team member asks "why was X chosen?"
- Any change that would surprise a new engineer reading the codebase in 6 months

---

## Artifact 1: ADR (Architecture Decision Record)

Use the **MADR compact** format. Store files at `docs/adr/NNNN-titulo-kebab-case.md`.

### Numbering & Status

- Sequential four-digit prefix: `0001`, `0002`, …
- Valid statuses: `proposto`, `aceito`, `depreciado`, `substituído por [NNNN]`
- Status moves forward — never delete an ADR; deprecate or supersede it

### MADR Compact Template

```markdown
# NNNN — Título da Decisão

## Status

aceito

## Contexto

<!-- O problema ou força que motivou a decisão. Inclua restrições relevantes,
     requisitos não-funcionais e o estado atual do sistema. -->

## Decisão

<!-- A escolha feita, descrita de forma afirmativa:
     "Decidimos usar X porque Y." -->

## Consequências

<!-- O que muda após esta decisão — tanto pontos positivos quanto negativos.
     Liste trade-offs explicitamente. -->
```

### ADR Writing Rules

- Write in Brazilian Portuguese
- Be specific: name the exact library version, pattern name, or protocol
- State the **why**, not just the **what**
- If alternatives were considered, list them briefly under **Contexto**
- Link related ADRs: "Ver também: [0003 — Estratégia de autenticação](0003-estrategia-autenticacao.md)"
- Keep each ADR focused on a single decision

### Example

```markdown
# 0001 — Uso de PostgreSQL como banco de dados principal

## Status

aceito

## Contexto

O sistema precisa de suporte a transações ACID, consultas relacionais complexas
e extensibilidade via tipos customizados. SQLite foi descartado por não suportar
concorrência adequada em produção. MongoDB foi descartado por ausência de
suporte nativo a joins e transações multi-documento na versão avaliada.

## Decisão

Adotamos PostgreSQL 16 como banco de dados principal, acessado via SQLModel
(SQLAlchemy) com driver psycopg3. Migrações gerenciadas pelo Alembic.

## Consequências

- (+) Transações ACID, suporte a JSONB, extensões como pgvector disponíveis
- (+) Alembic fornece histórico auditável de schema
- (-) Requer instância dedicada (não embutida); aumenta complexidade do ambiente local
- (-) Equipe precisa conhecer SQL e SQLAlchemy
```

---

## Artifact 2: C4 Model Diagrams (via Excalidraw)

Always use the `excalidraw` skill to generate `.excalidraw` files.  
Store diagrams at `docs/diagrams/` or `Excalidraw/` depending on the project.

### The Four C4 Levels

| Level | Name | Shows | Audience |
|---|---|---|---|
| L1 | Contexto do Sistema | O sistema e seus usuários/sistemas externos | Stakeholders não-técnicos |
| L2 | Container | Processos executáveis, bancos de dados, SPA, APIs | Desenvolvedores e arquitetos |
| L3 | Componente | Módulos internos de um container específico | Desenvolvedores do container |
| L4 | Código | Classes, funções, interfaces | Raramente necessário; gerado por ferramentas |

**Rule:** always produce L1 + L2. Add L3 only when a container is complex enough to warrant it. Skip L4.

### C4 Color Palette for Excalidraw

Use these colors consistently across all C4 diagrams:

```python
# Pessoa / usuário
PERSON_BG     = "#dbeafe"   # blue-100
PERSON_STROKE = "#1d4ed8"   # blue-700

# Sistema em escopo (o que estamos documentando)
SYSTEM_BG     = "#dcfce7"   # green-100
SYSTEM_STROKE = "#15803d"   # green-700

# Sistema externo (fora do nosso controle)
EXTERNAL_BG     = "#f1f5f9"  # slate-100
EXTERNAL_STROKE = "#475569"  # slate-600

# Container (dentro do sistema em escopo)
CONTAINER_BG     = "#ede9fe"  # violet-100
CONTAINER_STROKE = "#6d28d9"  # violet-700

# Banco de dados
DB_BG     = "#fef9c3"   # yellow-100
DB_STROKE = "#a16207"   # yellow-700

# Relações / setas
ARROW_COLOR = "#374151"  # gray-700

# Legenda / anotação
NOTE_BG     = "#fafafa"
NOTE_STROKE = "#d1d5db"
```

### C4 Element Conventions

**Pessoa (L1):**
- Shape: `ellipse` or `rectangle` with rounded corners
- Label format: `Nome\n[Persona]`
- Example: `Usuário Final\n[Navegador web]`

**Sistema/Container (L1, L2):**
- Shape: `rectangle` with `roundness: {"type": 3}`
- Label format (two lines): `Nome do Sistema\n[Tecnologia]`
- Sub-label (description): smaller text element below, `strokeColor: "#6b7280"`

**Sistema externo (L1):**
- Same shape, but use `EXTERNAL_*` colors
- Add `[Sistema Externo]` tag

**Banco de dados (L2):**
- Shape: `ellipse` (top half) + `rectangle` (body) — or use a plain `rectangle` with a cylinder icon as text prefix `🗄`
- Label: `Nome do Banco\n[PostgreSQL 16]`

**Relações (setas):**
- Elemento `type: "arrow"` com `endArrowhead: "arrow"`, `startArrowhead: null`
- `startBinding` e `endBinding` apontando para os elementos de origem e destino
- Label na seta: elemento `type: "text"` flutuante posicionado no meio da seta, descrevendo interação + protocolo (ex.: `"HTTPS/REST"`, `"SQL (psycopg3)"`)
- Não usar `addArrow` nem `addLabelToLine` — essas são APIs do Obsidian, não do JSON puro

**Legenda:**
- Always include a legend box in the bottom-right corner
- List each color used with its meaning

### C4 Generation Workflow

To build the `.excalidraw` JSON for a C4 diagram, follow the **`excalidraw`** skill.

Use the C4 color palette and element conventions from this skill (rectangles for systems/containers, ellipses for persons, arrows with protocol labels, legend box). Build the JSON directly as a data structure and save the file with the `Write` tool — no Python scripts, no lzstring compression.

---

## Artifact 3: Service Inventory Table

Include in a `docs/architecture.md` or `README.md`. Update whenever a service is added or removed.

```markdown
## Inventário de Serviços

| Serviço | Responsabilidade | Tecnologia | Porta | Dependências | Repositório / Pasta |
|---|---|---|---|---|---|
| API Backend | Lógica de negócio e endpoints REST | FastAPI + Python 3.12 | 8000 | PostgreSQL, Redis | `backend/` |
| Frontend Web | Interface do usuário | React 19 + Vite + Tailwind v4 | 5173 | API Backend | `frontend/` |
| Banco de Dados | Persistência relacional | PostgreSQL 16 | 5432 | — | `docker-compose.yml` |
| Cache | Sessões e filas | Redis 7 | 6379 | — | `docker-compose.yml` |
| Renderizador PDF | Conversão PPTX → PDF | Gotenberg (LibreOffice) | 3000 | — | `Dockerfile.gotenberg` |
```

---

## Review Checklist

Before finalizing any architecture artifact, confirm:

- [ ] O diagrama tem título, data e nível C4 identificados
- [ ] Todos os elementos têm legenda de tecnologia (ex.: `[PostgreSQL 16]`)
- [ ] Sistemas externos estão visualmente distintos dos internos (cor diferente)
- [ ] As setas têm protocolo ou mecanismo de comunicação identificado
- [ ] O ADR responde "por que não usamos a alternativa óbvia?"
- [ ] O ADR tem status atualizado
- [ ] A tabela de inventário foi atualizada se um serviço foi adicionado/removido
- [ ] Os arquivos estão em `docs/adr/` e `docs/diagrams/` (ou `Excalidraw/`)

---

## Cross-References

- Geração de diagramas: ver skill **`excalidraw`** para schema de elementos, paleta, workflow de geração direta
- Documentação de endpoints: ver skill **`doc-backend`**
- Documentação de componentes UI: ver skill **`doc-frontend`**
