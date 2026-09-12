import type { ProcessingProgress, ScanProgress } from '../types/music';
import './ProcessingBanner.css';

interface ProcessingBannerProps {
  scan: ScanProgress | null;
  processing: ProcessingProgress | null;
}

export function ProcessingBanner({ scan, processing }: ProcessingBannerProps) {
  const showScan = scan?.is_scanning;
  const showProcessing =
    processing &&
    processing.total_songs > 0 &&
    (processing.audio_analysis < 100 || processing.metadata < 100);

  if (!showScan && !showProcessing) return null;

  return (
    <div className="processing-banner">
      {showScan && (
        <div className="processing-item">
          <span>Scanning: {scan.scanned}/{scan.total_files}</span>
          <div className="progress-bar">
            <span
              style={{
                width: `${scan.total_files ? (scan.scanned / scan.total_files) * 100 : 0}%`,
              }}
            />
          </div>
        </div>
      )}
      {showProcessing && (
        <>
          <div className="processing-item">
            <span>Metadata: {processing.metadata}%</span>
            <div className="progress-bar"><span style={{ width: `${processing.metadata}%` }} /></div>
          </div>
          <div className="processing-item">
            <span>Audio analysis: {processing.audio_analysis}%</span>
            <div className="progress-bar"><span style={{ width: `${processing.audio_analysis}%` }} /></div>
          </div>
        </>
      )}
    </div>
  );
}
