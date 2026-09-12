import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  selectMusicFolders: (): Promise<string[]> => ipcRenderer.invoke('select-music-folders'),
  toAudioUrl: (filePath: string): Promise<string> => ipcRenderer.invoke('to-audio-url', filePath),
  toFileUrl: (filePath: string): Promise<string> => ipcRenderer.invoke('to-file-url', filePath),
  getBackendUrl: (): Promise<string> => ipcRenderer.invoke('get-backend-url'),
  getAppDataPath: (): Promise<string> => ipcRenderer.invoke('get-app-data-path'),
});

export {};
