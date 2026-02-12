# 🧠 Metadata Management System (`backend/core/config`)

> **Role**: AI Context Optimization Engine
> **Scope**: Semantic Schema, RAG-lite Indexing, Context Filtering
> **Key File**: `db_metadata_optimized.json`

## 🏗️ Architecture

The system operates as an **independent metadata engine** that decouples the physical database schema from the "semantic" schema presented to the AI.

| Component | File | Functionality |
| :--- | :--- | :--- |
| **Manager** | `metadata_manager.py` | Core logic for indexing and retrieval. Singleton pattern. |
| **Data Source** | `db_metadata_optimized.json` | The "Truth Source". Defines tables, columns, descriptions, and common queries manually optimized for AI understanding. |
| **Facade** | `database_metadata.py` | Backward compatibility layer. |

## 🔍 Indexing & Retrieval Strategy

The system implements a local **Inverted Index** initialized at startup:

1.  **Keyword Extraction**: Splits table/column names and maps synonyms (e.g., `CLI` -> `CLIENTE`).
2.  **Inverted Index Construction**:
    *   `Table Index`: `{ "CLIENTE": {"CLIENTE", "FACTURA"}, "VENTAS": {"DOCCAB", "FACTURA"} }`
    *   `Column Index`: `{ "DOCCAB": { "PRECIO": {"IMPORTETOTAL"} } }`

### `get_focused_schema(user_query)`

Instead of sending the full DB schema (expensive/limited tokens), the system:
1.  Analyzes `user_query` for keywords.
2.  Maps keywords to **Categories** (e.g., "Compresor" -> `Productos`).
3.  Returns a **Subset Schema** containing only tables from relevant categories + Core tables.

## 🛠️ Configuration (`db_metadata_optimized.json`)

To add knowledge to the AI, **DO NOT modify python code**. Edit the JSON:

```json
"TABLENAME": {
    "category": "sales|inventory|crm",
    "record_count": 1000, // Helps AI prioritize tables
    "description": "Natural language description for AI",
    "columns": {
        "COL_NAME": "TYPE - Human readable description"
    },
    "consultas_comunes": [
        "Natural language query example: SQL EXAMPLE"
    ]
}
```

## 🚀 Usage

**Injecting Context into AI Prompts:**

```python
from backend.core.config.metadata_manager import get_metadata_manager

mgr = get_metadata_manager()

# Option A: Full Schema (Limited by max_tables)
full_context = mgr.get_schema_for_ai(max_tables=10)

# Option B: Query-Specific Context (Recommended)
focused_context = mgr.get_focused_schema("cuánto vendimos a clientes de Madrid?")
```
