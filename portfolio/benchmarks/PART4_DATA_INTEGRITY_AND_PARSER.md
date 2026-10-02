# [실증 보고서] 파트 4. 비정형 텍스트의 정형화와 대량 동기화 파이프라인 (계층형 버퍼 파서 & 벌크 무결성)

> **실증 일자**: 2026-09-16  
> **검증 대상 모듈**: [`src/bot/utils/text_parser.py`](file:///c:/work/rpg_sync_project/src/bot/utils/text_parser.py), [`src/database/connection.py:L208-L258`](file:///c:/work/rpg_sync_project/src/database/connection.py#L208-L258), [`src/bot/cogs/system/nickname_format_cmd.py`](file:///c:/work/rpg_sync_project/src/bot/cogs/system/nickname_format_cmd.py) (Git Commit: `7a6482e`)  
> **실행 스크립트**: `tests/benchmark_data_integrity.py`  
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
  | `rpg-db-dev` | `postgres:15-alpine` | 36.43 MiB / 7.668 GiB | 0.03% | 5432:5432, `init.sql` 스키마 마운트 |
  | `rpg-redis-dev` | `redis:7-alpine` | 4.93 MiB / 7.668 GiB | 0.52% | 6379:6379, `--maxmemory 50mb volatile-lru` |
  | `rpg-api-dev` | `rpg_sync_project-api` (python:3.11-slim) | 96.23 MiB / 7.668 GiB | 6.53% | 8000:8000 |

### 3) 외부 의존성 및 네트워크 토폴로지
- **대상 DB**: PostgreSQL 15 (Docker Container `rpg-db-dev`, `jobs`, `users`, `system_configs` 테이블 실질의)
- **네트워크 토폴로지**: 로컬 도커 가상 브리지 네트워크(`rpg_sync_project_default`) 및 호스트 포트 바인딩(`localhost:5432`)

---

## 2. 부하 조건 및 검증 시나리오 (Workload Profile)

### 1) 시나리오 설명
- **시나리오 1: 디스코드 비정규 마크다운 파싱 및 PostgreSQL jobs 테이블 일괄 UPSERT 실측**:
  - 실제 디스코드 포스트 텍스트(게이트 H2, 직업 H3, 인라인 브래킷 `[영웅]`/`[빌런]`, `<<조건문>>`, 비정규 개행/공백) 파싱.
  - Naive Regex 파싱 (게이트/직업 누락률 50.0%, 인라인 태그 미정제로 DB 설명문 컬럼 오염 발생) vs 계층형 버퍼 파서 (4개 직업 100% 완전 추출, 본문과 메타데이터 완벽 분리).
  - 파싱된 직업 데이터를 실제 Docker PostgreSQL `jobs` 테이블에 `ON CONFLICT (name) DO UPDATE`로 100회 일괄 UPSERT 트랜잭션 레이턴시 계측.
- **시나리오 2: 가변 닉네임 동적 템플릿과 system_configs JSONB 영속화 실측**:
  - PostgreSQL `system_configs` 테이블에 동적 닉네임 포맷(`config_key = 'nickname_formats'`) JSONB 적재 및 조회.
  - 다양한 실무 닉네임(`[STF]`, `OWN`, `🌈`, 2파트, 3파트, 4파트) 5,000회 파싱 및 스태프 권한 탐지율 실측.
- **시나리오 3: 2단계 직업 매칭 및 대량 벌크 업서트(Bulk Sync) 실측 (`connection.py:208-258`)**:
  - 동기화 대상: 커뮤니티 동시 활동 유저 40명 페이로드 (완전 일치 20명, 부분 단일 10명, 가문명 중복 10명).
  - **대조군 (Naive 방식)**:
    - 매 유저마다 DB에 `SELECT` 단건 쿼리 실행 (총 40회 DB 왕복 I/O).
    - 가문명 축약("루나")에 대해 단순 부분 일치(`LIKE '%루나%'`)의 첫 번째 항목 무조건 매핑 $\rightarrow$ 엉뚱한 캐릭터 오매핑 (데이터 오염 발생).
    - 단건 INSERT/UPDATE 반복 실행 (총 40회 DB 쓰기).
  - **실험군 (Hardened 프로젝트 방식, `connection.py:208-258`)**:
    - 유저 순회 전 단 1회의 쿼리로 전체 직업 목록 메모리 선캐싱 (`cached_jobs`).
    - 1차 완전 일치 우선 탐색 $\rightarrow$ 일치 항목 없을 때만 2차 부분 일치 수행.
    - 부분 일치 후보군이 2개 이상 검출되면 안전 탈락 (`failed_users`) 및 스태프 채널 리포트 사유 생성 (`is_collision = True`).
    - 검증 통과 유저군(`valid_users`)만 `executemany` 기반 `ON CONFLICT (discord_id) DO UPDATE`로 원자적 일괄 업서트 (총 2회 DB 질의).

### 2) 부하 파라미터
- **DB 일괄 UPSERT 반복 (Jobs Bulk)**: 100회 커밋 배치
- **닉네임 파싱 검증 연산 수**: 5,000 회
- **벌크 동기화 대상 유저 수**: 40 명 (완전 일치 20명, 부분 단일 10명, 가문명 중복 10명)

### 3) 재현 실행 명령어 (PowerShell Lifecycle)
```powershell
# 1. 인프라 사전 기동 및 상태 확인
docker compose -f docker-compose.dev.yml up -d db redis
docker ps --filter "name=rpg-"

# 2. 벤치마크 실행 및 메트릭 계측
uv run --with psycopg2-binary --with redis --with python-dotenv python tests/benchmark_data_integrity.py

# 3. 컨테이너 리소스 모니터링 확인
docker stats --no-stream
```

---

## 3. 정량적 실측 결과 (Empirical Metrics)

### 1) 디스코드 포스트 파싱 및 DB jobs 테이블 UPSERT 실측
| 측정 항목 | Naive Regex 방식 | 계층형 버퍼 파서 (Hardened) | 변동치 및 개선 효과 |
|---|---|---|---|
| **직업 추출 건수** | 2 / 4 개 (누락률 50.0%) | **4 / 4 개 (완전 복원율 100.0%)** | **게이트 경계 누락 원천 차단** |
| **인라인 태그/조건 정제** | `<<태그>>` 미정제 (본문 오염) | **완벽 분리 (`req_condition` 적재)** | **설명문 컬럼 무결성 확보** |
| **진영 타입([빌런]) 식별** | '정보 없음' (식별 실패) | **'빌런' (정확 식별)** | **서사 텍스트 간섭 원천 차단** |
| **PostgreSQL 일괄 UPSERT 레이턴시** | - | **3.86 ms/배치** (100회: 386.45 ms) | 초당 **258.77 배치 RPS** |

### 2) 가변 닉네임 동적 템플릿 및 system_configs JSONB 실측
| 검증 항목 | 관측치 | 비고 |
|---|---|---|
| **system_configs 로드 포맷 수** | 3개 포맷 (2파트, 3파트, 4파트) | JSONB 컬럼 정상 영속화 |
| **총 파싱 검증 연산 수** | 5,000 회 | 인메모리 템플릿 순회 |
| **스태프 권한(STF/OWN/🌈) 탐지율** | **100.0%** (5,000 / 5,000 회) | 권한 오탐 및 탈취 0.0% |
| **직업명 추출 정확도** | **100.0%** (5,000 / 5,000 회) | 가변 파트 인덱스 정확 분발 |
| **평균 파싱 레이턴시** | **4.80 us/op** | 마이크로초 초고속 동기화 |

### 3) 2단계 직업 매칭 및 대량 벌크 동기화(Bulk Sync) 실측 (유저 40명)
| 측정 지표 | Naive 방식 (단건 반복) | 프로젝트 적용 (Hardened) | 변동치 및 개선율 |
|---|---|---|---|
| **총 소요 시간 (Total Elapsed)** | 36.74 ms | **14.23 ms** | **-61.3% 단축** |
| **총 DB 쿼리 수 (Queries)** | 80 회 (읽기 40 + 쓰기 40) | **2 회** (읽기 1 + 쓰기 1) | **-97.5% 질의 제거 (78회 감축)** |
| **처리량 (Throughput)** | 1088.63 RPS | **2810.39 RPS** | **+158.2% 향상** |
| **가문명 중복 캐릭터 오매핑** | 10 / 10 건 (**오염률 100.0%**) | **0 건 (오염률 0.0%)** | **무결성 100% 완벽 방어** |
| **충돌 계정 안전 격리** | 0 명 (오염 적재) | **10 명 (안전 탈락)** | `failed_users` 리스트 분리 |
| **옵저버빌리티 리포트 발송** | 미지원 (조용한 오염) | **스태프 채널 실시간 리포팅** | `후보군: 아르테미스루나, 셀레네루나` |

---

## 4. 컨테이너 리소스 관측치 (docker stats Dump)

```text
CONTAINER ID   NAME            CPU %     MEM USAGE / LIMIT     MEM %     NET I/O          BLOCK I/O         PIDS
8e20a255b500   rpg-api-dev     6.53%     96.23MiB / 7.668GiB   1.23%     218kB / 3.29MB   1.21MB / 819kB    8
0901aec972d5   rpg-redis-dev   0.52%     4.93MiB / 7.668GiB    0.06%     122kB / 52.8kB   17.5MB / 28.7kB   6
2637393e5810   rpg-db-dev      0.03%     36.43MiB / 7.668GiB   0.46%     646kB / 295kB    26.2MB / 56.6MB   8
```

---

## 5. 실무적 한계 및 Red Teaming 고찰 (Engineering Retrospective)

1. **운영 워크플로우 보존과 텍스트 파서의 타협**:
   - 웹 어드민 폼을 구축하는 것이 가장 이상적인 정규화 수단이었으나, 기획·회의·패치 논의가 100% 디스코드 내부에서 완결되던 커뮤니티 특성상 플랫폼 전환 피로와 이중 입력 부담으로 인한 현장 저항이 극심할 것이 명확했음.
   - 따라서 운영진의 작성 동선을 유지하되, `[영웅]`, `<<조건문>>` 최소 브래킷 가이드라인만 배포하여 프로세스와 코드가 상호 보완하는 실무적 타협안을 도출함.
2. **2단계 직업 매칭과 사전 캐싱의 실효성**:
   - 커뮤니티의 관습적 5자 이내 라스트 네임 축약 표기로 인해 동일 가문명 유저 간 오매핑 위험이 상존했음.
   - 직업 목록 1회 사전 캐싱을 통해 40명 동기화 시 DB 쿼리를 80회에서 2회로 97.5% 줄였으며, 2개 이상 후보 검출 시 안전 탈락 및 관리자 리포트를 통해 데이터 오염을 100% 원천 차단함.
