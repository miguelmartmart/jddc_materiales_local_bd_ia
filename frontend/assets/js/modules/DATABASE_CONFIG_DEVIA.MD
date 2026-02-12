# 🧠 Database Config Module Context (`frontend/assets/js/modules`)

> **Role**: AI Metadata Editor & Analyzer UI
> **Scope**: Metadata Management, AI Table Analysis, JSON Editing

## 📞 Database Config Module (`database_config.js`)

**Namespace**: `DatabaseConfigModule`

### 🏗️ Architecture
*   **Editor**: Uses a simple `<textarea>` (in future `monaco-editor`) for JSON manipulation.
*   **Workflow**: Load Tables -> Select Table -> Analyze with AI -> Review Preview -> Append to JSON -> Save.

### ⚡ Core Functions

| Function | Async | Description |
| :--- | :--- | :--- |
| `analyze_table()` | ✅ | Calls `POST /database/analyze/{table}`. Blocks UI, shows "⏳ Analizando...". |
| `appendAnalysis()` | ❌ | Merges the AI-generated JSON snippet into the main metadata JSON. |
| `saveMetadata()` | ✅ | Validates JSON syntax and sends it to `POST /database/metadata`. |

### 🔌 API Communication

**1. Analyze Table**
`POST /database/analyze/{table_name}`
*   **Input**: DB params.
*   **Output**: JSON snippet with `description`, `columns` (with types), `consultas_comunes`.

**2. Metadata Operations**
*   `GET /database/metadata`: Load current `db_metadata_optimized.json`.
*   `POST /database/metadata`: file overwrite (Dangerous operation, requires valid JSON).

### 🚨 Critical UI Flows
*   **AI Analysis**: The AI returns a suggested JSON. The user *MUST* verify it before clicking "Append". The system does *not* auto-save the analysis; it requires manual confirmation via the "Append" and "Save" buttons.
