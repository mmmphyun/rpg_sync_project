# RPG Sync Project

> **마인크래프트 RPG 서버 데이터 동기화 디스코드 봇 및 FastAPI 직업 위키 웹 포털**  
> *본 프로젝트는 **2026년 7월까지 실제로 가동 및 운영된 실운영 서버 시스템(커뮤니티 유저 약 40명, 피크 동접 20명, 최대 90종 직업군 관리)**으로, 제한된 리소스(GCP Free Tier, 1GB RAM 단일 노드) 및 대륙 간 물리적 지연(GCP US ↔ Supabase KR, RTT 200ms) 환경에서 **단일 노드 내 다중 프로세스 격리 및 DB I/O 0화 아키텍처**를 달성한 엔지니어링 프로젝트입니다.*

---

## 핵심 실측 성과 (Headline Empirical Metrics)

| 핵심 검증 영역 | 최적화 전 (Naive) | 프로젝트 적용 (Hardened) | 핵심 성과 및 실측 임팩트 |
|---|---|---|---|
| **물리적 RTT 200ms 극복** | 405.66 ms | **16.18 ms** (Redis Fast Path) | **평균 지연시간 -96.0% 단축** (DB I/O 0화 및 TCP Pre-warming) |
| **이벤트 루프 동결 방지** | 206.04 ms (Lag) | **14.64 ms** (Lag) | **하트비트 지터 -92.9% 억제** (게이트웨이 1006 커넥션 드롭 차단) |
| **경합 동시성 무결성** | Race Condition 발생 | **0.0% 오류율 (20건 중 1건 승인)** | Safe TTL (15s) 분산 락으로 운영진 중복 클릭 0건 방어 |
| **원격 소켓 단절 복구** | 서버 비정상 다운 | **100.0% 자동 복구 (6회 전원 성공)** | `@db_retry` 기반 Stale 소켓 폐기 및 1회 재연결 자가 치유 |

---

## 시스템 아키텍처 (System Architecture)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="public/images/architecture-dark.svg">
    <img alt="System Architecture Diagram" src="public/images/architecture-light.svg" width="100%">
  </picture>
</p>

---

## 실운영 인프라 스펙 및 서비스 규모 (Production Scale)

* **운영 기간**: ~ 2026년 7월 (실제 서버 가동 및 운영 종료)
* **커뮤니티 및 트래픽 규모**:
  * **디스코드 커뮤니티 유저**: 약 40명
  * **피크 동시 접속자 (Peak CCU)**: 최대 20명
  * **관리 직업 데이터셋**: 최대 약 90종 (스토리 내 등장인물 기반 방대한 직업군)
* **단일 노드 리소스 제약 (FinOps)**:
  * **호스트 인프라**: GCP Compute Engine Free Tier `e2-micro` (vCPU 2개, **1.0GB RAM**)
  * **원격 데이터베이스**: Supabase PostgreSQL 15 (Seoul 리전, US ↔ KR 물리적 RTT 200ms)
* **웹 포털 구축 목적 (Why FastAPI Web)**:
  * 인게임 미접속 외부 유저 대상의 **직업 위키(Wiki) 웹 포털**을 제공하여 신규 유저 유입 및 온보딩 가이드 접근성 극대화.
  * 검색 엔진 최적화(SEO) 및 Cloudflare CDN 캐싱을 통해 불특정 다수의 유입 트래픽 수용.

---

## 5대 도메인 벤치마크 종합 실증 매트릭스 (Empirical Benchmark Suite)

본 프로젝트는 단순 코드 작성을 넘어, 실제 도커 인프라(`postgres:15-alpine`, `redis:7-alpine`, `FastAPI`) 상에서 부하 및 결함을 주입하고 메트릭을 실측 검증했습니다.

