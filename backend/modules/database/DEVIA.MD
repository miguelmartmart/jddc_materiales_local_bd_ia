# 🧠 Backend Database Module (`backend/modules/database`)

> **Role**: Metadata Generator & Manager
> **Scope**: AI Table Analysis, Metadata IO
> **Key File**: `service.py`

## 🏗️ Architecture

This module acts as the **"Teacher"** for the Metadata System. It uses AI to study the physical database and write the "textbook" (`db_metadata_optimized.json`) that the Chat module studies.

| Component | File | Functionality |
| :--- | :--- | :--- |
| **Analyzer** | `service.py` | `analyze_table()`: Extracts schema + samples -> Prompt -> AI -> JSON. |
| **IO** | `service.py` | Reads/Writes `db_metadata_optimized.json` directly. |
| **Router** | `router.py` | Endpoints for the Config UI. |

## 🤖 AI Analysis Logic (`analyze_table`)

1.  **Introspection**:
    *   Queries `RDB$RELATION_FIELDS` to get all columns.
    *   Queries `SELECT FIRST 3 *` to get data samples.
2.  **Prompt Engineering**:
    *   Constructs a payload with Columns + Samples.
    *   Asks AI to generate a *strict* JSON structure including:
        *   `category`: Auto-classification (e.g., "ventas", "inventario").
        *   `description`: Human readable summary.
        *   `consultas_comunes`: Generates 2-3 SQL examples based on data patterns.
3.  **Model Selection**:
    *   Iterates through preferred models (`gemini-1.5-flash`, `grok-2`, etc.).
    *   **Fallback**: If one fails, auto-switches to next available enabled model.

## ⚠️ Integrity & Safety

*   **Validation**: The AI output is regex-parsed (`re.search(r'\{.*\}')`) to ensure valid JSON.
*   **Human-in-the-loop**: The backend *never* auto-saves AI analysis. It returns the suggestion to the Frontend for user approval.

## 🔄 Relationship with Chat Module
1.  **Database Module** (Writer): Updates `db_metadata_optimized.json`.
2.  **Metadata System** (`core/config`): Indexes the JSON.
3.  **Chat Module** (Reader): Uses the Index to find context.
