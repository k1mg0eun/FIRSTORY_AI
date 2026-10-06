# FIRSTORY AI 파이프라인 — 백엔드 공유용 소개

> 레포: https://github.com/k1mg0eun/FIRSTORY_AI
> 2026-10-02 기준. 자세한 설계는 `ARCHITECTURE.md`, 실행법은 `README.md`.

## 한 줄로

부모가 아이 상황을 입력하면 → AI가 인터뷰로 고민을 구체화하고 → 간접화한 맞춤 동화(텍스트+그림)와 부모용 독서 가이드를 만들어서 → 부모가 검토·확정하는 흐름을 **로컬에서 끝까지 돌려볼 수 있는 프로토타입**.

서버·DB 없음. 터미널이나 Streamlit 뷰어로 돌리고, 결과는 `out/` 폴더에 쌓인다. 목적은 "동화가 얼마나 잘 나오는지"를 반복해서 보고 올리는 것.

## 스택

- **Python + LangGraph** — 플로우를 그래프로 선언. 인터뷰 루프, 사람 입력 대기(interrupt), 병렬 실행, 상태 저장·재개가 기본 제공
- **LangSmith** — 모든 LLM 호출이 자동 기록됨. "이 동화 왜 이렇게 나왔지?"를 노드별로 추적
- **OpenAI** — 텍스트 `gpt-5.5` / `gpt-5.4-mini`, 이미지 `gpt-image-2`
- **SQLite** — 그래프 상태 체크포인트 (`out/checkpoints.db`). 나중에 Postgres로 교체
- **Streamlit** — 입력↔출력 확인용 뷰어. 버리는 물건, 진짜 프론트 아님

## 흐름

```
form_input ─▶ interview(루프) ─▶ design_story ─▶ write_story ─┬─▶ reading_guide ─┐
                                                              └─▶ illustrate    ─┴─▶ render ─▶ ⏸ parent_review
                                                                                                    │
                                                                           완료 → END  /  재생성(scope) → 해당 노드로
```

| 노드 | 하는 일 | 모델 |
|---|---|---|
| `form_input` | 1차 폼 JSON 검증. 백엔드 사전조사 ①의 `StoryInputContext` 그대로 (pydantic) | – |
| `interview` | 비어 있는 필드(`concern`, `message_direction`)만 묻는다. 매 턴 **추출+질문 동시**, `missingFields`는 코드가 계산, 종료는 AI+코드 이중 확인. "모르겠다"→정리 질문 2회→`undecided`. 최대 5턴, skip 가능. 끝에 `summary` 한 문단 | mini |
| `design_story` | 간접화 설계: 주인공(아이 관심사에서)·조연(보호자)·세계·상황 재구성·`values_to_honor` | 5.5 |
| `write_story` | 8페이지 텍스트 + 캐릭터 시트(주인공·조연 외형) + 페이지별 이미지 프롬프트. **교훈 선언 금지, 사건은 닫고 의미는 엶, 사람 등장 금지, 질문은 안 씀** | 5.5 |
| `reading_guide` | Role B 독서 코치. 동화 속 질문 2개(`after_page`로 위치), 읽기 전 팁, 현실로 잇는 질문. 텍스트만 보므로 이미지와 **병렬** | 5.5 |
| `illustrate` | 캐릭터 시트 1장씩 생성 → 각 페이지는 그 장면에 나오는 캐릭터 시트만 참조 이미지로 넣어 병렬 생성 (동시 3장) | image-2 |
| `render` | 단계별 JSON + `book.html` | – |
| `parent_review` | 멈추고 사람 입력 대기. 완료 / 다시 쓰기(+피드백) / 캐릭터 바꾸기 / 그림만 다시 | – |

인터뷰는 실제로 `interview_step`(LLM) → `interview_answer`(interrupt) → … 세 노드로 쪼개져 있음. interrupt는 재개할 때 노드를 처음부터 다시 실행하므로 LLM 호출과 같은 노드에 두면 답변마다 LLM이 다시 돈다.

## 지금까지 확인된 것

- 동글이·별이 케이스 end-to-end 성공. 인터뷰 2턴, 텍스트 ~60초, 이미지 포함 ~2분
- **캐릭터 일관성**: 주인공·조연 각각 시트 → 8페이지 전부 같은 캐릭터로 나옴
- **간접화·교훈 미주입·열린 결말** (10/2 기준, 10/6에 "사건은 닫고 의미는 엶"으로 변경): 프롬프트대로 나옴. 부모가 "소리 질러서 미안"이라고 한 게 조연의 행동으로 들어감
- **비용**: 권당 약 500~600원. 90%가 이미지(10장). 텍스트는 60~70원. 지원서 가정 850원 안
- **아직 안 한 것**: 검수 노드(사람 평가에서 기준 나온 뒤), 평가 스크립트(`evals/`), 캐릭터 시트 재사용, 이미지 품질 low 비교

## 코드 어디에 뭐가

```
src/firstory/
  graph.py          노드·엣지. 플로우 바꿀 땐 여기
  state.py          그래프를 흐르는 상태 (TypedDict)
  schemas.py        pydantic. 입력 Context, 인터뷰 결과, 동화, 가이드. description이 모델에게 그대로 간다
  llm.py            structured() 하나로 모든 텍스트 호출. 벤더 바꿀 땐 여기만
  nodes/            노드별 함수
  prompts/*.md      역할별 프롬프트. {{변수}}는 코드가 채움. PM도 고칠 수 있게 분리
  cli.py            터미널 실행
viewer/app.py       Streamlit
datasets/inputs/    테스트 입력 5개 (scripted_answers = 자동 인터뷰 답변)
datasets/samples/   PM 수동 샘플 3개 (기준선)
evals/mock_run.py   API 없이 배선 확인
out/<시각>_<샘플>/  00-context … 05-illustrations.json, images/, book.html, 99-cost.json
```

## 돌려보기

```bash
git clone https://github.com/k1mg0eun/FIRSTORY_AI.git && cd FIRSTORY_AI
uv sync                            # uv 없으면 curl -LsSf https://astral.sh/uv/install.sh | sh
cp .env.example .env               # OPENAI_API_KEY, LANGSMITH_API_KEY
uv run python evals/mock_run.py    # 키 없이 배선 확인
uv run streamlit run viewer/app.py # 뷰어
```

## 같이 정할 것

- `design_story`를 별도 노드로 둘지 `write_story`에 접을지 — 둘 다 돌려서 비교
- 생성본이 PM 샘플보다 "조용함" (조연이 아이에게 구체적 행동을 안 줌). 맞는 방향인지 PM과 첫 20권 보면서
- 페이지당 문장 수 상한 (지금 2~4, 4문장이면 길어 보임)
- 이미지 비용: 시트 재사용 / 품질 low / 페이지 6장 / Gemini 비교
- 평가 루프: 사람 먼저 → rubric → LLM 판정 → `evals/run.py`
