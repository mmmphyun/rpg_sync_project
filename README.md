# RPG Sync Project

> **마인크래프트 RPG 서버 데이터 동기화 디스코드 봇 및 FastAPI 통합 웹 포털**  
> *본 프로젝트는 **2026년 7월까지 실제로 가동 및 운영된 실운영 서버 시스템**으로, 제한된 리소스(Free Tier) 환경에서의 **단일 노드 내 다중 프로세스 격리 및 DB I/O 0화 아키텍처**를 목표로 설계되었습니다.*

---

## 전체 시스템 아키텍처 (System Architecture)

```
[ 마인크래프트 서버 (외부 유동 IP) ]
        │  ▲
        │  │  Tailscale VPN (WireGuard Encrypted Tunnel, 100.x.x.x)
        ▼  │
┌─────────────────────────────────────────────────────────────┐
│ GCP VM (Free Tier, Single Node)                              │
│                                                             │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │   discord.py (Bot)    │       │     FastAPI (Web)     │  │
│  │   - Voice Sync        │       │   - Jinja2 SSR / SEO  │  │
│  │   - ThreadPool Isol.  │       │   - Cloudflare Limiter│  │
│  └───────────┬───────────┘       └───────────┬───────────┘  │
│              │                               │              │
│              ▼                               ▼              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Redis (State Broker)                                  │  │
│  │  - Pub/Sub (Real-time Event Relay)                    │  │
│  │  - Distributed Lock (SET NX EX, Safe TTL 15s)         │  │
│  │  - In-Memory User O(1) Caching                        │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               │  TCP Keepalive & Connection Pre-warming
                               ▼  (RTT 200ms network pre-warming & Fast Path)
┌─────────────────────────────────────────────────────────────┐
│ Supabase PostgreSQL (Korea Region)                          │
└─────────────────────────────────────────────────────────────┘
```

### 핵심 엔지니어링 전략

1. **지연 시간 극복을 위한 네트워크 엔지니어링 (GCP US ↔ Supabase KR)**
   - 물리적 네트워크 지연(RTT 200ms) 극복을 위해 **TCP Keepalive** 및 커넥션 풀 사전 예열(**Pre-warming**)을 적용하고, 핵심 정보를 메모리 캐싱(**Fast Path**)하여 쿼리 지연을 극복했습니다.
2. **보안 가상 네트워크 구축 (Tailscale VPN)**
   - 외부 마인크래프트 서버와 GCP VM의 Redis(6379) 포트를 공인 인터넷에 노출하지 않고 **Tailscale (WireGuard 기반)** 암호화 터널로 연결하여 해킹 위험을 차단하고 유동 IP 변경에 영향받지 않도록 설계했습니다.
3. **Async-Sync 하이브리드 동시성 제어**
   - `discord.py`의 비동기 이벤트 루프를 보호하기 위해 동기식 DB 작업(`psycopg2`)을 전용 **ThreadPoolExecutor**로 완전 격리하여 봇 게이트웨이 끊김을 방지했습니다.
4. **Redis 기반 분산 상태 관리 및 DB I/O 0화**
   - **Pub/Sub**: 마인크래프트-디스코드 간 무상태(Stateless) 실시간 이벤트(사유 제출, 킥, 승인) 전파.
   - **Distributed Lock**: 복수 스태프의 동일 카드 동시 클릭 처리 시 레이스 컨디션을 막기 위해 `SET NX EX` 기반 분산 락 탑재.
   - **O(1) 캐싱 & Warm-up**: 음성 채널 상태 변경 시 DB 읽기를 배제하고 Redis 캐시를 활용, 봇 기동 시 단 1회의 벌크 쿼리로 예열.
5. **웹 보안 & SEO 최적화 (FastAPI)**
   - Cloudflare `cf-connecting-ip` 연동 Client IP 기반 SlowAPI Rate Limiting.
   - static 자산 동적 `mtime` 쿼리스트링 주입으로 캐시 무효화.
   - `/robots.txt`, `/favicon.ico` 및 페이지별 OG 메타 태그 지원 (로그인 페이지 `noindex` 처리).

---

## 프로젝트 구조

```
rpg_sync_project/
├── src/
│   ├── bot/          # Discord.py 봇 (유저 데이터, 닉네임, 음성/직업 동기화)
│   ├── database/     # PostgreSQL 연동 (자가 치유 db_retry 연결 풀) 및 Redis 캐시 계층
│   └── web/          # FastAPI 웹 서버 (Jinja2 SSR, mtime 캐시, 라우터, SlowAPI)
├── public/           # Static 자산 (CSS, JS, 이미지, 파비콘)
├── docs/             # 설계 명세서 (아키텍처, 인프라, 봇/플러그인 연동 가이드)
├── portfolio/        # 아키텍처 백서, 포렌식 개발 로그, 트러블슈팅 문서
├── docker-compose.yml
├── Dockerfile
├── init.sql          # DB 초기 스키마
└── requirements.txt
```

---

## 트러블슈팅 및 해결 사례 (Troubleshooting)

- **Supabase 유휴 연결 종료 대처 (`db_retry` 커넥션 풀 자가 치유)**
  - 원격 소켓 강제 종료 시 `conn.closed` 감지가 불가능한 문제를 해결하기 위해 `OperationalError` / `DatabaseError` 발생 시 자동 재연결(Auto-Reconnect) 및 1회 재시도를 수행하는 데코레이터 패턴 도입.
- **Event Loop Starvation 방지**
  - 동기 DB 작업에 `asyncio.to_thread` 적용 및 FastAPI 라우터의 적절한 스레드 분리로 봇 이벤트 루프 병목 제거.
- **XSS & SQL Injection 원천 차단**
  - f-string 쿼리를 수동 파라미터 바인딩으로 교체하고 CSR 방식 대신 Jinja2 SSR 방식을 적용하여 DOM XSS 공격 표면 제거.

---

## 시작하기

```bash
# 1. 환경 변수 설정
cp .env.example .env

# 2. Docker Container 구동
docker-compose up -d --build
```
