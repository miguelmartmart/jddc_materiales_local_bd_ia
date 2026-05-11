# AI Code Lab

Aplicación de escritorio con asistente IA integrado para desarrollo de software paso a paso.
Construida con **Electron + React + TypeScript** en el frontend y **FastAPI (Python)** en el backend.
Usa exclusivamente el modelo **Qwen3 VL 30B** en la red LAN JDDC — sin internet, sin APIs externas.

## Estructura

```
desktop-codelab/
├── backend/               ← FastAPI en puerto 8002
│   ├── server.py          ← Orquestador: endpoints, retry LAN, _fix_next_action
│   └── prompt_engine/     ← Motor modular de prompts (17 fases)
│       ├── builder.py     ← PromptBuilder: ensambla fases según contexto
│       ├── context.py     ← PhaseContext: datos que comparten todas las fases
│       └── phases/        ← Una clase por fase (p01_header.py … p17_error.py)
├── electron/
│   ├── main.ts            ← Proceso principal: ventana, IPC, arranque de backend
│   └── preload.ts         ← Bridge seguro renderer ↔ main
├── src/
│   ├── App.tsx            ← UI principal (chat, editor Monaco, terminal, árbol)
│   ├── api.ts             ← Cliente HTTP hacia backend
│   ├── components/
│   │   └── TaskManager.tsx ← Tareas/subtareas/chats con drag & drop
│   └── utils/
│       ├── nextActionParser.ts ← Parser robusto de [[NEXT_ACTION]] (3 capas)
│       ├── systemReports.ts    ← Fábrica de mensajes [SYSTEM] para el chat
│       └── ContextManager.ts  ← Memoria persistente en .codelab/
├── DOCS_README/           ← Documentación técnica detallada (7 documentos)
├── DEVIA.MD               ← Referencia completa de arquitectura
└── start_codelab.bat      ← Script de arranque recomendado
```

## Arranque rápido

### Opción A — Script automático (recomendado)
```cmd
cd C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
start_codelab.bat
```

### Opción B — Modo desarrollo (hot-reload)
```cmd
cd desktop-codelab
npm run dev
```

### Opción C — Manual (dos terminales)
```cmd
REM Terminal 1
python backend/server.py

REM Terminal 2
npm run build && npm start
```

## Requisitos

- Node.js 18+
- Python 3.10+
- Red LAN JDDC con acceso a `10.13.79.31` (Qwen3 VL 30B)
- `pip install fastapi uvicorn httpx`

## Diagnóstico rápido

```cmd
REM Backend activo?
curl http://127.0.0.1:8002/health

REM IA LAN responde?
curl http://127.0.0.1:8002/debug/ping-ai

REM Test de generación
curl -X POST http://127.0.0.1:8002/api/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\": \"hola\"}"
```

## Documentación completa

Ver [DEVIA.MD](DEVIA.MD) para arquitectura detallada, endpoints, sistema de fases y guía de resolución de problemas.
Ver [DOCS_README/](DOCS_README/) para documentación técnica exhaustiva por área.
