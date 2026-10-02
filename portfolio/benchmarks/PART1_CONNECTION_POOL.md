# [실증 보고서] 파트 1. 네트워크 RTT 극복과 DB 커넥션 풀 자가 치유

> **실증 일자**: 2026-09-16  
> **검증 대상 모듈**: [`src/database/connection.py`](file:///c:/work/rpg_sync_project/src/database/connection.py), [`src/database/cache.py`](file:///c:/work/rpg_sync_project/src/database/cache.py) (Git Commit: `7a6482e`)  
> **실행 스크립트**: `tests/benchmark_connection.py`  
> **테스트 데이터셋**: [`data.js`](file:///c:/work/rpg_sync_project/data.js) 하드코딩 원천 데이터셋 (실제 게임 직업 71종 전체 파싱 및 시딩)

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
  | `rpg-db-dev` | `postgres:15-alpine` | 32.79 MiB / 7.668 GiB | 0.00% | 5432:5432, `init.sql` 스키마 마운트 |
  | `rpg-redis-dev` | `redis:7-alpine` | 4.586 MiB / 7.668 GiB | 1.20% | 6379:6379, `--maxmemory 50mb volatile-lru` |

### 3) 외부 의존성 및 네트워크 토폴로지
- **대상 DB**: PostgreSQL 15 (Docker Container `rpg-db-dev`)
- **대상 캐시**: Redis 7.4 (Docker Container `rpg-redis-dev`)
- **네트워크 지연 주입**: GCP 미국 리전 ↔ Supabase 한국 리전 간 물리적 왕복 지연시간(RTT 200ms) 소켓 레벨 지연 주입
- **장애 주입 메커니즘**: `SELECT pg_terminate_backend(pid)`를 통한 서버 측 유휴 소켓 강제 드랍(Stale Drop) 실측

---

## 2. 부하 조건 및 검증 시나리오 (Workload Profile)

### 1) 시나리오 설명
- **데이터셋 구축**: 극초기 개발 단계에서 하드코딩으로 관리하던 `data.js`의 직업 객체 71종을 정규식으로 파싱하여 PostgreSQL `jobs` 테이블에 일괄 UPSERT 및 Redis 캐시 예열 완료.
- **Naive 방식 (최적화 전)**:
  - 매 요청마다 71종 직업 중 무작위 대상을 선정하고, 쿼리 실행 직전 커넥션 생존 검증을 위해 `SELECT 1;`을 강제 질의(RTT 200ms 추가 발생)한 후 실제 쿼리 실행.
- **Hardened 방식 (프로젝트 적용 방식)**:
  - `SELECT 1` 질의를 배제하고 즉시 71종 직업 중 무작위 대상을 선정하여 비즈니스 쿼리 실행.
  - 런타임 소켓 강제 종료(`pg_terminate_backend`) 발생 시, `@db_retry`가 `OperationalError`를 포착하여 Stale 소켓을 풀에서 영구 폐기(`putconn(close=True)`) 후 1회 재연결하여 무중단 복구.
- **Fast Path 방식 (Redis 캐시 결합)**:
  - 71개 전체 직업 캐시 적중(85%) 시 DB I/O를 0으로 바이패스하고 인메모리에서 즉시 응답.

### 2) 부하 파라미터
- **총 요청 수 (Total Requests)**: 각 전략당 40회 연속 호출 (71종 직업 무작위 질의)
- **장애 주입률 (Stale Socket Drop Rate)**: 8.0% 확률로 서버 측 백엔드 프로세스 강제 킬 주입
- **캐시 적중률 (Cache Hit Rate)**: 85.0%

### 3) 재현 실행 명령어 (PowerShell Lifecycle)
```powershell
# 1. 인프라 사전 기동 및 상태 확인
docker compose -f docker-compose.dev.yml up -d db redis
docker ps --filter "name=rpg-"

# 2. 벤치마크 실행 및 메트릭 계측 (data.js 71종 시딩 및 질의)
uv run --with psycopg2-binary --with redis --with python-dotenv python tests/benchmark_connection.py

# 3. 사후 정리
docker compose -f docker-compose.dev.yml stop db redis
```

---

## 3. 정량적 실측 결과 (Empirical Metrics)

### 1) Latency & Throughput 비교 (대륙 간 RTT 200ms 환경, data.js 71종 랜덤 질의)
| 측정 지표 | 최적화 전 (Naive) | 프로젝트 적용 (Hardened) | Fast Path (Redis 결합) | 변동치 및 개선율 (Hardened vs Naive) |
|---|---|---|---|---|
| **평균 레이턴시 (Mean)** | 405.66 ms | **243.41 ms** | **16.18 ms** | **-40.0% 단축** (Fast Path 결합 시 **-96.0%**) |
| **p95 레이턴시** | 411.09 ms | **477.17 ms** | **207.34 ms** | 소켓 단절 재연결 비용 포함 |
| **최대 레이턴시 (Max)** | 411.32 ms | **479.26 ms** | **207.34 ms** | 단절 시 자가 치유 1회 재시도 반영 |
| **처리량 (Throughput)** | 2.47 RPS | **4.11 RPS** | **61.78 RPS** | **+66.7% 향상** (Fast Path 결합 시 **+2401.2%**) |

### 2) 소켓 단절 자가 치유 및 무결성 실측
| 검증 항목 | 관측치 | 비고 |
|---|---|---|
| **서버 측 세션 강제 종료 후 `conn.closed` 값** | **`0` (False)** | 클라이언트 메모리 플래그가 원격 소켓 강제 종료를 감지하지 못함을 실증 |
| **소켓 강제 종료 시 발생 예외** | `psycopg2.OperationalError` | `server closed the connection unexpectedly` 확인 |
| **자가 치유 성공률 (Self-healing)** | **100.0% (6회 주입 중 6회 전원 성공)** | 끊어진 커넥션 자동 폐기(`close=True`) 및 새 PID 할당 확인 |
| **자가 치유 1회 복구 소요 시간** | **4.77 ms (로컬) / 479 ms (RTT 포함)** | 에러 전파 없이 트랜잭션 정상 완결 |

---

## 4. 컨테이너 리소스 관측치 (docker stats Dump)

```text
CONTAINER ID   NAME            CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O       PIDS
0901aec972d5   rpg-redis-dev   1.20%     4.586MiB / 7.668GiB   0.06%     36.5kB / 22.8kB   7.26MB / 0B     6
2637393e5810   rpg-db-dev      0.00%     32.79MiB / 7.668GiB   0.42%     167kB / 117kB     20MB / 54.7MB   6
```

---

## 5. 실무적 한계 및 Red Teaming 고찰 (Engineering Retrospective)

1. **실제 데이터셋(`data.js`) 도입에 따른 관측 결과**:
   - 단일 더미 데이터가 아닌 실제 71종 직업 데이터셋을 대상으로 다양한 키를 랜덤 질의함으로써, 실제 인덱스 조회 및 캐시 히트/미스 전환 시의 현실적인 레이턴시 분포를 도출함.
2. **발견된 병목 및 메모리 플래그의 한계**:
   - `pg_terminate_backend`를 통해 백엔드 소켓을 끊었을 때, `target_conn.closed`가 여전히 `0`으로 남아 있는 현상을 실측으로 입증함.
   - 즉, `if conn.closed != 0:` 방식의 방어 코드는 서버 측 타임아웃/프록시 재부팅을 방어할 수 없으며, 반드시 쿼리 실행 레벨의 `@db_retry`가 병행되어야 함을 실증함.
3. **이상론 대비 1단계 타협 근거 (멱등성 제약)**:
   - 교과서적인 접근은 모든 쿼리에 지수 백오프(Exponential Backoff) 재시도를 거는 것이지만, 이는 INSERT/UPDATE 중복 실행으로 데이터 정합성을 파괴할 위험이 있음.
   - 본 프로젝트에서는 `@db_retry` 대상을 멱등성이 완벽히 보장되는 `ON CONFLICT DO UPDATE` (UPSERT) 및 단순 SELECT로 한정하고, 비멱등 로직은 즉시 롤백 후 명시적 예외를 전파하는 실용적 타협을 채택함.
