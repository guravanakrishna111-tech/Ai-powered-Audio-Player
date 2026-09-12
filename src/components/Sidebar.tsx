import {
  Home,
  Library,
  Users,
  Disc3,
  ListMusic,
  Heart,
  PlayCircle,
  Settings,
} from 'lucide-react';
import './Sidebar.css';

export type ViewId =
  | 'home'
  | 'library'
  | 'artists'
  | 'albums'
  | 'playlists'
  | 'favorites'
  | 'now-playing'
  | 'settings';

interface SidebarProps {
  activeView: ViewId;
  onNavigate: (view: ViewId) => void;
}

const NAV_ITEMS: { id: ViewId; label: string; icon: typeof Home }[] = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'library', label: 'Library', icon: Library },
  { id: 'artists', label: 'Artists', icon: Users },
  { id: 'albums', label: 'Albums', icon: Disc3 },
  { id: 'playlists', label: 'Playlists', icon: ListMusic },
  { id: 'favorites', label: 'Favorites', icon: Heart },
  { id: 'now-playing', label: 'Now Playing', icon: PlayCircle },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export function Sidebar({ activeView, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon">♪</div>
        <div>
          <strong>AI Audio Player</strong>
          <span>Local-first music</span>
        </div>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`nav-item ${activeView === id ? 'active' : ''}`}
            onClick={() => onNavigate(id)}
          >
            <Icon size={18} />
            {label}
          </button>
        ))}
      </nav>
    </aside>
  );
}
