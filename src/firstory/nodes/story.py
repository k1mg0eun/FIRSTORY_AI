"""design_story (💡) → write_story (🔒 생성기) → parent_review (interrupt) → reading_guide (🔒 Role B)"""
from __future__ import annotations

from langgraph.graph import END
from langgraph.types import interrupt

from ..config import config
from ..llm import prompt, structured
from ..schemas import ReadingGuide, StoryDesign, StoryText
from ..state import PipelineState

_persona = prompt("_persona")


def _age(ctx):
    return ctx.child.age_months // 12, ctx.child.age_months


def design_story(state: PipelineState) -> dict:
    ctx = state["context"]
    d, cost = structured(
        node="design_story",
        model=config.model_main,
        schema=StoryDesign,
        system=prompt(
            "design_story",
            persona=_persona,
            context=ctx,
            summary=state.get("interview_summary") or "",
            interests=", ".join(ctx.child.interests + ([ctx.child.custom_interest] if ctx.child.custom_interest else [])) or "(없음)",
            traits=", ".join(ctx.child.traits + ([ctx.child.custom_trait] if ctx.child.custom_trait else [])) or "(없음)",
            page_count=config.page_count,
        ),
        user="이야기를 설계하세요.",
        reasoning="medium",
    )
    return {"story_design": d, "cost": [cost]}


def write_story(state: PipelineState) -> dict:
    ctx = state["context"]
    years, months = _age(ctx)
    fb = state.get("writer_feedback")
    feedback_block = ""
    if fb:
        prev = state.get("story")
        feedback_block = (
            "## 부모 피드백 (이 부분만 고치고 나머지는 최대한 유지)\n" + fb
            + ("\n\n## 기존 원고\n" + prev.model_dump_json(indent=2, exclude={"character_sheet", "style_guide"}) if prev else "")
        )
    s, cost = structured(
        node="write_story",
        model=config.model_main,
        schema=StoryText,
        system=prompt(
            "write_story",
            persona=_persona,
            context=ctx,
            summary=state.get("interview_summary") or "",
            design=state.get("story_design"),
            page_count=config.page_count,
            age_years=years,
            age_months=months,
            feedback=feedback_block,
        ),
        user="동화를 작성하세요.",
        reasoning="medium",
    )
    s.pages.sort(key=lambda p: p.order)
    return {"story": s, "writer_feedback": None, "cost": [cost], "status": "generating_images"}


def parent_review(state: PipelineState) -> dict:
    """⏸ 부모 검토 — 텍스트+이미지+가이드 완성 후 (기획안 STEP 5~6).
    뷰어/CLI가 {action, scope, feedback}를 넣어주면 재개. 자동 재생성 없음."""
    if state.get("auto_approve"):
        return {"review_action": "approve", "regenerate_scope": None, "review_feedback": None, "status": "completed"}
    r = interrupt({
        "type": "review",
        "story": state["story"].model_dump(),
        "guide": state["guide"].model_dump() if state.get("guide") else None,
        "run_dir": state["run_dir"],
    }) or {}
    action = r.get("action", "approve")
    return {
        "review_action": action,
        "regenerate_scope": r.get("scope"),
        "review_feedback": r.get("feedback"),
        "writer_feedback": r.get("feedback") if r.get("scope") == "text" else None,
        "status": "completed" if action == "approve" else "generating_text",
    }


def route_after_review(state: PipelineState) -> str:
    if state.get("review_action") != "regenerate":
        return END
    scope = state.get("regenerate_scope")
    if scope in ("character", "story"):
        return "design_story"
    if scope == "images":
        return "illustrate_only"
    return "write_story"  # text / None


def reading_guide(state: PipelineState) -> dict:
    ctx = state["context"]
    story = state["story"]
    g, cost = structured(
        node="reading_guide",
        model=config.model_main,
        schema=ReadingGuide,
        system=prompt(
            "reading_guide",
            persona=_persona,
            context=ctx,
            summary=state.get("interview_summary") or "",
            pages=[{"order": p.order, "text": p.text} for p in story.pages],
            min_prompts=config.guide_prompts_min,
            max_prompts=config.guide_prompts_max,
            age_months=ctx.child.age_months,
        ),
        user="독서 가이드를 작성하세요.",
        reasoning="low",
    )
    g.prompts = g.prompts[: config.guide_prompts_max]
    return {"guide": g, "cost": [cost]}
