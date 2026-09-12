import { useEffect, useState } from 'react';
import { FolderOpen } from 'lucide-react';
import { api } from '../api/client';
import type { RecommendationItem, Song, ProcessingProgress, ScanProgress } from '../types/music';
import { SongList } from '../components/SongList';
import { RecommendationRail } from '../components/RecommendationRail';
import { usePlayerStore } from '../stores/playerStore';

export function HomePage() {
  const [songs, setSongs] = useState<Song[]>([]);
  const { setQueue } = usePlayerStore();

  useEffect(() => {
    void api.getSongs().then((res) => setSongs(res.songs.slice(0, 12)));
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Home</h1>
        <p>Your local music library, analyzed in the background.</p>
      </div>
      {songs.length > 0 && (
        <button className="btn" style={{ marginBottom: 24 }} onClick={() => void setQueue(songs, 0)}>
          Play recent additions
        </button>
      )}
      <SongList songs={songs} />
    </div>
  );
}

export function LibraryPage() {
  const [songs, setSongs] = useState<Song[]>([]);
  const [search, setSearch] = useState('');

  const load = () => {
    void api.getSongs({ search: search || undefined }).then((res) => setSongs(res.songs));
  };

  useEffect(() => {
    load();
  }, [search]);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Library</h1>
        <input
          placeholder="Search songs, artists, albums..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: '100%',
            maxWidth: 420,
            padding: '12px 16px',
            borderRadius: 999,
            border: '1px solid var(--border)',
            background: 'var(--bg-elevated)',
            color: 'var(--text-primary)',
          }}
        />
      </div>
      <SongList songs={songs} onRefresh={load} />
    </div>
  );
}

