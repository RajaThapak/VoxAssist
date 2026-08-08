import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "mock_key")
    RIME_API_KEY: str = os.getenv("RIME_API_KEY", "mock_key")
    RIME_VOICE_ID: str = os.getenv("RIME_VOICE_ID", "marcus")
    RIME_SPEAKER_SPEED: float = float(os.getenv("RIME_SPEAKER_SPEED", "1.0"))
    
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "voxassist")
    
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    @property
    def is_openai_live(self) -> bool:
        return bool(self.OPENAI_API_KEY and self.OPENAI_API_KEY != "mock_key" and not self.OPENAI_API_KEY.startswith("your_"))

    @property
    def is_rime_live(self) -> bool:
        return bool(self.RIME_API_KEY and self.RIME_API_KEY != "mock_key" and not self.RIME_API_KEY.startswith("your_"))

settings = Settings()
