export interface ElectronAPI {
  selectMusicFolders: () => Promise<string[]>;
  toAudioUrl: (filePath: string) => Promise<string>;
  toFileUrl: (filePath: string) => Promise<string>;
  getBackendUrl: () => Promise<string>;
  getAppDataPath: () => Promise<string>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
