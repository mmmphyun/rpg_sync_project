# [실증 보고서] 파트 {N}. {파트 제목}

> **실증 일자**: YYYY-MM-DD  
> **검증 대상 모듈**: [`src/{path}`](file:///c:/work/rpg_sync_project/src/{path}) (Git Commit: `{commit_hash}`)  
> **실행 스크립트**: `tests/benchmark_{part_name}.py`

---

## 1. 테스트베드 및 인프라 사양 (Testbed Specifications)

### 1) 호스트 시스템
- **OS**: Windows 11 (PowerShell 7+)
- **CPU**: {Host CPU Name / Cores}
- **RAM**: {Host Total RAM}

### 2) Docker Compose 컨테이너 환경
- **Docker Engine**: {Docker Engine Version}
- **기동 서비스 및 리소스 제약 (cgroups)**:
  | 컨테이너명 | 베이스 이미지 | 메모리 상한 (`mem_limit`) | CPU 할당 (`cpus`) | 포트 / 특수 옵션 |
  |---|---|---|---|---|
  | `rpg-{service}-container` | `{image}:{tag}` | `{예: 100m / 300m}` | `{예: 0.5}` | `{예: 6379, --maxmemory 50mb volatile-lru}` |

### 3) 외부 의존성 및 네트워크 토폴로지
- **원격 DB**: Supabase Managed PostgreSQL (AWS ap-northeast-2 서울 리전)
- **네트워크 지연 주입**: {직접 연결 / RTT 200ms 모의 지연 주입 여부}

---

## 2. 부하 조건 및 검증 시나리오 (Workload Profile)

### 1) 시나리오 설명
- **Naive 방식 (최적화/하드닝 전)**: {대조군 동작 설명}
- **Hardened 방식 (프로젝트 적용 방식)**: {실험군 동작 설명}

### 2) 부하 파라미터
- **동시 클라이언트 (Concurrency / VUs)**: {N}개 세션
- **총 반복 횟수 (Total Iterations / Requests)**: {N}회
- **요청 주기 (Interval / Think Time)**: {N}ms
- **페이로드 크기**: {N} bytes

### 3) 재현 실행 명령어 (PowerShell Lifecycle)
```powershell
# 1. 인프라 사전 기동 및 상태 확인
docker-compose up -d {service_name}
docker ps --filter "name=rpg-"

# 2. 벤치마크 실행 및 메트릭 계측
python tests/benchmark_{part_name}.py

# 3. 사후 정리 (리소스 반환)
docker-compose stop {service_name}
```

---

## 3. 정량적 실측 결과 (Empirical Metrics)

### 1) Latency & Throughput 비교
| 측정 지표 | 최적화 전 (Naive) | 프로젝트 적용 (Hardened) | 변동치 및 개선율 |
|---|---|---|---|
| **평균 레이턴시 (Mean)** | 000.0 ms | **000.0 ms** | **-00.0% 단축** |
| **p95 레이턴시** | 000.0 ms | **000.0 ms** | **-00.0% 단축** |
| **최대 레이턴시 (Max)** | 000.0 ms | **000.0 ms** | **-00.0% 단축** |
| **처리량 (Throughput)** | 00.0 RPS | **00.0 RPS** | **+00.0% 향상** |

### 2) 무결성 및 리소스 소비 비교
| 검증 항목 | 최적화 전 (Naive) | 프로젝트 적용 (Hardened) | 비고 |
|---|---|---|---|
| **동시성 오류율 (Race Condition)** | 00.0% ({N}건 유실/중복) | **0.0% ({N}건 전원 방어)** | 무결성 100% |
| **피크 메모리 (RSS)** | 000 MB | **00 MB** | cgroups 상한 준수 |
| **CPU 점유율 (Peak)** | 00.0% | **00.0%** | 이벤트 루프 블로킹 해소 |

---

## 4. 컨테이너 리소스 관측치 (docker stats Dump)

```text
CONTAINER ID   NAME                  CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O
{hash}         rpg-{service}         0.15%     12.4MiB / 100MiB      12.4%     1.2MB / 850KB     0B / 0B
```

---

## 5. 실무적 한계 및 Red Teaming 고찰 (Engineering Retrospective)
1. **발견된 병목 또는 잠재 리스크**:
   - {실측 과정에서 관측된 시스템 레벨 한계 서술}
2. **이상론 대비 1단계 타협 근거**:
   - {Free Tier 1GB RAM 환경에서 해당 성능치로 타협한 엔지니어링 사유}
