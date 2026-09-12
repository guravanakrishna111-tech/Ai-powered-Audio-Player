import { useEffect, useRef } from 'react';
import { usePlayerStore } from '../stores/playerStore';

export function AudioEngine() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const {
    audioUrl,
    isPlaying,
    volume,
    currentTime,
    setCurrentTime,
    setDuration,
    setIsPlaying,
    onTrackEnded,
  } = usePlayerStore();

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      void audio.play().catch(() => setIsPlaying(false));
    } else {
      audio.pause();
    }
  }, [isPlaying, audioUrl, setIsPlaying]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = volume;
  }, [volume]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || Math.abs(audio.currentTime - currentTime) < 0.5) return;
    audio.currentTime = currentTime;
  }, [currentTime]);

  return (
    <audio
      ref={audioRef}
      src={audioUrl ?? undefined}
      onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
      onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
      onEnded={() => void onTrackEnded()}
      onPlay={() => setIsPlaying(true)}
      onPause={() => setIsPlaying(false)}
    />
  );
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export { formatTime };
