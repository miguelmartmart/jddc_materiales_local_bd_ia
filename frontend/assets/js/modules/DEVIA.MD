# 🧠 Frontend Modules Context (`frontend/assets/js/modules`)

> **Role**: AI Context Source for Frontend Logic (Vanilla JS)
> **Scope**: Chat UI, State Management, API Integration, DOM Manipulation

## 📞 Chat Module (`chat.js`)

**Namespace**: `ChatModule`

### 🏗️ Architecture & DOM Strategy
*   **Initialization**: `init()` replaces DOM elements (cloneNode) to clear old event listeners automatically.
*   **Selector Pattern**: Uses `DOM_SELECTORS` constant (e.g., `DOM_SELECTORS.CHAT.INPUT`).
*   **Streaming**: Currently simulated via `appendMessage` (Full response reception).

### 🧩 State Management
```javascript
{
  conversationHistory: [
    { role: "user", content: "..." },
    { role: "assistant", content: "..." }
  ],
  currentSessionId: "uuid-v4" | null, // null = New Chat
  pendingImages: ["base64_string"]    // Cleared after send
}
```

### ⚡ Core Functions

| Function | Async | Description |
| :--- | :--- | :--- |
| `sendMessage()` | ✅ | Orchestrates validation, UI update, API call, and response handling. |
| `loadHistory()` | ✅ | Fetches `/api/chat/history` and renders the sidebar list. |
| `loadSession(id)` | ✅ | Fetches messages for a specific session and replays them into the chat window. |
| `startNewChat()` | ❌ | Resets `currentSessionId` and clears UI buffers. |
| `handleFileSelect(e)`| ❌ | Process image uploads -> FileReader -> Base64 (Max 5 images). |

### 🔌 API Communication

**Helper**: `fetch(API.ENDPOINTS.CHAT + '/send', ...)`

**Payload Construction**:
```javascript
const payload = {
    message: "User text",
    model_id: "selected_model_id",
    db_params: { ... }, // Sensitive: Retrieved from DB_CONFIG global
    conversation_history: this.conversationHistory, // Full context for stateless backend
    images: this.pendingImages,
    session_id: this.currentSessionId
};
```

### 🚨 Critical UI Flows

1.  **Confirmation Modal**:
    *   **Trigger**: Backend returns `status: "confirmation_required"`.
    *   **Action**: Shows `showConfirmationModal`.
    *   **Logic**: If confirmed, re-calls `/send` with `confirm_data_sending: true`.

2.  **Thinking State**:
    *   Injects a temporary DOM element (`id="thinking-timestamp"`).
    *   Removed immediately upon `success` or `error`.

## 📎 Dependencies
*   `../core/constants.js`: Contains `API`, `DB_CONFIG`, `DOM_SELECTORS`.
