export const API_BASE = 'http://127.0.0.1:8002';

export interface Model {
  id: string;
  name: string;
  provider: string;
  enabled: boolean;
}

export const api = {
  async getModels(): Promise<Model[]> {
    try {
      const response = await fetch(`${API_BASE}/api/models`);
      if (!response.ok) throw new Error('Failed to fetch models');
      const data = await response.json();
      return data.models;
    } catch (e) {
      console.error(e);
      return [];
    }
  },

  async generateCode(prompt: string, codeContext: string, modelId?: string, messages?: {role: string, content: string}[], rootDir?: string): Promise<{ response: string, model: string }> {
    const response = await fetch(`${API_BASE}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        code_context: codeContext,
        model_id: modelId,
        messages: messages,
        project_path: rootDir
      })
    });
    
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Generation failed');
    }
    
    const data = await response.json();
    // Support both old and new backend response format
    if (typeof data.response === 'string') {
        return { response: data.response, model: data.model || 'unknown' };
    }
    return { response: data.response, model: data.model || 'unknown' };
  }
};
