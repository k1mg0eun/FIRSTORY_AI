"""계정에서 쓸 수 있는 모델 확인: uv run python -m firstory.models"""
from .llm import client

ids = sorted(m.id for m in client().models.list().data)
print("\n텍스트 (gpt-5*)\n  " + "\n  ".join(i for i in ids if i.startswith("gpt-5")))
print("\n이미지 (gpt-image*)\n  " + "\n  ".join(i for i in ids if i.startswith("gpt-image")))
print("\n→ .env 의 MODEL_LIGHT / MODEL_MAIN / IMAGE_MODEL 에 위 이름 중 하나.\n")
