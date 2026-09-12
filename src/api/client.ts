import type {
  Album,
  Artist,
  ProcessingProgress,
  RecommendationResponse,
  ScanProgress,
  Song,
} from '../types/music';

let baseUrl = 'http://127.0.0.1:8765';

export async function initApi(): Promise<void> {
  if (window.electronAPI?.getBackendUrl) {
    baseUrl = await window.electronAPI.getBackendUrl();
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  getSongs: (params?: { search?: string; artist_id?: number; album_id?: number; favorites?: boolean }) => {
    const query = new URLSearchParams();
    if (params?.search) query.set('search', params.search);
    if (params?.artist_id) query.set('artist_id', String(params.artist_id));
    if (params?.album_id) query.set('album_id', String(params.album_id));
    if (params?.favorites) query.set('favorites', 'true');
    return request<{ songs: Song[]; count: number }>(`/api/songs?${query}`);
  },
  getArtists: () => request<{ artists: Artist[] }>('/api/artists'),
  getAlbums: () => request<{ albums: Album[] }>('/api/albums'),
  toggleFavorite: (songId: number) =>
    request<{ song_id: number; is_favorite: boolean }>(`/api/songs/${songId}/favorite`, { method: 'POST' }),
  recordPlay: (songId: number) =>
    request<{ ok: boolean }>(`/api/songs/${songId}/played`, { method: 'POST' }),
  getRecommendations: (songId: number, limit = 5) =>
    request<RecommendationResponse>(`/api/recommendations/${songId}?limit=${limit}`),
  addFolder: (path: string) =>
    request<{ ok: boolean }>('/api/folders', { method: 'POST', body: JSON.stringify({ path }) }),
  getFolders: () => request<{ folders: { id: number; path: string; enabled: number }[] }>('/api/folders'),
  removeFolder: (id: number) => request<{ ok: boolean }>(`/api/folders/${id}`, { method: 'DELETE' }),
  triggerScan: () => request<{ ok: boolean }>('/api/scan', { method: 'POST' }),
  getScanProgress: () => request<ScanProgress>('/api/scan/progress'),
  getProcessingProgress: () => request<ProcessingProgress>('/api/processing/progress'),
  getSettings: () => request<Record<string, unknown>>('/api/settings'),
  updateSettings: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/api/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  clearCache: () => request<{ ok: boolean }>('/api/settings/clear-cache', { method: 'POST' }),
  resetDatabase: () => request<{ ok: boolean }>('/api/settings/reset-database', { method: 'POST' }),
};

export async function toPlayableUrl(filePath: string): Promise<string> {
  if (window.electronAPI?.toAudioUrl) {
    return window.electronAPI.toAudioUrl(filePath);
  }
  return `file://${filePath}`;
}

export async function toArtworkUrl(filePath: string): Promise<string> {
  if (window.electronAPI?.toFileUrl) {
    return window.electronAPI.toFileUrl(filePath);
  }
  return `file://${filePath}`;
}
