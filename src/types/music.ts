export interface Song {
  id: number;
  file_path: string;
  title: string;
  duration: number | null;
  track_number: number | null;
  disc_number: number | null;
  artwork_path: string | null;
  is_favorite: number;
  play_count: number;
  analysis_status: string;
  artist_id: number;
  artist_name: string;
  album_id: number;
  album_title: string;
  album_year: number | null;
}

export interface RecommendationItem {
  rank: number;
  score: number;
  reasons: string[];
  breakdown: Record<string, number>;
  song: Song;
}

export interface RecommendationResponse {
  song_id: number;
  source_song: Song;
  recommendations: RecommendationItem[];
  candidate_count: number;
  latency_ms: number;
  algorithm_version: string;
  config_version: string;
  weights: Record<string, number>;
}

export interface Artist {
  id: number;
  name: string;
  song_count: number;
}

export interface Album {
  id: number;
  title: string;
  year: number | null;
  artwork_path: string | null;
  artist_name: string;
  song_count: number;
}

export interface ProcessingProgress {
  scanning: number;
  metadata: number;
  audio_analysis: number;
  enrichment: number;
  total_songs: number;
  is_processing: boolean;
}

export interface ScanProgress {
  total_files: number;
  scanned: number;
  added: number;
  updated: number;
  skipped: number;
  errors: number;
  is_scanning: boolean;
}

export type RepeatMode = 'off' | 'all' | 'one';
