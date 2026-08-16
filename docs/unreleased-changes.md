# v2.9.13 추가 변경 (버전 번호 유지)

> **앱 표시 버전**: `2.9.13` (`src/app.py`, About 다이얼로그)  
> **작성일**: 2026-08-16  
> 릴리스 태그·버전 숫자는 올리지 않고, 동일 `2.9.13` 위에 쌓인 변경만 기록합니다.

---

## 1. DeepSeek V4 Flash 출력 잘림 수정

**증상**: 상세 분석 시 `completion_tokens`가 ~8191에서 `finish_reason=length`로 잘림.

**원인**: DeepSeek API는 `max_tokens`를 사용. `max_completion_tokens`만내면 무시되고 서버 기본 한도(~8K) 적용.

**수정** (`src/detail_prompt.py`, `src/full_config.py`):

- DeepSeek: `max_tokens` + `thinking: disabled`
- `LLMProvider.max_tokens_api_field` / `thinking_disabled`로 제공자별 필드 명시

| 제공자 | 출력 한도 API 필드 | thinking |
|--------|-------------------|----------|
| MiniMax | `max_completion_tokens` | — |
| MiMo | `max_completion_tokens` | disabled |
| DeepSeek | `max_tokens` | disabled |
| GLM·ChatGPT·Grok·Perplexity·OR·Kilo·Ollama | `max_tokens` (기본) | — |

**환경 변수** (`.env.local` / `env.local.example`):

- `DEEPSEEK_MAX_TOKENS` — 기본 32768 (코드 기본값과 동일; 필드명 버그와 무관)
- `DEEPSEEK_MODEL`, `DEEPSEEK_API_KEY`

**로그**: 잘림 시 `{필드}={요청값} 요청, completion_tokens={실제}` 출력.

---

## 2. NFS/SMB SQLite 안정화 (v2.9.13 본편)

- 네트워크 경로(`F:` → NFS) 감지 시 `journal_mode=DELETE` (DB 경로 `data/db/` **공유 유지**)
- 로컬 디스크는 WAL 유지
- 선택 env: `SQLITE_JOURNAL_MODE`, `CHAT_DB_PATH` (개인 PC만, 전역 기본 변경 없음)
- 백업/복원이 `resolve_chat_db_path()` 실제 경로를 따름

---

## 3. 채팅방 목록 정렬 UI

**위치**: 좌측 패널 `💬 채팅방` 헤더 오른쪽 콤보박스

| 옵션 | 정렬 |
|------|------|
| 메시지 수 (기본) | 메시지 개수 내림차순 |
| 최신 업데이트 | `last_sync_at` 최근 순 (없으면 아래) |
| 이름순 | 채팅방명 오름차순 |

**파일**: `src/ui/main_window.py` (`ROOM_SORT_OPTIONS`, `_sort_rooms_with_counts`)  
**DB**: `get_all_rooms_with_message_counts()` — 정렬은 UI에서 수행

---

## 4. DeepSeek V4 Flash 제공자 (v2.9.12)

- 키: `deepseek`, 모델 `deepseek-v4-flash`, env `DEEPSEEK_API_KEY`
- 1M context, `DEEPSEEK_MAX_INPUT_CHARS` 기본 1450848

---

## 재기동

```powershell
.\start_background.ps1
```

## 확인 체크리스트

- [ ] 좌측 채팅방 헤더에 정렬 콤보 표시
- [ ] DeepSeek 상세 분석: 로그 `completion_tokens`가 8191 근처가 아님 (장문일 때)
- [ ] NFS에서 채팅방 생성/조회 시 `disk I/O error` 재발 여부
- [ ] `logs/summarizer_*.log`에 `journal_mode=DELETE` (네트워크 경로 시)
