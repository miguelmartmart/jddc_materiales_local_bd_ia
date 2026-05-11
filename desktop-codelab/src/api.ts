/**
 * api.ts — Cliente HTTP para el backend de CodeLab (puerto 8002)
 *
 * MODO: AI_LOCAL_ONLY — Solo Qwen3 VL 30B en red LAN JDDC.
 * El backend en server.py garantiza que NUNCA se usa internet.
 * El modelo preferido es jddcia-qwen3-30b-ip (IP directa 10.13.79.31).
 *
 * AUTODESCUBRIMIENTO: Detecta automáticamente:
 * 1. Tailscale VPN (100.73.44.46) — Más confiable en DHCP
 * 2. IP local configurada (10.13.79.31)
 * 3. DNS local (jddcia.local)
 * 4. Caché de última conexión exitosa
 */

// Punto de conexión principal (fallback a localhost si no hay autodescubrimiento)
let API_BASE = 'http://127.0.0.1:8002';
let DISCOVERED_ROUTE: any = null;

/**
 * Intenta descubrir la mejor ruta al servidor de IA.
 * Se ejecuta una sola vez al inicio de la app.
 * NOTA: El autodescubrimiento es para el backend, no cambia la URL del frontend.
 */
export async function initializeAPIRoute(): Promise<void> {
  try {
    const response = await fetch('http://127.0.0.1:8002/api/autodiscover', {
      method: 'GET',
      signal: AbortSignal.timeout(5000) // Timeout 5s
    });
    
    if (response.ok) {
      DISCOVERED_ROUTE = await response.json();
      // NO cambiar API_BASE - el frontend siempre habla con el backend local
      console.log(
        `[API] ✅ Servidor descubierto: ${DISCOVERED_ROUTE.source}`,
        `(${DISCOVERED_ROUTE.host})`
      );
    }
  } catch (e) {
    console.warn('[API] ⚠️ Autodescubrimiento falló, usando localhost', e);
    // Mantener API_BASE = 'http://127.0.0.1:8002' como fallback
  }
}

/**
 * ID del modelo LAN preferido para CodeLab.
 * Coincide con el ID en jddcia_models.json (score 95 — IP directa).
 * Si no está disponible, el backend usa el siguiente modelo LAN automáticamente.
 */
export const LAN_MODEL_ID = 'jddcia-qwen3-30b-ip';

export interface Model {
  id: string;
  name: string;
  provider: string;
  enabled: boolean;
  score?: number;
}

