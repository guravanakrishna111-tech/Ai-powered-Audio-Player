import { useEffect, useRef } from 'react';
import { usePlayerStore } from '../stores/playerStore';

export function AudioEngine() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const prevUrlRef = useRef<string | null>(null);
  const isSwitchingTrackRef = useRef(false);

  const {
    audioUrl,
    isPlaying,
    volume,
    currentTime,
    repeat,
    setCurrentTime,
    setDuration,
    setIsPlaying,
    onTrackEnded,
  } = usePlayerStore();

  // Handle URL changes
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audioUrl === prevUrlRef.current) return;

    prevUrlRef.current = audioUrl;

    if (!audioUrl) {
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
      return;
    }

    isSwitchingTrackRef.current = true;
    audio.src = audioUrl;
    audio.load();

    if (isPlaying) {
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            isSwitchingTrackRef.current = false;
          })
          .catch((err: any) => {
            isSwitchingTrackRef.current = false;
            if (err?.name !== 'AbortError') {
              console.error('Audio playback failed:', err, 'URL:', audioUrl);
              setIsPlaying(false);
            }
          });
      }
    } else {
      isSwitchingTrackRef.current = false;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioUrl]);

  // Handle play / pause toggle for same track
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !audioUrl) return;
    if (isSwitchingTrackRef.current) return;

    if (isPlaying) {
      if (audio.paused) {
        const playPromise = audio.play();
        if (playPromise !== undefined) {
          playPromise.catch((err: any) => {
            if (err?.name !== 'AbortError') {
              console.warn('Playback toggle error:', err);
              setIsPlaying(false);
            }
          });
        }
      }
    } else {
      if (!audio.paused) {
        audio.pause();
      }
    }
  }, [isPlaying, setIsPlaying, audioUrl]);

  // Handle volume
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = Math.max(0, Math.min(1, volume));
  }, [volume]);

  // Handle seeking
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !Number.isFinite(currentTime)) return;
    if (Math.abs(audio.currentTime - currentTime) > 0.5) {
      audio.currentTime = currentTime;
    }
  }, [currentTime]);

  return (
    <audio
      ref={audioRef}
      preload="auto"
      loop={repeat === 'one'}
      onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
      onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
      onEnded={() => void onTrackEnded()}
      onPlay={() => {
        isSwitchingTrackRef.current = false;
        setIsPlaying(true);
      }}
      onPause={() => {
        if (!isSwitchingTrackRef.current) {
          setIsPlaying(false);
        }
      }}
      onError={(e) => {
        isSwitchingTrackRef.current = false;
        const err = e.currentTarget.error;
        const src = e.currentTarget.src;
        if (err && src) {
          console.error('Audio element error:', err.code, '-', err.message, '| URL:', src);
        }
      }}
    />
  );
}

export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