export function ArtistsPage() {
  const [artists, setArtists] = useState<{ id: number; name: string; song_count: number }[]>([]);
  const [selectedArtist, setSelectedArtist] = useState<number | null>(null);
  const [songs, setSongs] = useState<Song[]>([]);

  useEffect(() => {
    void api.getArtists().then((res) => setArtists(res.artists));
  }, []);

  useEffect(() => {
    if (selectedArtist) {
      void api.getSongs({ artist_id: selectedArtist }).then((res) => setSongs(res.songs));
    }
  }, [selectedArtist]);

  if (selectedArtist) {
    const artist = artists.find((a) => a.id === selectedArtist);
    return (
      <div className="page">
        <div className="page-header">
          <button className="btn secondary" onClick={() => setSelectedArtist(null)}>Back</button>
          <h1>{artist?.name}</h1>
        </div>
        <SongList songs={songs} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header"><h1>Artists</h1></div>
      <div className="card-grid">
        {artists.map((artist) => (
          <button key={artist.id} className="card" onClick={() => setSelectedArtist(artist.id)}>
            <strong>{artist.name}</strong>
            <div className="muted small">{artist.song_count} songs</div>
          </button>
        ))}
      </div>
    </div>
  );
}

export function AlbumsPage() {
  const [albums, setAlbums] = useState<{ id: number; title: string; artist_name: string; song_count: number }[]>([]);
  const [selectedAlbum, setSelectedAlbum] = useState<number | null>(null);
  const [songs, setSongs] = useState<Song[]>([]);

  useEffect(() => {
    void api.getAlbums().then((res) => setAlbums(res.albums));
  }, []);

  useEffect(() => {
    if (selectedAlbum) {
      void api.getSongs({ album_id: selectedAlbum }).then((res) => setSongs(res.songs));
    }
  }, [selectedAlbum]);

  if (selectedAlbum) {
    const album = albums.find((a) => a.id === selectedAlbum);
    return (
      <div className="page">
        <div className="page-header">
          <button className="btn secondary" onClick={() => setSelectedAlbum(null)}>Back</button>
          <h1>{album?.title}</h1>
          <p className="muted">{album?.artist_name}</p>
        </div>
        <SongList songs={songs} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header"><h1>Albums</h1></div>
      <div className="card-grid">
        {albums.map((album) => (
          <button key={album.id} className="card" onClick={() => setSelectedAlbum(album.id)}>
            <div className="artwork artwork-placeholder" style={{ width: '100%', aspectRatio: '1', marginBottom: 12 }}>Music</div>
            <strong>{album.title}</strong>
            <div className="muted small">{album.artist_name} · {album.song_count} songs</div>
          </button>
        ))}
      </div>
    </div>
  );
}

export function FavoritesPage() {
  const [songs, setSongs] = useState<Song[]>([]);
  const load = () => void api.getSongs({ favorites: true }).then((res) => setSongs(res.songs));
  useEffect(() => { load(); }, []);
  return (
    <div className="page">
      <div className="page-header"><h1>Favorites</h1></div>
      <SongList songs={songs} onRefresh={load} />
    </div>
  );
}

export function PlaylistsPage() {
  return (
    <div className="page">
      <div className="page-header">
        <h1>Playlists</h1>
        <p>Custom playlists will be expanded in a future update. Use Library and Favorites for now.</p>
      </div>
    </div>
  );
}

export function NowPlayingPage() {
  const { currentSong, isPlaying, togglePlay, playSong } = usePlayerStore();
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [candidateCount, setCandidateCount] = useState<number | undefined>(undefined);
  const [latencyMs, setLatencyMs] = useState<number | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    if (!currentSong) {
      setRecommendations([]);
      setRecommendationError(null);
      setCandidateCount(undefined);
      setLatencyMs(undefined);
      return;
    }

    setLoadingRecommendations(true);
    setRecommendationError(null);
    void api.getRecommendations(currentSong.id, 5)
      .then((response) => {
        if (cancelled) return;
        setRecommendations(response.recommendations);
        setCandidateCount(response.candidate_count);
        setLatencyMs(response.latency_ms);
      })
      .catch((error: Error) => {
        if (cancelled) return;
        setRecommendations([]);
        setRecommendationError(error.message);
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingRecommendations(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentSong?.id]);

  if (!currentSong) {
    return (
      <div className="page empty-state">
        <p>Nothing playing. Select a song from your library.</p>
      </div>
    );
  }

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
      <div style={{ display: 'flex', gap: 32, alignItems: 'center' }}>
        <div className="artwork artwork-placeholder large">Music</div>
        <div>
          <h1>{currentSong.title}</h1>
          <p className="muted">{currentSong.artist_name}</p>
          <p className="muted">{currentSong.album_title}</p>
          <button className="btn" onClick={togglePlay} style={{ marginTop: 24 }}>
            {isPlaying ? 'Pause' : 'Play'}
          </button>
        </div>
      </div>
      <RecommendationRail
        recommendations={recommendations}
        loading={loadingRecommendations}
        error={recommendationError}
        candidateCount={candidateCount}
        latencyMs={latencyMs}
        onPlay={(song, queue) => void playSong(song, queue)}
      />
    </div>
  );
}

export function SettingsPage() {
  const [folders, setFolders] = useState<{ id: number; path: string }[]>([]);
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const [folderRes, settingsRes] = await Promise.all([api.getFolders(), api.getSettings()]);
    setFolders(folderRes.folders);
    setSettings(settingsRes);
  };

  useEffect(() => {
    void refresh();
  }, []);

  const addFolder = async () => {
    if (!window.electronAPI?.selectMusicFolders) {
      alert('Folder picker is available in the desktop app.');
      return;
    }
    setBusy(true);
    try {
      const paths = await window.electronAPI.selectMusicFolders();
      for (const path of paths) {
        await api.addFolder(path);
      }
      await api.triggerScan();
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Manage folders, processing, privacy, and cache.</p>
      </div>

      <section style={{ marginBottom: 32 }}>
        <h2>Music folders</h2>
        <button className="btn" onClick={() => void addFolder()} disabled={busy}>
          <FolderOpen size={16} /> Add folder
        </button>
        <ul>
          {folders.map((f) => (
            <li key={f.id} className="muted">{f.path}</li>
          ))}
        </ul>
      </section>

      <section style={{ marginBottom: 32 }}>
        <h2>Processing</h2>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
          <input
            type="checkbox"
            checked={Boolean(settings.background_analysis ?? true)}
            onChange={(e) => void api.updateSettings({ background_analysis: e.target.checked }).then(refresh)}
          />
          Background analysis
        </label>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="checkbox"
            checked={Boolean(settings.enrichment_enabled ?? false)}
            onChange={(e) => void api.updateSettings({ enrichment_enabled: e.target.checked }).then(refresh)}
          />
          Online metadata enrichment (MusicBrainz - title/artist only)
        </label>
      </section>

      <section>
        <h2>Privacy & cache</h2>
        <p className="muted small">Audio files never leave your device. Enrichment sends only search queries.</p>
        <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
          <button className="btn secondary" onClick={() => void api.clearCache()}>Clear cache</button>
          <button className="btn secondary" onClick={() => void api.resetDatabase().then(refresh)}>Reset database</button>
        </div>
      </section>
    </div>
  );
}

export function useProgressPolling() {
  const [scan, setScan] = useState<ScanProgress | null>(null);
  const [processing, setProcessing] = useState<ProcessingProgress | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      void api.getScanProgress().then(setScan).catch(() => undefined);
      void api.getProcessingProgress().then(setProcessing).catch(() => undefined);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return { scan, processing };
}

