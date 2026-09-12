import { Play, Heart } from 'lucide-react';
import type { Song } from '../types/music';
import { usePlayerStore } from '../stores/playerStore';
import { api } from '../api/client';
import { formatTime } from './AudioEngine';

interface SongListProps {
  songs: Song[];
  onRefresh?: () => void;
}

export function SongList({ songs, onRefresh }: SongListProps) {
  const { currentSong, playSong } = usePlayerStore();

  const handleFavorite = async (song: Song) => {
    await api.toggleFavorite(song.id);
    onRefresh?.();
  };

  if (songs.length === 0) {
    return (
      <div className="empty-state">
        <p>No songs found. Add a music folder in Settings and scan your library.</p>
      </div>
    );
  }

  return (
    <div className="song-list">
      <div className="song-row header muted small">
        <span>#</span>
        <span>Title</span>
        <span>Album</span>
        <span>Duration</span>
        <span></span>
      </div>
      {songs.map((song) => (
        <div
          key={song.id}
          className={`song-row ${currentSong?.id === song.id ? 'active' : ''}`}
          onDoubleClick={() => void playSong(song, songs)}
        >
          <button
            className="icon-btn"
            onClick={() => void playSong(song, songs)}
            title="Play"
          >
            <Play size={16} />
          </button>
          <div>
            <strong>{song.title}</strong>
            <div className="muted small">{song.artist_name}</div>
          </div>
          <div className="muted small">{song.album_title}</div>
          <div className="muted small">{formatTime(song.duration ?? 0)}</div>
          <button
            className="icon-btn"
            onClick={() => void handleFavorite(song)}
            title="Toggle favorite"
          >
            <Heart size={16} fill={song.is_favorite ? 'currentColor' : 'none'} />
          </button>
        </div>
      ))}
    </div>
  );
}
