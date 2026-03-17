import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    host: str = os.getenv("DM_HOST", "localhost")
    port: int = int(os.getenv("DM_PORT", "20194"))
    scheme: str = os.getenv("DM_SCHEME", "https")
    username: str = os.getenv("DM_USERNAME", "root")
    password: str = os.getenv("DM_PASSWORD", "")
    verify_ssl: bool = os.getenv("DM_VERIFY_SSL", "false").lower() in ("true", "1", "yes")
    token_refresh_margin: int = int(os.getenv("DM_TOKEN_REFRESH_MARGIN", "60"))

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/api/v1.0"


config = Config()
