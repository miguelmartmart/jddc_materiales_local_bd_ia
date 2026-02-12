import { app, BrowserWindow, ipcMain, Menu, dialog, shell } from 'electron';
import path from 'path';
import { spawn, exec } from 'child_process';
import fs from 'fs/promises';

let mainWindow: BrowserWindow | null;
let pythonProcess: any = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'), // Ensure this is compiled
      webSecurity: true
    },
    title: "AI Code Lab"
  });

  const isDev = process.env.NODE_ENV === 'development';
  
  if (isDev) {
    // Retry connection logic
    const loadURL = async () => {
      try {
        await mainWindow?.loadURL('http://localhost:5173');
      } catch (e) {
        console.log('Waiting for Vite server...');
        setTimeout(loadURL, 1000);
      }
    };
    loadURL();
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../../dist/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Intercept right-click context menu at the main process level
  mainWindow.webContents.on('context-menu', (event, params) => {
    // Prevent native default context menu
    event.preventDefault();

    // Send event to renderer to handle custom logic if needed
    mainWindow?.webContents.send('main-process-context-menu', {
      x: params.x,
      y: params.y
    });
  });

  createMenu();
}

function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Open Folder',
          accelerator: 'CmdOrCtrl+O',
          click: async () => {
            const result = await dialog.showOpenDialog({
              properties: ['openDirectory']
            });
            if (!result.canceled && result.filePaths.length > 0) {
              mainWindow?.webContents.send('menu:folder-selected', result.filePaths[0]);
            }
          }
        },
        { role: 'quit' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' }
      ]
    }
  ];
  const menu = Menu.buildFromTemplate(template as any);
  Menu.setApplicationMenu(menu);
}

ipcMain.handle('shell:openExternal', async (_event, url) => {
  await shell.openExternal(url);
});

// IPC Handlers
ipcMain.handle('fs:readDir', async (_event, dirPath) => {
  try {
    const dirents = await fs.readdir(dirPath, { withFileTypes: true });
    return dirents.map(dirent => ({
      name: dirent.name,
      isDirectory: dirent.isDirectory(),
      path: path.join(dirPath, dirent.name)
    })).sort((a, b) => {
        if (a.isDirectory === b.isDirectory) return a.name.localeCompare(b.name);
        return a.isDirectory ? -1 : 1;
    });
  } catch (error: any) {
    throw new Error(`Error reading directory: ${error.message}`);
  }
});

ipcMain.handle('fs:readFile', async (_event, filePath) => {
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return content;
  } catch (error: any) {
    throw new Error(`Error reading file: ${error.message}`);
  }
});

ipcMain.handle('fs:exists', async (_event, targetPath) => {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
});

ipcMain.handle('fs:makeDir', async (_event, dirPath) => {
  try {
    await fs.mkdir(dirPath, { recursive: true });
    return true;
  } catch (error: any) {
    throw new Error(`Error creating directory: ${error.message}`);
  }
});

ipcMain.handle('fs:writeFile', async (_event, filePath, content) => {
  // Direct write without confirmation for smooth AI workflow
  try {
    const dir = path.dirname(filePath);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(filePath, content, 'utf-8');
    return true;
  } catch (error: any) {
    throw new Error(`Error writing file: ${error.message}`);
  }
});

ipcMain.handle('fs:createDir', async (_event, dirPath) => {
  // Direct create without confirmation
  try {
    await fs.mkdir(dirPath, { recursive: true });
    return true;
  } catch (error: any) {
    throw new Error(`Error creating directory: ${error.message}`);
  }
});

ipcMain.handle('fs:delete', async (_event, targetPath) => {
  try {
    await fs.rm(targetPath, { recursive: true, force: true });
    return true;
  } catch (error: any) {
    throw new Error(`Error deleting path: ${error.message}`);
  }
});

ipcMain.handle('fs:copy', async (_event, sourcePath, destPath) => {
  try {
    await fs.cp(sourcePath, destPath, { recursive: true });
    return true;
  } catch (error: any) {
    throw new Error(`Error copying path: ${error.message}`);
  }
});

ipcMain.handle('fs:move', async (_event, sourcePath, destPath) => {
  try {
    await fs.rename(sourcePath, destPath);
    return true;
  } catch (error: any) {
    throw new Error(`Error moving path: ${error.message}`);
  }
});

ipcMain.handle('shell:execute', async (_event, command) => {
  const { response } = await dialog.showMessageBox({
    type: 'warning',
    buttons: ['Execute', 'Cancel'],
    title: 'Confirm Command Execution',
    message: `Do you want to execute this command?\n\n${command.slice(0, 200)}${command.length > 200 ? '...' : ''}`
  });

  if (response === 0) { // Execute
    return new Promise((resolve, reject) => {
      exec(command, { 
        cwd: path.join(__dirname, '../../'),
        shell: 'powershell.exe'
      }, (error, stdout, stderr) => {
        if (error) {
          resolve({ success: false, output: stderr || error.message });
        } else {
          resolve({ success: true, output: stdout });
        }
      });
    });
  }
  return { success: false, output: 'Cancelled by user' };
});

ipcMain.handle('dialog:openFolder', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory']
  });
  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0];
  }
  return null;
});


function startPythonServer() {
  const scriptPath = path.join(__dirname, '../../backend/server.py');
  
  // Try to find the venv python first
  const venvPython = path.resolve(__dirname, '../../../../.venv/Scripts/python.exe');
  const systemPython = 'python';
  
  const pythonExec = require('fs').existsSync(venvPython) ? venvPython : systemPython;
  
  console.log(`Starting Python server using ${pythonExec} at ${scriptPath}`);
  
  pythonProcess = spawn(pythonExec, [scriptPath], {
    cwd: path.join(__dirname, '../../'), // Root of desktop-codelab
    env: { 
      ...process.env, 
      PORT: '8002',
      PYTHONIOENCODING: 'utf-8' // Fix for unicode errors in Windows console
    }
  });

  pythonProcess.stdout.on('data', (data: any) => {
    console.log(`[Python]: ${data}`);
  });

  pythonProcess.stderr.on('data', (data: any) => {
    console.error(`[Python Error]: ${data}`);
  });
  
  pythonProcess.on('error', (err: any) => {
     console.error('[Python Spawn Error]:', err);
  });
  
  pythonProcess.on('close', (code: any) => {
    console.log(`Python process exited with code ${code}`);
  });
}

app.on('ready', () => {
  createWindow();
  startPythonServer(); 
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