| 벤치마크 파트 | 핵심 검증 주제 | 실측 조건 및 부하 프로파일 | 상세 실증 보고서 |
|---|---|---|---|
| **Part 1. 네트워크 & DB** | RTT 200ms 극복과 커넥션 풀 자가 치유 | `data.js` 71종 직업 데이터셋 랜덤 질의, RTT 200ms 모의 주입, `pg_terminate_backend` 강제 소켓 킬 | [`PART1_CONNECTION_POOL.md`](portfolio/benchmarks/PART1_CONNECTION_POOL.md) |
| **Part 2. 동시성 & 락** | 비동기 이벤트 루프 격리와 Safe TTL 분산 락 | 50ms 주기 Discord WebSocket 하트비트 태스크 지터 계측, 동일 키 20개 코루틴 동시 경합 | [`PART2_EVENT_LOOP_AND_LOCK.md`](portfolio/benchmarks/PART2_EVENT_LOOP_AND_LOCK.md) |
| **Part 3. 웹 보안** | Pure ASGI 미들웨어 & 도메인 경계 하드닝 | 보안 헤더 6종 주입, HSTS 로컬 배제, CSRF Origin 경계, Redis 연동 Client IP Rate Limiting | [`PART3_WEB_SECURITY.md`](portfolio/benchmarks/PART3_WEB_SECURITY.md) |
| **Part 4. 데이터 무결성** | 비정형 텍스트 정형화와 벌크 무결성 파이프라인 | 디스코드 비정규 포스트 계층형 버퍼 파싱, `jobs` 100회 일괄 UPSERT, JSONB 닉네임 템플릿 영속화 | [`PART4_DATA_INTEGRITY_AND_PARSER.md`](portfolio/benchmarks/PART4_DATA_INTEGRITY_AND_PARSER.md) |
| **Part 5. 분산 이벤트** | 크로스 플랫폼 이벤트 브로커 & 봇 순단 사후 대사 | Redis Pub/Sub E2E 디스패치 레이턴시 계측, 봇 오프라인 순단 시 누락 이벤트 PostgreSQL 사후 대사 | [`PART5_DISTRIBUTED_PUBSUB.md`](portfolio/benchmarks/PART5_DISTRIBUTED_PUBSUB.md) |

---

## 핵심 엔지니어링 전략 및 구현 메커니즘

### 1. 물리적 네트워크 지연(RTT 200ms) 극복과 자가 치유 커넥션 풀
* **문제 (Context)**: 미국 리전(GCP VM)과 한국 리전(Supabase PG) 간의 물리적 왕복 시간(RTT 200ms)으로 인해, 쿼리 직전 연결 유효성을 검사하는 `SELECT 1` 방식 사용 시 매 호출마다 400ms 이상의 누적 지연이 발생함. 또한 Supabase 유휴 연결 종료 시 클라이언트 메모리 플래그(`conn.closed`)가 이를 감지하지 못해(`conn.closed == 0`) 런타임 쿼리 크래시 발생.
* **해결 (Action)**:
  * `SELECT 1` 사전 질의를 전면 배제하고 커널 레벨 TCP Keepalive를 적용하여 사전 연결을 유지.
  * `@db_retry` 데코레이터를 구현하여 런타임에 `psycopg2.OperationalError` 또는 `DatabaseError` 발생 시 Stale 커넥션을 풀에서 영구 폐기(`putconn(close=True)`)하고 즉시 재연결하여 1회 재시도(Fail-fast Auto-Reconnect) 수행.
  * 봇 기동 시 단 1회의 벌크 쿼리로 사용자 및 직업(최대 90종) 데이터를 Redis에 사전 예열(Pre-warming)하여 반복 읽기를 인메모리 Fast Path로 전환.
* **결과 (Result)**:
  * 일반 쿼리 레이턴시 **405.66ms $\rightarrow$ 243.41ms (-40.0% 단축)**.
  * Redis Fast Path 적중 시 **16.18ms (-96.0% 단축, RPS +2401.2% 향상)**.
  * 서버 측 강제 소켓 단절 주입 시 **자가 치유 성공률 100.0% (6/6회 전원 복구)** 달성.

