import React, { useState } from 'react';
import { Plus, Trash2, MessageSquare, ChevronRight, ChevronDown, CheckCircle, Circle, FileText, CornerDownRight, BookOpen } from 'lucide-react';

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  contextFile?: string;
}

export interface Task {
  id: string;
  title: string;
  status: 'todo' | 'in-progress' | 'done';
  chats: ChatSession[];
  subtasks: Task[];
  isExpanded: boolean;
  createdAt: number;
  contextFile?: string;
}

interface TaskManagerProps {
  tasks: Task[];
  activeTaskId: string | null;
  activeChatId: string | null;
  onAddTask: (parentId: string | null, title: string) => void;
  onDeleteTask: (taskId: string) => void;
  onSelectTask: (taskId: string) => void;
  onUpdateTaskStatus: (taskId: string, status: Task['status']) => void;
  onToggleTaskExpanded: (taskId: string) => void;
  onAddChat: (taskId: string) => void;
  onSelectChat: (taskId: string, chatId: string) => void;
  onDeleteChat: (taskId: string, chatId: string) => void;
  onExportChat: (taskId: string, chatId: string) => void;
  onOpenContext: (taskId: string, chatId?: string) => void;
  onMoveTask: (draggedTaskId: string, targetTaskId: string | null) => void;
}

