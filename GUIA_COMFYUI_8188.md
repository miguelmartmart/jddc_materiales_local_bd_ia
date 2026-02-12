# Guía de Implementación: Servicio de Análisis de Imágenes en ComfyUI (Puerto 8188)

## 1. Estado Actual en `interjddcia` (Análisis Situacional)

Es importante aclarar que en la aplicación actual `interjddcia`, el servicio de **análisis/visión** NO se está ejecutando en el servidor 8188 (ComfyUI).

*   **ComfyUI (Puerto 8188)**: Se utiliza exclusivamente para la **Generación de Imágenes** (Txt2Img).
*   **Análisis de Imágenes**: El código actual (`backend/modules/images/service.py`) utiliza dos métodos para "ver" y describir imágenes:
    1.  **Local (Puerto 1234)**: Intenta conectar con **LM Studio** corriendo un modelo `qwen/qwen3-vl-8b`.
    2.  **Cloud (OpenAI)**: Si falla el local, usa `gpt-4o` en la nube.

> **Nota**: El código tiene un mensaje de error explícito que dice: *"Para analizar imágenes localmente con ComfyUI, necesitas instalar nodos de visión (VLM). Por ahora, no puedo 'ver' la imagen."*

---

## 2. Requisitos para Implementar Análisis en ComfyUI (Puerto 8188)

Para lograr tu objetivo de implementar el análisis *dentro* del servidor ComfyUI (8188) y replicarlo en otra aplicación, necesitas los siguientes componentes funcionales y técnicos que actualmente **no existen** en la configuración base de `interjddcia`.

### A. Información Técnica (Infraestructura ComfyUI)

Para habilitar "visión" en ComfyUI, debes instalar **Nodos Personalizados (Custom Nodes)** capaces de interrogar imágenes.

**Opciones Recomendadas:**
1.  **WD14 Tagger**: Para etiquetado rápido (tags tipo booru).
    *   *Repo*: `pythongosssss/ComfyUI-WD14-Tagger`
2.  **JoyTag**: Etiquetado moderno y preciso.
3.  **VLM Nodes (Qwen-VL / LLaVA)**: Para descripciones en lenguaje natural (lo más cercano a GPT-4 Vision).
    *   *Repo*: `cerulli/comfyui-llm-party` o similar.

**Instalación requerida en el servidor 8188:**
Debes usar `ComfyUI-Manager` para instalar estos nodos.

### B. Información Funcional (El Workflow)

Necesitas crear y guardar un workflow `.json` en formato API (no el formato estándar de UI) que haga lo siguiente:

1.  **LoadImage Node**: Nodo de entrada para recibir la imagen.
2.  **VLM/Tagger Loader**: Cargar el modelo de visión.
3.  **Interrogator Node**: Procesar la imagen y generar texto.
4.  **Text Output/Save**: Un nodo que exponga el resultado de texto para que la API pueda leerlo.

**Ejemplo conceptual del Workflow JSON:**
```json
{
  "3": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "input_image.png"
    }
  },
  "4": {
    "class_type": "WD14Tagger",
    "inputs": {
      "image": ["3", 0],
      "model": "wd-v1-4-convnext-tagger-v2",
      "threshold": 0.35
    }
  },
  "5": {
    "class_type": "ShowText", 
    "inputs": {
      "text": ["4", 0]
    }
  }
}
```

### C. Integración en la Nueva Aplicación (Código Backend)

Para replicar esto en tu nueva aplicación, tu backend debe implementar un cliente API para ComfyUI diferente al de generación. El flujo técnico es:

1.  **Subir Imagen**: `POST http://127.0.0.1:8188/upload/image` (form-data).
2.  **Cargar Workflow**: Leer el JSON del workflow de análisis.
3.  **Reemplazar Input**: Modificar el nodo `LoadImage` en el JSON para que apunte al nombre del archivo subido.
4.  **Ejecutar (Queue)**: `POST http://127.0.0.1:8188/prompt` con el JSON modificado.
5.  **Polling**: Consultar `GET http://127.0.0.1:8188/history/{prompt_id}` hasta que termine.
6.  **Extraer Resultado**: Leer el output del nodo de salida (`ShowText` o similar) desde el JSON de respuesta del historial.

### Resumen de Diferencias

| Característica | App Actual (`interjddcia`) | Tu Objetivo (Nueva App con 8188) |
| :--- | :--- | :--- |
| **Motor de Análisis** | LM Studio (Puerto 1234) o OpenAI | ComfyUI (Puerto 8188) |
| **Protocolo** | OpenAI API Standard (`/v1/chat/completions`) | ComfyUI API (`/prompt`, `/history`) |
| **Complejidad** | Baja (Estándar de industria) | Media (Requiere gestión de Workflows y WebSockets/Polling) |
| **Requisito Server** | Modelo cargado en LM Studio | Nodos de Visión + Modelos (CLIP/LLaVA) en ComfyUI |

Para "hacerlo igual" a como **funciona realmente** hoy `interjddcia`, deberías usar LM Studio en el puerto 1234. Para "hacerlo como quieres" (en 8188), debes implementar el flujo de ComfyUI descrito arriba.
