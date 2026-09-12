import { app, BrowserWindow, ipcMain, dialog, protocol } from 'electron';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import { BackendManager } from './backend-manager.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const isDev = !!process.env.VITE_DEV_SERVER_URL;
let mainWindow: BrowserWindow | null = null;
const backend = new BackendManager();

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'local-audio',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      bypassCSP: true,
    },
  },
]);

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: '#0a0a0f',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL!);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  protocol.handle('local-audio', (request) => {
    const filePath = decodeURIComponent(request.url.replace('local-audio://', ''));
    return fetch(pathToFileURL(filePath).href);
  });

  await backend.start();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  backend.stop();
});

ipcMain.handle('select-music-folders', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ['openDirectory', 'multiSelections'],
    title: 'Select Music Folders',
  });
  return result.canceled ? [] : result.filePaths;
});

ipcMain.handle('to-audio-url', (_event, filePath: string) => {
  return `local-audio://${encodeURIComponent(filePath.replace(/\\/g, '/'))}`;
});

ipcMain.handle('to-file-url', (_event, filePath: string) => {
  return pathToFileURL(filePath).href;
});

ipcMain.handle('get-backend-url', () => backend.getBaseUrl());

ipcMain.handle('get-app-data-path', () => app.getPath('userData'));
