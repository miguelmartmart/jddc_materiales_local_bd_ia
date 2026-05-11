import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  openFolder: () => ipcRenderer.invoke('dialog:openFolder'),
  readDir: (path: string) => ipcRenderer.invoke('fs:readDir', path),
  readFile: (path: string) => ipcRenderer.invoke('fs:readFile', path),
  exists: (path: string) => ipcRenderer.invoke('fs:exists', path),
  makeDir: (path: string) => ipcRenderer.invoke('fs:makeDir', path),
  createDir: (path: string) => ipcRenderer.invoke('fs:createDir', path),
  delete: (path: string) => ipcRenderer.invoke('fs:delete', path),
  copy: (source: string, dest: string) => ipcRenderer.invoke('fs:copy', source, dest),
  move: (source: string, dest: string) => ipcRenderer.invoke('fs:move', source, dest),
  writeFile: (path: string, content: string) => ipcRenderer.invoke('fs:writeFile', path, content),
  openExternal: (url: string) => ipcRenderer.invoke('shell:openExternal', url),
  writeTempImage: (dataUrl: string) => ipcRenderer.invoke('fs:writeTempImage', dataUrl),
  executeCommand: (command: string, cwd?: string) => ipcRenderer.invoke('shell:execute', command, cwd),
  onFolderSelected: (callback: (path: string) => void) => {
    ipcRenderer.on('menu:folder-selected', (_event, path) => callback(path));
  },
  on: (channel: string, callback: (data: any) => void) => {
      ipcRenderer.on(channel, (_event, data) => callback(data));
  }
});