export const api = {
  /**
   * Obtiene la URL base del backend (considera autodescubrimiento).
   */
  getBaseUrl(): string {
    return API_BASE;
  },

  /**
   * Obtiene información del autodescubrimiento (ruta actual, fuente, etc.).
   */
  getDiscoveredRoute(): any {
    return DISCOVERED_ROUTE;
  },

  async getModels(): Promise<Model[]> {
    try {
      const response = await fetch(`${API_BASE}/api/models`);
      if (!response.ok) throw new Error('Failed to fetch models');
      const data = await response.json();
      return data.models;
    } catch (e) {
      console.error('[CodeLab API] Error fetching models:', e);
      return [];
    }
  },

  /**
   * Genera código usando el backend LAN.
   *
   * @param prompt        - Mensaje del usuario
   * @param codeContext   - Contenido del editor activo (contexto de código)
   * @param modelId       - ID del modelo a usar (si es null, usa el mejor LAN disponible)
   * @param messages      - Historial de mensajes del chat
   * @param rootDir       - Ruta raíz del proyecto
   * @returns             - { response: string, model: string }
   */
  async generateCode(
    prompt: string,
    codeContext: string,
    modelId?: string,
    messages?: { role: string; content: string }[],
    rootDir?: string,
    images?: string[],
    documents?: { name: string; text: string }[]
  ): Promise<{ response: string; model: string }> {
    const effectiveModelId = modelId || LAN_MODEL_ID;

    const body: Record<string, unknown> = {
      prompt,
      code_context: codeContext,
      model_id: effectiveModelId,
      messages: messages,
      project_path: rootDir
    };
    if (images && images.length > 0) body.images = images;
    if (documents && documents.length > 0) body.documents = documents;

    // Retry up to 3 attempts on 503 (model busy) or network errors
    const MAX_RETRIES = 3;
    const RETRY_DELAYS_MS = [3000, 7000, 12000];
    let lastError: Error = new Error('Generation failed');

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        const response = await fetch(`${API_BASE}/api/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });

        if (response.status === 503 && attempt < MAX_RETRIES - 1) {
          console.warn(`[API] 503 en intento ${attempt + 1}/${MAX_RETRIES}, reintentando en ${RETRY_DELAYS_MS[attempt] / 1000}s…`);
          await new Promise(r => setTimeout(r, RETRY_DELAYS_MS[attempt]));
          continue;
        }

        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: response.statusText }));
          throw new Error(err.detail || 'Generation failed');
        }

        const data = await response.json();
        return {
          response: typeof data.response === 'string' ? data.response : String(data.response),
          model: data.model || LAN_MODEL_ID
        };
      } catch (e) {
        lastError = e as Error;
        if (attempt < MAX_RETRIES - 1) {
          console.warn(`[API] Error en intento ${attempt + 1}/${MAX_RETRIES}: ${lastError.message}, reintentando en ${RETRY_DELAYS_MS[attempt] / 1000}s…`);
          await new Promise(r => setTimeout(r, RETRY_DELAYS_MS[attempt]));
        }
      }
    }

    throw lastError;
  },

  /**
   * Genera texto para actualización de contexto (ContextManager).
   * Usa el modelo LAN preferido sin historial de mensajes.
   *
   * @param prompt - Prompt de actualización de contexto
   * @returns      - Texto generado o null si falla
   */
  async generateContextUpdate(prompt: string): Promise<string | null> {
    try {
      const response = await fetch(`${API_BASE}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          code_context: '',
          model_id: LAN_MODEL_ID,
          messages: []
        })
      });

      if (!response.ok) {
        console.error('[CodeLab API] Context update failed:', response.statusText);
        return null;
      }

      const data = await response.json();
      return typeof data.response === 'string' ? data.response : null;
    } catch (e) {
      console.error('[CodeLab API] Error in generateContextUpdate:', e);
      return null;
    }
  },

  /**
   * Extrae texto de un documento (PDF, DOCX, XLSX, XLS, CSV, TXT, etc.)
   * enviando el archivo en base64 al backend.
   *
   * @param filename    - Nombre del archivo (para detectar tipo por extensión)
   * @param contentB64  - Contenido del archivo en base64 (data:...;base64,... o raw)
   * @returns           - { filename, text, pages?, rows?, truncated, error? }
   */
  async extractText(filename: string, contentB64: string): Promise<{
    filename: string;
    text: string;
    pages?: number;
    rows?: number;
    truncated: boolean;
    error?: string;
  }> {
    const response = await fetch(`${API_BASE}/api/extract-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, content_b64: contentB64 })
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(err.detail || `Extract failed for ${filename}`);
    }
    return response.json();
  },

  /**
   * Verifica que el backend LAN está disponible.
   * @returns true si el backend responde, false si no.
   */
  async checkHealth(): Promise<{ ok: boolean; mode: string; models: string[] }> {
    try {
      const response = await fetch(`${API_BASE}/health`, {
        signal: AbortSignal.timeout(5000)
      });
      if (!response.ok) return { ok: false, mode: 'unknown', models: [] };
      const data = await response.json();
      return {
        ok: data.status === 'ok',
        mode: data.mode || 'unknown',
        models: data.lan_models || []
      };
    } catch (e) {
      return { ok: false, mode: 'offline', models: [] };
    }
  }
};
