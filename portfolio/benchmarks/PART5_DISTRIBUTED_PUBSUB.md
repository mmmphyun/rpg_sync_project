# [실증 보고서] 파트 5. 크로스 플랫폼 분산 이벤트 브로커와 메시지 무결성 (Redis Pub/Sub & 멱등성)

> **실증 일자**: 2026-09-16  
> **검증 대상 모듈**: [`src/bot/main.py:L129-L185`](file:///c:/work/rpg_sync_project/src/bot/main.py#L129-L185), [`src/database/cache.py:L135-L149`](file:///c:/work/rpg_sync_project/src/database/cache.py#L135-L149), [`src/web/routers/auth.py:L30-L42`](file:///c:/work/rpg_sync_project/src/web/routers/auth.py#L30-L42), [`src/database/auth.py:L94-L126`](file:///c:/work/rpg_sync_project/src/database/auth.py#L94-L126) (Git Commit: `c6cc131`)  
> **실행 스크립트**: `tests/benchmark_pubsub.py`  
> **실증 인프라**: Docker Compose (`rpg-redis-dev`, `rpg-db-dev`, `rpg-api-dev`)

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
  | `rpg-redis-dev` | `redis:7-alpine` | 5.31 MiB / 7.668 GiB | 0.41% | 6379:6379, `--maxmemory 50mb volatile-lru` |
  | `rpg-db-dev` | `postgres:15-alpine` | 38.36 MiB / 7.668 GiB | 0.31% | 5432:5432, `init.sql` 스키마 마운트 |
  | `rpg-api-dev` | `rpg_sync_project-api` (python:3.11-slim) | 96.61 MiB / 7.668 GiB | 6.18% | 8000:8000 |

### 3) 외부 의존성 및 네트워크 토폴로지
- **메시지 브로커**: Redis 7 Alpine (Docker Container `rpg-redis-dev`, 채널: `onboarding:complete`, `benchmark:pubsub:latency`)
- **영속 저장소 (Single Source of Truth)**: PostgreSQL 15 (Docker Container `rpg-db-dev`, `users` 테이블 `is_guide_completed`, `server_role`)
- **네트워크 토폴로지**: 로컬 도커 가상 브리지 네트워크(`rpg_sync_project_default`) 및 호스트 포트 바인딩(`localhost:6379`, `localhost:5432`)

---

## 2. 부하 조건 및 검증 시나리오 (Workload Profile)

### 1) 시나리오 설명
- **시나리오 1: Redis Pub/Sub 정상 디스패치 레이턴시 계측**:
  - `redis.asyncio` 기반 단일 발행자-구독자 연결 환경에서 50회 연속 이벤트(`seq`, 고정밀 타임스탬프 `ts`) 발행.
  - 리스너 수신 시점 타임스탬프와의 차이($\Delta t$)를 통해 End-to-End 전달 지연시간(평균, p95, 최대) 및 처리량(RPS) 실측.
- **시나리오 2: 봇 다운/순단 시 메시지 유실(Silent Loss) 및 DB 상태 대사(Reconciliation) 실측**:
  - 봇 리스너가 오프라인(순단/재기동/네트워크 파티션) 상태일 때 20명의 유저 온보딩 완료 이벤트 인입.
  - **대조군 (Naive 방식)**: DB 영속화 없이 Redis Pub/Sub 단일 채널에만 의존 $\rightarrow$ 메시지 영구 소멸 및 봇-웹 상태 불일치 발생.
  - **실험군 (Hardened 프로젝트 방식)**: Web 계층에서 PostgreSQL에 선영속화(`is_guide_completed = true`) 후 Redis 발행 $\rightarrow$ 봇 재기동 시 단 1회의 대사 쿼리(`WHERE is_guide_completed = true AND server_role = 'NEWBIE'`)로 미반영 유저를 100% 자동 검출하여 원자적 일괄 복구.
- **시나리오 3: 중복 요청 폭주 시 멱등성(Idempotency) 방어 실측 (동시 20건 경합)**:
  - 동일 유저 ID에 대해 20건의 가이드 완료 요청 동시 인입.
  - **대조군 (Naive TOCTOU)**: 선행 `SELECT` 조회 후 `UPDATE` 실행 $\rightarrow$ 동시 실행 코루틴들이 모두 `False`를 읽어 20건 전량 중복 UPDATE 및 중복 Redis 발행 유발 (동시성 결함 발생).
  - **실험군 (Hardened 원자적 조건부 갱신)**: `UPDATE users SET is_guide_completed = true WHERE discord_id = %s AND is_guide_completed = false` 조건부 원자적 갱신(Compare-and-Set) 수행 $\rightarrow$ 단 1건만 성공(rowcount=1), 19건 즉각 차단(rowcount=0)으로 멱등성 완벽 방어.

### 2) 부하 파라미터
- **정상 발행 메시지 수**: 50 건 (5ms 인터벌)
- **오프라인 유실 검증 이벤트 수**: 20 건
- **동시성 멱등성 경합 요청 수**: 20 세션 동시 폭주 (VUs)

### 3) 재현 실행 명령어 (PowerShell Lifecycle)
```powershell
# 1. 인프라 사전 기동 및 상태 확인
docker compose -f docker-compose.dev.yml up -d db redis
docker ps --filter "name=rpg-"

# 2. 벤치마크 실행 및 메트릭 계측
uv run --with psycopg2-binary --with redis --with python-dotenv python tests/benchmark_pubsub.py

# 3. 컨테이너 리소스 모니터링 확인
docker stats --no-stream
```

---

## 3. 정량적 실측 결과 (Empirical Metrics)

### 1) Redis Pub/Sub 실시간 디스패치 레이턴시 계측 (50회 연속 발행)
| 측정 지표 | 관측치 | 비고 |
|---|---|---|
| **발행 / 수신 성공률** | **100.0%** (50 / 50 건) | 정상 소켓 연결 상태 무유실 |
| **평균 수신 레이턴시 (Mean)** | **1.42 ms** | 마이크로초 인메모리 버퍼링 |
| **p95 레이턴시** | **3.28 ms** | 지터 극소화 |
| **최대 레이턴시 (Max)** | **9.84 ms** | 10ms 미만 안정권 |
| **처리량 (Throughput)** | **61.62 RPS** | 5ms 간격 전송 실측치 |

### 2) 봇 오프라인 상태 메시지 유실 및 DB 상태 대사(Reconciliation) 실측 (20건)
| 검증 항목 | 대조군 (Naive Pub/Sub 의존) | 실험군 (Hardened DB 선영속화 + 대사) | 개선 효과 및 차이점 |
|---|---|---|---|
| **오프라인 발생 이벤트 수** | 20 건 | 20 건 | 동일 조건 주입 |
| **실시간 수신 성공 건수** | 0 건 (수신자 부재) | 0 건 (수신자 부재) | Redis Pub/Sub 특성 동일 |
| **메시지 유실률 (Silent Loss)** | **100.0%** (20건 영구 소멸) | 0.0% (DB 완벽 영속화) | **영구 상태 불일치 원천 차단** |
| **상태 대사 미반영 유저 검출** | 0 건 (추적 불가) | **20 건 (100.0% 검출)** | 단일 SQL 인덱스 스캔 |
| **무중단 일괄 복구 건수** | 0 건 (수동 복구 필요) | **20 건 (복구율 100.0%)** | **원자적 일괄 대사 완료** |
| **상태 대사 복구 소요 시간** | $\infty$ (영구 방치) | **23.58 ms** | 24ms 이내 전건 정상화 |

### 3) 동일 유저 동시 요청 폭주 멱등성(Idempotency) 방어 실측 (동시 20건 경합)
| 측정 지표 | 대조군 (Naive TOCTOU) | 프로젝트 적용 (Hardened 조건부 원자 갱신) | 변동치 및 개선율 |
|---|---|---|---|
| **동시 인입 요청 수** | 20 건 | 20 건 | 동시 코루틴 폭주 |
| **정상 처리 건수** | 20 건 (중복 실행) | **1 건 (최초 1회만 반영)** | 단일 진입 보장 |
| **중복 차단 건수 (Skip)** | 0 건 | **19 건** | 중복 연산 원천 제거 |
| **중복 실행 결함률** | **95.0%** (19건 중복 처리) | **0.0% (무결성 100% 방어)** | **Discord API 429 차단** |
| **평균 처리 레이턴시** | 77.24 ms | **38.65 ms** | **-50.0% 단축** |

---

## 4. 컨테이너 리소스 관측치 (docker stats Dump)

```text
CONTAINER ID   NAME            CPU %     MEM USAGE / LIMIT     MEM %     NET I/O          BLOCK I/O         PIDS
8e20a255b500   rpg-api-dev     6.18%     96.61MiB / 7.668GiB   1.23%     250kB / 3.32MB   1.21MB / 819kB    8
0901aec972d5   rpg-redis-dev   0.41%     5.309MiB / 7.668GiB   0.07%     181kB / 104kB    17.5MB / 57.3kB   6
2637393e5810   rpg-db-dev      0.31%     38.36MiB / 7.668GiB   0.49%     866kB / 508kB    26.2MB / 58.2MB   8
```

---

## 5. 실무적 한계 및 Red Teaming 고찰 (Engineering Retrospective)

1. **발견된 병목 또는 잠재 리스크**:
   - **Redis Pub/Sub의 Fire-and-Forget 특성**:
     - Redis Pub/Sub은 발행 시점에 리스너가 연결되어 있지 않으면 메시지를 보관하지 않고 버림(At-most-once delivery).
     - 봇 배포 중이거나 일시적 네트워크 순단 발생 시 실시간 역할 부여 신호가 누락될 수 있음.
   - **TOCTOU (Time-of-Check to Time-of-Use) 레이스 컨디션**:
     - 애플리케이션 레벨에서 단순 `is_guide_completed` 조회 후 분기하는 방식은 동시 다중 요청 시 읽기 일관성 보장이 어려움.
     - DB 레벨의 조건부 원자적 갱신(`WHERE is_guide_completed = false`)이 필수적임.

2. **이상론 대비 1단계 타협 근거**:
   - **Kafka / RabbitMQ / Redis Streams를 쓰지 않은 이유 (FinOps 0원 & 1GB RAM VM)**:
     - Redis Streams(`XADD`, `XREADGROUP`, ACK)나 RabbitMQ는 메시지 오프셋과 디스크/인메모리 버퍼를 유지하므로 유실 방지에는 이상적임.
     - 그러나 1GB RAM e2-micro VM 환경에서 추가 큐 관리 프로세스를 구동하거나 스트림 미소비 메시지가 누적되면 즉각적인 OOM(Out of Memory)으로 이어짐.
     - 따라서 **'Redis Pub/Sub은 1.42ms급 실시간 트리거용으로만 사용하고, 영속성과 원천 진실(Single Source of Truth)은 PostgreSQL이 전담'**하는 2계층 하이브리드 아키텍처를 채택함.
     - 메시지 누락은 봇 재기동 시 단 23.58ms의 DB 상태 대사(Reconciliation) 쿼리로 100% 복구 가능하므로, 복잡한 인프라 도입 없이 시스템 안정성과 가용성을 완전히 확보함.
