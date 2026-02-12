import React, { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { Bot, Play, Settings, RefreshCw, Folder, File, ChevronRight, ChevronDown, Terminal, AlertCircle, CheckCircle, Info, Save, XCircle } from 'lucide-react';
import { api, Model, API_BASE } from './api';
import { TaskManager, Task, ChatSession } from './components/TaskManager';
import { contextManager } from './utils/ContextManager';

// Add global type for exposed Electron API
declare global {
  interface Window {
    electronAPI: {
      openFolder: () => Promise<string>;
      readDir: (path: string) => Promise<any[]>;
      readFile: (path: string) => Promise<string>;
      exists: (path: string) => Promise<boolean>;
      createDir: (path: string) => Promise<boolean>;
      delete: (path: string) => Promise<boolean>;
      copy: (source: string, dest: string) => Promise<boolean>;
      move: (source: string, dest: string) => Promise<boolean>;
      writeFile: (path: string, content: string) => Promise<boolean>;
      openExternal: (url: string) => Promise<void>;
      executeCommand: (command: string) => Promise<{ success: boolean; output: string }>;
      onFolderSelected: (callback: (path: string) => void) => void;
      on: (channel: string, callback: (data: any) => void) => void;
    };
  }
}

interface FileNode {
  name: string;
  path: string;
  isDirectory: boolean;
  children?: FileNode[];
  isOpen?: boolean;
}

interface LogEntry {
  id: string;
  timestamp: Date;
  type: 'info' | 'success' | 'error' | 'warning' | 'default';
  message: string;
}

// Reusable Collapsible Section
const CollapsibleSection = ({ title, children, defaultOpen = true, actionButton = null }: { title: string, children: React.ReactNode, defaultOpen?: boolean, actionButton?: React.ReactNode }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-gray-700 rounded mb-2 overflow-hidden bg-[#1e1e1e]">
      <div className="flex items-center justify-between p-1 bg-gray-800/50">
         <button 
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1 text-xs font-mono text-gray-400 hover:text-white transition-colors flex-1 text-left"
        >
          {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <span className="truncate font-medium">{title}</span>
        </button>
        {actionButton && <div className="ml-2">{actionButton}</div>}
      </div>
      {isOpen && (
        <div className="p-2 border-t border-gray-700/50 overflow-x-auto">
          {children}
        </div>
      )}
    </div>
  );
};



  const FileTreeItem = ({ node, onSelect, onToggle, onOpenMenu, onDragStart, onDragOver, onDrop }: { 
    node: FileNode, 
    onSelect: (node: FileNode) => void, 
    onToggle: (node: FileNode) => void,
    onOpenMenu: (x: number, y: number, node: FileNode) => void,
    onDragStart: (e: React.DragEvent, node: FileNode) => void,
    onDragOver: (e: React.DragEvent, node: FileNode) => void,
    onDrop: (e: React.DragEvent, node: FileNode) => void
  }) => {
    const handleClick = () => {
      if (node.isDirectory) {
        onToggle(node);
        // Only trigger onSelect (which loads children) if we are opening the folder.
        // If we are closing it (node.isOpen is true), we don't need to load/select.
        if (!node.isOpen) {
            onSelect(node);
        }
      } else {
        onSelect(node);
      }
    };
  
    return (
      <div className="pl-2">
        <div 
          className="flex items-center gap-1 cursor-pointer hover:bg-gray-700 py-1 text-sm text-gray-300 select-none"
          onClick={handleClick}
          draggable={true}
          onDragStart={(e) => onDragStart(e, node)}
          onDragOver={(e) => onDragOver(e, node)}
          onDrop={(e) => onDrop(e, node)}
          onPointerDown={(e) => {
              console.log("Item Pointer Down:", e.button, node.name);
              if (e.button !== 2) return; // Right click only
              e.preventDefault();
              e.stopPropagation();
              onOpenMenu(e.clientX, e.clientY, node);
          }}
          onContextMenu={(e) => {
              e.preventDefault(); // Prevent native menu
          }}
          data-context-clickable="true"
          data-node-path={node.path}
          data-node-is-dir={node.isDirectory}
          data-node-name={node.name}
        >
          {node.isDirectory && (
            node.isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          )}
          {!node.isDirectory && <span className="w-4" />} {/* Spacer */}
          {node.isDirectory ? <Folder size={14} className="text-blue-400" /> : <File size={14} className="text-gray-400" />}
          <span className="truncate">{node.name}</span>
        </div>
        {node.isOpen && node.children && (
          <div className="border-l border-gray-700 ml-2">
             {node.children.map(child => (
               <FileTreeItem 
                 key={child.path} 
                 node={child} 
                 onSelect={onSelect} 
                 onToggle={onToggle} 
                 onOpenMenu={onOpenMenu}
                 onDragStart={onDragStart}
                 onDragOver={onDragOver}
                 onDrop={onDrop}
               />
             ))}
           </div>
         )}
       </div>
    );
  };
  
  function App() {
    // Context Menu State
    const [contextMenu, setContextMenu] = useState<{
      visible: boolean;
      x: number;
      y: number;
      node: FileNode | null;
    }>({ visible: false, x: 0, y: 0, node: null });
  
    const menuRef = React.useRef<HTMLDivElement>(null);

  const openContextMenu = (x: number, y: number, node: FileNode) => {
    console.log("OPEN CONTEXT MENU TRIGGERED", x, y, node);
    setContextMenu({ visible: true, x, y, node });
  };

  // Close context menu logic (Pointer Down for Robustness)
  useEffect(() => {
    const handlePointerDown = (e: PointerEvent) => {
      if (!contextMenu.visible) return;
      if (e.button !== 0) return; // solo izquierdo cierra

      // Si el click fue dentro del menú, NO cierres (deja que funcione el onClick)
      if (menuRef.current && menuRef.current.contains(e.target as Node)) return;

      setContextMenu(prev => (prev.visible ? { ...prev, visible: false } : prev));
    };

    window.addEventListener('pointerdown', handlePointerDown, true);
    return () => window.removeEventListener('pointerdown', handlePointerDown, true);
  }, [contextMenu.visible]);


  // Debugging: Check click anywhere
  useEffect(() => {
    const fn = (e: MouseEvent) => console.log("WINDOW CLICK", e.clientX, e.clientY, e.target);
    window.addEventListener("click", fn, true);
    return () => window.removeEventListener("click", fn, true);
  }, []);

  const [code, setCode] = useState('// Write your code here...');
  const [output, setOutput] = useState('');
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [status, setStatus] = useState<string>('Connecting to backend...');
  
  const [rootDir, setRootDir] = useState<string>('');
  const [fileTree, setFileTree] = useState<FileNode[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [messages, setMessages] = useState<{role: 'user' | 'assistant' | 'system', content: string, timestamp: number, model?: string}[]>([]);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  // Current File State
  const [currentFilePath, setCurrentFilePath] = useState<string>('');
  const currentFilePathRef = React.useRef<string>('');

  // Layout State
  const [leftSidebarWidth, setLeftSidebarWidth] = useState(300);
  const [rightSidebarWidth, setRightSidebarWidth] = useState(350);
  const [logsHeight, setLogsHeight] = useState(200); // Height when expanded
  const [isLogsExpanded, setIsLogsExpanded] = useState(false);
  
  const [isResizingLeftSidebar, setIsResizingLeftSidebar] = useState(false);
  const [isResizingRightSidebar, setIsResizingRightSidebar] = useState(false);
  const [isResizingLogs, setIsResizingLogs] = useState(false);
  const [isResizingTasks, setIsResizingTasks] = useState(false);
  
  // Terminal Panel State
  const [isTerminalOpen, setIsTerminalOpen] = useState(true);
  const [terminalHeight, setTerminalHeight] = useState(150);
  const [isResizingTerminal, setIsResizingTerminal] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState('');
  const [terminalInput, setTerminalInput] = useState('');
  const terminalEndRef = React.useRef<HTMLDivElement>(null);
  
  const leftSidebarRef = React.useRef<HTMLDivElement>(null);
  const rightSidebarRef = React.useRef<HTMLDivElement>(null);
  const logsEndRef = React.useRef<HTMLDivElement>(null);

  // Task Management State
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [tasksHeight, setTasksHeight] = useState(200);

  // File System State
  const [clipboard, setClipboard] = useState<{ path: string; mode: 'copy' | 'cut' } | null>(null);

  // File Operations Handlers
  const refreshDir = async (dirPath: string) => {
      // Helper to refresh a directory in the tree
      // This is a simplified deep update. 
      // Ideally we should use a proper tree manager or immutable updates.
      // For now, let's try to update the specific node if it exists in tree.
      
      const updateTree = async (nodes: FileNode[]): Promise<FileNode[]> => {
          return Promise.all(nodes.map(async (node) => {
              if (node.path === dirPath && node.isDirectory) {
                  try {
                      const childrenRaw = await window.electronAPI.readDir(node.path);
                      const children: FileNode[] = childrenRaw.map((f: any) => ({
                          name: f.name,
                          path: f.path,
                          isDirectory: f.isDirectory,
                          children: []
                      }));
                      // Preserve open state if it was open
                      return { ...node, children, isOpen: node.isOpen };
                  } catch (e) {
                      console.error("Failed to refresh dir", e);
                      return node;
                  }
              }
              if (node.children) {
                  return { ...node, children: await updateTree(node.children) };
              }
              return node;
          }));
      };
      
      if (dirPath === rootDir) {
           // Reload root
           const files = await window.electronAPI.readDir(rootDir);
           const nodes = files.map((f: any) => ({
                name: f.name,
                path: f.path,
                isDirectory: f.isDirectory,
                children: []
           }));
           setFileTree(nodes);
      } else {
           setFileTree(await updateTree(fileTree));
      }
  };

  const handleCopy = (node: FileNode) => {
    setClipboard({ path: node.path, mode: 'copy' });
    addLog('info', `Copied to clipboard: ${node.name}`);
    setContextMenu(prev => ({ ...prev, visible: false }));
  };

  const handleCut = (node: FileNode) => {
    setClipboard({ path: node.path, mode: 'cut' });
    addLog('info', `Cut to clipboard: ${node.name}`);
    setContextMenu(prev => ({ ...prev, visible: false }));
  };

  const handlePaste = async (targetNode: FileNode) => {
    if (!clipboard) {
        addLog('error', 'Clipboard is empty. Copy or Cut a file first.');
        alert('Clipboard is empty.');
        return;
    }
    
    try {
        // Normalize path helpers
        const normalize = (p: string) => p.replace(/\//g, '\\');
        
        // Determine target directory
        const rawTargetDir = targetNode.isDirectory ? targetNode.path : targetNode.path.split(/[\\/]/).slice(0, -1).join('\\');
        const targetDir = normalize(rawTargetDir);
        
        const fileName = clipboard.path.split(/[\\/]/).pop();
        if (!fileName) throw new Error('Invalid source file name');

        let destPath = `${targetDir}\\${fileName}`; 
        
        // Check for existence and handle collisions
        const exists = await window.electronAPI.exists(destPath);
        
        if (exists) {
            if (clipboard.mode === 'cut') {
                 if (!confirm(`File ${fileName} already exists. Overwrite?`)) {
                     setContextMenu(prev => ({ ...prev, visible: false }));
                     return;
                 }
                 // Proceed to overwrite
            } else {
                 // Auto-rename for copy
                 let counter = 1;
                 const extIndex = fileName.lastIndexOf('.');
                 const nameWithoutExt = extIndex !== -1 ? fileName.substring(0, extIndex) : fileName;
                 const ext = extIndex !== -1 ? fileName.substring(extIndex) : '';
                 
                 while (await window.electronAPI.exists(destPath)) {
                     destPath = `${targetDir}\\${nameWithoutExt} - Copy${counter > 1 ? ` (${counter})` : ''}${ext}`;
                     counter++;
                 }
                 addLog('info', `Renamed paste to: ${destPath.split('\\').pop()}`);
            }
        }

        console.log(`Pasting: ${clipboard.path} -> ${destPath} (Mode: ${clipboard.mode})`);

        if (clipboard.mode === 'copy') {
             await window.electronAPI.copy(clipboard.path, destPath);
             addLog('success', `Copied ${fileName} to ${destPath.split('\\').pop()}`);
        } else {
             await window.electronAPI.move(clipboard.path, destPath);
             addLog('success', `Moved ${fileName} to ${destPath.split('\\').pop()}`);
             setClipboard(null);
        }
        
        setContextMenu(prev => ({ ...prev, visible: false }));
        
        // Refresh target directory
        await refreshDir(targetDir);
        
        // For move, refresh source parent if different
        if (clipboard.mode === 'cut') {
            const sourceDir = clipboard.path.split(/[\\/]/).slice(0, -1).join('\\');
            if (normalize(sourceDir) !== targetDir) {
                await refreshDir(normalize(sourceDir));
            }
        }
      
    } catch (e: any) {
      console.error(e);
      addLog('error', `Paste failed: ${e.message}`);
      alert(`Paste failed: ${e.message}`);
    }
  };

  const handleDelete = async (node: FileNode) => {
       if (confirm(`Are you sure you want to delete ${node.name}?`)) {
          try {
             await window.electronAPI.delete(node.path);
             addLog('success', `Deleted ${node.name}`);
             setContextMenu(prev => ({ ...prev, visible: false }));
             
             // Refresh parent
             const parentDir = node.path.split(/[\\/]/).slice(0, -1).join('/');
             await refreshDir(parentDir);
          } catch (e: any) {
             addLog('error', `Delete failed: ${e.message}`);
          }
       }
  };

  // Drag and Drop Handlers
  const onDragStart = (e: React.DragEvent, node: FileNode) => {
      e.dataTransfer.setData('text/plain', node.path);
      e.dataTransfer.effectAllowed = 'move';
  };

  const onDragOver = (e: React.DragEvent, node: FileNode) => {
      e.preventDefault(); 
      if (node.isDirectory) {
          e.dataTransfer.dropEffect = 'move';
          // Visual feedback could be added here (e.g. highlight)
      }
  };

  const onDrop = async (e: React.DragEvent, targetNode: FileNode) => {
      e.preventDefault();
      const sourcePath = e.dataTransfer.getData('text/plain');
      if (!sourcePath) return;
      if (sourcePath === targetNode.path) return;

      // Logic: Move sourcePath to targetNode
      const targetDir = targetNode.isDirectory ? targetNode.path : targetNode.path.split(/[\\/]/).slice(0, -1).join('/');
      const fileName = sourcePath.split(/[\\/]/).pop();
      const destPath = `${targetDir}/${fileName}`;

      if (destPath === sourcePath) return;

      try {
           await window.electronAPI.move(sourcePath, destPath);
           addLog('success', `Moved ${fileName} to ${targetDir}`);
           
           // Refresh target
           await refreshDir(targetDir);
           // Refresh source parent
           const sourceDir = sourcePath.split(/[\\/]/).slice(0, -1).join('/');
           if (sourceDir !== targetDir) {
               await refreshDir(sourceDir);
           }
      } catch (e: any) {
           addLog('error', `Move failed: ${e.message}`);
      }
  };

  // Load Tasks on rootDir change
  useEffect(() => {
    if (rootDir) {
      contextManager.setRootDir(rootDir); // Init context manager

      // Try loading from disk index first
      contextManager.loadProjectIndex().then(diskTasks => {
          if (diskTasks && diskTasks.length > 0) {
              // Migrate if needed (reuse migration logic)
              const migrateTasks = (taskList: any[]): Task[] => {
                  return taskList.map(t => ({
                      ...t,
                      subtasks: migrateTasks(t.subtasks || []),
                      isExpanded: t.isExpanded ?? true,
                      chats: (t.chats || []).map((c: any) => ({
                          ...c,
                          messages: (c.messages || []).map((m: any) => ({
                              ...m,
                              timestamp: m.timestamp || c.createdAt || Date.now()
                          }))
                      }))
                  }));
              };
              setTasks(migrateTasks(diskTasks));
          } else {
              // Fallback to localStorage (legacy)
              const savedTasks = localStorage.getItem(`codelab_tasks_${rootDir}`);
              if (savedTasks) {
                try {
                  const parsed = JSON.parse(savedTasks);
                  // Same migration...
                   const migrateTasks = (taskList: any[]): Task[] => {
                      return taskList.map(t => ({
                          ...t,
                          subtasks: migrateTasks(t.subtasks || []),
                          isExpanded: t.isExpanded ?? true,
                          chats: (t.chats || []).map((c: any) => ({
                              ...c,
                              messages: (c.messages || []).map((m: any) => ({
                                  ...m,
                                  timestamp: m.timestamp || c.createdAt || Date.now()
                              }))
                          }))
                      }));
                  };
                  setTasks(migrateTasks(parsed));
                } catch (e) { console.error(e); }
              } else {
                setTasks([]);
              }
          }
      });
      
      // Reset active states on folder change
      setActiveTaskId(null);
      setActiveChatId(null);
      setMessages([]);
    }
  }, [rootDir]);

  // Save Tasks whenever they change
  useEffect(() => {
    if (rootDir) {
        if (tasks.length > 0) {
            localStorage.setItem(`codelab_tasks_${rootDir}`, JSON.stringify(tasks));
            // Also save to disk index
            contextManager.saveProjectIndex(tasks);
        } else {
            localStorage.removeItem(`codelab_tasks_${rootDir}`);
        }
    }
  }, [tasks, rootDir]);

  // Task Handlers - Recursive Logic
  
  // Helper to deep update tasks
  const updateTaskInTree = (tasks: Task[], taskId: string, updater: (t: Task) => Task): Task[] => {
      let hasChanges = false;
      const newTasks = tasks.map(t => {
          if (t.id === taskId) {
              hasChanges = true;
              return updater(t);
          }
          if (t.subtasks && t.subtasks.length > 0) {
              const newSubtasks = updateTaskInTree(t.subtasks, taskId, updater);
              // Only update if subtasks actually changed reference (meaning something inside changed)
              if (newSubtasks !== t.subtasks) {
                  hasChanges = true;
                  return { ...t, subtasks: newSubtasks };
              }
          }
          return t;
      });
      return hasChanges ? newTasks : tasks;
  };

  // Helper to find task path (root -> subtask)
  const findTaskPath = (tasks: Task[], taskId: string): Task[] | null => {
      for (const t of tasks) {
          if (t.id === taskId) return [t];
          if (t.subtasks) {
              const found = findTaskPath(t.subtasks, taskId);
              if (found) return [t, ...found];
          }
      }
      return null;
  };

  // Helper to find task (for selecting chat etc)
  const findTaskInTree = (tasks: Task[], taskId: string): Task | null => {
      for (const t of tasks) {
          if (t.id === taskId) return t;
          if (t.subtasks) {
              const found = findTaskInTree(t.subtasks, taskId);
              if (found) return found;
          }
      }
      return null;
  };

  const handleAddTask = async (parentId: string | null, title: string) => {
    const newTask: Task = {
      id: Math.random().toString(36).substr(2, 9),
      title,
      status: 'todo',
      chats: [],
      subtasks: [],
      isExpanded: true,
      createdAt: Date.now()
    };

    if (!parentId) {
        // Add to root
        setTasks(prev => [...prev, newTask]);
        setActiveTaskId(newTask.id);
        setActiveChatId(null); // Reset chat
        setMessages([]); // Reset messages
    } else {
        // Add to parent subtasks
        setTasks(prev => updateTaskInTree(prev, parentId, (t) => ({
            ...t,
            subtasks: [...t.subtasks, newTask],
            isExpanded: true // Expand parent to show new subtask
        })));
        // Select the new subtask
        setActiveTaskId(newTask.id);
        setActiveChatId(null); // Reset chat
        setMessages([]); // Reset messages
    }

    // Force context switch: Create and open context file
    try {
        const contextPath = await contextManager.ensureContextFile(newTask.id, 'task', title);
        await handleOpenContext(newTask.id); // This will update 'code' state
        addLog('info', `Created and opened context for new task: ${title}`);
    } catch (e) {
        console.error("Failed to init context for new task", e);
    }
  };

  const handleDeleteTask = (taskId: string) => {
    if (!confirm('Are you sure you want to delete this task?')) return;
    // Recursive filter
    const filterTasks = (tasks: Task[]): Task[] => {
        return tasks.filter(t => t.id !== taskId).map(t => ({
            ...t,
            subtasks: filterTasks(t.subtasks)
        }));
    };

    setTasks(prev => filterTasks(prev));
    
    if (activeTaskId === taskId) {
      setActiveTaskId(null);
      setActiveChatId(null);
      setMessages([]);
    }
  };

  const handleUpdateTaskStatus = (taskId: string, status: Task['status']) => {
    setTasks(prev => updateTaskInTree(prev, taskId, t => ({ ...t, status })));
  };

  const handleToggleTaskExpanded = (taskId: string) => {
    console.log(`Toggling task ${taskId}`);
    setTasks(prev => {
        const next = updateTaskInTree(prev, taskId, t => ({ ...t, isExpanded: !t.isExpanded }));
        console.log('Tasks updated:', next === prev ? 'No Change' : 'Changed');
        return next;
    });
  };

  const handleMoveTask = (draggedTaskId: string, targetTaskId: string | null) => {
    setTasks(prev => {
        // 1. Find and remove dragged task
        let draggedTask: Task | null = null;
        
        const removeTask = (list: Task[]): Task[] => {
            const result: Task[] = [];
            for (const t of list) {
                if (t.id === draggedTaskId) {
                    draggedTask = t;
                    continue;
                }
                if (t.subtasks && t.subtasks.length > 0) {
                    const newSub = removeTask(t.subtasks);
                    // Use a simple check if length changed or reference changed
                    // Since we are creating a new array in map/filter logic, simple comparison works if we return new array
                    // But here we are pushing to result.
                    result.push({ ...t, subtasks: newSub });
                } else {
                    result.push(t);
                }
            }
            return result;
        };
        
        const tasksWithoutDragged = removeTask(prev);
        
        if (!draggedTask) return prev; // Should not happen
        
        // 2. Insert into target
        if (!targetTaskId) {
            // Move to root
            return [...tasksWithoutDragged, draggedTask];
        } else {
            // Move to target subtasks
            return updateTaskInTree(tasksWithoutDragged, targetTaskId, t => ({
                ...t,
                subtasks: [...(t.subtasks || []), draggedTask!],
                isExpanded: true // Ensure target is expanded
            }));
        }
    });
  };

  // Context Management
  // Removed getContextPath as it's now in ContextManager


  const handleOpenContext = async (taskId: string, chatId?: string) => {
      if (!rootDir) {
          addLog('error', 'Please open a folder first.');
          return;
      }

      const id = chatId || taskId;
      const type = chatId ? 'chat' : 'task';
      
      try {
          // Use ContextManager to ensure file exists
          const task = findTaskInTree(tasks, taskId);
          const title = chatId 
                ? task?.chats.find(c => c.id === chatId)?.title 
                : task?.title;
          
          const path = await contextManager.ensureContextFile(id, type, title || 'Unknown');
          
          // Open in editor
          const existingTab = openFiles.find(f => f.path === path);
          if (existingTab) {
              setActiveFile(path);
              setCode(existingTab.content);
              setCurrentFilePath(path);
              currentFilePathRef.current = path;
          } else {
             const fileContent = await window.electronAPI.readFile(path);
             setOpenFiles(prev => [...prev, { path: path, content: fileContent }]);
             setActiveFile(path);
             setCode(fileContent);
             setCurrentFilePath(path);
             currentFilePathRef.current = path;
          }

      } catch (e: any) {
          addLog('error', `Failed to open context: ${e.message}`);
      }
  };

  const handleAddChat = (taskId: string) => {
    const newChat: ChatSession = {
      id: Math.random().toString(36).substr(2, 9),
      title: `Chat ${new Date().toLocaleTimeString()}`,
      messages: [],
      createdAt: Date.now()
    };
    
    setTasks(prev => updateTaskInTree(prev, taskId, t => ({
        ...t,
        chats: [...t.chats, newChat]
    })));
    
    setActiveTaskId(taskId); // Ensure task is active
    setActiveChatId(newChat.id);
    setMessages([]);
  };

  const handleDeleteChat = (taskId: string, chatId: string) => {
     if (!confirm('Are you sure you want to delete this chat?')) return;
     setTasks(prev => updateTaskInTree(prev, taskId, t => ({
         ...t,
         chats: t.chats.filter(c => c.id !== chatId)
     })));
    
    if (activeChatId === chatId) {
        setActiveChatId(null);
        setMessages([]);
    }
  };

  const handleExportChat = (taskId: string, chatId: string) => {
      const taskPath = findTaskPath(tasks, taskId);
      if (!taskPath) return;
      const task = taskPath[taskPath.length - 1];
      const chat = task.chats.find(c => c.id === chatId);
      if (!chat) return;

      const formattedHistory = chat.messages.map(m => {
          const time = new Date(m.timestamp || Date.now()).toLocaleString();
          const sender = m.role.toUpperCase();
          const modelInfo = (m as any).model ? `\nModel: ${(m as any).model}` : '';
          return `[${time}] [${sender}]${modelInfo}\n${m.content}\n\n${'-'.repeat(40)}\n`;
      }).join('\n');

      const taskHierarchy = taskPath.map(t => t.title).join(' > ');
      const header = `CHAT EXPORT\nTask Hierarchy: ${taskHierarchy}\nChat: ${chat.title}\nModel: ${selectedModel}\nBaseURL: ${API_BASE}\nExported: ${new Date().toLocaleString()}\n${'='.repeat(40)}\n\n`;
      
      const fullContent = header + formattedHistory;
      
      // Open in editor
      setCode(fullContent);
      setCurrentFilePath(''); // Mark as unsaved/virtual file
      addLog('success', `Chat "${chat.title}" exported to editor.`);
  };

  const handleSelectTask = async (taskId: string) => {
    setActiveTaskId(taskId);
    // When selecting a task, we don't necessarily select a chat unless there's only one?
    // Or restore last used? For now, clear chat selection to let user choose.
    setActiveChatId(null);
    setMessages([]);

    // Optional: Auto-open context if no chat is selected, to set the "stage"
    try {
        await handleOpenContext(taskId);
    } catch (e) { console.error(e); }
  };

  const handleSelectChat = async (taskId: string, chatId: string) => {
    setActiveTaskId(taskId);
    setActiveChatId(chatId);
    
    const task = findTaskInTree(tasks, taskId);
    const chat = task?.chats.find(c => c.id === chatId);
    if (chat) {
        setMessages(chat.messages);
    }

    // Also open the chat context
    try {
        await handleOpenContext(taskId, chatId);
    } catch (e) { console.error(e); }
  };

  // Sync Messages to Current Chat
  useEffect(() => {
    if (activeTaskId && activeChatId) {
      setTasks(prev => updateTaskInTree(prev, activeTaskId, t => ({
          ...t,
          chats: t.chats.map(c => c.id === activeChatId ? { ...c, messages } : c)
      })));
    }
  }, [messages, activeTaskId, activeChatId]);

  // Auto-scroll logs
  useEffect(() => {
    if (isLogsExpanded) {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isLogsExpanded]);

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, output]);

  const addLog = (type: 'info' | 'success' | 'error', message: string) => {
    setLogs(prev => [...prev, {
      id: Math.random().toString(36).substr(2, 9),
      timestamp: new Date(),
      type,
      message
    }]);
  };

  // Listen for Main Process Context Menu events (Fallback/Debugging)
  useEffect(() => {
    if (window.electronAPI) {
        window.electronAPI.on('main-process-context-menu', (data: any) => {
            console.log("Renderer received main-process-context-menu event:", data);
            alert("Main Process intercepted Right Click! (Electron Level)");
        });
    }
  }, []);

  const handleGlobalContextMenu = (e: React.MouseEvent) => {
    // Force log to console to verify handler execution
    console.log("Global Context Menu Handler Triggered");

    // 1. Prevent defaults immediately
    e.preventDefault();
    e.stopPropagation();

    // 2. Find closest clickable item
    const target = (e.target as HTMLElement).closest('[data-context-clickable="true"]');
    
    // Debug info about what was clicked
    console.log("Click Target:", e.target);
    console.log("Closest Clickable:", target);

    if (!target) {
        console.log("No clickable target found");
        return;
    }

    // 3. Extract data
    const path = target.getAttribute('data-node-path');
    const isDir = target.getAttribute('data-node-is-dir') === 'true';
    const name = target.getAttribute('data-node-name') || '';

    if (!path) {
        console.log("No path attribute found");
        return;
    }

    // 4. Feedback
    const msg = `Right Click detected on: ${path}`;
    console.log(msg);
    // alert(msg); // Removed alert as it interrupts flow
    addLog('info', msg);

    // 5. Construct partial node for context menu logic
    const node: FileNode = {
        name,
        path,
        isDirectory: isDir,
        children: [] // Not needed for menu
    };

    // 6. Show Menu
    setContextMenu({
        visible: true,
        x: e.clientX,
        y: e.clientY,
        node: node
    });
  };

  // Resize logic for Terminal
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isResizingLeftSidebar) {
        setLeftSidebarWidth(Math.max(200, Math.min(e.clientX, 600)));
      }
      if (isResizingRightSidebar) {
        setRightSidebarWidth(Math.max(250, Math.min(window.innerWidth - e.clientX, 800)));
      }
      if (isResizingLogs && leftSidebarRef.current && isLogsExpanded) {
         const sidebarRect = leftSidebarRef.current.getBoundingClientRect();
         const newHeight = sidebarRect.bottom - e.clientY;
         const maxHeight = sidebarRect.height - 100;
         setLogsHeight(Math.max(100, Math.min(newHeight, maxHeight)));
      }
      if (isResizingTasks) {
          const sidebarRect = leftSidebarRef.current?.getBoundingClientRect();
          if (sidebarRect) {
             const bottomLimit = sidebarRect.bottom - (isLogsExpanded ? logsHeight : 35);
             const newHeight = bottomLimit - e.clientY;
             setTasksHeight(Math.max(100, Math.min(newHeight, sidebarRect.height - 100)));
          }
      }
      if (isResizingTerminal) {
          // Terminal is at the bottom of the center pane
          // Height = WindowHeight - MouseY
          // But we need to account for status bar? No, terminal is inside flex column.
          // Let's rely on simple delta from bottom.
          const newHeight = window.innerHeight - e.clientY;
          setTerminalHeight(Math.max(50, Math.min(newHeight, window.innerHeight - 200)));
      }
    };

    const handleMouseUp = () => {
      setIsResizingLeftSidebar(false);
      setIsResizingRightSidebar(false);
      setIsResizingLogs(false);
      setIsResizingTasks(false);
      setIsResizingTerminal(false);
      document.body.style.cursor = 'default';
      document.body.style.userSelect = 'auto';
    };

    if (isResizingLeftSidebar || isResizingRightSidebar || isResizingLogs || isResizingTasks || isResizingTerminal) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizingLeftSidebar, isResizingRightSidebar, isResizingLogs, isResizingTasks, isResizingTerminal, isLogsExpanded, logsHeight]);

  useEffect(() => {
    // Restore state from localStorage
    const savedMessages = localStorage.getItem('chat_history');
    if (savedMessages) {
      try {
        const parsed = JSON.parse(savedMessages);
        setMessages(parsed.map((m: any) => ({
            ...m,
            timestamp: m.timestamp || Date.now()
        })));
      } catch (e) {
        console.error("Failed to parse chat history", e);
      }
    }

    const savedRootDir = localStorage.getItem('last_root_dir');
    if (savedRootDir) {
      // Defer loading slightly to ensure Electron API is ready if needed, 
      // though typically window.electronAPI is available immediately in preload.
      // But let's check if we need to verify existence first.
      loadDirectory(savedRootDir);
    }
    
    loadModels();

    // Listen for folder selection from Menu
    if (window.electronAPI) {
      window.electronAPI.onFolderSelected((path: string) => {
        loadDirectory(path);
      });
    }
  }, []);

  // Persist messages whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('chat_history', JSON.stringify(messages));
    }
  }, [messages]);

  // Persist rootDir whenever it changes
  useEffect(() => {
    if (rootDir) {
      localStorage.setItem('last_root_dir', rootDir);
    }
  }, [rootDir]);

  const loadModels = async () => {
    setStatus('Loading models...');
    try {
      const fetched = await api.getModels();
      setModels(fetched);
      if (fetched.length > 0) {
        setSelectedModel(fetched[0].id);
        setStatus('Ready');
      } else {
        setStatus('Backend offline or no models found');
      }
    } catch (e) {
      setStatus('Backend offline');
    }
  };

  const loadDirectory = async (path: string) => {
    setRootDir(path);
    try {
      const files = await window.electronAPI.readDir(path);
      
      // Merge function to preserve isOpen state
      const mergeNodes = (newFiles: any[], currentNodes: FileNode[]): FileNode[] => {
          return newFiles.map(f => {
              const existing = currentNodes.find(n => n.path === f.path);
              return {
                  ...f,
                  children: existing?.children || [], // Keep existing children for now, unless we recurse
                  isOpen: existing?.isOpen || false
              };
          });
      };

      setFileTree(prev => mergeNodes(files, prev));
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggleFolder = (node: FileNode) => {
    const updateTree = (nodes: FileNode[]): FileNode[] => {
        return nodes.map(n => {
            if (n.path === node.path) {
                return { ...n, isOpen: !n.isOpen };
            }
            if (n.children) {
                return { ...n, children: updateTree(n.children) };
            }
            return n;
        });
    };
    setFileTree(prev => updateTree(prev));
  };

  // Multi-tab State
  const [openFiles, setOpenFiles] = useState<{path: string, content: string, isUnsaved?: boolean}[]>([]);
  const [activeFile, setActiveFile] = useState<string | null>(null);

  // Helper to open files in browser
  const handleOpenInBrowser = async (filePath: string) => {
    console.log(`Opening in browser: ${filePath}`);
    try {
        if (window.electronAPI && window.electronAPI.openExternal) {
            // Convert file path to file:// URL for consistent browser opening
            let url = filePath;
            if (!url.startsWith('http') && !url.startsWith('file://')) {
                // Ensure Windows paths are handled correctly
                const normalizedPath = filePath.replace(/\\/g, '/');
                url = `file:///${normalizedPath}`;
            }
            console.log(`Normalized URL: ${url}`);
            await window.electronAPI.openExternal(url);
        } else {
             addLog('error', 'Open in Browser not supported in this environment yet.');
             console.error('electronAPI.openExternal is missing');
        }
    } catch (e: any) {
        console.error('Failed to open in browser', e);
        addLog('error', `Failed to open in browser: ${e.message}`);
    }
  };

  // Load tabs from localStorage
  useEffect(() => {
    const savedTabs = localStorage.getItem('open_tabs');
    const savedActive = localStorage.getItem('active_tab');
    const savedTaskId = localStorage.getItem('active_task_id');
    const savedChatId = localStorage.getItem('active_chat_id');

    if (savedTabs) {
        try {
            const parsed = JSON.parse(savedTabs);
            // Normalize paths in loaded tabs immediately to avoid duplicates with new explorer clicks
            const normalized = parsed.map((t: any) => ({
                ...t,
                path: t.path.replace(/\//g, '\\')
            }));
            setOpenFiles(normalized);
        } catch (e) {
            console.error(e);
        }
    }
    if (savedActive) {
        setActiveFile(savedActive.replace(/\//g, '\\'));
    }
    if (savedTaskId) setActiveTaskId(savedTaskId);
    if (savedChatId) setActiveChatId(savedChatId);
  }, []);

  // Save tabs to localStorage
  useEffect(() => {
      localStorage.setItem('open_tabs', JSON.stringify(openFiles));
      if (activeFile) {
          localStorage.setItem('active_tab', activeFile);
      }
      if (activeTaskId) localStorage.setItem('active_task_id', activeTaskId);
      if (activeChatId) localStorage.setItem('active_chat_id', activeChatId);
  }, [openFiles, activeFile, activeTaskId, activeChatId]);

  const handleCloseTab = (path: string, e: React.MouseEvent) => {
      e.stopPropagation();
      const newOpenFiles = openFiles.filter(f => f.path !== path);
      setOpenFiles(newOpenFiles);
      
      if (activeFile === path) {
          if (newOpenFiles.length > 0) {
              handleSelectTab(newOpenFiles[newOpenFiles.length - 1].path);
          } else {
              setActiveFile(null);
              setCurrentFilePath('');
              currentFilePathRef.current = '';
              setCode('// Select a file to view or create a new one');
          }
      }
  };

  const handleSelectTab = (path: string) => {
      const file = openFiles.find(f => f.path === path);
      if (file) {
          setActiveFile(path);
          setCode(file.content);
          setCurrentFilePath(path);
          currentFilePathRef.current = path;
      }
  };

  const handleRefreshModels = async () => {
      addLog('info', 'Refreshing AI Models configuration from Providers...');
      try {
          const res = await fetch(`${API_BASE}/api/models/refresh`, { method: 'POST' });
          if (!res.ok) throw new Error('Failed to refresh models');
          const data = await res.json();
          addLog('success', `Models refreshed: ${data.message || 'Success'}`);
          loadModels();
      } catch (e: any) {
          addLog('error', `Failed to refresh models: ${e.message}`);
      }
  };

  const handleNodeSelect = async (node: FileNode) => {
    // Normalize path to ensure consistency
    const nodePath = node.path.replace(/\//g, '\\');

    if (node.isDirectory) {
      // Lazy load children
      try {
        const children = await window.electronAPI.readDir(nodePath);
        
        // Helper to update tree deeply
        const updateTree = (nodes: FileNode[]): FileNode[] => {
          return nodes.map(n => {
            const nPath = n.path.replace(/\//g, '\\');
            if (nPath === nodePath) {
              // Preserve existing children open states if possible, but here we are loading fresh children
              // But if we just opened it, children are likely not loaded yet or empty.
              // If we are refreshing, we might want to merge.
              
              // Simple merge for children
              const mergedChildren = children.map(c => {
                  const cPath = c.path.replace(/\//g, '\\');
                  const existingChild = n.children?.find(ec => ec.path.replace(/\//g, '\\') === cPath);
                  return {
                      ...c,
                      children: existingChild?.children || [],
                      isOpen: existingChild?.isOpen || false
                  };
              });

              return { ...n, children: mergedChildren, isOpen: true }; // Ensure open
            }
            if (n.children) {
              return { ...n, children: updateTree(n.children) };
            }
            return n;
          });
        };
        setFileTree(prev => updateTree(prev));
      } catch (e) {
        console.error(e);
      }
    } else {
      // Load file content
      try {
        // Check if already open (normalize paths for comparison)
        const existingTab = openFiles.find(f => f.path.replace(/\//g, '\\') === nodePath);
        if (existingTab) {
            setActiveFile(existingTab.path); // Use the stored path
            setCode(existingTab.content);
            setCurrentFilePath(existingTab.path);
            currentFilePathRef.current = existingTab.path;
            return;
        }

        const content = await window.electronAPI.readFile(nodePath);
        
        setOpenFiles(prev => {
            // Double check inside setter to avoid race conditions
            if (prev.find(f => f.path.replace(/\//g, '\\') === nodePath)) return prev;
            return [...prev, { path: nodePath, content }];
        });
        setActiveFile(nodePath);
        setCode(content);
        setCurrentFilePath(nodePath);
        currentFilePathRef.current = nodePath;
      } catch (e) {
        console.error(e);
      }
    }
  };

  // Sync code changes to openFiles state
  const handleEditorChange = (value: string | undefined) => {
    setCode(value || '');
    if (activeFile) {
        setOpenFiles(prev => prev.map(f => 
            f.path === activeFile ? { ...f, content: value || '', isUnsaved: true } : f
        ));
    }
  };


  const generateAIResponse = async (currentMessages: {role: 'user' | 'assistant' | 'system', content: string, timestamp: number}[], userText: string) => {
    let retries = 3;
    let lastError: any = null;
    let success = false;

    while (retries > 0 && !success) {
        try {
            const modelName = models.find(m => m.id === selectedModel)?.name || selectedModel || 'Auto (Best Match)';
            const contextInfo = activeTaskId ? `Task: ${tasks.find(t => t.id === activeTaskId)?.title || 'Unknown'}` : 'Global Context';
            const chatInfo = activeChatId ? `Chat: ${tasks.find(t => t.id === activeTaskId)?.chats.find(c => c.id === activeChatId)?.title || 'Unknown'}` : 'New Session';
            
            const logMsg = retries === 3 
                ? `Sending request to AI Assistant...\nModel: ${modelName}\nContext: ${contextInfo}\n${chatInfo}`
                : `Retrying AI request (${4 - retries}/3)...`;
            
            addLog('info', logMsg);

            // Collect Context from indexed files
            let contextPrompt = "";
            
            // Explicitly force the current task context to be dominant
            const activeTaskTitle = activeTaskId ? tasks.find(t => t.id === activeTaskId)?.title || 'Unknown' : 'Unknown';
            contextPrompt += `CURRENT FOCUS TASK: ${activeTaskTitle}\n`;
            
            if (rootDir) {
                try {
                        // Helper to read file safely
                        const readContext = async (id: string, type: 'task' | 'chat') => {
                            const p = contextManager.getContextPath(id, type);
                            try {
                                return await window.electronAPI.readFile(p);
                            } catch { return null; }
                        };

                        // Active Task Context (Hierarchy)
                        if (activeTaskId) {
                            const taskPath = findTaskPath(tasks, activeTaskId);
                            if (taskPath) {
                                for (const t of taskPath) {
                                    const c = await readContext(t.id, 'task');
                                    if (c) contextPrompt += `\n\n--- Context for Task: ${t.title} ---\n${c}`;
                                }
                            }
                        }
                        // Active Chat Context
                        if (activeChatId) {
                            const c = await readContext(activeChatId, 'chat');
                            if (c) contextPrompt += `\n\n--- Context for Chat ---\n${c}`;
                        }
                } catch (e) { console.error("Error reading context files", e); }
            }

            // Filter out system messages for API context if needed
            const apiMessages = currentMessages.map(m => ({
                role: m.role === 'system' ? 'user' : m.role,
                content: m.content.replace('[SYSTEM_HIDDEN]', '[SYSTEM]') // Expose hidden system messages to AI as normal system messages
            }));
            
            // Use contextPrompt as the primary system context, 
            // BUT we must be careful. 'code' (second arg) is the ACTIVE EDITOR CONTENT.
            // If the user has a file from ANOTHER task open, 'code' might mislead the AI.
            // We should pass 'contextPrompt' combined with 'code' if appropriate, 
            // OR prioritize contextPrompt if it contains the "Task Context".
            
            // Let's pass contextPrompt as the code_context if it's substantial.
            // The api.generateCode takes (prompt, codeContext, ...).
            // We will concatenate contextPrompt + "\n\n--- Active File ---\n" + code.
            
            const fullContext = `${contextPrompt}\n\n--- Active Editor File ---\n${code}`;
            
            const { response: result, model: usedModel } = await api.generateCode(userText, fullContext, selectedModel, apiMessages, rootDir); 
  
            // Auto-Update Context in background (Systematic Management)
            const currentChatId = activeChatId;
            const currentTaskId = activeTaskId;
            
            setTimeout(async () => {
                    console.log(`[ContextUpdate] Triggering for Task: ${currentTaskId}, Chat: ${currentChatId}`);
                    if (currentChatId && currentTaskId) {
                        // Update Chat Context
                        const chatContextPath = contextManager.getContextPath(currentChatId, 'chat');
                        let chatContextContent = "";
                        try { chatContextContent = await window.electronAPI.readFile(chatContextPath); } catch {}
                        
                        // We send the last interaction
                        const recentActivity = `User: ${userText}\nAssistant: ${result}`;
                        const chatUpdated = await contextManager.updateContextWithAI(currentChatId, 'chat', recentActivity, chatContextContent);
                        console.log(`[ContextUpdate] Chat updated: ${chatUpdated}`);
                        if (chatUpdated) {
                            try {
                                const newContent = await window.electronAPI.readFile(chatContextPath);
                                setOpenFiles(prev => prev.map(f => f.path === chatContextPath ? { ...f, content: newContent } : f));
                                if (currentFilePathRef.current === chatContextPath) {
                                    setCode(newContent);
                                }
                            } catch (e) { console.error("Failed to reload chat context", e); }
                        }

                        // Update Task Context (Sync with Chat)
                        const taskContextPath = contextManager.getContextPath(currentTaskId, 'task');
                        let taskContextContent = "";
                        try { taskContextContent = await window.electronAPI.readFile(taskContextPath); } catch {}
                        const taskUpdated = await contextManager.updateContextWithAI(currentTaskId, 'task', recentActivity, taskContextContent);
                        console.log(`[ContextUpdate] Task updated: ${taskUpdated}`);
                        if (taskUpdated) {
                             try {
                                const newContent = await window.electronAPI.readFile(taskContextPath);
                                setOpenFiles(prev => prev.map(f => f.path === taskContextPath ? { ...f, content: newContent } : f));
                                if (currentFilePathRef.current === taskContextPath) {
                                    setCode(newContent);
                                }
                             } catch (e) { console.error("Failed to reload task context", e); }
                        }
                     } else {
                        console.warn("[ContextUpdate] Missing taskId or chatId");
                    }
            }, 2000);

            setMessages(current => {
                const updated = [...current, { role: 'assistant' as const, content: result, model: usedModel, timestamp: Date.now() }];
                
                // CHECK FOR AUTO-SAVE ACTIONS IN THE NEW RESPONSE - DISABLED BY USER REQUEST
                // if (result.includes('**ACCIÓN**') || result.includes('**ACTION**')) {
                //         // Schedule it to run after state update to avoid blocking rendering
                //         setTimeout(() => {
                //             const localRegex = /```(\w*)\n([\s\S]*?)```/g;
                //             let localMatch;
                //             while ((localMatch = localRegex.exec(result)) !== null) {
                //                 const codeContent = localMatch[2];
                //                 const lines = codeContent.split('\n');
                //                 for(let i=0; i<Math.min(lines.length, 3); i++) {
                //                     const line = lines[i].trim();
                //                     const pathMatch = line.match(/^([#\/!<-]+)\s*([\w\.\-\\/]+\.\w+)/);
                //                     if (pathMatch) {
                //                         let filePath = pathMatch[2].trim();
                //                         filePath = filePath.replace(/(\-\->|\*\/)$/, '');
                //                         addLog('info', `Auto-saving detected file: ${filePath}`);
                //                         handleSaveFile(filePath, codeContent);
                //                         break; 
                //                     }
                //                 }
                //             }
                //         }, 100);
                // }
                
                return updated;
            });
            addLog('success', 'AI Assistant responded.');
            success = true;
        } catch (e: any) {
            lastError = e;
            console.error(`Attempt failed: ${e.message}`);
            if (e.message.includes('Failed to fetch') || e.message.includes('NetworkError')) {
                    // Network error, wait and retry
                    await new Promise(resolve => setTimeout(resolve, 2000));
            } else {
                retries = 0; 
            }
            retries--;
        }
    }

    if (!success) {
        const isNetworkError = lastError?.message?.includes('Failed to fetch');
        const friendlyError = isNetworkError 
            ? "Error de conexión con el servidor local. Asegúrate de que el backend está ejecutándose."
            : `No se pudo generar una respuesta. El sistema intentó con los modelos disponibles pero fallaron. Revisa los logs para más detalles.`;

        // Log error to terminal/logs panel
        addLog('error', `AI Request Failed: ${lastError?.message || 'Unknown error'}`);
        
        setMessages(current => [...current, { 
            role: 'assistant', 
            content: `[SYSTEM] ⚠️ ${friendlyError}`, 
            timestamp: Date.now() 
        }]);
    }
    
    setIsGenerating(false);
  };

  const submitMessage = async (text: string, role: 'user' | 'system' = 'user', skipGeneration: boolean = false) => {
    if (!text) return;
    if (!skipGeneration) setIsGenerating(true);
    
    // Add message to history
    const newMessage = { role, content: text, timestamp: Date.now() };
    
    setMessages(prev => {
        const newMessages = [...prev, newMessage];
        // Trigger generation with new history only if not skipped
        if (!skipGeneration) {
            generateAIResponse(newMessages, text);
        }
        return newMessages;
    });
  };

  const handleGenerate = async () => {
    if (!prompt) return;
    
    // Automatically create a chat if none exists for the active task
    if (activeTaskId && !activeChatId) {
        const newChatId = Math.random().toString(36).substr(2, 9);
        const newChat: ChatSession = {
            id: newChatId,
            title: `Chat ${new Date().toLocaleTimeString()}`,
            messages: [],
            createdAt: Date.now()
        };
        
        // We must update tasks state immediately to ensure the chat exists
        setTasks(prev => updateTaskInTree(prev, activeTaskId, t => ({
            ...t,
            chats: [...t.chats, newChat]
        })));
        
        setActiveChatId(newChatId);
        // Note: The state update for activeChatId might not be reflected immediately in the closure below
        // But since we use functional updates in submitMessage and the effect depends on activeChatId,
        // we just need to ensure the effect eventually saves it.
        // However, submitMessage uses `activeChatId`? No, it uses `setMessages`.
        // The effect uses `activeChatId`.
        // We need to wait for render?
        // Let's rely on React batching or pass the ID if needed.
        // Actually, submitMessage doesn't need ID. It updates `messages`.
        // The EFFECT needs ID.
        // If we set ID here, the next render will have ID.
        // And submitMessage will update messages.
        // So the effect will run with New ID and New Messages.
    }

    const userPrompt = prompt;
    setPrompt(''); // Clear input immediately
    await submitMessage(userPrompt);
  };

  const handleRunCommand = async (command: string, autoContinue: boolean = false, saveReport?: string) => {
    try {
      // Clean up the command (remove empty lines, trim)
      let cleanCommand = command.trim();
      
      // Sanitizer: Fix Start-Process -Path to -FilePath (Common AI error)
      if (cleanCommand.includes('Start-Process')) {
         // Replace -Path with -FilePath when used with Start-Process
         cleanCommand = cleanCommand.replace(/(Start-Process[\s\S]*?)-Path/gi, '$1-FilePath');
      }
      
      addLog('info', `Running: ${cleanCommand}`);

      const result = await window.electronAPI.executeCommand(cleanCommand);
      
      let executionReport = '';

      if (result.success) {
        const out = result.output || "(No output)";
        addLog('success', `Executed: ${cleanCommand}\nOutput:\n${out}`);
        alert(`Ejecución Exitosa:\n${out}`);
        
        executionReport = `[SYSTEM] Execution Result for: ${cleanCommand}\nSuccess: True\nOutput:\n${out}`;

        // Refresh file tree if rootDir is set
        if (rootDir) loadDirectory(rootDir);

        // Auto-feed result back to AI
        if (autoContinue) {
             // Disabled auto-advance to prevent loops
        }

      } else {
        addLog('error', `Failed: ${cleanCommand}\nOutput: ${result.output}`);
        alert(`Command Failed:\n${result.output}`);
        
        const rawOutput = result.output || "";
        const isUserCancelled = rawOutput.toLowerCase().includes("cancelled by user");

        if (isUserCancelled) {
          executionReport = `[SYSTEM] ❌ CRITICAL EXECUTION FAILURE for: ${cleanCommand}
SUCCESS_FLAG: False
ERROR_TYPE: USER_CANCELLED
EXIT_CODE: ${result.exitCode || 'Unknown'}
ERROR_OUTPUT:
${rawOutput}

⚠️ URGENT INSTRUCTION FOR AI:
The command was CANCELLED BY THE USER from the confirmation dialog.
This is NOT a bug in the code.
You MUST:
1. Explicitly say that the previous execution was cancelled by the user.
2. Confirm that the current code does NOT need changes due to this cancellation.
3. Offer to re-run the same command with a NEXT_ACTION run_command button.
4. Do NOT say "Perfecto" or "Genial" until a successful run happens after the cancellation.`;
        } else {
          executionReport = `[SYSTEM] ❌ CRITICAL EXECUTION FAILURE for: ${cleanCommand}
SUCCESS_FLAG: False
ERROR_TYPE: EXECUTION_ERROR
EXIT_CODE: ${result.exitCode || 'Unknown'}
ERROR_OUTPUT:
${rawOutput}

⚠️ URGENT INSTRUCTION FOR AI:
The command FAILED. Do NOT say "Perfecto" or "Great". Do NOT proceed to the next step yet.
Your PRIORITY is to ANALYZE this error and FIX the code immediately.
You MUST:
1. Start your answer explicitly acknowledging the error (in Spanish).
2. Explain in 1 frase clara cuál fue la causa probable del fallo.
3. Reescribir el bloque COMPLETO del archivo afectado ya corregido.
4. Decir literalmente: "He corregido el error anterior modificando el fichero [ruta]."
5. Incluir al final un botón NEXT_ACTION de tipo run_command para volver a ejecutar el script corregido.`;
        }
      }

      // Combine with save report if available and send to AI
      // User request: "los resultados han de enviarse, junto con los resultados de guardado, para que los interprete el modelo de ia"
      let finalReport = executionReport;
      if (saveReport) {
          finalReport = `${saveReport}\n\n${executionReport}`;
      }
      
      // Send report to AI context
      await submitMessage(finalReport, 'system');

    } catch (e: any) {
      const msg = `Error executing command: ${e.message}`;
      addLog('error', msg);
      alert(msg);
      await submitMessage(`[SYSTEM] Execution Exception: ${msg}`, 'system');
    }
  };

  const handleSaveFile = async (path: string, content: string) => {
    console.log(`[handleSaveFile] Attempting to save: ${path}`);
    // DEBUG ALERT
    alert(`DEBUG: Iniciando guardado de: ${path}`); 
    try {
       // Normalize path slashes for Windows
       const normalizedPath = path.replace(/\//g, '\\');
       
       // Join with rootDir if path is relative
       let fullPath = normalizedPath;
       if (rootDir && !normalizedPath.startsWith(rootDir) && !normalizedPath.includes(':')) {
           // Remove leading slashes/backslashes from path before joining
           let cleanPath = normalizedPath.replace(/^[\\\/]+/, '');

           // If the path starts with the project directory name, remove it to avoid nesting
           // Make check robust against different slash types
           const rootDirName = rootDir.split('\\').pop();
           
           if (rootDirName) {
                // Normalize both to forward slashes for comparison
                const normClean = cleanPath.replace(/\\/g, '/').toLowerCase();
                const normRoot = rootDirName.toLowerCase();
                
                if (normClean.startsWith(normRoot + '/')) {
                    cleanPath = cleanPath.substring(rootDirName.length + 1);
                    // Clean up any remaining leading slash
                    cleanPath = cleanPath.replace(/^[\\\/]+/, '');
                }
           }

           fullPath = `${rootDir}\\${cleanPath}`;
       }
       
       console.log(`[handleSaveFile] Resolved path: ${fullPath}`);

       // Ensure parent directory exists
       const parentDir = fullPath.substring(0, fullPath.lastIndexOf('\\'));
       if (parentDir && parentDir !== rootDir) {
           const exists = await window.electronAPI.exists(parentDir); 
           if (!exists) {
               console.log(`[handleSaveFile] Creating directory: ${parentDir}`);
               await window.electronAPI.createDir(parentDir);
           }
       }

       let finalContent = content;
       if (fullPath.toLowerCase().endsWith('.py')) {
           const lines = finalContent.split('\n');
           let firstNonEmptyFixed = false;
           for (let i = 0; i < lines.length; i++) {
               if (!firstNonEmptyFixed && lines[i].trim() !== '') {
                   lines[i] = lines[i].replace(/^\s+/, '');
                   firstNonEmptyFixed = true;
               }
           }
           finalContent = lines.join('\n');
       }

       await window.electronAPI.writeFile(fullPath, finalContent);
       
       // Update UI
       addLog('success', `File saved: ${path}`);
       setStatus('saved'); // For local button state
       alert(`Guardado correctamente en:\n${fullPath}`);
       
       // Refresh File Explorer
       if (rootDir) {
           loadDirectory(rootDir);
       }
    } catch (e: any) {
      console.error("[handleSaveFile] Error:", e);
      const errorMsg = `Failed to save file: ${e.message}`;
      addLog('error', errorMsg);
      alert(errorMsg); // Force visual feedback
      throw e; // Propagate to caller
    }
  };

  // Keep latest handleSaveFile in a ref for the editor command
  const handleSaveFileRef = React.useRef(handleSaveFile);
  useEffect(() => {
    handleSaveFileRef.current = handleSaveFile;
  }, [handleSaveFile]);

  // REMOVED AUTO-SAVE EFFECT TO PREVENT HISTORY EXECUTION LOOP
  
  // Auto-scroll terminal
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [terminalOutput, isTerminalOpen]);

  const handleTerminalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!terminalInput.trim()) return;
    
    const cmd = terminalInput.trim();
    setTerminalInput(''); // Clear input
    
    // Append command to output
    setTerminalOutput(prev => prev + `\n> ${cmd}\n`);
    
    try {
        const result = await window.electronAPI.executeCommand(cmd);
        if (result.success) {
            setTerminalOutput(prev => prev + `${result.output}\n`);
        } else {
            setTerminalOutput(prev => prev + `Error: ${result.output}\n`);
        }
    } catch (err: any) {
        setTerminalOutput(prev => prev + `Error: ${err.message}\n`);
    }
  };

  const handleEditorDidMount = (editor: any, monaco: any) => {
    // Bind Ctrl+S (and Cmd+S) to save
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      const path = currentFilePathRef.current;
      if (path) {
        handleSaveFileRef.current(path, editor.getValue());
      } else {
        // Fallback: If no file is selected (e.g. just started), we can't save to a file yet.
        addLog('error', 'No file open. Please select a file to save.');
      }
    });
  };

  // Helper to extract title from code block
  const getCodeBlockTitle = (code: string, lang: string) => {
    const lines = code.split('\n');
    for (let i = 0; i < Math.min(lines.length, 3); i++) {
      const line = lines[i].trim();
      // Check for comments like # filename, // filename, <!-- filename, /* filename
      // Regex updated to include forward slash in path and handle trailing comment markers, and CSS style comments
      if (line.match(/^([#\/!<\-\*]+)\s*[\w\.\-\\/]+\.\w+/)) {
         let title = line.replace(/^([#\/!<\-\*]+)\s*/, '');
         // Remove trailing comment markers like --> or */
         title = title.replace(/(\-\->|\*\/)$/, '');
         return title.trim();
      }
      // Fallback: detect comentarios tipo //cibrseg/monitor_resources.py (sin espacio)
      if (line.match(/^\/\/[\w\.\-\\/]+\.\w+/)) {
         let title = line.replace(/^\/\//, '');
         return title.trim();
      }
    }
    // If no comment, check if lang is a filename extension or typical format
    if (lang.includes('.')) return lang;
    
    return `${lang} Code`;
  };
 
 // Sanitize code content by removing leading filename/comment lines
 const sanitizeCodeContent = (code: string, lang: string) => {
   const lines = code.split('\n');
   let start = 0;
   for (let i = 0; i < Math.min(lines.length, 3); i++) {
     const line = lines[i].trim();
     // Remove leading filename hint comments (e.g., "# path/file.py", "// path/file.py", "<!-- path/file.py -->", "/* path/file.py */")
     if (line.match(/^([#\/!<\-\*]+)\s*[\w\.\-\\/]+\.\w+/)) {
       start = i + 1;
       continue;
     }
     // Remove standalone markers like "Save"
     if (line.toLowerCase() === 'save') {
       start = i + 1;
       continue;
     }
     break;
   }
   return lines.slice(start).join('\n');
 };

  // Code Block Component with internal state for feedback
  const CodeBlock = ({ content, lang, onRun, onSave }: { content: string, lang: string, onRun: (code: string, autoContinue?: boolean, saveReport?: string) => void, onSave: (path: string, content: string) => void }) => {
  const [status, setStatus] = useState<'idle' | 'running' | 'saved'>('idle');
  
  const title = getCodeBlockTitle(content, lang);
  // Update runnable check to include Python and Node
  const isShell = lang === 'powershell' || lang === 'bash' || lang === 'sh' || lang === 'cmd';
  const isScript = (lang === 'python' || lang === 'py' || lang === 'javascript' || lang === 'js' || lang === 'typescript' || lang === 'ts') && title.match(/[\w\.\-\\/]+\.\w+/);
  
  const isRunnable = isShell || isScript;
  
  // Allow forward slashes in path for isSaveable check
  const isSaveable = title.match(/[\w\.\-\\/]+\.\w+/);

  const handleRunClick = async () => {
    setStatus('running');
    let saveReport = '';

    try {
        // Auto-save before running if possible
        if (isSaveable) {
            try {
                // Ensure we save the current content before running
                await onSave(title, sanitizeCodeContent(content, lang));
                saveReport = `[SYSTEM] Auto-Save: Successfully saved ${title} before execution.`;
            } catch (e: any) {
                console.error("Auto-save failed before run:", e);
                // We continue trying to run even if save fails, though it might fail.
                saveReport = `[SYSTEM] Auto-Save: Failed to save ${title} before execution. Error: ${e.message}`;
            }
        }

        if (isScript) {
            // For scripts, we construct the execution command
            // We assume the file is saved relative to root or absolute
             
             // Normalize script path logic same as handleSaveFile to avoid nesting issues
             // If the title includes the project folder name as prefix, strip it
             let scriptPath = title;
             let absolutePath = title; // Fallback

             if (rootDir) {
                 const rootDirName = rootDir.split('\\').pop();
                 if (rootDirName) {
                     const normTitle = title.replace(/\\/g, '/').toLowerCase();
                     const normRoot = rootDirName.toLowerCase();
                     
                     if (normTitle.startsWith(normRoot + '/')) {
                         // Strip root dir name from title
                         scriptPath = title.substring(rootDirName.length + 1);
                          // Clean up any remaining leading slash
                         scriptPath = scriptPath.replace(/^[\\\/]+/, '');
                     }
                 }
                 // Use absolute path to ensure execution works regardless of CWD
                 absolutePath = `${rootDir}\\${scriptPath}`;
             }
             
             let cmd = '';
             if (lang === 'python' || lang === 'py') {
                 cmd = rootDir ? `cd "${rootDir}"; python "${scriptPath}"` : `python "${absolutePath}"`;
             }
             if (lang === 'javascript' || lang === 'js') {
                 cmd = rootDir ? `cd "${rootDir}"; node "${scriptPath}"` : `node "${absolutePath}"`;
             }
             if (lang === 'typescript' || lang === 'ts') {
                 cmd = rootDir ? `cd "${rootDir}"; ts-node "${scriptPath}"` : `ts-node "${absolutePath}"`;
             }
 
             addLog('info', `Prepared command: ${cmd}`);
             alert(`Ejecutando:\n${cmd}`);
             
             await onRun(cmd, false, saveReport);
        } else {
            // For shell, run content directly
            await onRun(content, false, saveReport);
        }
    } finally {
        setTimeout(() => setStatus('idle'), 2000);
    }
  };

  const handleSaveClick = async () => {
    // DEBUG: Alert to confirm button click and params
    alert(`DEBUG: Click en Save.\nTitle: ${title}\nRootDir: ${rootDir}`);
    
    setStatus('running'); // Use running state for saving visual feedback
    try {
        const sanitized = sanitizeCodeContent(content, lang);
        await onSave(title, sanitized);
        setStatus('saved');
        // Keep 'saved' status to prevent double-saving. User can collapse section if needed.
    } catch (e: any) {
        setStatus('idle');
        alert(`Failed to save: ${e.message}`);
    }
  };

  const actionButtons = (
      <div className="flex gap-2 items-center">
          {isSaveable && (
            <button 
                onClick={handleSaveClick}
                disabled={status === 'running' || status === 'saved'}
                className={`${status === 'saved' ? 'bg-green-600' : status === 'running' ? 'bg-yellow-600' : 'bg-blue-600 hover:bg-blue-500'} text-white px-2 py-0.5 rounded flex items-center gap-1 transition-colors text-xs`}
                title={`Save to ${title}`}
            >
                <File size={10} /> {status === 'saved' ? 'Saved' : status === 'running' ? 'Saving...' : 'Save'}
            </button>
          )}
          {isRunnable && (
            <button 
                onClick={handleRunClick}
                disabled={status === 'running'}
                className={`${status === 'running' ? 'bg-yellow-600' : 'bg-green-600 hover:bg-green-500'} text-white px-2 py-0.5 rounded flex items-center gap-1 transition-colors text-xs`}
                title="Execute in terminal"
            >
                <Play size={10} /> {status === 'running' ? 'Running...' : 'Run'}
            </button>
          )}
      </div>
  );

  return (
    <CollapsibleSection title={title} defaultOpen={false} actionButton={actionButtons}>
       <pre className="text-xs overflow-x-auto text-green-400 font-mono scrollbar-thin scrollbar-thumb-gray-700 whitespace-pre-wrap break-all">
         {content}
       </pre>
    </CollapsibleSection>
  );
};

  // Render output with "Run" buttons for code blocks
  const renderMessageContent = (content: string) => {
    if (!content) return null;
    
    // Regex permissive: capture any code block
    // 1. Starts with ```
    // 2. Optional language identifier (alphanumeric, +, -, .) OR immediately starts with content if space/newline missing
    // 3. Content (non-greedy)
    // 4. Ends with ```
    const parts = content.split(/(```(?:[\w\+\-\.]*)?[\s\S]*?```)/g);
    
    // Filter empty parts
    const filteredParts = parts.filter(p => p.trim() !== '');

    return filteredParts.map((part, index) => {
      if (part.startsWith('```')) {
        // Try to match standard format: ```lang\ncode\n```
        let match = part.match(/```([\w\+\-\.]*)\n([\s\S]*?)```/);
        
        // Fallback for malformed blocks (e.g. ```// path/to/file or ``` code without lang)
        if (!match) {
             const rawContent = part.slice(3, -3); // remove ``` delimiters
             // Check if first line looks like a file path comment immediately after backticks
             const firstLineEnd = rawContent.indexOf('\n');
             const firstLine = firstLineEnd !== -1 ? rawContent.substring(0, firstLineEnd) : rawContent;
             
             if (firstLine.trim().startsWith('//') || firstLine.trim().startsWith('#')) {
                 // It's likely a malformed block like ```// file.py
                 const inferredLang = firstLine.includes('.py') ? 'python' : 
                                      firstLine.includes('.js') ? 'javascript' : 
                                      firstLine.includes('.ts') ? 'typescript' : '';
                 const codeContent = rawContent; // Keep the comment line as it is part of the file usually
                 return <CodeBlock key={index} content={codeContent} lang={inferredLang} onRun={handleRunCommand} onSave={handleSaveFile} />;
             } else {
                 // Just generic code
                 return <CodeBlock key={index} content={rawContent} lang="" onRun={handleRunCommand} onSave={handleSaveFile} />;
             }
        }

        if (match) {
          const lang = match[1];
          const codeContent = match[2];
          return <CodeBlock key={index} content={codeContent} lang={lang} onRun={handleRunCommand} onSave={handleSaveFile} />;
        }
      }
      return <div key={index} className="whitespace-pre-wrap">{part}</div>;
    });
  };

  // Helper for Logs
  const renderLogEntry = (log: LogEntry) => {
    if (!log || !log.message) return null;
    const lines = log.message.split('\n');
    const titleLine = lines[0] || 'Log Entry';
    const rest = log.message;

    return (
      <CollapsibleSection 
        key={log.id} 
        title={`${new Date(log.timestamp).toLocaleTimeString()} - ${titleLine}`} 
        defaultOpen={false}
      >
        <div className="flex items-center gap-2 mb-2">
           {log.type === 'success' && <CheckCircle size={12} className="text-green-500" />}
           {log.type === 'error' && <AlertCircle size={12} className="text-red-500" />}
           {log.type === 'info' && <Info size={12} className="text-blue-500" />}
           <span className={`uppercase font-bold text-xs ${
             log.type === 'success' ? 'text-green-500' : 
             log.type === 'error' ? 'text-red-500' : 'text-blue-500'
           }`}>{log.type}</span>
        </div>
        <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap break-all">
          {rest}
        </pre>
      </CollapsibleSection>
    );
  };

  const activeTaskPath = activeTaskId ? findTaskPath(tasks, activeTaskId) : null;
  const activeTask = activeTaskPath ? activeTaskPath[activeTaskPath.length - 1] : null;
  const activeChat = activeTask?.chats.find(c => c.id === activeChatId);
  const tokenCount = messages.reduce((acc, m) => acc + Math.ceil(m.content.length / 4), 0);
  const taskHierarchyDisplay = activeTaskPath ? activeTaskPath.map(t => t.title).join(' > ') : '';

  // Helper to extract code blocks from message content
  const extractCodeFromMessage = (content: string, filename: string): string | null => {
      // Look for code blocks
      const parts = content.split(/```/);
      for (let i = 0; i < parts.length; i++) {
          const part = parts[i];
          // Simple heuristic: check if the filename appears shortly before the block or inside the first line
          // This is tricky. Let's look at the "Save" block format the AI uses.
          // Usually: "filename\n Save \n ```...```"
          // Or just look for the content.
          
          // Better approach: Since we parse the message in renderMessageContent, we can't easily access the React components state.
          // But we can parse raw content.
      }
      return null;
  };

  const handleExecuteNextAction = async (action: { type: string, content: string, label?: string }, messageContent?: string) => {
      // DEBUG: Verify action
      console.log("Executing Next Action:", action);
      alert(`DEBUG: NextAction Triggered\nType: ${action.type}\nContent: ${action.content}`);

      try {
          if (action.type === 'run_command') {
              // AUTO-SAVE LOGIC FOR NEXT_ACTION
              let targetFile = '';
              let saveReport = '';
              const cmd = action.content;
              
              // Identify target file from command
              const scriptMatch = cmd.match(/(?:python|node|ts-node)\s+["']?([^"'\s]+)["']?/);
              if (scriptMatch) {
                  targetFile = scriptMatch[1];
              } else if (cmd.includes('pip install') && cmd.includes('-r')) {
                   const reqMatch = cmd.match(/-r\s+["']?([^"'\s]+)["']?/);
                   if (reqMatch) targetFile = reqMatch[1];
              } else if (cmd.includes('npm install') || cmd.includes('yarn install') || cmd === 'npm i') {
                   targetFile = 'package.json';
              }

              // Si el target parece un script python sin extensión, intenta normalizar a .py
              if (targetFile && !targetFile.includes('.') && cmd.trim().toLowerCase().startsWith('python')) {
                  targetFile = `${targetFile}.py`;
              }

              if (targetFile && messageContent) {
                   // Search for matching code block using robust regex
                   const blocks = Array.from(messageContent.matchAll(/```(?:([\w\+\-\.]*)\s+)?([\s\S]*?)```/g));
                   
                   for (const block of blocks) {
                       let lang = block[1] || '';
                       let code = block[2];
                       
                       // Handle malformed blocks where first line is comment (e.g. ```// file.py)
                       if (!lang && (code.trim().startsWith('//') || code.trim().startsWith('#'))) {
                            const firstLineEnd = code.indexOf('\n');
                            const firstLine = firstLineEnd !== -1 ? code.substring(0, firstLineEnd) : code;
                            if (firstLine.includes('.py')) lang = 'python';
                            else if (firstLine.includes('.js')) lang = 'javascript';
                            else if (firstLine.includes('.ts')) lang = 'typescript';
                       }

                       const blockTitle = getCodeBlockTitle(code, lang);
                       
                       // Normalize paths for comparison (handle Windows backslashes and case)
                       const normTarget = targetFile.replace(/\\/g, '/').toLowerCase();
                       const normTitle = blockTitle.replace(/\\/g, '/').toLowerCase();
                       
                       console.log(`Checking match: Block '${normTitle}' vs Target '${normTarget}'`);

                       // Check for match
                       // 1. Title matches (loose check)
                       if (blockTitle && (normTitle === normTarget || normTarget.endsWith('/' + normTitle) || normTitle.endsWith('/' + normTarget) || normTarget.endsWith(normTitle) || normTitle.endsWith(normTarget))) {
                            try {
                                await handleSaveFile(targetFile, sanitizeCodeContent(code, lang));
                                saveReport = `[SYSTEM] Auto-Save: Successfully saved ${targetFile} before execution.`;
                            } catch (e: any) {
                                saveReport = `[SYSTEM] Auto-Save: Failed to save ${targetFile} before execution. Error: ${e.message}`;
                            }
                            break; 
                       }
                       
                       // 2. Special case for package.json (since JSON has no comments)
                       if (targetFile === 'package.json' && (lang === 'json' || blockTitle === 'package.json')) {
                            // Check if content looks like package.json
                            if (code.includes('"name":') || code.includes('"dependencies":')) {
                                try {
                                    await handleSaveFile('package.json', sanitizeCodeContent(code, lang));
                                    saveReport = `[SYSTEM] Auto-Save: Successfully saved package.json before execution.`;
                                } catch (e: any) {
                                    saveReport = `[SYSTEM] Auto-Save: Failed to save package.json before execution. Error: ${e.message}`;
                                }
                                break;
                            }
                       }

                       // 3. Special case for requirements.txt
                       if (targetFile === 'requirements.txt' && (lang === '' || lang === 'txt' || lang === 'text')) {
                            try {
                                await handleSaveFile('requirements.txt', sanitizeCodeContent(code, lang));
                                saveReport = `[SYSTEM] Auto-Save: Successfully saved requirements.txt before execution.`;
                            } catch (e: any) {
                                saveReport = `[SYSTEM] Auto-Save: Failed to save requirements.txt before execution. Error: ${e.message}`;
                            }
                            break;
                       }
                   }
              }

              // Validación de existencia del archivo antes de ejecutar
              if (targetFile && rootDir && cmd.toLowerCase().startsWith('python')) {
                  let candidatePath = targetFile.replace(/\//g, '\\');
                  const rootName = rootDir.split('\\').pop() || '';
                  const lowerCandidate = candidatePath.replace(/\\/g, '/').toLowerCase();
                  if (rootName && lowerCandidate.startsWith(rootName.toLowerCase() + '/')) {
                      candidatePath = candidatePath.substring(rootName.length + 1).replace(/^[\\\/]+/, '');
                  }
                  const fullPath = `${rootDir}\\${candidatePath}`;
                  
                  // Ensure parent folder exists (User Feedback Fix)
                  const folderPath = fullPath.substring(0, fullPath.lastIndexOf('\\'));
                  if (folderPath && folderPath !== rootDir) {
                       try {
                           const folderExists = await window.electronAPI.exists(folderPath);
                           if (!folderExists) {
                               addLog('info', `[Auto-Fix] Folder not found for execution, creating: ${folderPath}`);
                               await window.electronAPI.createDir(folderPath);
                           }
                       } catch (e: any) {
                           console.error("Failed to auto-create folder", e);
                       }
                  }

                  try {
                      const exists = await window.electronAPI.exists(fullPath);
                      if (!exists) {
                          const msg = `El asistente quiere ejecutar "${cmd}", pero el archivo esperado no existe:\n${fullPath}\n\nRevisa que se haya generado y guardado el código (botón Save) o pide al asistente que cree el archivo correctamente.`;
                          addLog('error', msg);
                          alert(msg);
                          return;
                      }
                  } catch (e: any) {
                      const msg = `No se ha podido verificar la existencia del archivo antes de ejecutar.\nDetalle: ${e.message}`;
                      addLog('error', msg);
                      alert(msg);
                      return;
                  }
              }

              let finalCommand = action.content;
              if (rootDir) {
                  const m = finalCommand.match(/^(python|node|ts-node)\s+(.+)$/i);
                  if (m) {
                      const interpreter = m[1];
                      let rest = m[2].trim();
                      let scriptPart = "";
                      let argsPart = "";
                      if (rest.startsWith('"') || rest.startsWith("'")) {
                          const quote = rest[0];
                          const closingIndex = rest.indexOf(quote, 1);
                          if (closingIndex !== -1) {
                              scriptPart = rest.substring(1, closingIndex);
                              argsPart = rest.substring(closingIndex + 1).trim();
                          } else {
                              scriptPart = rest.substring(1);
                          }
                      } else {
                          const firstSpace = rest.indexOf(" ");
                          if (firstSpace === -1) {
                              scriptPart = rest;
                          } else {
                              scriptPart = rest.substring(0, firstSpace);
                              argsPart = rest.substring(firstSpace + 1).trim();
                          }
                      }
                      let p = scriptPart.replace(/\//g, '\\').replace(/^[\\\/]+/, '');
                      const rootName = rootDir.split('\\').pop() || '';
                      const lowerP = p.replace(/\\/g, '/').toLowerCase();
                      if (rootName && lowerP.startsWith(rootName.toLowerCase() + '/')) {
                          p = p.substring(rootName.length + 1).replace(/^[\\\/]+/, '');
                      }
                      const abs = `${rootDir}\\${p}`;
                      finalCommand = `${interpreter} "${abs}"${argsPart ? " " + argsPart : ""}`;
                  } else if (finalCommand.includes('pip install') && finalCommand.includes('-r')) {
                      const req = finalCommand.match(/-r\s+["']?([^"' \t]+)["']?/);
                      if (req) {
                          let p = req[1].replace(/\//g, '\\').replace(/^[\\\/]+/, '');
                          const rootName = rootDir.split('\\').pop() || '';
                          const lowerP = p.replace(/\\/g, '/').toLowerCase();
                          if (rootName && lowerP.startsWith(rootName.toLowerCase() + '/')) {
                              p = p.substring(rootName.length + 1).replace(/^[\\\/]+/, '');
                          }
                          const abs = `${rootDir}\\${p}`;
                          finalCommand = finalCommand.replace(req[0], `-r "${abs}"`);
                      }
                  }
              }
              
              addLog('info', `Prepared command: ${finalCommand}`);
              alert(`Ejecutando:\n${finalCommand}`);
              await handleRunCommand(finalCommand, false, saveReport);
          } else if (action.type === 'open_file') {
              const name = action.content.split(/[\\/]/).pop() || action.content;
              // We need to resolve full path if possible, but handleNodeSelect usually takes what's in the tree.
              // If it's a relative path from AI, we might need to join with rootDir.
              let fullPath = action.content;
              if (rootDir && !action.content.includes(':') && !action.content.startsWith('/')) {
                   fullPath = `${rootDir}\\${action.content.replace(/\//g, '\\')}`;
              }
              const node = { path: fullPath, name, isDirectory: false };
              await handleNodeSelect(node);
          } else if (action.type === 'browser') {
              await handleOpenInBrowser(action.content);
          } else if (action.type === 'chat_message') {
              await submitMessage(action.content);
          } else {
              addLog('error', `Unknown action type: ${action.type}`);
          }
      } catch (e: any) {
          addLog('error', `Action failed: ${e.message}`);
          alert(`Action Failed: ${e.message}`);
      }
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-gray-900 text-white overflow-hidden font-sans">
      {/* Header */}
      <header className="h-12 bg-gray-800 border-b border-gray-700 flex items-center px-4 justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="text-blue-400" />
          <span className="font-bold">AI Code Lab</span>
          <span className="text-xs text-gray-500 ml-2">({status})</span>
        </div>
        <div className="flex items-center gap-2">
          {activeTaskId && (
            <button 
                className="p-1 px-3 bg-purple-600 hover:bg-purple-500 rounded text-xs font-bold flex items-center gap-1"
                title="Open Super Optimized Schematic Summary (Long Term Memory)"
                onClick={() => handleOpenContext(activeTaskId)}
            >
                <File size={12} />
                CONTEXT
            </button>
          )}
          <select 
            className="bg-gray-700 border border-gray-600 rounded text-xs p-1 max-w-[200px]"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
          >
            {models.map(m => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
          <button className="p-2 hover:bg-gray-700 rounded" title="Reload Models" onClick={loadModels}>
            <RefreshCw size={16} />
          </button>
          <button className="p-2 hover:bg-gray-700 rounded text-yellow-500" title="Sync Models with Providers (Download & Update)" onClick={handleRefreshModels}>
            <RefreshCw size={16} className={isGenerating ? 'animate-spin' : ''} />
          </button>
          <button className="p-2 hover:bg-gray-700 rounded" title="Settings">
            <Settings size={18} />
          </button>
        </div>
      </header>



      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar: File Explorer & Logs */}
        <div 
          ref={leftSidebarRef}
          className="bg-gray-800 border-r border-gray-700 flex flex-col shrink-0 relative"
          style={{ width: leftSidebarWidth }}
        >
           {/* File Explorer Section (Flex-1) */}
          <div className="flex flex-col flex-1 min-h-0">
             <div className="p-2 font-semibold text-xs text-gray-400 uppercase tracking-wider bg-gray-900 shrink-0 flex justify-between items-center">
               <span>Explorer {rootDir ? `- ${rootDir.split('\\').pop()}` : ''}</span>
               {rootDir && (
                   <button 
                       onClick={() => refreshDir(rootDir)} 
                       className="hover:text-white text-gray-500 transition-colors"
                       title="Refresh Explorer"
                   >
                       <RefreshCw size={12} />
                   </button>
               )}
             </div>
             <div 
                 className="flex-1 overflow-y-auto overflow-x-auto p-2"
                 // onContextMenuCapture={handleGlobalContextMenu} // REMOVED to avoid blocking events
             >
               {!rootDir && (
                <div className="text-center text-gray-500 mt-4 text-sm">
                  <p>No folder opened.</p>
                  <button 
                    className="mt-2 text-blue-400 hover:underline"
                    onClick={async () => {
                      const path = await window.electronAPI.openFolder();
                      if (path) loadDirectory(path);
                    }}
                  >
                    Open Folder
                  </button>
                </div>
              )}
               {fileTree.map(node => (
                 <FileTreeItem 
                 key={node.path} 
                 node={node} 
                 onSelect={handleNodeSelect} 
                 onToggle={handleToggleFolder} 
                 onOpenMenu={openContextMenu}
                 onDragStart={onDragStart}
                 onDragOver={onDragOver}
                 onDrop={onDrop}
               />
               ))}
             </div>
          </div>


          {/* Resizer Handle (Explorer vs TaskManager) */}
          <div 
            className="h-1 bg-gray-700 hover:bg-blue-500 cursor-row-resize shrink-0 transition-colors z-10"
            onMouseDown={() => {
              setIsResizingTasks(true);
              document.body.style.cursor = 'row-resize';
            }}
          />

          {/* Task Manager Section */}
          <div style={{ height: tasksHeight }} className="flex flex-col shrink-0 min-h-0">
            <TaskManager 
                tasks={tasks}
                activeTaskId={activeTaskId}
                activeChatId={activeChatId}
                onAddTask={handleAddTask}
                onDeleteTask={handleDeleteTask}
                onSelectTask={handleSelectTask}
                onUpdateTaskStatus={handleUpdateTaskStatus}
                onToggleTaskExpanded={handleToggleTaskExpanded}
                onAddChat={handleAddChat}
                onSelectChat={handleSelectChat}
                onDeleteChat={handleDeleteChat}
                onExportChat={handleExportChat}
                onOpenContext={handleOpenContext}
                onMoveTask={handleMoveTask}
            />
          </div>

          {/* Resizer Handle (TaskManager vs Logs) - Only when Logs expanded */}
          {isLogsExpanded && (
            <div 
               className="h-1 bg-gray-700 hover:bg-blue-500 cursor-row-resize shrink-0 transition-colors z-10"
               onMouseDown={() => {
                 setIsResizingLogs(true);
                 document.body.style.cursor = 'row-resize';
               }}
            />
          )}

          {/* Logs Section */}
           <div 
             className="flex flex-col shrink-0 transition-all duration-75 ease-out border-t border-gray-700"
             style={{ height: isLogsExpanded ? logsHeight : 'auto' }}
           >
              <div 
                className="p-2 font-semibold text-xs text-gray-400 uppercase tracking-wider bg-gray-900 shrink-0 flex items-center justify-between cursor-pointer hover:bg-gray-800"
                onClick={() => setIsLogsExpanded(!isLogsExpanded)}
                title={isLogsExpanded ? "Minimize Logs" : "Maximize Logs"}
              >
                <div className="flex items-center gap-2">
                    <Terminal size={12} />
                    <span>Logs & History</span>
                </div>
                {isLogsExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </div>
              
              {isLogsExpanded && (
                  <div className="flex-1 p-2 overflow-y-auto bg-black font-mono text-xs">
                     {logs.length === 0 && (
                       <div className="text-gray-600 italic">No logs yet. Run commands to see history.</div>
                     )}
                     {logs.map(log => renderLogEntry(log))}
                     <div ref={logsEndRef} />
                  </div>
              )}
           </div>

           {/* Left Sidebar Resizer Handle (Vertical) */}
           <div 
             className="absolute top-0 right-0 w-1 h-full hover:bg-blue-500 cursor-col-resize z-50 translate-x-1/2 opacity-0 hover:opacity-100"
             onMouseDown={() => {
               setIsResizingLeftSidebar(true);
               document.body.style.cursor = 'col-resize';
             }}
           />
        </div>

        {/* Editor Area */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#1e1e1e]">
           {/* Tab Bar */}
           <div className="flex items-center bg-[#1e1e1e] border-b border-gray-700 overflow-x-auto no-scrollbar">
              {openFiles.map(file => (
                  <div 
                      key={file.path}
                      className={`
                          group flex items-center gap-2 px-3 py-2 text-xs cursor-pointer border-r border-gray-700 min-w-[120px] max-w-[200px] shrink-0 relative
                          ${activeFile === file.path ? 'bg-[#1e1e1e] text-white border-t-2 border-t-blue-500' : 'bg-[#2d2d2d] text-gray-400 hover:bg-[#252525]'}
                      `}
                      onClick={() => handleSelectTab(file.path)}
                  >
                      <File size={12} className={activeFile === file.path ? 'text-blue-400' : 'text-gray-500'} />
                      <span className="truncate flex-1" title={file.path}>{file.path.split('\\').pop()?.split('/').pop()}</span>
                      {file.isUnsaved && <span className="w-2 h-2 rounded-full bg-white/50" title="Unsaved changes"></span>}
                      <button 
                          onClick={(e) => handleCloseTab(file.path, e)}
                          className="hover:text-red-400 p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-gray-700 transition-opacity"
                      >
                          ×
                      </button>
                  </div>
              ))}
          </div>

          <div className="flex-1 relative">
            <Editor
            height="100%"
            defaultLanguage="python"
            theme="vs-dark"
            value={code}
            onChange={(val) => setCode(val || '')}
            onMount={handleEditorDidMount}
            options={{
              minimap: { enabled: true },
              fontSize: 14,
              padding: { top: 16 },
            }}
          />
          </div>

          {/* Terminal Resizer Handle */}
          <div 
             className="h-1 bg-gray-700 hover:bg-blue-500 cursor-row-resize shrink-0 transition-colors z-10"
             onMouseDown={() => {
               setIsResizingTerminal(true);
               document.body.style.cursor = 'row-resize';
             }}
          />

          {/* Terminal Panel */}
          <div style={{ height: isTerminalOpen ? terminalHeight : 30 }} className="flex flex-col shrink-0 bg-[#1e1e1e] border-t border-gray-700 transition-all duration-75 ease-out">
              <div 
                className="p-1 px-2 font-semibold text-xs text-gray-400 uppercase tracking-wider bg-gray-900 shrink-0 flex items-center justify-between cursor-pointer hover:bg-gray-800"
                onClick={() => setIsTerminalOpen(!isTerminalOpen)}
              >
                 <div className="flex items-center gap-2">
                    <Terminal size={12} />
                    <span>Terminal</span>
                 </div>
                 {isTerminalOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </div>
              
              {isTerminalOpen && (
                  <div className="flex-1 flex flex-col min-h-0 bg-black p-2 font-mono text-xs">
                      <div className="flex-1 overflow-y-auto mb-2 text-gray-300 whitespace-pre-wrap">
                          {terminalOutput}
                          <div ref={terminalEndRef} />
                      </div>
                      <form onSubmit={handleTerminalSubmit} className="flex gap-2 shrink-0">
                          <span className="text-green-500 font-bold">{'>'}</span>
                          <input 
                              type="text" 
                              className="flex-1 bg-transparent border-none outline-none text-white focus:ring-0"
                              value={terminalInput}
                              onChange={(e) => setTerminalInput(e.target.value)}
                              placeholder="Type command..."
                          />
                      </form>
                  </div>
              )}
          </div>
        </div>

        {/* Right Sidebar: AI Assistant */}
        <div 
          ref={rightSidebarRef}
          className="bg-gray-800 border-l border-gray-700 flex flex-col shrink-0 relative"
          style={{ width: rightSidebarWidth }}
        >
           {/* Right Sidebar Resizer Handle (Vertical - Left Edge) */}
           <div 
             className="absolute top-0 left-0 w-1 h-full hover:bg-blue-500 cursor-col-resize z-50 -translate-x-1/2 opacity-0 hover:opacity-100"
             onMouseDown={() => {
               setIsResizingRightSidebar(true);
               document.body.style.cursor = 'col-resize';
             }}
           />

           {/* Chat Section */}
           <div className="flex-1 flex flex-col min-h-0">
              <div className="p-2 font-semibold text-xs text-gray-400 bg-gray-900 border-b border-gray-700 shrink-0 flex flex-col gap-1">
                <div className="flex justify-between items-center">
                   <div className="uppercase tracking-wider font-bold text-gray-300">AI Assistant</div>
                   <div className="text-[10px] text-blue-300 bg-blue-900/40 px-2 py-1 rounded border border-blue-700/50 shadow-sm font-mono min-w-[100px] text-center">
                      {models.find(m => m.id === selectedModel)?.name || selectedModel || 'Auto (Best Match)'}
                   </div>
                </div>
                <div className="flex flex-col gap-1 text-[10px] normal-case text-gray-400 bg-gray-800/50 p-1.5 rounded border border-gray-700/50 mt-1">
                    <div className="flex items-center gap-2 truncate" title={taskHierarchyDisplay || 'No task selected'}>
                        <Folder size={10} className="text-gray-500" />
                        <span className="text-gray-500 font-semibold">Context:</span> 
                        <span className="text-gray-300">{taskHierarchyDisplay || 'Global (No task selected)'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <div className="flex items-center gap-2 truncate" title={activeChat?.title || 'No chat selected'}>
                            <Bot size={10} className="text-gray-500" />
                            <span className="text-gray-500 font-semibold">Chat:</span> 
                            <span className="text-gray-300">{activeChat?.title || 'New Session'}</span>
                        </div>
                        <span className="bg-gray-800 px-1.5 py-0.5 rounded text-gray-400 border border-gray-700 text-[9px]" title="Approximate Token Count">
                            {tokenCount} tokens
                        </span>
                    </div>
                </div>
              </div>
              <div className="flex-1 p-2 overflow-y-auto overflow-x-auto min-h-0 bg-[#1e1e1e]">
                 <div className="flex flex-col gap-4">
                   {messages.map((msg, idx) => (
                     <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                       <div className={`max-w-[95%] rounded-lg p-3 ${
                         msg.role === 'user' 
                           ? 'bg-blue-900/30 border border-blue-800 text-white' 
                           : 'bg-gray-800/50 border border-gray-700 text-gray-200'
                       }`}>
                         {msg.role === 'assistant' && (
                           <div className="text-xs font-bold text-blue-400 mb-2 uppercase tracking-wider flex items-center gap-2">
                             <Bot size={12} /> AI Assistant
                           </div>
                         )}
                         <div className="text-sm leading-relaxed overflow-x-auto">
                           {(() => {
                            const rawContent = msg.content;
                            const displayContent = rawContent.replace(/\[\[\s*NEXT_ACTION\s*:\s*[\s\S]*?\]\]/gi, '').trim();
                            const regex = /\[\[\s*NEXT_ACTION\s*:\s*([\s\S]*?)\]\]/i;
                            const nextActionMatch = rawContent.match(regex);
                            
                            return (
                              <>
                                {renderMessageContent(displayContent)}
                                  {displayContent.includes('NEXT_ACTION') && (
                                     <div className="mt-2 p-2 bg-yellow-900/40 border border-yellow-700/50 rounded text-[10px] text-yellow-200 font-mono overflow-hidden">
                                        <div className="font-bold mb-1">⚠️ DETECTADO 'NEXT_ACTION' PERO NO PROCESADO</div>
                                        <div>Regex Failed. Raw segment around marker:</div>
                                        <div className="opacity-70 break-all p-1 bg-black/20 mt-1">
                                            {displayContent.substring(Math.max(0, displayContent.indexOf('NEXT_ACTION') - 20), Math.min(displayContent.length, displayContent.indexOf('NEXT_ACTION') + 100))}
                                        </div>
                                     </div>
                                  )}
                                </>
                             );
                           })()}
                         </div>
                         
                        {/* Next Step Confirmation Buttons - Render for ANY assistant message that has the tag */}
                        {msg.role === 'assistant' && (() => {
                            const rawContent = msg.content;
                            const regex = /\[\[\s*NEXT_ACTION\s*:\s*([\s\S]*?)\]\]/i;
                            const nextActionMatch = rawContent.match(regex);
                            
                            let nextAction = null;
                            let error = null;
 
                             if (nextActionMatch) {
                                try {
                                    let jsonStr = nextActionMatch[1].trim();
                                    // Cleanup common markdown artifacts
                                    jsonStr = jsonStr.replace(/^```json\s*/, '').replace(/^```\s*/, '').replace(/\s*```$/, '');
                                    // Sanitize newlines to spaces (common issue in LLM JSON output)
                                    jsonStr = jsonStr.replace(/\n/g, ' ');
                                    
                                    nextAction = JSON.parse(jsonStr);
                                } catch (e: any) {
                                    console.error("Failed to parse NEXT_ACTION", e);
                                    error = e.message;
                                }
                             }
                             
                             // If no match but marker exists, we handled visual warning above in content render.
                             // Here we just handle success or parse error.

                             if (error) {
                                return (
                                   <div className="mt-2 p-2 bg-red-900/50 border border-red-700 rounded text-xs text-red-200">
                                       <div className="font-bold flex items-center gap-1"><AlertCircle size={12}/> Error parsing action button</div>
                                       <div className="font-mono opacity-70 truncate">{error}</div>
                                       <div className="mt-1 opacity-50 text-[10px] break-all">Raw: {nextActionMatch?.[1]}</div>
                                   </div>
                                );
                             }

                            if (nextAction) {
                                return (
                                   <div className="mt-3 pt-3 border-t border-gray-700/50 flex flex-col gap-2">
                                       <div className="text-[10px] uppercase tracking-wider font-bold text-gray-400 flex items-center gap-1">
                                         <Play size={10} className="text-blue-400" /> Acción Recomendada
                                       </div>
                                       <div className="flex gap-2">
                                           <button 
                                               onClick={() => handleExecuteNextAction(nextAction, msg.content)}
                                               className="bg-green-600/90 hover:bg-green-500 text-white px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm hover:shadow-md"
                                               title={nextAction.label || "Ejecutar acción"}
                                           >
                                               <CheckCircle size={14} />
                                               {nextAction.label || (nextAction.type === 'run_command' ? "Ejecutar Pasos" : "Confirmar y Ejecutar")}
                                           </button>
                                           <button 
                                               onClick={() => submitMessage("Cancela esa acción. Espera a nuevas instrucciones.")}
                                               className="bg-gray-700 hover:bg-red-900/50 text-gray-300 hover:text-red-200 px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1.5 transition-all border border-gray-600 hover:border-red-800"
                                               title="Cancelar acción"
                                           >
                                               <XCircle size={14} />
                                               Cancelar
                                           </button>
                                       </div>
                                   </div>
                                );
                            } else if (idx >= messages.length - 1 && msg.content.match(/(Próximos Pasos|Next Steps|ESTADO|STATUS|Resumen|Summary|Listo|Button|Botón|Ejecutar|Run)/i)) {
                                // Fallback to generic continue button if no explicit action block AND it is the last message
                                return (
                                   <div className="mt-3 pt-3 border-t border-gray-700/50 flex flex-col gap-2">
                                       <div className="text-[10px] uppercase tracking-wider font-bold text-gray-400 flex items-center gap-1">
                                         <Play size={10} className="text-blue-400" /> Siguiente Paso
                                       </div>
                                       <div className="flex gap-2">
                                           <button 
                                               onClick={() => submitMessage("Continúa con el siguiente paso, por favor.")}
                                               className="bg-green-600/90 hover:bg-green-500 text-white px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm hover:shadow-md"
                                               title="Confirmar y ejecutar el siguiente paso sugerido"
                                           >
                                               <CheckCircle size={14} />
                                               Continuar
                                           </button>
                                           <button 
                                               onClick={() => submitMessage("Espera, no continúes todavía.")}
                                               className="bg-gray-700 hover:bg-red-900/50 text-gray-300 hover:text-red-200 px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1.5 transition-all border border-gray-600 hover:border-red-800"
                                           >
                                               <XCircle size={14} />
                                               Cancelar
                                           </button>
                                       </div>
                                   </div>
                                );
                            }
                            return null;
                        })()}
                       </div>
                     </div>
                   ))}
                   {isGenerating && (
                     <div className="flex items-center gap-2 text-gray-500 italic text-xs p-2">
                       <RefreshCw className="animate-spin" size={12} />
                       <span>Thinking...</span>
                     </div>
                   )}
                   <div ref={messagesEndRef} />
                 </div>
              </div>
              <div className="p-2 border-t border-gray-700 bg-gray-900 shrink-0">
                <div className="flex flex-col gap-2">
                  <textarea 
                    className="w-full bg-gray-800 border border-gray-600 rounded p-2 text-sm text-white focus:outline-none focus:border-blue-500 resize-none font-sans"
                    rows={3}
                    placeholder="Describe what you want..."
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleGenerate();
                      }
                    }}
                  />
                  <div className="flex justify-end">
                    <button 
                      className={`flex items-center gap-2 px-4 py-2 rounded text-sm font-medium transition-colors ${
                        isGenerating 
                          ? 'bg-gray-700 text-gray-400 cursor-not-allowed' 
                          : 'bg-blue-600 hover:bg-blue-500 text-white'
                      }`}
                      onClick={handleGenerate}
                      disabled={isGenerating}
                    >
                      {isGenerating ? <RefreshCw className="animate-spin" size={14} /> : <Play size={14} fill="currentColor" />}
                      <span>{isGenerating ? 'Generating...' : 'Generate Code'}</span>
                    </button>
                  </div>
                </div>
              </div>
           </div>
        </div>
      </div>
      {/* Context Menu */}
      {contextMenu.visible && (
        <div 
            ref={menuRef}
            className="fixed z-[9999] bg-gray-800 border-2 border-blue-500 rounded shadow-2xl py-1 min-w-[160px]"
            style={{ top: contextMenu.y, left: contextMenu.x }}
            onPointerDown={(e) => e.stopPropagation()} 
            onContextMenu={(e) => e.preventDefault()}
        >
            <button 
                className="w-full text-left px-3 py-1.5 hover:bg-gray-700 text-xs text-gray-300 flex items-center gap-2"
                onClick={() => { if (contextMenu.node) handleCopy(contextMenu.node); }}
            >
                <span>📄 Copy</span>
            </button>
            <button 
                className="w-full text-left px-3 py-1.5 hover:bg-gray-700 text-xs text-gray-300 flex items-center gap-2"
                onClick={() => { if (contextMenu.node) handleCut(contextMenu.node); }}
            >
                <span>✂️ Cut</span>
            </button>
            <button 
                className={`w-full text-left px-3 py-1.5 hover:bg-gray-700 text-xs text-gray-300 flex items-center gap-2 ${!clipboard ? 'opacity-50' : ''}`}
                onClick={() => { if (contextMenu.node) handlePaste(contextMenu.node); }}
            >
                <span>📋 Paste</span>
            </button>
             <div className="border-t border-gray-700 my-1"></div>
             <button 
                className="w-full text-left px-3 py-1.5 hover:bg-red-900/50 text-xs text-red-300 flex items-center gap-2"
                onClick={() => { if (contextMenu.node) handleDelete(contextMenu.node); }}
            >
                <span>🗑️ Delete</span>
            </button>
             <div className="border-t border-gray-700 my-1"></div>

            <button 
                className="w-full text-left px-3 py-1.5 hover:bg-gray-700 text-xs text-gray-300 flex items-center gap-2"
                onClick={() => {
                    if (contextMenu.node) {
                        handleOpenInBrowser(contextMenu.node.path);
                        setContextMenu({ ...contextMenu, visible: false });
                    }
                }}
            >
                <span>🌐 Open in Browser</span>
            </button>
             <button 
                className="w-full text-left px-3 py-1.5 hover:bg-gray-700 text-xs text-gray-300 flex items-center gap-2"
                onClick={async () => {
                     if (contextMenu.node) {
                         // Reveal in Explorer
                         await window.electronAPI.executeCommand(`explorer.exe /select,"${contextMenu.node.path.replace(/\//g, '\\')}"`);
                         setContextMenu({ ...contextMenu, visible: false });
                     }
                }}
            >
                <span>📂 Reveal in Explorer</span>
            </button>
             <button 
                className="w-full text-left px-3 py-1.5 hover:bg-gray-700 text-xs text-gray-300 flex items-center gap-2"
                onClick={async () => {
                     if (contextMenu.node) {
                         // Open with default app
                         await window.electronAPI.executeCommand(`start "" "${contextMenu.node.path.replace(/\//g, '\\')}"`);
                         setContextMenu({ ...contextMenu, visible: false });
                     }
                }}
            >
                <span>🚀 Open with Default App</span>
            </button>
        </div>
      )}
    </div>
  );
}

export default App;