### 2. Event Loop Starvation 방지 및 ThreadPoolExecutor 격리
* **문제 (Context)**: `discord.py`는 단일 비동기 이벤트 루프 기반으로 동작하므로, 동기식 DB 쿼리(`psycopg2`)가 루프를 200ms 이상 블로킹할 경우 게이트웨이 하트비트 전송이 지연되어 `1006 Connection Closed` 에러와 함께 봇 프로세스가 강제 재연결 루프에 빠짐.
* **해결 (Action)**:
  * 비동기 메인 루프에 전용 `ThreadPoolExecutor(max_workers=20)`를 결합하고 모든 동기 DB I/O 호출을 `await asyncio.to_thread`로 래핑하여 완전히 격리.
* **결과 (Result)**:
  * 10회 동시 DB 쿼리 부하 시 하트비트 Lag **206.04ms $\rightarrow$ 14.64ms (-92.9% 지터 억제)**.
  * 전체 처리 소요 시간 **2.495초 $\rightarrow$ 0.358초 (-85.7% 단축, 27.94 RPS)** 달성.

### 3. 1GB RAM 환경에서의 Safe TTL (15s) 경량 분산 락
* **문제 (Context)**: 복수의 운영진이 디스코드 채널에서 유저의 접속 사유 우회(`ReasonBypassView`) 버튼(승인/거절)을 동시 클릭할 경우 이중 처리(Race Condition)가 발생함. 그러나 1GB 단일 VM 환경에서 무거운 Redlock이나 백그라운드 Watchdog 프로세스를 운용하는 것은 메모리 고갈(OOM) 위험을 초래함.
* **해결 (Action)**:
  * Redis 단일 노드의 원자적 명령어인 `SET key val EX 15 NX`를 채택. 임계 구역의 실제 처리 시간(50ms) 대비 300배의 안전 마진을 갖는 15초 Safe TTL을 설정하고 완료 시 명시적 `DEL`을 수행하는 경량 동시성 제어 설계.
* **결과 (Result)**:
  * 20개 세션 동시 폭주 경합 테스트에서 **정확히 1건 승인, 19건 완벽 차단 (Race Condition 오류율 0.0%)** 실증.

