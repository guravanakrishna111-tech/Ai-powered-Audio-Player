import {
  Pause,
  Play,
  SkipBack,
  SkipForward,
  Shuffle,
  Repeat,
  Repeat1,
  Volume2,
  Heart,
} from 'lucide-react';
import { usePlayerStore } from '../stores/playerStore';
import { formatTime } from './AudioEngine';
import './PlayerBar.css';

export function PlayerBar() {
  const {
    currentSong,
    isPlaying,
    currentTime,
    duration,
    volume,
    shuffle,
    repeat,
    togglePlay,
    next,
    previous,
    seek,
    setVolume,
    toggleShuffle,
    cycleRepeat,
  } = usePlayerStore();

  return (
    <footer className="player-bar">
      <div className="player-track">
        {currentSong ? (
          <>
            <div className="artwork artwork-placeholder" style={{ width: 56, height: 56, borderRadius: 10 }}>
              ♪
            </div>
            <div>
              <strong>{currentSong.title}</strong>
              <div className="muted small">
                {currentSong.artist_name} · {currentSong.album_title}
              </div>
            </div>
            <button className="icon-btn" title="Favorite">
              <Heart size={18} />
            </button>
          </>
        ) : (
          <span className="muted">No song playing</span>
        )}
      </div>

      <div className="player-controls">
        <div className="control-buttons">
          <button className={`icon-btn ${shuffle ? 'active' : ''}`} onClick={toggleShuffle} title="Shuffle">
            <Shuffle size={18} />
          </button>
          <button className="icon-btn" onClick={() => void previous()} title="Previous">
            <SkipBack size={20} />
          </button>
          <button className="play-btn" onClick={togglePlay} title={isPlaying ? 'Pause' : 'Play'}>
            {isPlaying ? <Pause size={22} /> : <Play size={22} />}
          </button>
          <button className="icon-btn" onClick={() => void next()} title="Next">
            <SkipForward size={20} />
          </button>
          <button className={`icon-btn ${repeat !== 'off' ? 'active' : ''}`} onClick={cycleRepeat} title="Repeat">
            {repeat === 'one' ? <Repeat1 size={18} /> : <Repeat size={18} />}
          </button>
        </div>
        <div className="seek-row">
          <span className="small muted">{formatTime(currentTime)}</span>
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={currentTime}
            onChange={(e) => seek(Number(e.target.value))}
            className="seek-slider"
          />
          <span className="small muted">{formatTime(duration)}</span>
        </div>
      </div>

      <div className="player-volume">
        <Volume2 size={18} />
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={volume}
          onChange={(e) => setVolume(Number(e.target.value))}
          className="volume-slider"
        />
      </div>
    </footer>
  );
}
