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

  // Play / pause handling when audioUrl or isPlaying changes
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying && audioUrl) {
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch((err: any) => {
          // Ignore AbortError caused by rapid track switching or source reload
          if (err?.name !== 'AbortError') {
            console.warn('Playback error caught:', err);
            setIsPlaying(false);
          }
        });
      }
    } else {
      audio.pause();
    }
  }, [audioUrl, isPlaying, setIsPlaying]);

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
      preload="auto"
      onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
      onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
      onEnded={() => void onTrackEnded()}
      onPlay={() => setIsPlaying(true)}
      onPause={() => setIsPlaying(false)}
      onError={(e) => {
        const err = e.currentTarget.error;
        if (err) {
          console.warn('Audio element error code:', err.code, err.message);
        }
      }}
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
