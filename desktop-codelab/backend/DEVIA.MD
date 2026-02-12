# AI Code Lab - Project Context

## Project Overview
Desktop application integrating AI Assistant (FastAPI) with Code Editor (Monaco) and File Explorer (Electron).
**Goal**: Assist users in building software step-by-step via interactive chat and code execution.

## Directory Structure
* `desktop-codelab/` (Root)
  * `src/` (Frontend: React + Vite + Tailwind)
    * `App.tsx`: Core UI (Chat, File Tree, Terminal, State).
    * `api.ts`: Backend API Client.
    * `index.css`: Global styles (Tailwind v4).
  * `electron/` (Desktop Shell)
    * `main.ts`: Main process, IPC handlers (File System, Shell execution).
    * `preload.ts`: Secure bridge (`window.electronAPI`).
  * `backend/` (AI Logic)
    * `server.py`: FastAPI server (Port 8002), AI model orchestration.
  * `dist/`: Production build artifacts.

## Technical Constraints & Rules
* **OS**: Windows (PowerShell).
* **Stack**: React 19, Electron, Python FastAPI.
* **Code Generation**:
  * **MUST** include file path in first line comment: `// folder/file.ext`.
  * **MUST** use `powershell` for terminal commands.
  * **MUST** use `Start-Process -FilePath` (not `-Path`).
* **Process**: Strict 4-phase approach (Setup -> Structure -> Code -> Execution).

## AI Behavior Rules (Strict)
* **Format**: 
  1. **ESTADO**: Paso [X] de [Total].
  2. **EXPLICACIÓN**: [Máximo 2 frases]. Qué se hace y por qué.
  3. **ACCIÓN**: [CÓDIGO/COMANDO] (SIEMPRE AL FINAL).
* **Rules**:
  * **MINIGAMES**: Must create `learnwebapp/public/js/math-game.js` (or similar) with REAL logic if requested.
  * **PATHS**: Always use `learnwebapp/public/` as base for web apps to avoid security blocks.
  * **NO FLUFF**: No greetings, no "Claro que sí", no redundant text.
* **Flow**: One step at a time. Code block always comes LAST.
* **Context**: Always verify previous step success (via auto-fed logs) before moving on.

## Key Files for Context
* `App.tsx`: Handles `handleRunCommand` (execution), `handleSaveFile` (file writing), and Chat UI.
* `server.py`: Defines System Prompt and AI behavior.
* `electron/main.ts`: Executes actual filesystem/shell operations via IPC.

## Usage
* **Startup**: 
  * Run `start_codelab.bat` from the root project folder (Recommended - shows backend logs).
  * OR Run `desktop-codelab/start.bat` (Backend runs in background).
* **Save File**: AI provides code block -> User clicks "Save" -> App saves to path in comment relative to open folder.
* **Run Command**: AI provides command -> User clicks "Run" -> App executes in PowerShell.
