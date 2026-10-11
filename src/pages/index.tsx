import { useEffect, useState } from 'react';
import { FolderOpen, Sparkles, RefreshCw, Plus, Play, Music } from 'lucide-react';
import { api } from '../api/client';
import type { RecommendationItem, Song, ProcessingProgress, ScanProgress } from '../types/music';
import { SongList } from '../components/SongList';
import { RecommendationRail } from '../components/RecommendationRail';
import { usePlayerStore } from '../stores/playerStore';

export function HomePage() {
  const [songs, setSongs] = useState<Song[]>([]);
  const [loading, setLoading] = useState(true);
  const { setQueue } = usePlayerStore();

  const loadSongs = () => {
    void api.getSongs().then((res) => {
      setSongs(res.songs.slice(0, 16));
      setLoading(false);
    });
  };

  useEffect(() => {
    loadSongs();
  }, []);

  const handleQuickAdd = async () => {
    try {
      await api.scanWorkspace();
      loadSongs();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Home</h1>
        <p>Your local music library, analyzed with AI acoustic features & mood modeling.</p>
      </div>

      {songs.length > 0 ? (
        <div style={{ marginBottom: 24, display: 'flex', gap: 12 }}>
          <button className="btn" onClick={() => void setQueue(songs, 0)}>
            <Play size={16} /> Play all songs
          </button>
        </div>
      ) : !loading ? (
        <div className="card" style={{ padding: 24, marginBottom: 24, maxWidth: 640 }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sparkles size={20} color="var(--accent, #6366f1)" /> Welcome to AI Audio Player
          </h3>
          <p className="muted" style={{ margin: '8px 0 16px' }}>
            No songs found in the player yet. Scan your music library or quickly import the workspace playlist.
          </p>
          <button className="btn" onClick={() => void handleQuickAdd()}>
            <FolderOpen size={16} /> Import "Audio folder"
          </button>
        </div>
      ) : null}

      <SongList songs={songs} onRefresh={loadSongs} />
    </div>
  );
}

export function LibraryPage() {
  const [songs, setSongs] = useState<Song[]>([]);
  const [search, setSearch] = useState('');
  const [folderPathInput, setFolderPathInput] = useState('');
  const [showAddFolder, setShowAddFolder] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    void api.getSongs({ search: search || undefined }).then((res) => setSongs(res.songs));
  };

  useEffect(() => {
    load();
  }, [search]);

  const handleAddFolder = async () => {
    if (!folderPathInput.trim()) return;
    setBusy(true);
    setStatusMsg('Scanning folder...');
    try {
      await api.addFolder(folderPathInput.trim());
      await api.triggerScan();
      setStatusMsg('Folder added and scan initiated!');
      setFolderPathInput('');
      setShowAddFolder(false);
      setTimeout(load, 1000);
    } catch (e: any) {
      setStatusMsg(`Error: ${e?.message || 'Could not add folder'}`);
    } finally {
      setBusy(false);
    }
  };

  const handleQuickAddWorkspace = async () => {
    setBusy(true);
    setStatusMsg('Scanning workspace "Audio folder"...');
    try {
      const res = await api.scanWorkspace();
      setStatusMsg(`Scan started for ${res.added.length ? res.added.join(', ') : 'Audio folder'}!`);
      setTimeout(load, 1200);
    } catch (e: any) {
      setStatusMsg(`Error: ${e?.message || 'Could not scan workspace'}`);
    } finally {
      setBusy(false);
    }
  };

  const handleTrainModel = async () => {
    setBusy(true);
    setStatusMsg('Training model on audio playlist...');
    try {
      await api.trainModel();
      setStatusMsg('AI Model training started in background! Check Settings for live progress.');
    } catch (e: any) {
      setStatusMsg(`Error: ${e?.message || 'Training failed'}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1>Library</h1>
          <p className="muted">{songs.length} song{songs.length === 1 ? '' : 's'} available</p>
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button className="btn secondary" onClick={() => setShowAddFolder(!showAddFolder)}>
            <Plus size={16} /> Add Folder
          </button>
          <button className="btn secondary" onClick={() => void handleQuickAddWorkspace()} disabled={busy}>
            <FolderOpen size={16} /> Import "Audio folder"
          </button>
          <button className="btn" onClick={() => void handleTrainModel()} disabled={busy}>
            <Sparkles size={16} /> Train / Update Model
          </button>
        </div>
      </div>

      {statusMsg && (
        <div style={{ padding: '8px 16px', background: 'var(--bg-elevated, #1a1a24)', border: '1px solid var(--border, #2a2a38)', borderRadius: 8, marginBottom: 16, fontSize: 14 }}>
          {statusMsg}
        </div>
      )}

      {showAddFolder && (
        <div className="card" style={{ padding: 16, marginBottom: 20, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            placeholder="Folder path (e.g. 'Audio folder' or C:\Music)..."
            value={folderPathInput}
            onChange={(e) => setFolderPathInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void handleAddFolder(); }}
            style={{
              flex: 1,
              minWidth: 260,
              padding: '10px 14px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--bg-elevated)',
              color: 'var(--text-primary)',
            }}
          />
          <button className="btn" onClick={() => void handleAddFolder()} disabled={busy || !folderPathInput.trim()}>
            Add & Scan
          </button>
          <button className="btn secondary" onClick={() => setShowAddFolder(false)}>
            Cancel
          </button>
        </div>
      )}

      <div style={{ marginBottom: 20 }}>
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

      {songs.length === 0 ? (
        <div className="card empty-state" style={{ padding: 40, textAlign: 'center' }}>
          <Music size={48} style={{ opacity: 0.4, margin: '0 auto 16px' }} />
          <h3>No songs found in your library</h3>
          <p className="muted" style={{ margin: '8px 0 20px' }}>
            Click below to import the songs from your "Audio folder" or add your own music directory.
          </p>
          <button className="btn" onClick={() => void handleQuickAddWorkspace()} disabled={busy}>
            <FolderOpen size={16} /> Import "Audio folder" Now
          </button>
        </div>
      ) : (
        <SongList songs={songs} onRefresh={load} />
      )}
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
  const [folderPathInput, setFolderPathInput] = useState('');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { scan, processing } = useProgressPolling();

  const refresh = async () => {
    const [folderRes, settingsRes] = await Promise.all([api.getFolders(), api.getSettings()]);
    setFolders(folderRes.folders);
    setSettings(settingsRes);
  };

  useEffect(() => {
    void refresh();
  }, []);

  const handleBrowseFolder = async () => {
    if (!window.electronAPI?.selectMusicFolders) {
      setStatusMessage('Desktop folder browser is available in the desktop app. Enter a folder path below.');
      return;
    }
    setBusy(true);
    try {
      const paths = await window.electronAPI.selectMusicFolders();
      for (const path of paths) {
        await api.addFolder(path);
      }
      await api.triggerScan();
      setStatusMessage(`Added and scanned ${paths.length} folder(s).`);
      await refresh();
    } catch (e: any) {
      setStatusMessage(`Error: ${e?.message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleAddCustomFolder = async () => {
    if (!folderPathInput.trim()) return;
    setBusy(true);
    setStatusMessage('Adding and scanning folder...');
    try {
      const res = await api.addFolder(folderPathInput.trim());
      await api.triggerScan();
      setStatusMessage(`Successfully added: ${res.added_path || folderPathInput.trim()}`);
      setFolderPathInput('');
      await refresh();
    } catch (e: any) {
      setStatusMessage(`Error: ${e?.message || 'Failed to add folder'}`);
    } finally {
      setBusy(false);
    }
  };

  const handleScanWorkspace = async () => {
    setBusy(true);
    setStatusMessage('Scanning workspace "Audio folder"...');
    try {
      const res = await api.scanWorkspace();
      setStatusMessage(`Scanning workspace folder: ${res.added.join(', ') || 'Audio folder'}!`);
      await refresh();
    } catch (e: any) {
      setStatusMessage(`Error: ${e?.message || 'Failed to scan workspace'}`);
    } finally {
      setBusy(false);
    }
  };

  const handleTrainModel = async () => {
    setBusy(true);
    setStatusMessage('Training recommendation model and analyzing audio features...');
    try {
      await api.trainModel();
      setStatusMessage('AI Model training started! Features are being extracted and model updated.');
      await refresh();
    } catch (e: any) {
      setStatusMessage(`Error: ${e?.message || 'Training failed'}`);
    } finally {
      setBusy(false);
    }
  };

  const handleRemoveFolder = async (id: number) => {
    await api.removeFolder(id);
    await refresh();
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Manage music folders, AI audio feature extraction, privacy, and models.</p>
      </div>

      {statusMessage && (
        <div style={{ padding: '10px 16px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, marginBottom: 24, fontSize: 14 }}>
          {statusMessage}
        </div>
      )}

      <section style={{ marginBottom: 32 }}>
        <h2>Music folders</h2>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
          <button className="btn" onClick={() => void handleBrowseFolder()} disabled={busy}>
            <FolderOpen size={16} /> Browse folder
          </button>
          <button className="btn secondary" onClick={() => void handleScanWorkspace()} disabled={busy}>
            <Sparkles size={16} /> Quick Add Workspace "Audio folder"
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8, maxWidth: 540, marginBottom: 16 }}>
          <input
            placeholder="Or enter path (e.g. 'Audio folder' or C:\Music)..."
            value={folderPathInput}
            onChange={(e) => setFolderPathInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void handleAddCustomFolder(); }}
            style={{
              flex: 1,
              padding: '10px 14px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--bg-elevated)',
              color: 'var(--text-primary)',
            }}
          />
          <button className="btn" onClick={() => void handleAddCustomFolder()} disabled={busy || !folderPathInput.trim()}>
            Add & Scan
          </button>
        </div>

        {folders.length > 0 && (
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {folders.map((f) => (
              <li key={f.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--bg-elevated)', borderRadius: 6, marginBottom: 6 }}>
                <span className="muted" style={{ wordBreak: 'break-all' }}>{f.path}</span>
                <button className="btn secondary" style={{ fontSize: 12, padding: '4px 8px' }} onClick={() => void handleRemoveFolder(f.id)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={{ marginBottom: 32 }}>
        <h2>AI Model & Processing</h2>
        <p className="muted small" style={{ marginBottom: 16 }}>
          Extracts 13 MFCCs, Chroma harmony, BPM, loudness, spectral profiles, and estimates 9-dimensional mood distributions.
        </p>

        <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
          <button className="btn" onClick={() => void handleTrainModel()} disabled={busy}>
            <Sparkles size={16} /> Train & Update Model Now
          </button>
          <button className="btn secondary" onClick={() => void api.triggerScan().then(refresh)} disabled={busy}>
            <RefreshCw size={16} /> Re-scan library
          </button>
        </div>

        {scan && scan.is_scanning && (
          <div className="card" style={{ padding: 16, marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span>Scanning Folders:</span>
              <strong>{scan.scanned} / {scan.total_files} files</strong>
            </div>
            <div style={{ width: '100%', height: 8, background: 'var(--bg-surface, #222)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{ width: `${scan.total_files ? (scan.scanned / scan.total_files) * 100 : 0}%`, height: '100%', background: 'var(--accent, #6366f1)', transition: 'width 0.3s' }} />
            </div>
          </div>
        )}

        {processing && (
          <div className="card" style={{ padding: 16, marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span>Audio Analysis Coverage:</span>
              <strong>{processing.audio_analysis}% ({processing.total_songs} songs)</strong>
            </div>
            <div style={{ width: '100%', height: 8, background: 'var(--bg-surface, #222)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{ width: `${processing.audio_analysis}%`, height: '100%', background: 'var(--accent, #6366f1)', transition: 'width 0.3s' }} />
            </div>
          </div>
        )}

        <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
          <input
            type="checkbox"
            checked={Boolean(settings.background_analysis ?? true)}
            onChange={(e) => void api.updateSettings({ background_analysis: e.target.checked }).then(refresh)}
          />
          Automatic background audio feature extraction
        </label>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="checkbox"
            checked={Boolean(settings.enrichment_enabled ?? false)}
            onChange={(e) => void api.updateSettings({ enrichment_enabled: e.target.checked }).then(refresh)}
          />
          Online metadata enrichment (MusicBrainz)
        </label>
      </section>

      <section>
        <h2>Privacy & database</h2>
        <p className="muted small">All audio processing and model inference run completely offline on your device.</p>
        <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
          <button className="btn secondary" onClick={() => void api.clearCache().then(() => setStatusMessage('Cache cleared.'))}>
            Clear cache
          </button>
          <button className="btn secondary" onClick={() => void api.resetDatabase().then(() => { setStatusMessage('Database reset.'); void refresh(); })}>
            Reset database
          </button>
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
