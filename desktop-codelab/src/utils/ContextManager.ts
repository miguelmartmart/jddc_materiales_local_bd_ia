/**
 * ContextManager.ts — Gestión de contexto persistente para CodeLab
 *
 * Guarda y actualiza el contexto de tareas y chats en archivos .md
 * dentro de la carpeta .codelab/ del proyecto.
 *
 * MODO AI_LOCAL_ONLY: Las actualizaciones de contexto con IA usan
 * exclusivamente el modelo Qwen3 LAN (jddcia-qwen3-30b-ip).
 * Nunca se conecta a internet para actualizar el contexto.
 */

import { api } from '../api';

export interface TaskContext {
  id: string;
  path: string; // File path on disk
  summary: string;
  lastUpdated: number;
}

export class ContextManager {
  private static instance: ContextManager;
  private rootDir: string | null = null;
  private electronAPI: any = null;

  private constructor() {
    if (typeof window !== 'undefined') {
      this.electronAPI = (window as any).electronAPI;
    }
  }

  public static getInstance(): ContextManager {
    if (!ContextManager.instance) {
      ContextManager.instance = new ContextManager();
    }
    return ContextManager.instance;
  }

  public setRootDir(path: string) {
    this.rootDir = path;
  }

  // ─── Persistencia ──────────────────────────────────────────────────────────

  public async saveProjectIndex(tasks: any[]) {
    if (!this.rootDir || !this.electronAPI) return;
    const path = `${this.rootDir}\\.codelab\\project_index.json`;
    try {
      await this.ensureDir(`${this.rootDir}\\.codelab`);
      await this.electronAPI.writeFile(path, JSON.stringify(tasks, null, 2));
    } catch (e) {
      console.error('[ContextManager] Failed to save project index', e);
    }
  }

  public async loadProjectIndex(): Promise<any[] | null> {
    if (!this.rootDir || !this.electronAPI) return null;
    const path = `${this.rootDir}\\.codelab\\project_index.json`;
    try {
      const content = await this.electronAPI.readFile(path);
      return JSON.parse(content);
    } catch (e) {
      // File might not exist yet
      return null;
    }
  }

  // ─── Gestión de archivos de contexto ───────────────────────────────────────

  public getContextPath(id: string, type: 'task' | 'chat'): string {
    if (!this.rootDir) return '';
    return `${this.rootDir}\\.codelab\\contexts\\${type}_${id}.md`;
  }

  private async ensureDir(path: string) {
    if (!this.electronAPI) return;
    try {
      await this.electronAPI.createDir(path);
    } catch (e) {
      // Ignorar si ya existe
    }
  }

  public async ensureContextFile(
    id: string,
    type: 'task' | 'chat',
    initialTitle: string
  ): Promise<string> {
    if (!this.rootDir || !this.electronAPI) return '';
    const path = this.getContextPath(id, type);

    try {
      const exists = await this.electronAPI.exists(path);
      if (exists) {
        return path;
      }

      // Crear nuevo archivo de contexto con plantilla inicial
      const content = [
        `# Contexto de ${type === 'task' ? 'Tarea' : 'Chat'}: ${initialTitle}`,
        `ID: ${id}`,
        '',
        '## Estado',
        'Activo',
        '',
        '## Resumen',
        '(Sin resumen todavía)',
        '',
        '## Detalles Técnicos',
        '- ',
        '',
        '## Archivos Creados/Modificados',
        '- ',
        '',
        '## Próximos Pasos',
        '- ',
      ].join('\n');

      await this.ensureDir(`${this.rootDir}\\.codelab\\contexts`);
      await this.electronAPI.writeFile(path, content);
      return path;
    } catch (e) {
      console.error('[ContextManager] Error creando archivo de contexto:', e);
      return path; // Devolver la ruta de todas formas para no bloquear
    }
  }

  // ─── Actualización de contexto con IA (solo Qwen3 LAN) ────────────────────

  /**
   * Actualiza el archivo de contexto usando Qwen3 LAN.
   *
   * GARANTÍA: Solo usa api.generateContextUpdate() que fuerza el modelo
   * jddcia-qwen3-30b-ip. NUNCA llama a modelos de internet.
   *
   * Si la IA no está disponible, el contexto NO se actualiza (fail-safe).
   * El flujo de chat continúa normalmente aunque el contexto no se actualice.
   */
  public async updateContextWithAI(
    id: string,
    type: 'task' | 'chat',
    recentActivity: string,
    currentContextContent: string
  ): Promise<boolean> {
    if (!this.rootDir) return false;

    const prompt = `
Eres el Gestor de Contexto de un proyecto de programación.
Tu objetivo es mantener un **Resumen Esquemático Optimizado** del estado del desarrollo.
Este archivo sirve como "Memoria a Largo Plazo" para la IA, por lo que debe ser conciso, preciso y actualizado.

ARCHIVO DE CONTEXTO ACTUAL:
\`\`\`markdown
${currentContextContent}
\`\`\`

ACTIVIDAD RECIENTE (Chat/Logs):
\`\`\`text
${recentActivity}
\`\`\`

INSTRUCCIONES:
1. **Resumen de Estado**: Actualiza el resumen con un esquema del estado actual del proyecto. Usa viñetas.
2. **Fase Actual**: Indica explícitamente la fase/paso actual (ej: "Fase: Implementación UI", "Paso 3/5").
3. **Índice de Archivos**: Mantén una lista estructurada de TODOS los archivos creados o modificados, con descripción de 1 línea.
4. **Decisiones Técnicas**: Registra decisiones clave, librerías elegidas o patrones usados.
5. **Tareas Pendientes**: Lista los próximos pasos inmediatos basados en la actividad reciente.
6. **Optimización**: Elimina información obsoleta. Mantén alta densidad de información y eficiencia de tokens. No seas verboso.

Devuelve ÚNICAMENTE el contenido Markdown actualizado, sin explicaciones adicionales.
    `.trim();

    try {
      // Usar generateContextUpdate que fuerza el modelo LAN (jddcia-qwen3-30b-ip)
      const updatedContent = await api.generateContextUpdate(prompt);

      if (!updatedContent) {
        console.warn('[ContextManager] La IA LAN no devolvió contenido para el contexto. Saltando actualización.');
        return false;
      }

      // Limpiar respuesta (eliminar fences de markdown si la IA los añadió)
      let cleanContent = updatedContent.trim();
      if (cleanContent.startsWith('```markdown')) {
        cleanContent = cleanContent.replace(/^```markdown\n?/, '').replace(/\n?```$/, '');
      } else if (cleanContent.startsWith('```')) {
        cleanContent = cleanContent.replace(/^```\n?/, '').replace(/\n?```$/, '');
      }

      // Guardar en archivo
      const path = this.getContextPath(id, type);
      await this.electronAPI.writeFile(path, cleanContent.trim());
      console.log(`[ContextManager] ✅ Contexto actualizado para ${type} ${id} (Qwen3 LAN)`);
      return true;
    } catch (e) {
      // Fail-safe: si la IA falla, el contexto no se actualiza pero el chat continúa
      console.error('[ContextManager] Error actualizando contexto con IA LAN:', e);
      return false;
    }
  }
}

export const contextManager = ContextManager.getInstance();
