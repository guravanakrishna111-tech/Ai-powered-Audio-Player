import { useEffect, useState } from 'react';
import { Sidebar, type ViewId } from './components/Sidebar';
import { PlayerBar } from './components/PlayerBar';
import { AudioEngine } from './components/AudioEngine';
import { ProcessingBanner } from './components/ProcessingBanner';
import {
  HomePage,
  LibraryPage,
  ArtistsPage,
  AlbumsPage,
  PlaylistsPage,
  FavoritesPage,
  NowPlayingPage,
  SettingsPage,
  useProgressPolling,
} from './pages';
import { initApi } from './api/client';

function renderView(view: ViewId) {
  switch (view) {
    case 'home': return <HomePage />;
    case 'library': return <LibraryPage />;
    case 'artists': return <ArtistsPage />;
    case 'albums': return <AlbumsPage />;
    case 'playlists': return <PlaylistsPage />;
    case 'favorites': return <FavoritesPage />;
    case 'now-playing': return <NowPlayingPage />;
    case 'settings': return <SettingsPage />;
    default: return <HomePage />;
  }
}

export default function App() {
  const [view, setView] = useState<ViewId>('home');
  const [ready, setReady] = useState(false);
  const { scan, processing } = useProgressPolling();

  useEffect(() => {
    void initApi().then(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <div className="empty-state" style={{ height: '100vh' }}>
        <p>Starting AI Audio Player...</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Sidebar activeView={view} onNavigate={setView} />
      <div className="main-content">
        <ProcessingBanner scan={scan} processing={processing} />
        {renderView(view)}
      </div>
      <PlayerBar />
      <AudioEngine />
    </div>
  );
}
