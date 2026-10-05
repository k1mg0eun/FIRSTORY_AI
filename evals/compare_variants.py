"""
같은 입력·같은 인터뷰로 설계 방식만 바꿔 동화를 다시 뽑아 나란히 본다. (텍스트만, 이미지 없음)
  uv run python evals/compare_variants.py out/<A 실행 폴더> [out/<A 실행 폴더> ...]

A = 기존 실행 결과 (동물·동화적 공간·열린 결말)
B = evals/variants/b/ 프롬프트 (닮은 사람 아이·아는 공간·끝나는 사건). 근거: EVIDENCE.md §3
기본 파이프라인은 바꾸지 않는다. 결과는 <A 폴더>__B/ 와 out/compare-<이름>.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from firstory import llm  # noqa: E402
from firstory.nodes import story as story_node  # noqa: E402
from firstory.schemas import StoryInputContext  # noqa: E402

VARIANT = Path(__file__).parent / "variants" / "b"


# StoryDesign과 필드는 같고 설명만 B에 맞춘 것 (스키마 설명도 모델이 읽는다)
class ProtagonistB(BaseModel):
    name: str = Field(description="아이 이름이 아닌 새 이름. 2~3글자, 발음 쉬운")
    species: str = Field(description="'사람 아이'")
    traits: list[str]


class SupportingB(BaseModel):
    name: str
    species: str = Field(description="'사람 아이' 또는 '어른'")
    role: str = Field(description="주인공과의 관계. 예: 같은 반 친구, 엄마, 선생님")
    traits: list[str]


class StoryDesignB(BaseModel):
    protagonist: ProtagonistB
    supporting: Optional[SupportingB] = Field(None, description="이야기에 가장 필요한 한 명. 꼭 없어도 되면 null")
    world: str = Field(description="아이가 아는 일상 공간. 실제 기관 이름 없이")
    mirrored_situation: str = Field(description="감정 구조는 같고 겉의 디테일은 바꾼, 비슷한 일을 겪는 다른 아이의 상황")
    values_to_honor: list[str] = Field(description="이야기 안에 자연스럽게 있되 결론으로 주입하지 않을 가치")
    story_arc: list[str] = Field(description="페이지 흐름 요약 (배경→발단→감정→주인공의 시도→결과→반응)")


def run_b(a_dir: Path) -> Path:
    ctx = StoryInputContext(**json.loads((a_dir / "00-context.json").read_text(encoding="utf-8")))
    summary = json.loads((a_dir / "01-interview.json").read_text(encoding="utf-8")).get("summary") or ""
    state = {"context": ctx, "interview_summary": summary}

    prompts, design_schema = llm._PROMPTS, story_node.StoryDesign
    llm._PROMPTS, story_node.StoryDesign = VARIANT, StoryDesignB
    try:
        state.update(story_node.design_story(state))
        state.update(story_node.write_story(state))
    finally:
        llm._PROMPTS, story_node.StoryDesign = prompts, design_schema
    state.update(story_node.reading_guide(state))  # 가이드 프롬프트는 A와 동일

    b_dir = a_dir.with_name(a_dir.name + "__B")
    b_dir.mkdir(exist_ok=True)
    for name, key in (("02-design.json", "story_design"), ("03-story.json", "story"), ("04-guide.json", "guide")):
        (b_dir / name).write_text(json.dumps(state[key].model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return b_dir


def _load(d: Path):
    j = lambda n: json.loads((d / n).read_text(encoding="utf-8"))
    return j("02-design.json"), j("03-story.json"), j("04-guide.json")


def compare_md(a_dir: Path, b_dir: Path) -> str:
    (da, sa, ga), (db, sb, gb) = _load(a_dir), _load(b_dir)
    cell = lambda s: str(s).replace("\n", " ").replace("|", "\\|")
    who = lambda d: f"{d['protagonist']['name']} ({d['protagonist']['species']})" + (
        f" · {d['supporting']['name']} ({d['supporting']['role']})" if d.get("supporting") else "")
    out = [f"# {a_dir.name.split('_', 1)[-1]}: A vs B", "",
           "| | A. 지금 방식 | B. 닮은 아이·아는 공간·끝나는 사건 |", "|---|---|---|",
           f"| 제목 | {cell(sa['title'])} | {cell(sb['title'])} |",
           f"| 인물 | {cell(who(da))} | {cell(who(db))} |",
           f"| 배경 | {cell(da['world'])} | {cell(db['world'])} |"]
    pa, pb = {p["order"]: p["text"] for p in sa["pages"]}, {p["order"]: p["text"] for p in sb["pages"]}
    for o in sorted(set(pa) | set(pb)):
        out.append(f"| {o}쪽 | {cell(pa.get(o, ''))} | {cell(pb.get(o, ''))} |")
    qs = lambda g: "<br>".join(f"({q['after_page']}쪽 뒤) {cell(q['text'])}" for q in g["prompts"])
    out += [f"| 가이드 질문 | {qs(ga)} | {qs(gb)} |",
            f"| 연결 질문 | {cell(ga['after_reading'].get('bridge_question', ''))} | {cell(gb['after_reading'].get('bridge_question', ''))} |", ""]
    return "\n".join(out)


def main():
    for arg in sys.argv[1:]:
        a_dir = Path(arg)
        b_dir = run_b(a_dir)
        md = a_dir.parent / f"compare-{a_dir.name.split('_', 1)[-1]}.md"
        md.write_text(compare_md(a_dir, b_dir), encoding="utf-8")
        print("→", md)


if __name__ == "__main__":
    main()
