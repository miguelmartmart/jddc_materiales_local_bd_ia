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

  // --- Persistence ---

  public async saveProjectIndex(tasks: any[]) {
    if (!this.rootDir || !this.electronAPI) return;
    const path = `${this.rootDir}\\.codelab\\project_index.json`;
    try {
      // Ensure directory exists
      await this.ensureDir(`${this.rootDir}\\.codelab`);
      await this.electronAPI.writeFile(path, JSON.stringify(tasks, null, 2));
    } catch (e) {
      console.error("Failed to save project index", e);
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

  // --- Context File Management ---

  public getContextPath(id: string, type: 'task' | 'chat'): string {
    if (!this.rootDir) return '';
    return `${this.rootDir}\\.codelab\\contexts\\${type}_${id}.md`;
  }

  private async ensureDir(path: string) {
    if (!this.electronAPI) return;
    try {
      await this.electronAPI.createDir(path);
    } catch (e) {
      // Ignore if exists
    }
  }

  public async ensureContextFile(id: string, type: 'task' | 'chat', initialTitle: string): Promise<string> {
    if (!this.rootDir || !this.electronAPI) return '';
    const path = this.getContextPath(id, type);
    
    try {
        const exists = await this.electronAPI.exists(path);
        if (exists) {
            return path;
        }
        
        // Create new
        const content = `# Context for ${type === 'task' ? 'Task' : 'Chat'}: ${initialTitle}\nID: ${id}\n\n## Status\nActive\n\n## Summary\n(No summary yet)\n\n## Technical Details\n- \n`;
        await this.ensureDir(`${this.rootDir}\\.codelab\\contexts`);
        await this.electronAPI.writeFile(path, content);
        return path;
    } catch (e) {
        console.error("Context file error:", e);
        return path; // Return path anyway to avoid blockers
    }
  }

  // --- AI Auto-Update ---

  public async updateContextWithAI(id: string, type: 'task' | 'chat', recentActivity: string, currentContextContent: string) {
    if (!this.rootDir) return;

    // We use the existing API, but we need to format the prompt carefully.
    // We want the AI to merge the new activity into the existing context.
    
    const prompt = `
You are the Context Manager for a coding project.
Your goal is to maintain a **Super Optimized Schematic Summary** of the development state.
This file serves as the "Long Term Memory" for the AI, so it must be concise, accurate, and up-to-date.

CURRENT CONTEXT FILE:
\`\`\`markdown
${currentContextContent}
\`\`\`

RECENT ACTIVITY (Chat/Logs):
\`\`\`text
${recentActivity}
\`\`\`

INSTRUCTIONS:
1. **State Summary**: Update the summary to be a schematic overview of the project status. Use bullet points.
2. **Current Phase**: Explicitly state the current phase/step (e.g., "Phase: UI Implementation", "Step 3/5").
3. **File Index**: Maintain a structured, hierarchical list of ALL files created or modified, with 1-line descriptions.
4. **Technical Decisions**: Log key decisions, libraries chosen, or patterns used.
5. **Pending Tasks**: List immediate next steps based on the recent activity.
6. **Optimization**: Remove obsolete information. Keep it high-density and token-efficient. Do not be chatty.

Return ONLY the updated Markdown content.
    `;

    try {
        // Use a "fast" model if possible, or just the default.
        // We pass empty code context for now.
        const result = await api.generateCode(prompt, "", undefined, []);
        const updatedContent = result.response;
        
        // Clean up response (remove markdown fences if AI added them)
        let cleanContent = updatedContent;
        if (cleanContent.startsWith('```markdown')) cleanContent = cleanContent.replace(/^```markdown\n/, '').replace(/\n```$/, '');
        if (cleanContent.startsWith('```')) cleanContent = cleanContent.replace(/^```\n/, '').replace(/\n```$/, '');

        // Save back to file
        const path = this.getContextPath(id, type);
        await this.electronAPI.writeFile(path, cleanContent);
        console.log(`[ContextManager] Updated context for ${type} ${id}`);
        return true;
    } catch (e) {
        console.error("[ContextManager] Failed to update context with AI", e);
        return false;
    }
  }
}

export const contextManager = ContextManager.getInstance();
