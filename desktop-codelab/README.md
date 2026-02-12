# AI Code Lab

A desktop application for AI-assisted code development, built with Electron, React, and reusing the powerful AI core from the InterJDDCIA bot.

## Structure

- `electron/`: Main process code (window management, backend spawning).
- `src/`: Renderer process (React UI, Monaco Editor).
- `backend/`: Python server that bridges the Electron app with the existing AI core (`../backend/core`).

## Setup

1. Ensure you have Node.js installed.
2. Ensure you have Python installed and the dependencies for the main bot are satisfied.
3. Install dependencies:
   ```bash
   npm install
   ```

## Running

### Option 1: From Project Root (Recommended)
If you are in the main `interjddcia` folder, use the global start script:

```bash
start_codelab.bat
```
This will launch the Python backend in a separate window (useful for debugging) and then start the Electron app.

### Option 2: From this directory
You can start the application using the local batch script:

```bash
start.bat
```

Or using npm commands:

```bash
npm run dev
```

This will:
1. Start the Vite dev server for the UI.
2. Compile the Electron main process.
3. Start Electron.
4. Electron will spawn the Python backend (`backend/server.py`) on port 8002.

## Features

- **Model Selection**: Choose from any enabled AI model in your configuration.
- **Code Context**: The current code in the editor is automatically sent as context to the AI.
- **Independent**: Runs as a separate desktop app, but leverages your existing AI configuration and keys.

## Troubleshooting

- If models don't load, check the console for Python errors.
- Ensure the Python environment used by the spawn command has access to the required libraries (`fastapi`, `uvicorn`, etc.).
