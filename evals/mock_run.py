"""
API 없이 그래프가 끝까지 도는지 확인. (uv run python evals/mock_run.py)
LLM/이미지 호출을 가짜로 바꿔치기한다. 품질 평가가 아니라 배선 확인용.
"""
from __future__ import annotations

import io
import json
import struct
import sys
import zlib
from pathlib import Path

from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from firstory import llm  # noqa: E402
from firstory.graph import compile_graph, new_thread_id  # noqa: E402
from firstory.nodes import illustrate as ill  # noqa: E402
from firstory.schemas import (  # noqa: E402
    AfterReading, BeforeReading, GuidePrompt, InterviewSummary, InterviewTurnResult, ParentUpdate,
    Protagonist, ReadingGuide, StoryDesign, StoryPage, StoryText, CharacterSheet, SupportingCharacter,
)

_turn = {"n": 0}


def fake_structured(*, node, model, schema, system, user):
    if schema is InterviewTurnResult:
        _turn["n"] += 1
        if _turn["n"] == 1:
            return InterviewTurnResult(context_update=ParentUpdate(), status="ask",
                                       next_question="당시에 어떻게 반응해주셨어요?", reason="response 비어있음")
        if _turn["n"] == 2:
            return InterviewTurnResult(context_update=ParentUpdate(response="안아줌", concern="뭐라고 말할지 모르겠음"),
                                       status="ask", next_question="아이 마음을 먼저 다독이고 싶으신지, 친구 입장도 생각해보게 하고 싶으신지요?",
                                       reason="direction 비어있음")
        return InterviewTurnResult(context_update=ParentUpdate(message_direction="comfort_first", message="네 잘못 아니야"),
                                   status="sufficient", reason="다 채워짐")
    if schema is InterviewSummary:
        return InterviewSummary(summary="이 부모는 아이 마음을 먼저 받아주고 싶어하며, 친구를 나쁘게 만들고 싶지 않다.")
    if schema is StoryDesign:
        return StoryDesign(protagonist=Protagonist(name="포포", species="분홍 토끼", traits=["조심스러움"]),
                           supporting=SupportingCharacter(name="엄마곰", species="갈색 곰", role="보호자", traits=["느긋함"]),
                           world="숲속 그림 교실", mirrored_situation="같이 그리던 다람쥐가 오늘은 혼자 그리겠다고 함",
                           values_to_honor=["아이 마음 먼저"], story_arc=["시작", "상황", "감정", "교류", "열린 결말"])
    if schema is StoryText:
        return StoryText(title="포포와 비어 있는 자리",
                         characters=[CharacterSheet(name="포포", role="protagonist", visual_description="small pink rabbit"),
                                     CharacterSheet(name="엄마곰", role="supporting", visual_description="large brown bear")],
                         style_guide="soft watercolor",
                         pages=[StoryPage(order=i, text=f"{i}페이지. 포포는 깡충 뛰었어요.", characters_in_scene=["포포"] + (["엄마곰"] if i % 2 == 0 else []), image_prompt=f"scene {i}") for i in range(1, 9)])
    if schema is ReadingGuide:
        return ReadingGuide(prompts=[GuidePrompt(id="q1", after_page=3, text="포포는 어떤 기분이었을까요?", purpose="empathy", parent_hint="대답 안 해도 괜찮아요"),
                                     GuidePrompt(id="q2", after_page=8, text="내일 포포는 뭐라고 말하고 싶을까요?", purpose="predict")],
                            before_reading=BeforeReading(intent="거절당한 마음을 함께 보기", tips=["3페이지에서 잠깐 멈춰보세요"]),
                            after_reading=AfterReading(bridge_question="너도 포포처럼 느낀 적 있어?"))
    raise RuntimeError(f"mock 없음: {schema}")


def tiny_png(_prompt, _refs):
    # 1x1 PNG
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"\x00\xff\xcc\xaa"
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


llm.set_structured_override(fake_structured)
ill.set_image_override(tiny_png)

data = json.loads((Path(__file__).resolve().parents[1] / "datasets/inputs/donggeul.json").read_text(encoding="utf-8"))
data.pop("scripted_answers", None)

graph = compile_graph(Path(__file__).resolve().parents[1] / "out" / "mock-checkpoints.db")

# ── 1) interrupt 경로: 인터뷰 질문 2개 + 검토 → 재생성(images) → 완료 ──
tid = new_thread_id()
cfg = {"configurable": {"thread_id": tid}}
r = graph.invoke({"context": data, "auto_answers": [], "auto_approve": False, "skip_images": False}, cfg)
seen = []
while "__interrupt__" in r:
    p = r["__interrupt__"][0].value
    seen.append(p["type"])
    if p["type"] == "interview":
        r = graph.invoke(Command(resume="답변 " + str(p["turn"])), cfg)
    elif p["type"] == "review":
        if seen.count("review") == 1:
            r = graph.invoke(Command(resume={"action": "regenerate", "scope": "images", "feedback": "3"}), cfg)
        else:
            r = graph.invoke(Command(resume={"action": "approve"}), cfg)
print("interrupts:", seen)
assert seen == ["interview", "interview", "review", "review"], seen  # images 재생성 → render → review 다시
assert r["status"] == "completed" and len(r["guide"].prompts) == 2
nodes = [c.node for c in r["cost"]]
assert nodes.count("illustrate:page3") == 2 and nodes.count("illustrate:page1") == 1, nodes  # 3페이지만 다시 그림
assert nodes.count("illustrate:sheet:포포") == 1 and nodes.count("illustrate:sheet:엄마곰") == 1, nodes  # 시트는 재사용
print("run_dir:", r["run_dir"])

# ── 2) --auto 경로: scripted answers + auto_approve + 병렬 fan-in ──
_turn["n"] = 0
tid2 = new_thread_id()
cfg2 = {"configurable": {"thread_id": tid2}}
r2 = graph.invoke({"context": data, "auto_answers": ["a1", "a2"], "auto_approve": True, "skip_images": False}, cfg2)
assert "__interrupt__" not in r2
assert r2["status"] == "completed" and r2["guide"] is not None and r2["illustrations"] is not None
assert len(r2["interview_turns"]) == 2 and r2["interview_done_by"] == "sufficient"
assert all(p.status == "completed" for p in r2["illustrations"].pages)
out = Path(r2["run_dir"])
assert (out / "book.html").exists() and (out / "images" / "page-08.png").exists()
assert len(r2["illustrations"].character_sheets) == 2
print("auto ok:", out, "cost entries:", len(r2["cost"]))

# ── 3) 재개: 인터뷰 중간에 멈춘 thread를 get_state 로 보고 이어가기 ──
_turn["n"] = 0
tid3 = new_thread_id()
cfg3 = {"configurable": {"thread_id": tid3}}
r3 = graph.invoke({"context": data, "auto_answers": [], "auto_approve": True, "skip_images": True}, cfg3)
assert "__interrupt__" in r3
snap = graph.get_state(cfg3)
assert snap.next == ("interview_answer",), snap.next
r3 = graph.invoke(Command(resume="skip"), cfg3)      # user_skip 경로
assert r3["interview_done_by"] == "user_skip" and r3["status"] == "completed"
assert r3["context"].parent.message_direction == "undecided"
print("resume/skip ok")

print("\nALL OK")
