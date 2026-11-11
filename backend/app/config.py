from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_default_data_dir() -> Path:
    # 1. Prefer project backend/data directory where database & analysis are stored
    project_data = Path(__file__).resolve().parent.parent / "data"
    if project_data.is_dir():
        return project_data
    # 2. User home fallback
    home_data = Path.home() / ".ai-audio-player" / "data"
    try:
        home_data.mkdir(parents=True, exist_ok=True)
        return home_data
    except Exception:
        project_data.mkdir(parents=True, exist_ok=True)
        return project_data


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AAP_")

    data_dir: Path = _resolve_default_data_dir()
    db_name: str = "library.db"
    supported_extensions: tuple[str, ...] = (
        ".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus"
    )
    scan_batch_size: int = 50
    analysis_workers: int = 2
    enrichment_enabled: bool = False
    musicbrainz_user_agent: str = "AI-Audio-Player/0.1.0 (local-first)"

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name

    @property
    def artwork_dir(self) -> Path:
        return self.data_dir / "artwork"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"


settings = Settings()
