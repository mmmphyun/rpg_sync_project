# [실증 보고서] 파트 3. 웹 보안 및 Pure ASGI 미들웨어 하드닝

> **실증 일자**: 2026-09-16  
> **검증 대상 모듈**: [`src/web/main.py`](file:///c:/work/rpg_sync_project/src/web/main.py), [`src/web/limiter.py`](file:///c:/work/rpg_sync_project/src/web/limiter.py) (Git Commit: `7a6482e`)  
> **실행 스크립트**: `tests/benchmark_web_security.py`  
> **실증 인프라**: Docker Compose (`rpg-api-dev`, `rpg-redis-dev`, `rpg-db-dev`)

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
  | `rpg-api-dev` | `rpg_sync_project-api` (python:3.11-slim) | 95.98 MiB / 7.668 GiB | 6.67% | 8000:8000, `uvicorn src.web.main:app` |
  | `rpg-redis-dev` | `redis:7-alpine` | 4.734 MiB / 7.668 GiB | 0.76% | 6379:6379, `--maxmemory 50mb volatile-lru` |
  | `rpg-db-dev` | `postgres:15-alpine` | 36.29 MiB / 7.668 GiB | 0.00% | 5432:5432, `init.sql` 마운트 |

### 3) 외부 의존성 및 네트워크 토폴로지
- **대상 웹 서버**: FastAPI 0.141.1 + Starlette 1.6.0 + Uvicorn 0.53.0 (Docker Container `rpg-api-dev`)
- **대상 캐시/레이트 리미터 스토어**: Redis 7.4 (Docker Container `rpg-redis-dev`)
- **네트워크 토폴로지**: 로컬 도커 가상 브리지 네트워크(`rpg_sync_project_default`) 내 컨테이너 간 통신 및 호스트 포트 바인딩(`localhost:8000`)

---

## 2. 부하 조건 및 검증 시나리오 (Workload Profile)

### 1) 시나리오 설명
- **시나리오 1: Pure ASGI 미들웨어 보안 헤더 6종 및 HSTS 로컬 배제 실측**:
  - `http://localhost:8000/`로 실제 HTTP GET 요청을 전송하고, 반환된 응답 헤더에서 `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, `X-Process-Time`의 정상 주입 여부 확인.
  - `host == "localhost"` 요청 시 개발 환경 락아웃을 방지하기 위해 `Strict-Transport-Security` 헤더가 응답에서 배제(None)되는지 실측.
- **시나리오 2: CSRF Origin 도메인 경계(Boundary) 검증 실측**:
  - `http://localhost:8000/login` 엔드포인트로 실제 HTTP POST 요청을 전송.
  - 정상 Origin (`http://localhost:8000`, `http://localhost:8000/jobs`): CSRF 미들웨어를 정상 통과하여 라우터 레벨로 진입(405 Method Not Allowed 수신).
  - 공격자 Origin (`http://localhost:8000.attacker.com`, `http://localhost:8000-phishing.net`, `http://evil-attacker.com`): Pure ASGI 미들웨어가 HTTP 403 Forbidden으로 즉각 차단하는지 실측.
- **시나리오 3: Cloudflare 프록시 환경 Rate Limiter 및 DoS 방어 실측**:
  - 엔드포인트: `/tips` (`@limiter.limit("30/minute")`).
  - 단일 IP 35회 연속 요청: 30회까지는 HTTP 200 정상 반환, 31번째 요청부터 HTTP 429 Too Many Requests로 완벽 차단되는지 실측.
  - 서로 다른 10개 IP 유저(각 5회, 총 50회) 요청: `cf-connecting-ip` 헤더를 통해 각 클라이언트가 독립적으로 식별되어, 동일한 L4 소켓 IP더라도 오탐 429 없이 50회 전건 HTTP 200으로 승인(False Positive DoS 0.0%)되는지 실측.

### 2) 부하 파라미터
- **동시 클라이언트 (Concurrency / VUs)**: 10개 세션
- **총 요청 수 (Total Requests)**: 100회 (성능 벤치마크) + 35회 (단일 IP 레이트리밋) + 50회 (멀티 IP 레이트리밋) + 5회 (CSRF 경계 검증)
- **Rate Limit 임계치**: 분당 30회 (`30/minute`)

### 3) 재현 실행 명령어 (PowerShell Lifecycle)
```powershell
# 1. 인프라 사전 기동 및 상태 확인
docker compose -f docker-compose.dev.yml up -d db redis api
docker ps --filter "name=rpg-"

# 2. 실증 벤치마크 스크립트 실행
python tests/benchmark_web_security.py

# 3. 컨테이너 리소스 모니터링 확인
docker stats --no-stream
```

---

## 3. 정량적 실측 결과 (Empirical Metrics)

### 1) Latency & Throughput 비교 (Docker Compose `rpg-api-dev` 실측)
| 측정 지표 | 실측 결과 | 비고 |
|---|---|---|
| **평균 레이턴시 (Mean)** | **18.59 ms** | 100회 요청, 동시성 10 워커 기준 |
| **p95 레이턴시** | **30.47 ms** | 미들웨어 6종 헤더 주입 및 템플릿 렌더링 포함 |
| **최대 레이턴시 (Max)** | **37.03 ms** | 피크 지연 40ms 미만 안정적 유지 |
| **처리량 (Throughput)** | **495.74 RPS** | 컨테이너 환경 초당 약 500건 렌더링 처리 |

### 2) 웹 보안 및 미들웨어 하드닝 실측
| 검증 항목 | 대상 헤더 / 요청 값 | 기대 동작 | 실제 관측 결과 (HTTP Code) | 방어 및 검증 판정 |
|---|---|---|---|---|
| **CSRF 정상 도메인 허용** | `Origin: http://localhost:8000` | 미들웨어 통과 | **HTTP 405 (라우터 진입)** | 정상 허용 |
| **CSRF 하위 경로 허용** | `Origin: http://localhost:8000/jobs` | 미들웨어 통과 | **HTTP 405 (라우터 진입)** | 정상 허용 |
| **CSRF 접미사 변조 차단** | `Origin: http://localhost:8000.attacker.com` | 즉각 차단 | **HTTP 403 Forbidden** | **100% 차단 성공** |
| **CSRF 하이픈 피싱 차단** | `Origin: http://localhost:8000-phishing.net` | 즉각 차단 | **HTTP 403 Forbidden** | **100% 차단 성공** |
| **CSRF 외부 악성 도메인 차단** | `Origin: http://evil-attacker.com` | 즉각 차단 | **HTTP 403 Forbidden** | **100% 차단 성공** |
| **HSTS 로컬 Lockout 방지** | `Host: localhost:8000` | HSTS 주입 배제 | **헤더 없음 (`None`)** | **로컬 락아웃 방어** |
| **보안 헤더 6종 전역 주입** | `X-Frame-Options`, `CSP`, `nosniff` 등 | 전역 주입 | **6종 전건 정상 주입 완료** | 클릭재킹/스니핑 차단 |
| **단일 IP 레이트리밋 임계치** | 35회 연속 요청 (`30/min` 한도) | 30회 후 차단 | **200 OK 30회 / 429 5회** | **한도 초과 완벽 차단** |
| **Cloudflare 멀티 IP 쿼터 격리** | 10개 IP 유저 각 5회 (총 50회) | 개별 IP 격리 | **200 OK 50회 / 429 0회** | **False Positive DoS 0.0%** |

---

## 4. 컨테이너 리소스 관측치 (docker stats Dump)

```text
CONTAINER ID   NAME            CPU %     MEM USAGE / LIMIT     MEM %     NET I/O          BLOCK I/O         PIDS
8e20a255b500   rpg-api-dev     6.67%     95.98MiB / 7.668GiB   1.22%     215kB / 3.29MB   1.21MB / 819kB    8
0901aec972d5   rpg-redis-dev   0.76%     4.734MiB / 7.668GiB   0.06%     121kB / 51.4kB   17.5MB / 28.7kB   6
2637393e5810   rpg-db-dev      0.00%     36.29MiB / 7.668GiB   0.46%     250kB / 217kB    26MB / 55.6MB     8
```

---

## 5. 실무적 한계 및 Red Teaming 고찰 (Engineering Retrospective)

1. **도커 로컬 컨테이너 실측을 통해 증명된 성과**:
   - 순수 모의 시뮬레이션이 아닌, 실제 구동 중인 Docker Compose API 컨테이너(`rpg-api-dev`)와 Redis 컨테이너(`rpg-redis-dev`) 간의 HTTP/소켓 통신을 통해 미들웨어 및 Rate Limiter의 동작을 실증함.
   - 단일 IP 30회 초과 시 429 차단 및 서로 다른 `cf-connecting-ip` 헤더를 가진 다중 유저 트래픽에서 429 오탐 없이 쿼터가 격리됨을 실제 HTTP 요청으로 검증함.
2. **발견된 병목 및 실무적 한계**:
   - `cf-connecting-ip` 헤더 파싱은 오리진 서버가 직접 인터넷에 노출되어 있을 경우 스푸핑될 수 있으므로, GCP VPC 방화벽 인바운드 룰(Cloudflare CIDR 화이트리스트)과의 결합이 반드시 병행되어야 함을 실증 과정에서 재확인함.
   - Starlette의 `BaseHTTPMiddleware`를 배제하고 Pure ASGI를 채택함으로써, 100MiB 미만의 컨테이너 메모리 점유(`95.98 MiB`)와 495.74 RPS의 높은 처리량을 유지할 수 있었음.
