# [Antigravity] 가이드 페이지 동적 UI 디자인 고도화 작업 지시서

> **대상**: 안티그래비티 (프론트엔드 전문 서브에이전트)
> **목표**: 가이드 페이지에 추가된 조건부 UI(뉴비/멤버/게스트 섹션)를 기존 에디토리얼 테마에 맞춰 미려하게 디자인.

## 1. 개요
현재 `guide.html` 하단에 `user_status`에 따라 3가지 섹션이 노출되도록 로직이 추가되었습니다. 이 섹션들의 스타일이 아직 기본 상태이므로, 서버의 핵심 테마(에디토리얼, 딥 다크, 0px 직선미)에 맞게 `guide.css`를 수정해야 합니다.

## 2. 디자인 가이드라인
- **색상**: `global.css`의 변수 활용 (`--accent-hero`, `--accent-special`, `--bg-surface` 등).
- **형태**: 모든 요소의 `border-radius`는 **0px** (직선형 디자인 유지).
- **폰트**: 모노톤 텍스트는 `Space Mono`, 메인 타이틀은 `Jura` 사용.
- **아이콘**: FontAwesome 5 및 RPG Awesome 아이콘 라이브러리 활용.

## 3. 상세 작업 내용

### Task A: 상태 안내 박스 디자인 (`.status-info-box`)
멤버(`member-box`)와 게스트(`guest-box`)에게 노출되는 안내 박스 디자인.
- **배경**: `rgba(0, 0, 0, 0.2)` 또는 `var(--bg-widget-medium)`.
- **보더**: `1px solid var(--border-color)`.
- **효과**: 아이콘에 미세한 글로우 효과, 텍스트 가독성 확보.

### Task B: 버튼 스타일 고도화
- **게스트용 (`.discord-btn`)**: 디스코드 브랜드 컬러 대신 테마에 맞는 다크 스타일이나 `--accent-hero` 보더 스타일 제안.
- **멤버용 (`.return-link`)**: 심플한 언더라인 애니메이션 (`.editorial-underline` 패턴 활용).

### Task C: 뉴비 서약 섹션 디테일 수정
- **입력창 (`.promise-input`)**: 포커스 시 `--accent-hero` 글로우 및 보더 하이라이트 강화.
- **서약 텍스트**: 복사 방지 강조 및 시각적 무게감 부여.

## 4. 관련 파일
- **CSS**: `public/guide.css`, `public/global.css`
- **HTML**: `src/web/templates/guide.html`
