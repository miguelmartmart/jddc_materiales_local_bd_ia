# Directory: desktop-codelab/src
## Purpose
Contains the source code for the React frontend (Renderer process). This provides the user interface for the code editor and AI chat assistant.

## Contents
- `App.tsx`: Main React component.
  - Renders the layout (Sidebar, Editor, Output).
  - Manages state for code, chat prompts, and AI responses.
  - Integrates `Monaco Editor`.
- `api.ts`: API client module.
  - `getModels()`: Fetches available AI models from the Python backend.
  - `generateCode()`: Sends code and prompts to the backend for AI processing.
- `main.tsx`: Entry point for React rendering.
- `index.css`: Global styles and Tailwind CSS directives.