const TaskItem = ({ 
  task, 
  depth = 0, 
  ...props 
}: { 
  task: Task, 
  depth?: number 
} & Omit<TaskManagerProps, 'tasks' | 'onAddTask'> & { onAddTask: (parentId: string | null, title: string) => void }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [showSubtaskInput, setShowSubtaskInput] = useState(false);
  const [newSubtaskTitle, setNewSubtaskTitle] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);

  const handleAddSubtask = (e: React.FormEvent) => {
    e.preventDefault();
    if (newSubtaskTitle.trim()) {
      props.onAddTask(task.id, newSubtaskTitle.trim());
      setNewSubtaskTitle('');
      setShowSubtaskInput(false);
      // Ensure parent is expanded to see new subtask
      if (!task.isExpanded) {
        props.onToggleTaskExpanded(task.id);
      }
    }
  };

  const handleDragStart = (e: React.DragEvent) => {
    e.stopPropagation();
    e.dataTransfer.setData('application/react-task-id', task.id);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    const draggedTaskId = e.dataTransfer.getData('application/react-task-id');
    if (draggedTaskId && draggedTaskId !== task.id) {
      props.onMoveTask(draggedTaskId, task.id);
    }
  };

  return (
    <div className="flex flex-col">
      <div 
        className={`flex flex-col rounded border mb-1 ${props.activeTaskId === task.id ? 'border-blue-500/50 bg-blue-900/10' : 'border-gray-700 bg-gray-800'} ${isDragOver ? 'ring-2 ring-blue-500 bg-blue-900/30' : ''}`}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{ marginLeft: `${depth * 12}px` }}
        draggable
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Task Header */}
        <div 
          className="flex items-center p-2 gap-2 cursor-pointer hover:bg-gray-700/50 transition-colors group"
          onClick={() => props.onSelectTask(task.id)}
        >
          {/* Expand/Collapse Subtasks */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              props.onToggleTaskExpanded(task.id);
            }}
            className={`text-gray-500 hover:text-white transition-colors ${(task.subtasks || []).length === 0 ? 'opacity-30' : ''}`}
          >
            {task.isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>

          {/* Status Toggle */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              const nextStatus = task.status === 'todo' ? 'in-progress' : task.status === 'in-progress' ? 'done' : 'todo';
              props.onUpdateTaskStatus(task.id, nextStatus);
            }}
            className={`shrink-0 ${task.status === 'done' ? 'text-green-500' : task.status === 'in-progress' ? 'text-yellow-500' : 'text-gray-500'}`}
            title={`Status: ${task.status}`}
          >
            {task.status === 'done' ? <CheckCircle size={14} /> : <Circle size={14} fill={task.status === 'in-progress' ? 'currentColor' : 'none'} />}
          </button>
          
          {/* Title */}
          <span className={`flex-1 text-sm font-medium truncate ${task.status === 'done' ? 'text-gray-500 line-through' : 'text-gray-200'}`}>
            {task.title}
          </span>
          
          {/* Actions (visible on hover or active) */}
          <div className={`flex items-center gap-1 ${isHovered || props.activeTaskId === task.id ? 'opacity-100' : 'opacity-0'} transition-opacity`}>
             <button 
              onClick={(e) => {
                e.stopPropagation();
                props.onOpenContext(task.id);
              }}
              className="text-gray-400 hover:text-yellow-400 p-1"
              title="Open Context File"
            >
              <BookOpen size={12} />
            </button>
             <button 
              onClick={(e) => {
                e.stopPropagation();
                setShowSubtaskInput(!showSubtaskInput);
              }}
              className="text-gray-400 hover:text-blue-400 p-1"
              title="Add Subtask"
            >
              <CornerDownRight size={12} />
            </button>
            <button 
              onClick={(e) => {
                e.stopPropagation();
                props.onDeleteTask(task.id);
              }}
              className="text-gray-400 hover:text-red-300 p-1"
              title="Delete Task"
            >
              <Trash2 size={12} />
            </button>
          </div>
        </div>

        {/* Subtask Input */}
        {showSubtaskInput && (
           <form onSubmit={handleAddSubtask} className="px-2 pb-2 flex gap-1">
              <CornerDownRight size={12} className="text-gray-500 mt-2" />
              <input
                type="text"
                value={newSubtaskTitle}
                onChange={(e) => setNewSubtaskTitle(e.target.value)}
                placeholder="Subtask title..."
                autoFocus
                className="flex-1 bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
              />
           </form>
        )}

        {/* Chats List (Only if active task) */}
        {props.activeTaskId === task.id && (
            <div className="pl-8 pr-2 pb-2 space-y-1 border-t border-gray-700/50 pt-1">
                <div className="flex items-center justify-between text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                    <span>Chats</span>
                    <button onClick={() => props.onAddChat(task.id)} className="hover:text-blue-400" title="New Chat">
                        <Plus size={10} />
                    </button>
                </div>
                {task.chats.map(chat => (
                    <div 
                        key={chat.id}
                        className={`flex items-center justify-between px-2 py-1 rounded text-xs cursor-pointer group ${props.activeChatId === chat.id ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-700 hover:text-gray-200'}`}
                        onClick={() => props.onSelectChat(task.id, chat.id)}
                    >
                        <div className="flex items-center gap-2 truncate flex-1">
                            <MessageSquare size={10} />
                            <span className="truncate">{chat.title || 'New Chat'}</span>
                        </div>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                             <button 
                                onClick={(e) => {
                                    e.stopPropagation();
                                    props.onOpenContext(task.id, chat.id);
                                }}
                                className={`hover:text-yellow-300 ${props.activeChatId === chat.id ? 'text-white' : 'text-gray-500'}`}
                                title="Open Chat Context"
                            >
                                <BookOpen size={10} />
                            </button>
                             <button 
                                onClick={(e) => {
                                    e.stopPropagation();
                                    props.onExportChat(task.id, chat.id);
                                }}
                                className={`hover:text-green-300 ${props.activeChatId === chat.id ? 'text-white' : 'text-gray-500'}`}
                                title="Export Chat to Editor"
                            >
                                <FileText size={10} />
                            </button>
                            <button 
                                onClick={(e) => {
                                    e.stopPropagation();
                                    props.onDeleteChat(task.id, chat.id);
                                }}
                                className={`hover:text-red-300 ${props.activeChatId === chat.id ? 'text-white' : 'text-gray-500'}`}
                                title="Delete Chat"
                            >
                                <Trash2 size={10} />
                            </button>
                        </div>
                    </div>
                ))}
                {task.chats.length === 0 && (
                    <div className="text-[10px] text-gray-600 italic pl-2">No chats.</div>
                )}
            </div>
        )}
      </div>

      {/* Render Subtasks */}
      {task.isExpanded && (task.subtasks || []).length > 0 && (
        <div className="flex flex-col">
          {(task.subtasks || []).map(subtask => (
            <TaskItem 
              key={subtask.id} 
              task={subtask} 
              depth={depth + 1} 
              {...props} 
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const TaskManager: React.FC<TaskManagerProps> = (props) => {
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [isExpanded, setIsExpanded] = useState(true);

  const handleAddTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (newTaskTitle.trim()) {
      props.onAddTask(null, newTaskTitle.trim()); // null parentId for root task
      setNewTaskTitle('');
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-800 border-t border-gray-700">
      {/* Header */}
      <div 
        className="p-2 font-semibold text-xs text-gray-400 uppercase tracking-wider bg-gray-900 shrink-0 flex items-center justify-between cursor-pointer hover:bg-gray-800"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
            <CheckCircle size={12} />
            <span>Tasks</span>
        </div>
        <div className="flex items-center gap-2">
             {/* Simple count of root tasks for now, or recursive count? Root is fine */}
             <span className="text-[10px] bg-gray-700 px-1.5 rounded-full">{props.tasks.length}</span>
             {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>

      {isExpanded && (
        <div className="flex-1 flex flex-col min-h-0">
          {/* Add Root Task Form */}
          <form onSubmit={handleAddTask} className="p-2 border-b border-gray-700 bg-gray-800/50">
            <div className="flex gap-1">
              <input
                type="text"
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                placeholder="New Root Task..."
                className="flex-1 bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
              />
              <button 
                type="submit"
                className="bg-blue-600 hover:bg-blue-500 text-white p-1 rounded transition-colors"
                title="Add Task"
              >
                <Plus size={14} />
              </button>
            </div>
          </form>

          {/* Task List */}
          <div 
            className="flex-1 overflow-y-auto p-2"
            onDragOver={(e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = 'move';
            }}
            onDrop={(e) => {
              e.preventDefault();
              const draggedTaskId = e.dataTransfer.getData('application/react-task-id');
              if (draggedTaskId) {
                  // Drop on container -> Move to root (target = null)
                  props.onMoveTask(draggedTaskId, null);
              }
            }}
          >
            {props.tasks.length === 0 && (
                <div className="text-gray-500 text-xs text-center italic py-4">No tasks yet.</div>
            )}
            {props.tasks.map(task => (
              <TaskItem key={task.id} task={task} {...props} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
