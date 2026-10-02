import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str) -> str:
    v = os.getenv(name, "").strip()
    return v or default


@dataclass(frozen=True)
class Config:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model_light: str = _env("MODEL_LIGHT", "gpt-5-mini")
    model_main: str = _env("MODEL_MAIN", "gpt-5")
    image_model: str = _env("IMAGE_MODEL", "gpt-image-2")
    image_quality: str = _env("IMAGE_QUALITY", "medium")
    image_size: str = _env("IMAGE_SIZE", "1024x1024")
    image_concurrency: int = int(_env("IMAGE_CONCURRENCY", "3"))

    page_count: int = 8
    max_interview_turns: int = 5        # 🔒 ②-5
    max_clarify_turns: int = 2          # 🔒 ②-4 "모르겠다" 정리 질문
    guide_prompts_min: int = 2          # 🔒 ③-4
    guide_prompts_max: int = 3

    out_dir: Path = ROOT / "out"
    checkpoint_db: Path = ROOT / "out" / "checkpoints.db"


config = Config()
config.out_dir.mkdir(parents=True, exist_ok=True)
