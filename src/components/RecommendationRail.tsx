import { useEffect, useState } from 'react';
import { Play } from 'lucide-react';
import { toArtworkUrl } from '../api/client';
import type { RecommendationItem, Song } from '../types/music';
import './RecommendationRail.css';

interface RecommendationRailProps {
  recommendations: RecommendationItem[];
  loading?: boolean;
  error?: string | null;
  candidateCount?: number;
  latencyMs?: number;
  onPlay: (song: Song, queue: Song[]) => void;
}

export function RecommendationRail({
  recommendations,
  loading = false,
  error = null,
  candidateCount,
  latencyMs,
  onPlay,
}: RecommendationRailProps) {
  if (loading) {
    return (
      <section className="recommendation-rail">
        <div className="recommendation-header">
          <div>
            <h2>AI Recommendations</h2>
            <p className="muted">Finding similar songs from your local library.</p>
          </div>
        </div>
        <div className="muted small">Loading recommendations...</div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="recommendation-rail">
        <div className="recommendation-header">
          <div>
            <h2>AI Recommendations</h2>
            <p className="muted">Recommendation lookup is unavailable right now.</p>
          </div>
        </div>
        <div className="muted small">{error}</div>
      </section>
    );
  }

  return (
    <section className="recommendation-rail">
      <div className="recommendation-header">
        <div>
          <h2>AI Recommendations</h2>
          <p className="muted">Ranked from your local analysis, metadata, and mood profile.</p>
        </div>
        <div className="recommendation-meta muted small">
          {candidateCount != null && <span>{candidateCount} candidates</span>}
          {latencyMs != null && <span>{latencyMs} ms</span>}
        </div>
      </div>

      {recommendations.length === 0 ? (
        <div className="muted small">No eligible recommendations yet. Add more analyzed songs and try again.</div>
      ) : (
        <div className="recommendation-list">
          {recommendations.map((item) => (
            <RecommendationCard
              key={item.song.id}
              item={item}
              onPlay={() => onPlay(item.song, recommendations.map((entry) => entry.song))}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function RecommendationCard({
  item,
  onPlay,
}: {
  item: RecommendationItem;
  onPlay: () => void;
}) {
  const [artworkUrl, setArtworkUrl] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!item.song.artwork_path) {
      setArtworkUrl(null);
      return;
    }
    void (async () => {
      try {
        const url = await toArtworkUrl(item.song.artwork_path!);
        if (active) {
          setArtworkUrl(url);
        }
      } catch {
        if (active) {
          setArtworkUrl(null);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [item.song.artwork_path]);

  return (
    <button className="recommendation-card" onClick={onPlay}>
      <div className="artwork recommendation-artwork">
        {artworkUrl ? <img src={artworkUrl} alt="" /> : <span>♫</span>}
      </div>
      <div className="recommendation-content">
        <div className="recommendation-topline">
          <strong>{item.song.title}</strong>
          <span className="recommendation-score">{Math.round(item.score * 100)}%</span>
        </div>
        <div className="muted small">{item.song.artist_name}</div>
        <div className="muted small">{item.song.album_title}</div>
        <div className="recommendation-reasons">
          {item.reasons.slice(0, 3).map((reason) => (
            <span key={reason} className="recommendation-chip">
              {reason}
            </span>
          ))}
        </div>
      </div>
      <div className="recommendation-play">
        <Play size={18} />
      </div>
    </button>
  );
}

