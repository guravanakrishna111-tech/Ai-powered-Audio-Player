import { create } from 'zustand';
import type { RepeatMode, Song } from '../types/music';
import { api, toPlayableUrl } from '../api/client';

interface PlayerState {
  queue: Song[];
  queueIndex: number;
  currentSong: Song | null;
  audioUrl: string | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  shuffle: boolean;
  repeat: RepeatMode;
  setQueue: (songs: Song[], startIndex?: number) => Promise<void>;
  playSong: (song: Song, queue?: Song[]) => Promise<void>;
  togglePlay: () => void;
  pause: () => void;
  resume: () => void;
  next: () => Promise<void>;
  previous: () => Promise<void>;
  seek: (time: number) => void;
  setVolume: (volume: number) => void;
  toggleShuffle: () => void;
  cycleRepeat: () => void;
  setCurrentTime: (time: number) => void;
  setDuration: (duration: number) => void;
  setIsPlaying: (playing: boolean) => void;
  onTrackEnded: () => Promise<void>;
}

export const usePlayerStore = create<PlayerState>((set, get) => ({
  queue: [],
  queueIndex: -1,
  currentSong: null,
  audioUrl: null,
  isPlaying: false,
  currentTime: 0,
  duration: 0,
  volume: 0.85,
  shuffle: false,
  repeat: 'off',

  setQueue: async (songs, startIndex = 0) => {
    const index = Math.max(0, Math.min(startIndex, songs.length - 1));
    if (songs.length === 0) {
      set({ queue: [], queueIndex: -1, currentSong: null, audioUrl: null, isPlaying: false });
      return;
    }
    const song = songs[index];
    const url = await toPlayableUrl(song.file_path);
    set({ queue: songs, queueIndex: index, currentSong: song, audioUrl: url, isPlaying: true, currentTime: 0 });
    void api.recordPlay(song.id);
  },

  playSong: async (song, queue) => {
    const songs = queue ?? get().queue;
    const index = songs.findIndex((s) => s.id === song.id);
    const activeQueue = queue ?? (index >= 0 ? songs : [...songs, song]);
    const activeIndex = index >= 0 ? index : activeQueue.length - 1;
    await get().setQueue(activeQueue, activeIndex);
  },

  togglePlay: () => {
    set((state) => ({ isPlaying: !state.isPlaying }));
  },

  pause: () => set({ isPlaying: false }),
  resume: () => set({ isPlaying: true }),

  next: async () => {
    const { queue, queueIndex, shuffle, repeat } = get();
    if (queue.length === 0) return;

    let nextIndex = queueIndex;
    if (shuffle) {
      nextIndex = Math.floor(Math.random() * queue.length);
    } else if (queueIndex < queue.length - 1) {
      nextIndex = queueIndex + 1;
    } else if (repeat === 'all') {
      nextIndex = 0;
    } else {
      set({ isPlaying: false });
      return;
    }

    const song = queue[nextIndex];
    const url = await toPlayableUrl(song.file_path);
    set({ queueIndex: nextIndex, currentSong: song, audioUrl: url, isPlaying: true, currentTime: 0 });
    void api.recordPlay(song.id);
  },

  previous: async () => {
    const { queue, queueIndex, currentTime } = get();
    if (queue.length === 0) return;

    if (currentTime > 3) {
      set({ currentTime: 0, isPlaying: true });
      return;
    }

    const prevIndex = queueIndex > 0 ? queueIndex - 1 : queue.length - 1;
    const song = queue[prevIndex];
    const url = await toPlayableUrl(song.file_path);
    set({ queueIndex: prevIndex, currentSong: song, audioUrl: url, isPlaying: true, currentTime: 0 });
    void api.recordPlay(song.id);
  },

  seek: (time) => set({ currentTime: time }),
  setVolume: (volume) => set({ volume: Math.max(0, Math.min(1, volume)) }),

  toggleShuffle: () => set((state) => ({ shuffle: !state.shuffle })),

  cycleRepeat: () =>
    set((state) => ({
      repeat: state.repeat === 'off' ? 'all' : state.repeat === 'all' ? 'one' : 'off',
    })),

  setCurrentTime: (time) => set({ currentTime: time }),
  setDuration: (duration) => set({ duration }),
  setIsPlaying: (playing) => set({ isPlaying: playing }),

  onTrackEnded: async () => {
    const { repeat, currentSong } = get();
    if (repeat === 'one') {
      set({ currentTime: 0, isPlaying: true });
      return;
    }

    if (currentSong) {
      try {
        const response = await api.getRecommendations(currentSong.id, 5);
        const recommendedSongs = response.recommendations.map((item) => item.song);
        if (recommendedSongs.length > 0) {
          await get().setQueue(recommendedSongs, 0);
          return;
        }
      } catch {
        // Fall back to the existing queue flow when recommendations are unavailable.
      }
    }

    await get().next();
  },
}));
