# 커밋 규칙

[이 글](https://velog.io/@shin6403/Git-git-%EC%BB%A4%EB%B0%8B-%EC%BB%A8%EB%B2%A4%EC%85%98-%EC%84%A4%EC%A0%95%ED%95%98%EA%B8%B0) 기준.

## 형식

```
<type>: <제목>

<본문>  (선택)

<꼬리말>  (선택)
```

- **제목** 50자 이내, 마침표·특수기호 없이. 한국어로 써도 됨. "무엇을 했다"가 바로 보이게
- **본문** 한 줄 72자. 무엇을·왜. 어떻게는 코드가 말해줌
- **꼬리말** `Resolves #12`, `Ref #7`

## type

| type | 언제 |
|---|---|
| `feat` | 새 기능 — 노드 추가, 프롬프트 신규, 뷰어 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서만 |
| `style` | 포맷팅. 동작 변화 없음 |
| `refactor` | 구조 변경. 동작 변화 없음 |
| `test` | 테스트·평가 스크립트 |
| `chore` | 빌드·패키지·설정 |

프롬프트 파일(`src/firstory/prompts/*.md`) 수정은 출력이 바뀌니까 `feat` 또는 `fix`로. `docs` 아님.

## 템플릿 걸기 (클론 후 한 번)

```bash
git config commit.template .gitmessage.txt
```

이후 `git commit` (메시지 옵션 없이) 치면 템플릿이 열림. `-m`으로 바로 써도 됨.

## 브랜치

- `main` — 돌아가는 상태 유지
- 작업은 `feat/조연-시트`, `fix/image-fidelity` 식으로 따서 PR
