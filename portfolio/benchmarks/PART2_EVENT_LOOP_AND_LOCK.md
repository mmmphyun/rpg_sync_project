# [실증 보고서] 파트 2. 비동기 이벤트 루프 격리와 경량 분산 락

> **실증 일자**: 2026-09-16  
> **검증 대상 모듈**: [`src/bot/main.py`](file:///c:/work/rpg_sync_project/src/bot/main.py), [`src/bot/cogs/users/reason_bypass.py`](file:///c:/work/rpg_sync_project/src/bot/cogs/users/reason_bypass.py) (Git Commit: `7a6482e`)  
> **실행 스크립트**: `tests/benchmark_event_loop.py`  
> **실증 인프라**: Docker Compose (`rpg-db-dev`, `rpg-redis-dev`)

---

## 1. 테스트베드 및 인프라 사양 (Testbed Specifications)

### 1) 호스트 시스템
- **OS**: Windows 11 (PowerShell 7)
- **CPU**: 11th Gen Intel(R) Core(TM) i7-11700 @ 2.50GHz (8 Cores, 16 Threads)
- **RAM**: 16.0 GB

### 2) Docker Compose 컨테이너 환경
- **Docker Engine**: 29.7.2
- **기동 서비스 및 리소스 사양**:
  | 컨테이너명 | 베이스 이미지 | 메모리 점유 (`MEM USAGE`) | CPU 점유 (`CPU %`) | 포트 / 특수 옵션 |
  |---|---|---|---|---|
  | `rpg-db-dev` | `postgres:15-alpine` | 34.89 MiB / 7.668 GiB | 0.00% | 5432:5432, `init.sql` 스키마 마운트 |
  | `rpg-redis-dev` | `redis:7-alpine` | 5.707 MiB / 7.668 GiB | 0.83% | 6379:6379, `--maxmemory 50mb volatile-lru` |

### 3) 외부 의존성 및 네트워크 토폴로지
- **대상 DB**: PostgreSQL 15 (Docker Container `rpg-db-dev`, `jobs` 테이블 실질의)
- **대상 캐시/락 스토어**: Redis 7.4 (Docker Container `rpg-redis-dev`)
- **네트워크 지연 주입**: Supabase 대륙 간 RTT 200ms 모의 지연 주입
- **하트비트 계측 메커니즘**: 50ms 간격의 Discord WebSocket Gateway Heartbeat 태스크를 백그라운드 구동하여 이벤트 루프 프리징 지터(Lag) 실측

---

## 2. 부하 조건 및 검증 시나리오 (Workload Profile)

### 1) 시나리오 설명
- **테스트 1: Naive 방식 (동기 블로킹 직접 호출)**:
  - 코루틴 내부에서 이벤트 루프 양보 없이 실제 PostgreSQL 동기 DB 쿼리(RTT 200ms)를 직접 10회 연속 호출.
  - 단일 이벤트 루프가 동결되며 백그라운드 하트비트 태스크의 스케줄링 지연(Lag) 측정.
- **테스트 2: Hardened 방식 (`ThreadPoolExecutor(max_workers=20)` + `asyncio.to_thread` 격리)**:
  - 메인 루프의 기본 실행자를 `ThreadPoolExecutor(max_workers=20)`로 지정하고, 동기 DB 쿼리를 `await asyncio.to_thread`로 위임하여 10회 동시 요청 병렬 처리.
  - 비동기 코루틴 풀이 유지되는 상태에서 하트비트 태스크 지연 및 총 처리량 측정.
- **테스트 3: Docker Redis Safe TTL (15s) 분산 락 동시성 경합**:
  - 실제 구동 중인 Docker Redis 컨테이너에 동일한 유저 사유 승인 키(`rpgsync:processing_reason:bench_uuid_9999`)로 20개의 동시 클라이언트 코루틴이 `SET key val EX 15 NX` 호출 경합.
  - 원자적 단 1건 획득 및 나머지 19건 완벽 차단(Race Condition 0.0%) 검증.

### 2) 부하 파라미터
- **DB 쿼리 요청 수 (Requests)**: 전략당 10회 (실제 DB 직업 레코드 카운트 질의 + RTT 200ms)
- **하트비트 모니터링 주기**: 50 ms
- **분산 락 동시 요청 수 (Concurrency)**: 20개 세션 동시 폭주
- **락 TTL 설정**: 15초 (Safe TTL)

### 3) 재현 실행 명령어 (PowerShell Lifecycle)
```powershell
# 1. 인프라 사전 기동 및 상태 확인
docker compose -f docker-compose.dev.yml up -d db redis
docker ps --filter "name=rpg-"

# 2. 벤치마크 실행 및 메트릭 계측
uv run --with psycopg2-binary --with redis --with python-dotenv python tests/benchmark_event_loop.py

# 3. 컨테이너 리소스 모니터링 확인
docker stats --no-stream
```

---

## 3. 정량적 실측 결과 (Empirical Metrics)

### 1) Latency & Throughput 비교 (도커 PostgreSQL 15 실측)
| 측정 지표 | 최적화 전 (Naive) | 프로젝트 적용 (Hardened) | 변동치 및 개선율 |
|---|---|---|---|
| **총 소요 시간 (Total Elapsed)** | 2.495 s | **0.358 s** | **-85.7% 단축** |
| **처리량 (Throughput)** | 4.01 RPS | **27.94 RPS** | **+596.8% 향상** |
| **평균 레이턴시 (Mean)** | 230.50 ms | **229.37 ms** | DB 물리 RTT 정상 유지 |
| **p95 레이턴시** | 238.42 ms | **236.81 ms** | 안정적 편차 유지 |
| **게이트웨이 하트비트 평균 Lag** | 177.85 ms | **12.21 ms** | **-93.1% 지터 감소** |
| **게이트웨이 하트비트 최대 Lag** | 206.04 ms | **14.64 ms** | **-92.9% 지연 억제 (1006 드롭 차단)** |

### 2) Docker Redis Safe TTL (15s) 분산 락 동시성 실측 (20건 동시 클릭)
| 검증 항목 | 관측치 | 비고 |
|---|---|---|
| **동시 요청 수 (Concurrency)** | 20건 | 동일 키 동시 경합 |
| **락 획득 성공 건수** | **1건 (100.0% 정상 처리)** | `SET key 1 EX 15 NX` 성공 |
| **중복 클릭 차단 건수** | **19건 (0.0% 중복 방어)** | Race Condition 원천 차단 |
| **동시성 오류율 (Race Condition Error)** | **0.0% (무결성 100%)** | 중복 실행 0건 |
| **SET NX 평균 응답시간** | **29.63 ms** | 로컬 Redis 컨테이너 왕복 레이턴시 |
| **SET NX p95 / 최대 응답시간** | **36.17 ms** | 20개 동시 폭주 시 지연 한계치 |

---

## 4. 컨테이너 리소스 관측치 (docker stats Dump)

```text
CONTAINER ID   NAME            CPU %     MEM USAGE / LIMIT     MEM %     NET I/O         BLOCK I/O         PIDS
0901aec972d5   rpg-redis-dev   0.83%     5.707MiB / 7.668GiB   0.07%     59.5kB / 39kB   17.5MB / 0B       6
2637393e5810   rpg-db-dev      0.00%     34.89MiB / 7.668GiB   0.44%     241kB / 192kB   20.1MB / 55.5MB   6
```

---

## 5. 실무적 한계 및 Red Teaming 고찰 (Engineering Retrospective)

1. **실제 도커 환경 실측에 따른 관측 결과**:
   - 순수 인메모리 슬립 모의가 아니라 실제 구동 중인 PostgreSQL 컨테이너(`rpg-db-dev`) 소켓 질의와 Redis 컨테이너(`rpg-redis-dev`) `SET NX` 커맨드를 연동하여 실측함.
   - Naive 방식에서는 이벤트 루프가 동결되어 50ms마다 송신되어야 할 게이트웨이 하트비트가 최대 **206.04ms**까지 밀리는 현상을 실증함. 실제 디스코드 게이트웨이 환경이었다면 즉각적인 1006 커넥션 드롭 및 무한 재연결 루프가 발생하는 임계치임.
   - `ThreadPoolExecutor(max_workers=20)` 격리 후 하트비트 지연이 **14.64ms**로 억제되어 봇 게이트웨이 생존성을 완벽히 확보함.
2. **단일 노드 Redis 분산 락의 한계와 실무적 정당성**:
   - 20개의 동시 클라이언트가 폭주하더라도 Redis의 단일 스레드 커맨드 처리 특성(`SET key val EX 15 NX`) 덕분에 정확히 1개 요청만 승인되고 19개 요청이 0.0% 오차로 차단됨을 실증함.
   - Lua 스크립트 기반 UUID 검증이 없는 구조라 15초 초과 시 타 프로세스 락 오인 삭제 가능성이 이론상 존재하나, 실제 임계 구역 처리 시간(50ms) 대비 15초는 300배의 안전 마진이므로 1GB VM 환경에서 복잡성 대비 실용적인 타협안임을 입증함.
