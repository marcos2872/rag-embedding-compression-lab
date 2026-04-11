---
name: doc-db
description: Guide for creating and updating database ER diagrams via Excalidraw — three detail levels (conceptual, logical, physical), color palette by table type, and element ID conventions for safe incremental updates. Instructions are in English; all generated documentation must be written in Brazilian Portuguese.
---

# Database ER Diagrams — Reference Guide

## When to Activate This Skill

Create or update a database ER diagram when:

- A new ORM model or schema class is added
- A migration adds, removes, or renames columns or tables
- A foreign key relationship changes
- A new developer joins and needs to understand the schema
- A performance review requires understanding indexes and relationships
- A new domain module is added (new set of related tables)

Always use this skill together with the `excalidraw` skill for the generation workflow.

---

## Three Detail Levels

Choose the level that fits the audience:

| Nível | Nome | Mostra | Quando usar |
|---|---|---|---|
| 1 | **Conceitual** | Entidades e nomes de relacionamento (sem colunas, sem tipos) | Stakeholders não-técnicos, visão geral de domínio |
| 2 | **Lógico** ← padrão | Tabelas, colunas, PK/FK, cardinalidades | Desenvolvedores, revisão de schema |
| 3 | **Físico** | Tipos PostgreSQL reais (`UUID`, `VARCHAR(255)`, `TIMESTAMPTZ`, `JSONB`), constraints, índices | DBA, otimização, migração de banco |

**Default:** always produce Level 2 (lógico) unless the user specifies otherwise.

---

## Color Palette

```python
# Tabela primária — entidade central do domínio
TABLE_PRIMARY_BG     = "#dcfce7"   # green-100
TABLE_PRIMARY_STROKE = "#15803d"   # green-700

# Tabela de lookup / enum / referência
TABLE_LOOKUP_BG      = "#fef9c3"   # yellow-100
TABLE_LOOKUP_STROKE  = "#a16207"   # yellow-700

# Tabela de junção (N:N)
TABLE_JUNCTION_BG    = "#ede9fe"   # violet-100
TABLE_JUNCTION_STROKE= "#6d28d9"   # violet-700

# View ou tabela materializada
TABLE_VIEW_BG        = "#dbeafe"   # blue-100
TABLE_VIEW_STROKE    = "#1d4ed8"   # blue-700

# Tabela de domínio externo (referenciada mas não pertence ao domínio atual)
TABLE_EXTERNAL_BG    = "#f1f5f9"   # slate-100
TABLE_EXTERNAL_STROKE= "#475569"   # slate-600

# Setas FK
ARROW_COLOR          = "#374151"   # gray-700

# Legenda / anotação
NOTE_BG              = "#fafafa"
NOTE_STROKE          = "#d1d5db"
```

---

## Element Conventions

### Table element

Each table = one `rectangle` with `roundness: {"type": 3}`.

Internal layout (all as `text` elements positioned inside the rectangle):

```
┌──────────────────────────────┐
│  usuarios                    │  ← header: fontSize 16, fontFamily 2, strokeColor = TABLE_*_STROKE
├──────────────────────────────┤  ← separator: addLine horizontal
│ 🔑 id              INTEGER   │  ← PK: prefix 🔑
│ → projeto_id       INTEGER   │  ← FK: prefix →
│ ⚡ email            VARCHAR   │  ← indexed (não-PK): prefix ⚡
│    nome            VARCHAR   │  ← campo regular: sem prefixo, 2 spaces indent
│    criado_em       TIMESTAMPTZ│
└──────────────────────────────┘
```

- **`fontFamily: 2`** (Helvetica) em todos os textos
- Header: `fontSize: 16`, bold via capitalização / separação visual
- Colunas: `fontSize: 12`
- Para Level 1 (conceitual): retângulo com apenas o nome da tabela, sem colunas

### Relationship arrows

Cada FK = um elemento `type: "arrow"` com:

```json
{
  "type": "arrow",
  "startBinding": {"elementId": "table-origem", "focus": 0, "gap": 2},
  "endBinding":   {"elementId": "table-destino", "focus": 0, "gap": 2},
  "startArrowhead": null,
  "endArrowhead": "arrow"
}
```

Cardinalidades como elemento `type: "text"` flutuante posicionado no meio da seta:

| Relacionamento | Label do texto |
|---|---|
| FK simples (N:1) | `"N:1"` |
| Opcional (0..1) | `"0..1"` |
| Many-to-many via junção | Duas setas `N:1`: junção → tabela A e junção → tabela B |

### Legend box (obrigatório)

Sempre incluir no canto inferior direito:

```
┌─────────────────────────────┐
│ Legenda                     │
│ ▬ verde    Tabela principal  │
│ ▬ amarelo  Lookup / enum     │
│ ▬ violeta  Junção N:N        │
│ ▬ azul     View              │
│ ▬ slate    Domínio externo   │
└─────────────────────────────┘
```

---

## Element ID Conventions

Use IDs determinísticos para permitir atualização sem duplicatas:

| Elemento | Padrão de ID | Exemplo |
|---|---|---|
| Retângulo da tabela | `table-<nome>` | `table-user` |
| Texto do header | `table-<nome>-header` | `table-user-header` |
| Linha separadora | `table-<nome>-sep` | `table-user-sep` |
| Texto de coluna | `table-<nome>-col-<campo>` | `table-user-col-email` |
| Seta FK | `fk-<origem>-<destino>` | `fk-pedido-usuario` |
| Label da seta | `fk-<origem>-<destino>-lbl` | `fk-pedido-usuario-lbl` |
| Caixa de legenda | `legend` | `legend` |
| Texto da legenda | `legend-<n>` | `legend-0`, `legend-1` |

---

## File Naming Convention

```
docs/diagrams/er-<dominio>.excalidraw
```

Use domain names that reflect the actual tables in the project. Examples:

| Arquivo | Tabelas sugeridas |
|---|---|
| `er-auth.excalidraw` | Entidades de autenticação e usuários |
| `er-<dominio-a>.excalidraw` | Tabelas do domínio A |
| `er-<dominio-b>.excalidraw` | Tabelas do domínio B |
| `er-completo.excalidraw` | Todas as tabelas do projeto |

---

## Generation Workflow

To build the `.excalidraw` JSON for an ER diagram, follow the **`excalidraw`** skill.

Use the element conventions and color palette from this skill (table rectangles, separator lines, column texts, FK arrows, legend box) and the ID conventions below. Build the JSON directly as a data structure and save the file with the `Write` tool — no Python scripts, no lzstring compression.

---

## Review Checklist

Before finishing any ER diagram, confirm:

- [ ] Toda FK tem seta com label de cardinalidade (`N:1`, `1:1`, `0..1`, `N:N`)
- [ ] PKs marcadas com `🔑`
- [ ] Colunas indexadas (não-PK) marcadas com `⚡`
- [ ] FKs marcadas com `→`
- [ ] Legenda de cores presente no canto inferior direito
- [ ] IDs de elementos seguem a convenção (`table-<nome>`, `fk-<a>-<b>`, etc.)
- [ ] Arquivo salvo em `docs/diagrams/er-<dominio>.excalidraw`
- [ ] Diagrama gerado como JSON puro (`.excalidraw`), não formato comprimido

---

## Cross-References

- Workflow de geração Excalidraw: ver skill **`excalidraw`**
- ADRs sobre decisões de schema: ver skill **`doc-architecture`**