### 4. Pure ASGI 미들웨어 웹 보안 및 IP 기반 트래픽 제어
* **문제 (Context)**: 불특정 다수가 접속하는 직업 위키 웹 포털 특성상 크롤링 및 악성 트래픽이 집중될 수 있으며, 리버스 프록시(Cloudflare) 뒤에서 실제 클라이언트 IP 식별이 누락될 경우 Rate Limiting이 무력화됨.
* **해결 (Action)**:
  * Starlette/FastAPI 레벨에서 순수 ASGI 미들웨어를 구축하여 필수 보안 헤더 6종(`X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `X-Process-Time`)을 일괄 주입.
  * Cloudflare의 `cf-connecting-ip` 헤더를 검증하여 신뢰된 클라이언트 IP 기반으로 Redis 연동 SlowAPI Rate Limiting 적용.
* **결과 (Result)**:
  * 모든 위키 엔드포인트에 보안 헤더 100% 주입 확인 및 임계치 초과 요청 시 정확한 `HTTP 429 Too Many Requests` 차단 실측.

### 5. Redis Pub/Sub 이벤트 브로커 및 단절 시 사후 상태 대사 (Reconciliation)
* **문제 (Context)**: 외부 마인크래프트 서버와 디스코드 간의 실시간 이벤트 동기화에 Redis Pub/Sub을 사용할 때, 봇 프로세스 순단이나 네트워크 파티션 발생 시 인메모리 메시지가 유실(Silent Loss)될 위험 존재.
* **해결 (Action)**:
  * Redis Pub/Sub을 실시간 통지용 'Fast Path'로 사용하되, 최종 진실의 원천(Single Source of Truth)은 PostgreSQL로 유지.
  * 봇 기동 및 재연결 시 `users` 테이블의 `is_guide_completed` 및 권한 상태를 스캔하여 미처리 이벤트를 일괄 보정하는 사후 상태 대사(Reconciliation) 파이프라인 구현.
* **결과 (Result)**:
  * 봇 다운 상태에서 인입된 20건의 완료 이벤트에 대해 사후 기동 시 단 1회의 대사 쿼리로 **100% 누락 복구 및 역할 동기화 완결** 검증.

---

## 실운영 장애 관제 및 서비스 종료 아카이빙 (Operations & Lifecycle)

### 1. 실시간 디스코드 도커 로그 관제 (Log Chunking)
* **배경**: 1GB 단일 VM 환경에서 ELK 스택이나 별도 로깅 에이전트를 띄우는 것은 메모리 낭비이며, 장애 발생 시마다 SSH 터미널에 접속하여 `docker logs`를 확인하는 것은 대응 지연을 초래함.
* **구현**: 
  * Docker 컨테이너의 표준 출력/에러 스트림을 디스코드 최대 메시지 길이(2,000자) 단위로 분할(Chunking)하여 운영자 전용 디스코드 관제 채널로 실시간 전파.
  * 별도 로깅 인프라 없이도 모바일/데스크톱 디스코드 환경에서 봇 크래시 및 `@db_retry` 경고 로그를 즉각 인지하고 대응함.

### 2. 서비스 정상 종료(Graceful Sunset) 및 콜드 아카이빙 파이프라인 ([`db_backup.py`](db_backup.py))
* **배경**: 2026년 7월 서비스 종료 시 운영 데이터를 유실 없이 영구 보존하기 위해 정적 콜드 아카이빙 파이프라인 구축.
* **구현**:
  * Cloudflare R2 도메인 매칭 정규식 필터링을 통해 안전한 정적 이미지만 선별 다운로드.
  * `DateTimeEncoder` 커스텀 직렬화를 거쳐 PostgreSQL의 관계형 테이블 및 JSONB 필드를 전수 덤프하여 정적 아카이브 디렉토리(`public/archive/`)로 백업 전환.

---

## 프로젝트 구조

```
rpg_sync_project/
├── src/
│   ├── bot/                # Discord.py 봇 메인 (이벤트 루프, Cogs, 스레드 풀 격리)
│   │   ├── cogs/           # 업무 도메인별 Cog (auth, board, jobs, system, users)
│   │   └── utils/          # 계층형 버퍼 텍스트 파서, S3 클라이언트, 권한 체크
│   ├── database/           # PostgreSQL 커넥션 풀 (@db_retry 자가 치유) 및 Redis 캐시 계층
│   └── web/                # FastAPI 웹 포털 (직업 위키, Pure ASGI 보안 미들웨어, SlowAPI, SSR)
│       ├── routers/        # 인증, 대시보드, 직업 위키, 가이드 라우터
│       └── templates/      # Jinja2 서버사이드 렌더링 템플릿
├── public/                 # Static 자산 및 아키텍처 다이어그램 SVG (Light/Dark)
│   └── images/
│       ├── architecture-light.svg
│       └── architecture-dark.svg
├── portfolio/              # 포렌식 개발 로그, 아키텍처 백서, 트러블슈팅 가이드
│   ├── benchmarks/         # 5대 도메인별 벤치마크 실증 보고서 (Part 1 ~ Part 5)
│   └── TROUBLESHOOTING.md  # 실제 발생 장애 및 4대 핵심 트러블슈팅 케이스
├── tests/                  # 재현 가능한 벤치마크 계측 스크립트 5종
├── db_backup.py            # 서비스 종료 시 R2 이미지 백업 및 DB JSON 덤프 스크립트
├── docker-compose.yml      # 프로덕션 컨테이너 정의
├── docker-compose.dev.yml  # 로컬 실증용 DB & Redis 인프라 정의
├── init.sql                # PostgreSQL 15 초기 스키마 및 인덱스 정의
└── requirements.txt
```

---

## 핵심 트러블슈팅 사례 요약

상세 트러블슈팅 로그 및 코드 레벨 해결책은 [`portfolio/TROUBLESHOOTING.md`](portfolio/TROUBLESHOOTING.md)에서 확인할 수 있습니다.

1. **Supabase 유휴 연결 강제 종료 및 `conn.closed` 감지 불가**
   * *원인*: 원격 방화벽/프록시의 비정상 소켓 단절 시 클라이언트 메모리 플래그(`conn.closed`)가 `0`으로 유지되어 장애 감지 우회.
   * *해결*: `@db_retry` 데코레이터를 통해 `psycopg2.OperationalError` 발생 시 Stale 소켓 강제 폐기 및 1회 재연결 자가 치유 체계 구축.
2. **동기 I/O 쿼리로 인한 Discord Gateway Heartbeat Starvation**
   * *원인*: 200ms RTT DB 쿼리가 단일 비동기 이벤트 루프를 블로킹하여 하트비트 전송 누락 및 `1006` 연결 끊김 발생.
   * *해결*: 메인 루프에 전용 `ThreadPoolExecutor(max_workers=20)`를 할당하고 `asyncio.to_thread`로 위임하여 하트비트 Lag을 14.6ms로 억제.
3. **AI 생성 코드 수용 시의 웹 보안 취약점 (SQLi & DOM XSS)**
   * *원인*: 초기 프로토타입 작성 시 f-string 쿼리 및 CSR 구조 도입으로 인한 보안 취약점 노출.
   * *해결*: 전체 데이터베이스 액세스를 파라미터 바인딩으로 전면 강제하고 Jinja2 SSR로 마이그레이션하여 공격 표면 원천 차단.
4. **1GB RAM VM 환경에서의 유저 사유 우회 중복 클릭 Race Condition**
   * *원인*: 복수 운영진이 동일 유저의 접속 사유(`ReasonBypassView`)를 동시 승인/거절할 때 분산 레이스 컨디션 발생.
   * *해결*: Watchdog 프로세스 메모리 부담을 배제하고 Safe TTL(15초) 기반 `SET NX EX` 분산 락을 설계하여 중복 실행 0.0% 달성.

---

## 로컬 재현 및 벤치마크 실행 가이드 (Reproducibility)

본 프로젝트의 모든 수치는 로컬 도커 테스트베드 환경에서 직접 재현 및 계측할 수 있습니다.

```powershell
# 1. 로컬 테스트 인프라 기동 (PostgreSQL 15 & Redis 7)
docker compose -f docker-compose.dev.yml up -d db redis

# 2. Part 1: 커넥션 풀 자가 치유 및 레이턴시 벤치마크 실행
uv run --with psycopg2-binary --with redis --with python-dotenv python tests/benchmark_connection.py

# 3. Part 2: 이벤트 루프 격리 및 Safe TTL 분산 락 동시성 벤치마크 실행
uv run --with psycopg2-binary --with redis --with python-dotenv python tests/benchmark_event_loop.py

# 4. Part 3: 웹 보안 미들웨어 및 Rate Limiting 벤치마크 실행
docker compose -f docker-compose.dev.yml up -d api
uv run --with httpx --with pytest python tests/benchmark_web_security.py

# 5. Part 4: 계층형 버퍼 파서 및 벌크 UPSERT 벤치마크 실행
uv run --with psycopg2-binary --with python-dotenv python tests/benchmark_data_integrity.py

# 6. Part 5: 크로스 플랫폼 Pub/Sub 및 사후 대사 벤치마크 실행
uv run --with redis --with psycopg2-binary --with python-dotenv python tests/benchmark_pubsub.py

# 7. 인프라 종료
docker compose -f docker-compose.dev.yml stop
```
