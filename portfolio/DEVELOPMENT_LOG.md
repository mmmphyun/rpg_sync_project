# Full Development & Growth Log (Forensic Audit)

본 문서는 RPG Sync Project의 시작부터 현재까지, **178개 커밋의 실제 코드 변화(diff)**를 전수 조사하여 기록한 정밀 개발 로그입니다. 단순한 기능 구현을 넘어, 리소스 제약과 보안 위협을 엔지니어링으로 해결해온 과정을 담고 있습니다.

## 🟢 Phase 1: 초기 아키텍처 설계 및 데이터 파싱 (Commit 7e28141 ~ c0bde38)
- **비정규 데이터의 정형화 (`83d7e01`, `2074b1e`)**
    - **현상**: 디스코드 채팅 포스트의 자유로운 텍스트 양식으로 인해 데이터베이스 정합성이 깨짐.
    - **분석**: 초기 단순 Regex 매칭은 줄바꿈과 특수문자(`+`, `:`, `<< >>`) 대응에 실패함.
    - **해결**: `git show 2074b1e`에서 확인되듯, **상태 머신(State Machine) 기반 파서**를 도입하여 컨텍스트를 유지하며 멀티라인 데이터를 정밀하게 추출함.
- **DB 스키마 및 호환성 구축 (`e5e81fc`, `a3eaa5d`)**
    - **증거**: `ON CONFLICT (NAME) DO UPDATE` 구문을 활용한 UPSERT 로직 최초 구현. Oracle에서 PostgreSQL(Supabase)로의 환경 전이에 따른 타입 캐스팅 문제 해결.

## 🟡 Phase 2: 인프라 제약 극복 및 성능 최적화 (Commit 78cd4d8 ~ 35b7c9b)
- **GCP 미국 리전 - 한국 DB 간 지연 시간(Latency) 해결 (`cd47bee`, `d2733b7`)**
    - **현상**: 200ms 이상의 네트워크 RTT로 인해 첫 로딩 및 DB 조회 시 사용자 경험 저하.
    - **해결**: `git show cd47bee`를 통해 **TCP Keepalive(idle=30, interval=10)** 파라미터를 커널 수준에서 주입하고, `minconn`을 10으로 상향하여 연결 오버헤드를 물리적으로 제거함.
- **AsyncIO 이벤트 루프 병목 제거 (`db1b536`, `14c9b6b`)**
    - **분석**: 동기식 DB 드라이버(`psycopg2`)가 봇의 메인 스레드를 점유하여 Discord Gateway 연결이 끊기는 현상 포착.
    - **해결**: `git show 14c9b6b`에서 전용 **ThreadPoolExecutor(max_workers=20)**를 수동 설정하고, FastAPI 라우터를 `async def`에서 `def`로 전환하여 블로킹 작업을 워커 스레드로 완전 격리.

## 🔴 Phase 3: 보안 하드닝 및 AI 코드 감사 (Commit af56d9f ~ 6e3f8ee)
- **SQL Injection 및 XSS 원천 차단 (`c05a260`, `6afe4bc`)**
    - **철학**: "AI가 제안한 f-string 기반 쿼리를 거부하고 파라미터 바인딩으로 전수 교체."
    - **해결**: `git show 6afe4bc`에서 CSR 방식의 `fetch`를 제거하고 **Jinja2 SSR**로 전환. `INITIAL_JOBS_DATA`를 서버에서 안전하게 주입하여 DOM 기반 XSS 공격 표면을 제거함.
- **실제 IP 추적 및 Rate Limiting (`66fe5c3`, `54b2cf8`)**
    - **증거**: Cloudflare 리버스 프록시 환경에서 `cf-connecting-ip` 헤더를 우선적으로 신뢰하도록 `limiter.py`를 커스터마이징하여 정밀한 DoS 방어 체계 구축.

## 🔵 Phase 4: 분산 시스템 고도화 및 자가 치유 (Commit fce7492 ~ e7c8c78)
- **Redis Pub/Sub 및 분산 락 구현 (`c6cc131`)**
    - **현상**: 마이크로서비스(Bot/Web) 분리로 인한 실시간 상태 공유의 어려움.
    - **해결**: `git show c6cc131`에서 Redis를 메시지 브로커로 활용하여 Minecraft-Discord 간 양방향 통신 구현. `SET NX EX` 방식의 **분산 락**으로 다중 스태프 간 Race Condition 해결.
- **연결 풀 자가 치유(Self-healing) 로직 (`e7c8c78`)**
    - **증거**: `DatabaseError` 예외 계층을 분석하여 상위 에러 발생 시에도 연결을 강제 폐기하고 재시도하도록 `get_connection` 로직 최후 보강.

---

## 🚀 성장의 기록: 엔지니어로서의 정체성
이 프로젝트의 178개 커밋은 저에게 **"도구를 지휘하는 능력"**을 가르쳐주었습니다. AI 에이전트의 생산성을 활용하되, 그 결과물을 **커널 레벨의 TCP 튜닝, 분산 락, 보안 취약점 감사** 등 엔지니어링 지식을 동원해 검증하고 다듬었습니다. 한정된 리소스(Free Tier) 환경은 제약을 넘어 아키텍처를 극한으로 효율화하는 최고의 스승이 되었습니다.
