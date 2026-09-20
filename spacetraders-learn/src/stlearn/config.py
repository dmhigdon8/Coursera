from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    spacetraders_token: str = ""
    spacetraders_account_token: str = ""
    spacetraders_symbol: str = "LEARNER"
    spacetraders_faction: str = "COSMIC"
    stlearn_data_dir: Path = Path("data")
    stlearn_db_path: Path = Path("data/warehouse/spacetraders.db")
    api_base: str = "https://api.spacetraders.io/v2"

    @property
    def raw_dir(self) -> Path:
        return self.stlearn_data_dir / "raw"

    @property
    def warehouse_dir(self) -> Path:
        return self.stlearn_data_dir / "warehouse"


def get_settings() -> Settings:
    return Settings()
