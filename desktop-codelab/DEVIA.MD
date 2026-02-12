# Directory: desktop-codelab
## Purpose
Root directory for the AI Code Lab desktop application. This application provides a VS Code-like environment for AI-assisted coding, leveraging the existing AI backend of the project.

## Contents
- `backend/`: Python backend bridge server connecting Electron to the main AI core.
- `electron/`: Electron main process source code.
- `src/`: React frontend source code (Renderer process).
- `package.json`: Dependencies and scripts for Electron, React, and Vite.
- `vite.config.ts`: Vite configuration for building the frontend.
- `tsconfig.json`: TypeScript configuration.
- `start.bat`: Windows batch script to launch the application easily.
- `../start_codelab.bat`: Root script that launches both backend (in separate window) and frontend.
- `README.md`: General documentation and setup instructions.
