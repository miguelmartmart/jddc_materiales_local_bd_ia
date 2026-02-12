# Directory: desktop-codelab/electron
## Purpose
Contains the main process code for the Electron application. This handles window creation, lifecycle management, and spawning the background Python server.

## Contents
- `main.ts`: Entry point for the Electron main process.
  - Creates the main application window.
  - Loads the React frontend (from dev server or built files).
  - Spawns and manages the `backend/server.py` Python process.
  - Handles application lifecycle events (ready, window-all-closed, quit).
