"""
스키마 — 백엔드 개발 사전 조사 ①③⑤ 확정안을 pydantic으로 옮긴 것.
💡 표시는 ARCHITECTURE.md 제안 항목.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────
# ① StoryInputContext — 1차 폼 + 인터뷰가 함께 채우는 입력 Context
# ──────────────────────────────────────────────────────────────
SituationCategory = Literal[
    "friend_conflict",   # 친구와 갈등
    "new_environment",   # 새로운 환경(입학, 이사 등)
    "separation",        # 이별·죽음
    "safety",            # 안전교육
    "rules",             # 규칙·훈육
    "family_change",     # 가족 변화(동생, 이혼 등)
    "fear",              # 두려움(병원, 어둠 등)
    "other",
]
Trait = Literal["shy", "active", "sensitive", "curious", "stubborn", "cautious", "other"]
Interest = Literal["dinosaur", "space", "animal", "vehicle", "princess", "hero", "drawing", "other"]
Reaction = Literal["cried", "silent", "angry_outburst", "clingy", "avoided", "asked_questions", "other"]
Emotion = Literal["sad", "angry", "scared", "confused", "ashamed", "excited", "unknown"]
MessageDirection = Literal[
    "comfort_first",       # 아이 마음 위로 우선
    "perspective_taking",  # 상대 입장 생각해보기
    "explain_situation",   # 상황 자체를 설명
    "set_boundary",        # 규칙·경계 전달
    "reassure",            # 안심시키기
    "undecided",
]


class Situation(BaseModel):
    category: SituationCategory
    custom_category: Optional[str] = None
    timing: Literal["past", "upcoming"]
    description: str = Field(max_length=60, description="상황에 대한 짧은 설명")


class Child(BaseModel):
    age_months: int = Field(description="만 나이×12 + 개월")
    gender: Literal["male", "female", "unspecified"] = "unspecified"
    traits: list[Trait] = []
    custom_trait: Optional[str] = None
    interests: list[Interest] = []
    custom_interest: Optional[str] = None


class Moment(BaseModel):
    """당시 정보. timing=upcoming 이면 비어 있을 수 있음."""
    reactions: list[Reaction] = []
    custom_reaction: Optional[str] = None
    emotions: list[Emotion] = []


class Parent(BaseModel):
    """전부 인터뷰에서 채움."""
    response: Optional[str] = Field(None, description="당시 부모가 어떻게 대응했는지")
    concern: Optional[str] = Field(None, description="부모가 고민하는 지점. '딱히 없다'도 유효")
    message: Optional[str] = Field(None, description="아이에게 전달하고 싶은 메시지 (원문 그대로)")
    message_direction: Optional[MessageDirection] = Field(
        None, description="AI가 정리한 전달 방향. 모르면 undecided"
    )


class StoryInputContext(BaseModel):
    situation: Situation
    child: Child
    moment: Moment = Moment()
    parent: Parent = Parent()

    # 종료 조건 이중 확인 (서버 쪽 판단, AI 말만 믿지 않음)
    def missing_fields(self) -> list[str]:
        m: list[str] = []
        if not self.parent.concern:
            m.append("parent.concern")
        if not self.parent.message_direction:
            m.append("parent.message_direction")
        if self.situation.timing == "past" and self.moment.emotions == ["unknown"]:
            m.append("moment.emotions(unknown→1회 보완 시도)")
        return m

    def is_sufficient(self) -> bool:
        return bool(self.parent.concern) and bool(self.parent.message_direction)


# ──────────────────────────────────────────────────────────────
# ② 인터뷰 — Role A
# ──────────────────────────────────────────────────────────────
class ParentUpdate(BaseModel):
    response: Optional[str] = None
    concern: Optional[str] = None
    message: Optional[str] = None
    message_direction: Optional[MessageDirection] = None


class MomentUpdate(BaseModel):
    reactions: Optional[list[Reaction]] = None
    custom_reaction: Optional[str] = None
    emotions: Optional[list[Emotion]] = None


class InterviewTurnResult(BaseModel):
    """AI가 매 턴 '질문'과 '필드 추출'을 동시에 한다."""
    context_update: ParentUpdate = Field(description="이번 답변(및 지금까지 대화)에서 뽑은 부모 정보")
    moment_update: Optional[MomentUpdate] = Field(None, description="당시 정보가 보완됐으면")
    status: Literal["ask", "sufficient"]
    next_question: Optional[str] = Field(None, description="status=ask 일 때 다음 질문 하나")
    reason: str = Field(description="디버깅용: 왜 이 질문을 했는지 / 왜 충분하다고 봤는지")


class InterviewSummary(BaseModel):
    summary: str = Field(description="이 부모는 ~를 걱정하고 ~를 전하고 싶어한다 — 한 문단")


class Turn(BaseModel):
    question: str
    answer: str
    reason: str = ""


# ──────────────────────────────────────────────────────────────
# 💡 StoryDesign — 간접화 설계 (design_story 노드)
# ──────────────────────────────────────────────────────────────
class Protagonist(BaseModel):
    name: str = Field(description="아이 이름이 아닌 새 이름. 2~3글자, 발음 쉬운")
    species: str = Field(description="아이 관심사에서 끌어온 동물/존재")
    traits: list[str]


class SupportingCharacter(BaseModel):
    name: str
    species: str
    role: str = Field(description="주인공과의 관계. 예: 보호자(큰 고슴도치), 친구, 선생님")
    traits: list[str]


class StoryDesign(BaseModel):
    protagonist: Protagonist
    supporting: Optional[SupportingCharacter] = Field(
        None, description="조연 1명. 보호자 역할이 거의 항상 필요하다. 꼭 없어도 되면 null"
    )
    world: str = Field(description="실제 장소를 그대로 쓰지 않은 동화적 배경")
    mirrored_situation: str = Field(description="실제 상황을 한 걸음 떨어진 동화적 상황으로 재구성")
    values_to_honor: list[str] = Field(description="이야기 안에 자연스럽게 있되 결론으로 주입하지 않을 가치")
    story_arc: list[str] = Field(description="페이지 흐름 요약 (시작→상황→감정→교류→열린 결말)")


# ──────────────────────────────────────────────────────────────
# ④ 동화 텍스트 — 생성기
# ──────────────────────────────────────────────────────────────
class CharacterSheet(BaseModel):
    name: str = Field(description="동화 속 이름 (한국어)")
    role: Literal["protagonist", "supporting"]
    visual_description: str = Field(
        description="외형 한 문단: 종, 몸 색, 크기감(주인공 대비), 눈, 특징적 표식/소지품, 옷. 모든 페이지에서 같게 그려질 고정 특징. 영어로"
    )


class StoryPage(BaseModel):
    order: int = Field(description="1부터")
    text: str = Field(description="4~6세 눈높이, 2~4문장")
    characters_in_scene: list[str] = Field(description="이 페이지 그림에 등장하는 캐릭터 이름들 (CharacterSheet.name과 동일하게)")
    image_prompt: str = Field(
        description="이 페이지 장면. 캐릭터 외형은 반복하지 말고 **정확한 자세·동작·위치·표정·구도**를 구체적으로. 본문의 미묘한 동작(예: 바퀴 하나만 담요 밖으로)을 그대로. 영어로"
    )


class StoryText(BaseModel):
    title: str
    characters: list[CharacterSheet] = Field(description="주인공 1 + 조연 0~1. 설계의 인물 그대로")
    style_guide: str = Field(description="그림책 화풍 (예: soft watercolor, warm pastel, rounded outlines). 영어로")
    pages: list[StoryPage]

    def protagonist(self) -> CharacterSheet:
        return next((c for c in self.characters if c.role == "protagonist"), self.characters[0])


# ──────────────────────────────────────────────────────────────
# ③ ReadingGuide — Role B
# ──────────────────────────────────────────────────────────────
PromptPurpose = Literal["empathy", "predict", "perspective", "connect"]


class GuidePrompt(BaseModel):
    id: str
    after_page: int = Field(description="이 페이지를 읽은 뒤 등장")
    text: str = Field(description="아이에게 하는 질문. 캐릭터의 속마음 형태")
    purpose: PromptPurpose
    parent_hint: Optional[str] = Field(None, description="부모용 한 줄. '아이가 대답 안 해도 괜찮아요'")


class BeforeReading(BaseModel):
    intent: str = Field(description="이 동화가 담은 방향 한 문단")
    tips: list[str] = Field(description="2~3개. 지시가 아닌 제안")


class AfterReading(BaseModel):
    bridge_question: str = Field(description="아이 실제 경험으로 연결하는 질문")
    if_undecided: Optional[str] = Field(
        None, description="message_direction=undecided 일 때만: 부모가 스스로 정리하도록 돕는 문장"
    )


class ReadingGuide(BaseModel):
    prompts: list[GuidePrompt] = Field(description="기본 2개, 최대 3개")
    before_reading: BeforeReading
    after_reading: AfterReading


# ──────────────────────────────────────────────────────────────
# 산출물 / 상태
# ──────────────────────────────────────────────────────────────
class PageImage(BaseModel):
    order: int
    path: Optional[str] = None
    status: Literal["pending", "generating", "completed", "failed"] = "pending"
    error: Optional[str] = None


class Illustrations(BaseModel):
    character_sheets: dict[str, str] = {}   # 이름 → 파일 경로
    pages: list[PageImage] = []

    @property
    def character_sheet_path(self) -> Optional[str]:  # 하위 호환 (주인공)
        return next(iter(self.character_sheets.values()), None)


class CostEntry(BaseModel):
    node: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    images: int = 0
    ms: int = 0


StoryStatus = Literal["requested", "generating_text", "reviewing", "generating_images", "completed", "failed"]
RegenerateScope = Literal["character", "story", "text", "images"]
