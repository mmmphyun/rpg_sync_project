# RPG Sync Project: 기술 내재화 및 면접 방어 가이드 (Master Study Note)

> 본 문서는 에이전트 기반 코딩으로 구축 및 실운영(2026년 7월 종료)된 `rpg_sync_project`의 핵심 아키텍처, 런타임 트러블슈팅, 정량적 벤치마크 데이터를 내재화하고, 기술 면접에서 실전형 트러블슈터 관점으로 방어하기 위한 지속 갱신형 학습 문서입니다.

---

## [공통 지시사항: 세션 학습 실행 프로토콜]
> **사용자 프롬프트 호출 규격**: `"STUDY_AND_INTERVIEW_GUIDE.md의 파트 N 진행해줘"` 또는 `"해당 문서의 라인 X~Y 기준으로 학습 자료와 실습 제공해줘"`
> 
> 위 요청 인입 시 에이전트는 사족 없이 아래 **표준 프로토콜**을 순차적으로 즉시 실행할 것.

0. **사용자 맥락 및 화자 원칙 정밀 로드 (mem0 Token Optimization)**:
   - `get_all_memories` 전체 덤프 호출 **절대 금지** (토큰 낭비 및 컨텍스트 오염 방지).
   - 본 문서의 `0. 엔지니어링 정체성 및 화자 원칙`을 기본 컨텍스트로 채택하되, 필요 시 `search_memory`를 통해 `query="화자 페르소나 거버넌스"`(limit=1), `query="한승윤 프로필"`(limit=1)만 **핀포인트(Pinpoint) 조회**할 것.
1. **원리 및 코드 라인 정밀 분석**:
   - 대상 파트의 앵커(타깃 파일 및 라인, Git 커밋 해시, 핵심 장애 원인)를 기반으로 시스템 레벨에서 분석.
   - 실제 프로젝트 소스 코드 파일의 정확한 경로 및 핵심 라인을 링크 형태로 발췌.
   - 설계 당시의 환경 제약(1GB VM, FinOps, 무상태 아키텍처)과 기술적 트레이드오프(2가지 이상) 명시.
2. **검증 인프라 환경 선별 및 벤치마크 실행**:
   - **파트별 실행 환경 거버넌스 준수**:
     - `파트 1, 2, 5, 6, 7`: **Docker Compose 인프라 실증 필수** (`docker-compose.yml` 서비스 기동 후 실제 소켓/네트워크 I/O 및 컨테이너 리소스 제약 환경에서 계측).
     - `파트 3`: **하이브리드 실증** (Cloudflare L7 헤더 파싱/Rate Limiting은 Docker Web 엔드포인트 호출, XSS/템플릿 이스케이핑은 순수 파이썬 계측).
     - `파트 4`: **순수 파이썬 로컬 알고리즘 실증** (순수 CPU 인메모리 문자열 파싱).
   - **PowerShell 라이프사이클 및 클린업(Teardown) 준수**:
     ```powershell
     # 1. 필요 컨테이너 사전 기동 (포트 6379, 8000 등)
     docker-compose up -d <service_name>
     # 2. 벤치마크 스크립트 실행 (tests/benchmark_<part_name>.py)
     python tests/benchmark_<part_name>.py
     # 3. 사후 리소스 반환 (테스트 종료 즉시 정지)
     docker-compose stop <service_name>
     ```
   - **[테스트베드 시딩 데이터 영속성 원칙]**:
     - 로컬 Docker 볼륨(`dev_db_data`) 및 Redis에 `data.js` 기반 71종 실운영 직업 데이터셋이 **이미 시딩되어 영구 보존(Persistent Volume)되어 있음**.
     - 임의의 가상 더미 데이터를 생성하지 말고, 이미 적재된 71종 실제 직업 데이터를 쿼리, 인메모리 캐시, 락 경합 벤치마크에 즉시 재사용할 것. (볼륨 재성성 등으로 데이터가 유실된 경우에만 `setup_seed_data()`로 1회 복구).
   - Naive 방식(최적화 전) vs 프로젝트 적용 방식(최적화 후)을 비교하여 Latency(평균/p95), 동시성 성공률, 리소스 점유율 등 정량적 수치 산출.
3. **문서 자동 갱신 및 실증 보고서 분리 (Documentation Sync)**:
   - **상세 실증 보고서 독립 생성**: 상세 테스트베드 사양, 부하 조건, `docker stats` 덤프 등은 [`portfolio/benchmarks/TEMPLATE.md`](file:///c:/work/rpg_sync_project/portfolio/benchmarks/TEMPLATE.md) 규격에 따라 `portfolio/benchmarks/PART_0X_<name>.md` 파일로 독립 생성할 것.
   - **본 가이드 문서 반영**: 본 문서(`STUDY_AND_INTERVIEW_GUIDE.md`)의 해당 파트에는 `[실증 보고서 원문](...)` 링크와 핵심 정량 데이터 요약표(3~4행), 핵심 코드 스니펫만 간결하게 영구 반영.
4. **면접관 Red Teaming 압박 질문 및 1분 방어 스크립트 도출**:
   - "에이전트 생성 코드의 단순 복붙" 또는 "로컬 가상 시뮬레이션의 확증 편향"을 파고드는 기술 면접관 관점의 날카로운 질문 2종 제시.
   - '실전형 트러블슈터' 페르소나에 맞춘 1분 구술 방어 스크립트 제공.

---

## 0. 엔지니어링 정체성 및 화자 원칙 (Persona Governance)
- **화자 정체성**: 한승윤 (21학번 컴퓨터공학과 4학년 2학기 휴학생 / 부트캠프 수강 중인 주니어 DevSecOps 엔지니어 지향)
- **핵심 가치관 및 행동 기제**:
  - 군 복무(포반장/분대장 임무 완수) 시절 체득한 조직 규율과 명확한 책임 의식.
  - 장애 인입 시 당황하거나 모호하게 추측하지 않고, 시스템 로그·OS 소켓·네트워크 패킷 단위로 끝까지 역추적하여 원인을 규명하고 조용히 완결 짓는 실전형 트러블슈터.
- **서술 톤 및 어휘 거버넌스**:
  - **시니어 아키텍트/엔터프라이즈 코스프레 전면 배제**: '혁신적', '완벽한', '무결점' 등 주관적 찬사나 과장된 수식어 엄금.
  - **정직한 실무 동사 사용**: 거창한 '구축/정립/설계' 남발을 지양하고, 실제 행동에 부합하는 '원리 분석', '실습 검증', '설정 보완', '예외 처리 추가'로 서술.
  - **환경 제약 속 1단계 개선 강조**: GCP Free Tier e2-micro(1GB RAM), FinOps 예산 0원, 단일 노드라는 극단적 제약 속에서 이론적 이상론 대신 시스템을 안정화한 구체적 1단계 개선에 집중.
  - **휴먼 에러의 투명한 인정**: 초기 인프라 프로비저닝 시 리전 RTT 계산 누락 등 미숙했던 점은 솔직히 인정하고, 이를 계기로 네트워크 프로토콜과 생명주기를 시스템 레벨에서 학습하여 자산화한 과정을 증명.

---

## 1. 면접 공통 스토리라인: 인프라 불일치와 휴먼 에러의 자산화

### Q1. "GCP 미국 리전에서 한국 Supabase DB를 호출하면 200ms 지연이 발생하는데, 왜 리전을 일치시키지 않고 이런 복잡한 커넥션 풀링과 캐싱을 짰습니까?"
- **솔직한 원인 규명**:
  - "초기 인프라 프로비저닝 시 GCP Free Tier e2-micro 인스턴스의 미국 리전(us-central1) 무료 제약에만 매몰되어, 한국 Supabase DB(ap-northeast-2)와의 물리적 거리(대륙 간 RTT ~200ms)를 사전에 계산하지 못한 **명백한 제 불찰이자 휴먼 에러**였습니다."
- **인지 및 조치 계획**:
  - "이후 팀 리뷰 과정에서 지연 원인을 분석하며 리전 불일치를 인지했고, Supabase 프로젝트를 미국 리전으로 이전하는 마이그레이션 절차를 수립했습니다. 그러나 운영 종료 일정이 맞물려 실제 데이터 이전은 집행하지 못했습니다."
- **기술적 자산화 (전화위복)**:
  - "하지만 이 실수를 수습하는 과정에서 교과서적인 `SELECT 1` 헬스체크가 200ms RTT 환경에서 매 쿼리마다 400ms 이상의 병목을 유발하는 현상을 시스템 레벨에서 목격했습니다.
  - 이를 해결하기 위해 **TCP Keepalive 커널 파라미터 보완, `conn.closed` 메모리 플래그 선조회 + 단절 시에만 재연결하는 `@db_retry` 예외 처리 추가, 봇 기동 시 단 1회 벌크 조회로 Redis를 예열하는 Fast Path**를 적용해 사용자 체감 지연을 34.7ms 수준으로 개선했습니다. 실수에서 도망치지 않고 네트워크 패킷 교환과 소켓 생명주기를 깊이 파고든 값진 배움의 기회였습니다."

---

### Q2. "왜 초기 Oracle DB에서 Supabase(PostgreSQL)로 변경했는가? 두 DBMS의 아키텍처적 차이는 무엇인가?"
- **솔직한 원인 규명**:
  - "학부 데이터베이스 수업에서 가장 익숙하게 다루어본 엔진이 Oracle이었기에 프로젝트 극초기(`2026-04-15`, 커밋 [`e5e81fc`](file:///c:/work/rpg_sync_project))에 관성적으로 `oracledb`를 선택했습니다. SQL 문법이 유사하니 엔진 간 차이도 크지 않을 것이라 안일하게 판단했던 제 미숙함이었습니다."
- **인프라 제약과 전환 계기 (FinOps 0원)**:
  - "실제 배포 대상인 GCP Free Tier e2-micro 인스턴스는 **1 vCPU / 1GB RAM** 사양에 불과했습니다. Oracle DB는 경량화 버전(Oracle XE)조차 최소 2GB 이상의 메모리를 요구하므로 단일 VM 내에서 봇, 웹 서버와 함께 구동 시 즉각적인 OOM(Out of Memory) 크래시가 발생했습니다.
  - 이에 FinOps 예산 0원 제약을 유지하면서 DB를 외부 인프라로 격리하기 위해, 500MB 무료 스토리지와 독립 호스팅을 제공하는 완전관리형(BaaS) PostgreSQL 서비스인 **Supabase**로 2시간 30분 만에 긴급 마이그레이션(`2026-04-15`, 커밋 [`a3eaa5d`](file:///c:/work/rpg_sync_project))했습니다."
- **실무를 통해 체득한 Oracle vs PostgreSQL 핵심 아키텍처 차이점**:
  | 비교 항목 | Oracle DB | PostgreSQL (Supabase) | 프로젝트 실무 영향 및 기술적 함의 |
  |---|---|---|---|
  | **1. MVCC 동시성 제어** | **Undo 세그먼트** 기반<br>- 원본 블록 직접 갱신 후 이전 데이터는 Undo 공간에 저장 | **Append-only (In-place Heap)** 기반<br>- UPDATE 시 신규 튜플 INSERT, 이전 튜플은 Dead Tuple화 (`xmax` 마킹) | - PostgreSQL은 누적 Dead Tuple 정리를 위한 **VACUUM / Autovacuum** 관리가 필수적임.<br>- Oracle은 긴 트랜잭션 시 Undo 공간 부족으로 `ORA-01555 (snapshot too old)` 발생. |
  | **2. UPSERT 구문** | `MERGE INTO ... USING (SELECT ... FROM DUAL) ON (...)` | `INSERT INTO ... VALUES (...) ON CONFLICT (key) DO UPDATE SET ...` | - Oracle은 문법이 장황하고 `DUAL` 더미 테이블 필수.<br>- PostgreSQL은 표준적이고 간결한 `ON CONFLICT` 지원 (`a3eaa5d` 커밋에서 코드 30줄 단축). |
  | **3. 빈 문자열과 NULL** | `''` (빈 문자열)을 **`NULL`로 자동 치환** | `''`와 `NULL`을 **서로 다른 값으로 엄격히 구분** | - Oracle 기준 쿼리(`WHERE col IS NULL`)가 PostgreSQL에서는 빈 문자열을 거르지 못해 데이터 조건문 누수 위험 발생. |
  | **4. 트랜잭션 DDL 지원** | DDL(`CREATE`, `ALTER`) 실행 시 **암묵적 COMMIT 자동 발생** (ROLLBACK 불가) | **DDL도 완전한 트랜잭션 내 롤백 가능** | - PostgreSQL은 마이그레이션 스크립트 도중 에러 발생 시 `ROLLBACK`으로 스키마 변경 전체를 안전하게 원상복구 가능. |
  | **5. 드라이버 및 바인딩** | `oracledb`: 콜론 네임드 바인딩 (`:name`) | `psycopg2`: `%s` 순차 바인딩<br>`asyncpg`: `$1, $2` 위치 바인딩 | - DB 전환 시 SQL뿐 아니라 애플리케이션 파라미터 매핑 계층 전체의 수정 공수 발생. |
- **1분 구술 방어 스크립트**:
  - "프로젝트 초기에는 학부 수업에서 가장 먼저 접했던 DB가 Oracle이었기 때문에 관성적으로 `oracledb`를 선택했습니다. SQL 문법이 유사하니 엔진 간 차이도 크지 않을 것이라 안일하게 생각했던 제 불찰이었습니다.
  - 하지만 GCP Free Tier 1GB RAM VM에 배포하려는 순간, Oracle은 최소 메모리 요구치(2GB 이상)로 인해 단일 인스턴스에서 구동 자체가 불가능한 벽에 부딪혔습니다. 이에 FinOps 제약(비용 0원)을 지키면서 DB를 외부로 분리하기 위해 관리형 PostgreSQL 서비스인 Supabase로 긴급 전환했습니다.
  - 이 전환을 계기로 두 DBMS의 시스템적 차이를 깊이 학습하게 되었습니다. Oracle이 **Undo 세그먼트**를 통해 롤백 블록을 재구성하며 읽기 일관성을 유지하는 반면, PostgreSQL은 **Append-only 방식**으로 새 튜플을 쌓기 때문에 누적되는 Dead Tuple을 정리하는 **Autovacuum 메커니즘**이 핵심이라는 점을 배웠습니다.
  - 또한 Oracle과 달리 PostgreSQL은 `''` 빈 문자열과 `NULL`을 엄격히 구분한다는 점, DDL 문장도 트랜잭션 롤백이 가능하다는 차이를 확인했습니다. 미숙한 선택으로 시작했지만, 인프라 한계를 마주하며 RDBMS별 엔진 구조와 MVCC 구현 방식의 차이를 몸으로 체득한 소중한 경험이었습니다."

---

## 2. [파트 1] 네트워크 RTT 극복과 DB 커넥션 풀 자가 치유

### [세션 자동 실행 앵커 (Target Anchors)]
- **핵심 소스 경로**: [`src/database/connection.py:L15-L115`](file:///c:/work/rpg_sync_project/src/database/connection.py#L15-L115) (TCP Keepalive 풀, `db_retry` 데코레이터, Stale 커넥션 강제 폐기)
- **관련 Git 커밋 해시**: `cd47bee` (RTT 완화), `e7c8c78` (자가 치유 풀), `7156289` (예외 계층 보완)
- **검증 인프라 규격**: **Docker Compose 필수** (원격 Supabase PostgreSQL 연동 및 TCP Keepalive/소켓 재시도 실측)
- **테스트 스크립트**: `tests/benchmark_connection.py`

### 1) 기술적 문제 및 원인 분석
1. **대륙 간 네트워크 지연 (RTT 200ms)**
   - 풀에서 커넥션을 꺼낼 때마다 살아있는지 확인하는 `SELECT 1` 질의는 왕복 200ms를 소모하여 단순 쿼리 하나에도 400ms 이상의 지연이 발생함.
2. **원격 소켓 강제 종료 (Stale Connection Drop)**
   - Supabase 및 중간 프록시(PgBouncer 등)의 유휴 세션 타임아웃으로 인해 서버 측에서 TCP RST/FIN 패킷으로 연결을 종료함.
   - OS 소켓 버퍼가 이를 감지하기 전까지 클라이언트(`psycopg2`)의 `conn.closed` 플래그는 여전히 `0`(정상)으로 남아 있어 쿼리 실행 시 `OperationalError` 또는 `DatabaseError`로 크래시 발생.

### 2) 핵심 해결 코드
- **TCP Keepalive 활성화 (`src/database/connection.py`)**:
  ```python
  _db_pool = pool.ThreadedConnectionPool(
      2, 8,
      dsn=os.getenv("DATABASE_URL"),
      keepalives=1,          # TCP Keepalive 활성화
      keepalives_idle=30,     # 30초 유휴 시 프로브 패킷 전송
      keepalives_interval=10, # 미응답 시 10초 주기 재전송
      keepalives_count=5      # 5회 실패 시 단절 판정
  )
  ```
- **자가 치유 `db_retry` 데코레이터 및 Stale 커넥션 폐기**:
  ```python
  def db_retry(max_retries=2):
      def decorator(func):
          @functools.wraps(func)
          def wrapper(*args, **kwargs):
              last_exc = None
              for attempt in range(max_retries + 1):
                  try:
                      return func(*args, **kwargs)
                  except (OperationalError, psycopg2.DatabaseError) as e:
                      last_exc = e
                      if attempt == max_retries:
                          raise last_exc
          return wrapper
      return decorator
  ```
  - `get_connection()`에서 `SELECT 1`을 제거하고 `conn.closed != 0`만 검사하여 200ms 지연 제거.
  - 쿼리 실행 실패 시 `putconn(conn, close=True)`로 끊어진 소켓을 풀에서 영구 제거 후 1회 재시도.

### 3) 도커 컴포즈 기반 실증 계측 결과
- **정량 실증 보고서 전문**: [`portfolio/benchmarks/PART1_CONNECTION_POOL.md`](file:///c:/work/rpg_sync_project/portfolio/benchmarks/PART1_CONNECTION_POOL.md)
- **실행 스크립트**: `tests/benchmark_connection.py` (Docker Compose `rpg-db-dev`, `rpg-redis-dev` 실측)
- **테스트 데이터셋**: [`data.js`](file:///c:/work/rpg_sync_project/data.js) 하드코딩 원천 데이터셋 (실제 게임 직업 71종 전체 파싱 및 시딩 후 무작위 질의)
- **실측 요약**:
  - `pg_terminate_backend`를 통한 실제 서버 세션 강제 종료 시, 클라이언트 메모리 플래그 `conn.closed`가 여전히 `0`(정상)으로 남아있는 런타임 결함을 실증함.
  - `@db_retry` 데코레이터를 통해 끊어진 소켓 자동 폐기(`putconn(close=True)`) 및 신규 커넥션 재연결로 6회 소켓 단절 주입 전건 무중단 자가 치유(성공률 100.0%, 복구 지연 4.77ms) 달성.
  - **대륙 간 RTT 200ms 환경 실측 메트릭 (data.js 71종 실데이터 질의)**:
    - **최적화 전 (Naive, 매번 SELECT 1)**: 평균 405.66 ms | p95 411.09 ms | 처리량 2.47 RPS
    - **프로젝트 적용 (Hardened, db_retry)**: 평균 **243.41 ms** (-40.0% 단축) | 처리량 **4.11 RPS** (+66.7% 향상)
    - **Fast Path (Redis 캐시 결합)**: 평균 **16.18 ms** (-96.0% 단축) | 처리량 **61.78 RPS** (+2401.2% 향상)
  - 상세 테스트베드 사양, 재현 명령어, `docker stats` 메트릭 덤프는 [실증 보고서](file:///c:/work/rpg_sync_project/portfolio/benchmarks/PART1_CONNECTION_POOL.md) 전문 참조.

### 4) 면접 1분 방어 스크립트
- **핵심 답변**:  
  "Supabase 원격 소켓이 끊어지는 문제는 OS 소켓 버퍼 동작 특성상 메모리 플래그(`conn.closed`)만으로는 감지할 수 없습니다. 실제로 로컬 도커 환경에서 `pg_terminate_backend`로 세션을 강제 종료시켜도 클라이언트의 `conn.closed`는 여전히 `0`으로 남아있음을 실측으로 검증했습니다.  
  이를 해결하기 위해 매번 `SELECT 1`을 날리는 방식은 200ms RTT 환경에서 응답 시간을 405.66ms로 배가시키는 치명적 안티패턴이었습니다.  
  따라서 정상 요청 95% 이상에 대해서는 사전 검증을 생략하고 즉시 쿼리를 실행하되, 소켓이 끊어졌을 때만 `OperationalError` 및 `DatabaseError`를 잡아 커넥션을 폐기하고 재연결하는 `@db_retry` 패턴을 적용했습니다. 개발 초기 `data.js`에 하드코딩되었던 71개 실제 직업 데이터셋을 대상으로 실측한 결과, DB I/O 지연시간을 405.66ms에서 243.41ms로 40.0% 단축시켰고, 봇 기동 시 단 1회의 벌크 쿼리로 예열된 Redis Fast Path 캐시를 결합하여 평균 16.18ms로 96.0%의 레이턴시를 개선했습니다. 단, 재시도로 인한 데이터 오염을 방지하기 위해 멱등성이 보장되는 `ON CONFLICT DO UPDATE` 및 단순 조회 쿼리에만 한정 적용했습니다."

---

## 3. [파트 2] 비동기 이벤트 루프 격리와 경량 분산 락

### [세션 자동 실행 앵커 (Target Anchors)]
- **핵심 소스 경로**:
  - 스레드 풀 격리: [`src/bot/main.py:L280-L283`](file:///c:/work/rpg_sync_project/src/bot/main.py#L280-L283) (`ThreadPoolExecutor(max_workers=20)`, `loop.set_default_executor`)
  - Safe TTL 분산 락: [`src/bot/cogs/users/reason_bypass.py:L31-L96`](file:///c:/work/rpg_sync_project/src/bot/cogs/users/reason_bypass.py#L31-L96) (`set(lock_key, "1", ex=15, nx=True)`)
- **관련 Git 커밋 해시**: `8d3c2a3` (`asyncio.to_thread` 도입), `28a2239` (적용 확대), `fbafdbb` (ThreadPoolExecutor 전역 주입), `c6cc131` (Safe TTL 락)
- **검증 인프라 규격**: **Docker Compose 필수** (`docker-compose up -d redis` 후 실제 Redis 분산 락 경합 및 봇 스레드 풀 지연 계측)
- **테스트 스크립트**: `tests/benchmark_event_loop.py`

### 1) 기술적 문제 및 원인 분석
1. **단일 이벤트 루프 블로킹과 WebSocket 게이트웨이 세션 단절**
   - `discord.py`는 단일 스레드 `asyncio` 이벤트 루프 위에서 게이트웨이 웹소켓 통신을 유지함.
   - 백그라운드에서 주기적으로(약 41.25초) Discord 서버로 `Heartbeat`(op 1) 패킷을 보내고 `Heartbeat ACK`(op 11)를 수신해야 세션이 유지됨.
   - DB 쿼리(`psycopg2`), Cloudflare R2 업로드(`boto3`) 등 동기 블로킹 I/O를 코루틴(`async def`) 내에서 직접 실행할 경우, 200ms 이상의 RTT 동안 이벤트 루프 전체가 동결됨.
   - 이로 인해 하트비트 프레임이 제때 송신되지 못해 게이트웨이 연결이 비정상 종료(Code 1006 / Heartbeat Timeout)되고, 무한 재연결 루프와 세션 유실(Zombie Connection)이 유발됨.
2. **FastAPI vs Discord Bot 간의 프레임워크 비대칭 결함**
   - `src/database/` 계층은 디스코드 봇뿐만 아니라 FastAPI 웹 백엔드(`src/web/routers/`)도 공용으로 참조함.
   - FastAPI는 라우터를 일반 `def`(동기)로 선언하면 Starlette 내부 워커 스레드로 자동 오프로딩하므로, 웹 서버 환경에서는 동기 `psycopg2` 호출이 이벤트 루프를 전혀 블로킹하지 않고 정상 작동함.
   - 반면 `discord.py`는 모든 커맨드와 이벤트 리스너가 강제적으로 `async def`(코루틴)임. 웹에서 문제없던 동일 DB 헬퍼 함수가 봇의 이벤트 루프를 동결시키는 비대칭 런타임 장애가 발생함.
3. **동시 클릭(Race Condition)과 다중 스태프 중복 처리**
   - 디스코드 UI 버튼(승인/거절, 일괄 복구)은 네트워크 지연 시 사용자의 다중 클릭 또는 복수 스태프의 동시 클릭이 빈번히 발생함.
   - 락이 없을 경우 마인크래프트 서버 웹소켓으로 승인/킥 신호가 중복 발행되어 불필요한 네트워크 트래픽과 상태 불일치를 유발함.

### 2) 핵심 해결 코드 및 아키텍처
- **전역 스레드 풀 격리 및 `asyncio.to_thread` 위임 ([`src/bot/main.py:L280-L283`](file:///c:/work/rpg_sync_project/src/bot/main.py#L280-L283))**:
  ```python
  loop = asyncio.get_running_loop()
  executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
  loop.set_default_executor(executor)
  ```
  - 모든 동기 DB 헬퍼 함수는 `await asyncio.to_thread(func, *args)` 형태로 호출하여 동기 I/O를 워커 스레드로 완전히 격리, 메인 이벤트 루프의 하트비트 지연시간(Lag)을 0ms에 가깝게 유지.
  - **FinOps & 리소스 제약 고려**: 1GB RAM e2-micro VM 환경에서 무제한 스레드 생성 시 스택 메모리(스레드당 수 MB) 고갈로 인한 OOM(Out of Memory)을 방지하기 위해 `max_workers=20`으로 상한선 고정. DB 풀(최대 8개)과의 비율도 균형 유지.
- **Safe TTL (15s) 단일 키 기반 경량 분산 락 ([`src/bot/cogs/users/reason_bypass.py:L31-L96`](file:///c:/work/rpg_sync_project/src/bot/cogs/users/reason_bypass.py#L31-L96))**:
  ```python
  lock_key = f"rpgsync:processing_reason:{mc_uuid}"

  # 1. Redis 원자적 분산 락 획득 시도 (15초 만료 보장)
  acquired = await redis_client.set(lock_key, "1", ex=15, nx=True)
  if not acquired:
      await interaction.response.send_message("이미 처리 중이거나 완료된 사유입니다.", ephemeral=True)
      return

  try:
      # 2. 락 획득 즉시 컴포넌트 비활성화 및 화면 갱신 (더블 클릭 물리적 차단)
      await interaction.response.defer()
      for item in self.children:
          if isinstance(item, discord.ui.Button):
              item.disabled = True
      await interaction.message.edit(view=self)

      # 3. 비즈니스 로직 및 Redis Pub/Sub 발행
      user_info = await asyncio.to_thread(get_user_by_uuid, mc_uuid)
      ...
  finally:
      # 4. 작업 완료 후 즉시 락 해제
      await redis_client.delete(lock_key)
  ```

### 3) 설계 트레이드오프 및 Git 커밋 히스토리 실증 분석
1. **왜 `asyncpg`로 전면 개편하지 않고 `ThreadPoolExecutor`를 덧붙였는가? (Git Fact)**
   - **타임라인 분석**:
     - `2026-04-15 15:01` ([`e5e81fc`](file:///c:/work/rpg_sync_project)): 초기 DB는 **Oracle DB(`oracledb`)** 동기 드라이버로 구축됨.
     - `2026-04-15 17:39` ([`a3eaa5d`](file:///c:/work/rpg_sync_project)): 클라우드 DB(Supabase) 이전을 위해 2시간 30분 만에 PostgreSQL로 긴급 전환. `oracledb`의 `cursor.execute` 구조를 1:1로 가장 빠르게 치환할 수 있는 **`psycopg2`**를 채택함.
     - `2026-04-20 23:45` ([`8d3c2a3`](file:///c:/work/rpg_sync_project)): 3초 인터랙션 타임아웃 발생으로 `/위키` 커맨드에 최초 `asyncio.to_thread` 도입.
     - `2026-04-23 02:51` ([`28a2239`](file:///c:/work/rpg_sync_project)): 대량 동기화 중 이벤트 루프 프리징 발견 후 `asyncio.to_thread` 확대.
     - `2026-04-29 19:24` ([`fbafdbb`](file:///c:/work/rpg_sync_project)): 봇 전역 루프에 `ThreadPoolExecutor(max_workers=20)` 주입 및 `statement_timeout = 2000` 설정.
   - **기회비용/한계**: `asyncpg` 대비 OS 스레드 풀 생성 및 미세한 컨텍스트 스위칭 오버헤드가 발생함.
   - **채택 근거**:
     - `src/database/` 모듈은 봇뿐만 아니라 FastAPI 웹 서버(수십 개 엔드포인트)가 공용으로 사용 중이었음.
     - 4월 말 서비스 오픈 피크 시점에 `asyncpg`로 전면 교체 시, 파라미터 바인딩 규격(`$1, $2`), 커넥션 풀(`async with pool.acquire()`), 쿼리 헬퍼 20여 개와 트랜잭션을 전부 비동기로 재작성해야 하여 운영 중단 리스크가 과도했음.
     - FastAPI가 동기 라우터를 내부 스레드 풀로 넘기는 방식과 동일하게, 봇 메인 루프에 `ThreadPoolExecutor(max_workers=20)`를 주입하고 동기 DB 호출부만 `asyncio.to_thread`로 위임하여 **코드 수정 범위를 최소화하면서 이벤트 루프 동결 장애를 즉시 100% 진화**함.
2. **단일 노드 `SET NX EX 15` vs Redlock / Watchdog (TTL 자동 연장)**
   - **선택**: Safe TTL 15s 단일 키 분산 락
   - **기회비용/한계**: 작업이 15초를 초과하면 락이 조기 해제되어 동시성 보호가 풀릴 수 있으며, 별도의 락 토큰(UUID) 검증이 없어 극단적인 경우 타 세션 락 삭제 가능성이 이론상 존재함.
   - **채택 근거**: 비즈니스 로직(DB 단건 조회 + Redis Pub/Sub 발행)은 최대 100ms 이내에 완료되므로 15초는 150배 이상의 안전 여유(Safe Margin)임. Redlock은 최소 3대 이상의 독립 Redis 인스턴스를 요구하여 Free Tier 1GB RAM FinOps 환경에 부적합하고, Watchdog은 비동기 태스크 누수 위험이 큼. 락 자동 만료(15s)를 두어 프로세스 크래시 시에도 시스템 데드락을 원천 방지함.

### 4) 도커 컴포즈 기반 실증 계측 결과
- **정량 실증 보고서 전문**: [`portfolio/benchmarks/PART2_EVENT_LOOP_AND_LOCK.md`](file:///c:/work/rpg_sync_project/portfolio/benchmarks/PART2_EVENT_LOOP_AND_LOCK.md)
- **실행 스크립트**: `tests/benchmark_event_loop.py` (Docker Compose `rpg-db-dev`, `rpg-redis-dev` 실측)
- **실측 요약**:
  - 실제 구동 중인 PostgreSQL 컨테이너(`rpg-db-dev`) 소켓 쿼리와 Redis 컨테이너(`rpg-redis-dev`) `SET NX` 커맨드를 연동하여 실측함.
  - **이벤트 루프 동결 및 하트비트 지연 (PostgreSQL 15 실측)**:
    - **최적화 전 (Naive, 이벤트 루프 내 직접 동기 쿼리)**: 총 2.495 s | 처리량 4.01 RPS | 하트비트 평균 Lag 177.85 ms | **하트비트 최대 Lag 206.04 ms** (게이트웨이 웹소켓 1006 커넥션 드롭 발생 임계치 초과)
    - **프로젝트 적용 (Hardened, ThreadPoolExecutor 격리)**: 총 **0.358 s** (-85.7% 단축) | 처리량 **27.94 RPS** (+596.8% 향상) | 하트비트 평균 Lag **12.21 ms** (-93.1% 지터 감소) | **하트비트 최대 Lag 14.64 ms** (-92.9% 지연 억제, 게이트웨이 세션 안정적 유지)
  - **Docker Redis Safe TTL (15s) 분산 락 동시성 실측 (20건 동시 클릭)**:
    - `SET key val EX 15 NX` 원자적 커맨드를 통해 20개 동시 폭주 중 **정상 처리 1건 / 중복 차단 19건 (동시성 오류율 0.0%, 무결성 100% 방어)** 실증.
    - SET NX 평균 응답시간: **29.63 ms** (p95/최대 36.17 ms).
  - 상세 테스트베드 사양, 재현 명령어, `docker stats` 메트릭 덤프는 [실증 보고서](file:///c:/work/rpg_sync_project/portfolio/benchmarks/PART2_EVENT_LOOP_AND_LOCK.md) 전문 참조.

### 5) 면접관 Red Teaming 압박 질문 & 1분 방어 스크립트

#### Q1. "비동기 프레임워크인 `discord.py`를 쓰면서 왜 `asyncpg` 같은 완전 비동기 드라이버를 쓰지 않고, 동기 드라이버(`psycopg2`)에 스레드 풀을 덧붙이는 구조를 취했습니까? 스레드 컨텍스트 스위칭 비용이 더 낭비 아닌가요?"
- **1분 구술 방어 (주니어 실전형 트러블슈터 관점)**:
  - "기술적으로 `asyncpg` 기반의 완전 비동기 논블로킹 I/O가 최적이라는 점에 전적으로 동의합니다. 하지만 이 구조가 만들어진 데에는 명확한 Git 히스토리와 실무적 제약이 있었습니다.
  - 최초 프로젝트는 Oracle DB(`oracledb`) 동기 드라이버로 시작되었고, Supabase로 긴급 전환하는 과정에서 1:1 치환이 가장 빠른 `psycopg2`를 채택했던 기술 부채가 있었습니다. 또한 이 DB 계층은 봇뿐만 아니라 FastAPI 웹 서비스도 공용으로 참조하고 있었습니다. FastAPI는 동기 함수를 내부 스레드 풀로 넘겨 루프를 보호했지만, 강제 `async def` 기반인 `discord.py`에서는 동기 DB I/O가 단일 이벤트 루프를 동결시켜 하트비트(op 1)를 누락하고 1006 커넥션 드롭을 유발하는 프레임워크 간 비대칭 결함이 터졌습니다.
  - 오픈을 앞둔 4월 말, 웹과 봇 전체의 DB 헬퍼 20여 개와 바인딩 규격을 `asyncpg`로 전면 재작성하는 것은 서비스 장애 위험이 과도했습니다. 이에 따라 FastAPI의 스레드 오프로딩 방식을 봇에도 동일하게 적용하여, `ThreadPoolExecutor(max_workers=20)`를 주입하고 `asyncio.to_thread`로 동기 I/O를 워커 스레드로 즉각 격리했습니다. 이때 1GB RAM e2-micro의 메모리 고갈을 막기 위해 풀 크기를 20개로 엄격히 제한했습니다.
  - 실제 도커 환경에서 계측한 결과, 하트비트 최대 지연을 206.04ms에서 14.64ms로 92.9% 낮추고 처리량을 4.01 RPS에서 27.94 RPS로 596.8% 향상시켜 연결 단절을 완전히 방어했습니다. 이론적 이상론을 위해 무리한 재작성을 감행하기보다, 시스템 붕괴 원인을 시스템 레벨에서 정확히 짚어내고 자원 제약 내에서 최소 변경으로 가용성을 확보한 실전적 트러블슈팅이었습니다."

#### Q2. "단일 노드 Redis에서 `SET key 1 EX 15 NX`로 락을 잡고 `finally`에서 `DELETE`하는 구조는, 만약 작업이 15초를 초과할 경우 락이 풀린 상태에서 다른 인스턴스가 획득한 락을 이전 인스턴스가 지워버리는 락 오인 삭제 결함이 있습니다. 왜 UUID 토큰 기반 Lua 스크립트 검증을 넣지 않았습니까?"
- **1분 구술 방어 (주니어 실전형 트러블슈터 관점)**:
  - "지적해주신 Split-brain과 타 프로세스 락 오인 삭제는 분산 락 환경에서 필연적으로 발생하는 명확한 한계 지점입니다.
  - 하지만 본 시스템은 FinOps 예산 0원, 단일 인스턴스로 운영되는 인프라였고, 보호 대상인 임계 구역은 '단건 유저 조회'와 'Redis Pub/Sub 1회 발행'으로 평균 실행 시간이 50ms 미만, 최악의 경우에도 200ms를 넘지 않았습니다. 15초 Safe TTL은 실제 수행 시간의 75배를 상회하는 충분한 안전 마진이었습니다.
  - 화려한 Lua 스크립트나 UUID 토큰 검증 같은 엔터프라이즈 패턴을 어설프게 흉내 내기보다는, 제가 처한 환경 제약 내에서 가장 단순하고 확실한 방어선을 구축했습니다. 락 획득 즉시 UI 컴포넌트(`item.disabled = True`)를 수정해 물리적 중복 클릭을 차단했고, 15초 만료를 통해 프로세스가 크래시되더라도 시스템 데드락 없이 자가 복구되도록 설계했습니다. 불필요한 복잡성을 배제하고 현장의 문제를 확실하게 1단계 해결한 엔지니어링 결정이었습니다."

---

## 4. [파트 3] 웹 보안 및 Pure ASGI 미들웨어 하드닝

### [세션 자동 실행 앵커 (Target Anchors)]
- **핵심 소스 경로**:
  - Pure ASGI 보안 미들웨어: [`src/web/main.py:L31-L98`](file:///c:/work/rpg_sync_project/src/web/main.py#L31-L98) (`SecurityMiddleware`, CSRF Origin 경계 검증, 로컬 HSTS 제외, 보안 헤더 6종)
  - Cloudflare IP 기반 Rate Limiter: [`src/web/limiter.py:L6-L12`](file:///c:/work/rpg_sync_project/src/web/limiter.py#L6-L12) (`get_real_ip`, `cf-connecting-ip`)
  - SSR 전환 & XSS 방어: [`src/web/templates/`](file:///c:/work/rpg_sync_project/src/web/templates), [`src/database/jobs.py:L15-L45`](file:///c:/work/rpg_sync_project/src/database/jobs.py#L15-L45) (컬럼 화이트리스트 및 파라미터 바인딩)
- **관련 Git 커밋 해시**: `6afe4bc` (Jinja2 SSR 전환), `66fe5c3` (Real IP 추적 및 DoS 방어), `b68a434` (Pure ASGI 미들웨어 통합)
- **검증 인프라 규격**: **Docker Compose 필수** (Docker Compose `rpg-api-dev`, `rpg-redis-dev` 기동 후 실제 HTTP 통신을 통한 보안 헤더, CSRF 차단 및 slowapi 레이트리밋 실측)
- **테스트 스크립트**: `tests/benchmark_web_security.py`

### 1) 기술적 문제 및 원인 분석
1. **AI 생성 코드의 보안 결함: f-string SQL Injection 및 CSR DOM XSS**
   - AI 에이전트로 초기 프로토타입 작성 시, SQL 쿼리를 파라미터 바인딩 없이 단순 문자열 포맷팅(`f"SELECT ... WHERE name = '{job_name}'"`)으로 조합하거나 동적 컬럼 갱신 시 `f"UPDATE JOBS SET {column} = '{val}'"`로 생성하여 외부 입력값 변조 시 데이터베이스 인증 우회 및 무단 조작 위험 노출.
   - 초기 프론트엔드는 바닐라 JS 기반 CSR(`main.js`)로 구축되어, API 응답 데이터를 `innerHTML`을 통해 유저 및 직업 설명(`job.desc`, `player.name`)에 그대로 삽입함. 악의적인 스크립트 태그(`<script>`, `<img onerror=...>`) 주입 시 사용자 브라우저 세션에서 임의 스크립트가 실행되는 Stored/DOM XSS 취약점 발생.
2. **Cloudflare Reverse Proxy 환경에서의 Rate Limiting 왜곡 및 DoS 위험**
   - FastAPI와 Slowapi의 기본 IP 추출(`get_remote_address`)은 L4 TCP 소켓 IP(`request.client.host`)를 참조함.
   - Cloudflare 프록시를 통과하면 모든 엔드유저의 소켓 IP가 Cloudflare 엣지 노드 IP(예: `172.68.x.x`)로 단일화됨.
   - 단일 유저가 30회 요청을 초과하면 동일 엣지를 공유하는 무고한 모든 사용자가 `429 Too Many Requests`에 걸리는 대규모 오탐 서비스 거부(False Positive DoS) 발생.
   - 반대로 단순히 `request.headers.get("cf-connecting-ip")`를 무비판적으로 신뢰할 경우, 공격자가 오리진 서버에 직접 요청하며 헤더를 위조(Spoofing)하여 Rate Limiting을 완전히 우회하는 취약점 상존.
3. **CSRF Origin 검증의 Boundary 누수 및 Local Developer HSTS Lockout**
   - 단순 접두사 비교(`origin.startswith("https://rpg-sync-wiki.example.com")`) 적용 시, 공격자가 `https://rpg-sync-wiki.example.com.attacker.com`과 같은 도메인 접미사 변조(Prefix Collision)로 검증을 통과하는 치명적 CSRF 방어선 누수 발생.
   - 보안 강화를 위해 `Strict-Transport-Security (HSTS)` 헤더(`max-age=31536000`)를 일괄 적용할 경우, 로컬 개발 환경(`http://localhost:8000`, `127.0.0.1`)에서 개발자 브라우저가 HSTS를 1년간 강제 캐싱하여 `https://localhost`로 강제 전환 후 연결 거부(Local Lockout)를 유발함.

### 2) 핵심 해결 코드 및 아키텍처
- **파라미터 바인딩 및 컬럼 화이트리스트 강제 ([`src/database/queries.py`](file:///c:/work/rpg_sync_project/src/database/queries.py), [`src/database/jobs.py:L15-L45`](file:///c:/work/rpg_sync_project/src/database/jobs.py#L15-L45))**:
  ```python
  # 1. 컬럼 식별자는 SQL 바인딩이 불가하므로 화이트리스트 딕셔너리로 엄격 제한
  allowed_columns = {
      "range": "RANGE_TYPE", "position": "POSITION", "resource": "RESOURCE_TYPE",
      "img": "IMG", "photo1": "PHOTO_1", "photo2": "PHOTO_2",
      "photo3": "PHOTO_3", "photo4": "PHOTO_4"
  }
  target_col = allowed_columns.get(column_name.lower())
  if not target_col:
      raise ValueError("Invalid column name")

  # 2. 값은 %s 튜플 바인딩으로 전달하여 SQL Injection 원천 무력화
  sql = f"UPDATE JOBS SET {target_col} = %s WHERE NAME = %s"
  cursor.execute(sql, (value, clean_job_name))
  ```
- **Jinja2 SSR 전환 및 자동 이스케이프 강제 ([`src/web/templates/`](file:///c:/work/rpg_sync_project/src/web/templates), [`src/web/main.py:L60-L95`](file:///c:/work/rpg_sync_project/src/web/main.py#L60-L95))**:
  - 클라이언트 사이드 `innerHTML` 직접 조작을 전면 폐기하고 Jinja2 템플릿 기반 SSR로 마이그레이션.
  - 템플릿 내 `{{ job.name }}`, `{{ job.description }}` 렌더링 시 Jinja2 기본 Auto-escape 엔진이 특수문자(`<, >, &, ", '`)를 자동 이스케이프하여 DOM XSS 벡터 제거.
- **계층형 IP 파싱 기반 Rate Limiting ([`src/web/limiter.py:L6-L12`](file:///c:/work/rpg_sync_project/src/web/limiter.py#L6-L12))**:
  ```python
  def get_real_ip(request: Request) -> str:
      # Cloudflare 경유 시 실제 클라이언트 IP 헤더 우선 추출
      if "cf-connecting-ip" in request.headers:
          return request.headers["cf-connecting-ip"]
      elif "x-forwarded-for" in request.headers:
          return request.headers["x-forwarded-for"].split(",")[0].strip()
      return get_remote_address(request)
  ```
- **Pure ASGI `SecurityMiddleware` 구현 ([`src/web/main.py:L31-L98`](file:///c:/work/rpg_sync_project/src/web/main.py#L31-L98))**:
  ```python
  class SecurityMiddleware:
      def __init__(self, app: ASGIApp):
          self.app = app
          self.allowed_origins = [
              origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "https://rpg-sync-wiki.example.com").split(",")
          ]

      async def __call__(self, scope: Scope, receive: Receive, send: Send):
          if scope["type"] != "http":
              await self.app(scope, receive, send)
              return

          request = Request(scope, receive)
          start_time = time.time()
          url = URL(scope=scope)

          # 1. CSRF Protection: 도메인 경계(Boundary) 정확 검증 (.attacker.com 우회 차단)
          if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
              origin = request.headers.get("origin")
              referer = request.headers.get("referer")
              
              def is_trusted(value: str):
                  if not value: return False
                  for allowed in self.allowed_origins:
                      if value == allowed or value.startswith(f"{allowed}/"):
                          return True
                  return False

              if not (is_trusted(origin) or is_trusted(referer)):
                  response = JSONResponse(status_code=403, content={"detail": "비정상적인 접근입니다. (CSRF 차단)"})
                  await response(scope, receive, send)
                  return

          async def send_wrapper(message):
              if message["type"] == "http.response.start":
                  headers = MutableHeaders(scope=message)
                  headers["X-Process-Time"] = str(time.time() - start_time)
                  headers["X-Frame-Options"] = "DENY"
                  headers["Content-Security-Policy"] = "frame-ancestors 'none'"
                  headers["X-Content-Type-Options"] = "nosniff"
                  headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                  headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
                  
                  # 2. HSTS Lockout 방지: localhost/127.0.0.1 개발 환경에서는 HSTS 헤더 주입 제외
                  host = url.hostname or ""
                  if host not in ["localhost", "127.0.0.1"]:
                      headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

              await send(message)

          await self.app(scope, receive, send_wrapper)
  ```

### 3) 설계 트레이드오프 및 Git 커밋 히스토리 실증 분석 (`b68a434`)
1. **초기 3중 `@app.middleware("http")` (`BaseHTTPMiddleware`)에서 Pure ASGI로의 통합 리팩토링**
   - **타임라인 및 실제 구현 히스토리**:
     - 초기 구현: FastAPI의 `@app.middleware("http")` 데코레이터를 사용하여 3개의 독립적인 미들웨어(`add_global_template_vars`, `csrf_protection_middleware`, `add_security_headers`)를 체이닝함.
     - **실무 런타임 결함 발생**:
       1. **`request.state` 주입 유실 버그**: `@app.middleware("http")`(내부적으로 `BaseHTTPMiddleware` 사용)는 요청마다 Starlette의 `Request` 객체를 재생성하면서 `request.state.discord_invite_url`이 라우터/템플릿 렌더링 시점에 간헐적으로 유실되어 500 에러 유발.
       2. **HSTS Local Lockout**: `add_security_headers`에서 `localhost:8000` 개발 환경을 예외 처리하지 않고 HSTS 헤더를 일괄 주입하여 개발자 브라우저가 HSTS를 1년간 캐싱, 강제 `https://localhost` 리다이렉트로 인한 접속 불능 사고 발생.
       3. **CSRF 검증 우회**: `csrf_protection_middleware`에서 `referer.startswith(allowed)`로 단순 검사하여 `.attacker.com` 접미사 스푸핑에 취약.
       4. **3중 래핑 오버헤드**: 1GB RAM e2-micro VM 환경에서 매 요청마다 3단계의 제너레이터 래핑 및 컨텍스트 스위칭 발생.
     - **해결책 (`2026-05-26`, 커밋 [`b68a434`](file:///c:/work/rpg_sync_project))**: 3개의 `@app.middleware("http")`를 전면 폐기하고, 단 하나의 **Pure ASGI `SecurityMiddleware`**로 통합. `scope["state"]`에 안전하게 직접 주입하고, 도메인 경계(`allowed/`) 검증과 `localhost` HSTS 제외 분기를 원자적으로 하드닝함.

2. **리팩토링 시 검토했던 대안 3가지 및 기술적 한계 (Why Pure ASGI?)**
   - **대안 A. 단일 `BaseHTTPMiddleware` 통합 + Jinja2 `env.globals` 전역 바인딩 (가장 유력했던 대안)**:
     - *방식*: 3개의 미들웨어를 1개의 클래스로 합치고, `request.state` 대신 `templates.env.globals["discord_invite_url"] = DISCORD_INVITE_URL`로 템플릿 엔진 초기화 시점에 바인딩.
     - *한계 및 기각 사유*: Starlette `BaseHTTPMiddleware`의 본질적 결함인 **비동기 태스크 누수 및 스트리밍 충돌(Issue #1012)** 상존. 내부적으로 바디 처리를 위해 별도 태스크 그룹(`anyio.create_task_group`)을 생성하므로 클라이언트 비정상 연결 종료 시 태스크가 유실되거나 1GB RAM VM 환경에서 불필요한 컨텍스트 스위칭 오버헤드가 남음.
   - **대안 B. FastAPI 의존성 주입(`Depends`) 계층 활용**:
     - *방식*: 미들웨어를 전면 배제하고 `dependencies=[Depends(verify_csrf)]`로 라우터별 검증.
     - *한계 및 기각 사유*: `Depends`는 요청(Request) 진입 시점만 통제할 수 있어, 응답(Response) 시점에 주입되어야 하는 `X-Process-Time`, `X-Frame-Options`, `HSTS` 등 6종 보안 헤더를 처리할 수 없음. 결국 별도 응답 미들웨어를 유지해야 하므로 관리 지점이 분열됨.
   - **대안 C. L7 리버스 프록시(Cloudflare Rules / Nginx)로 전면 오프로딩**:
     - *방식*: 백엔드는 순수 비즈니스 로직만 수행하고, 보안 헤더 및 HSTS 리다이렉트를 Cloudflare Transform Rules 또는 Nginx가 전담.
     - *한계 및 기각 사유*: 1GB RAM 단일 VM 환경에서 별도 Nginx 컨테이너 구동 시 프로세스 메모리 부담 발생(FinOps 0원 제약). 또한 HTTP Method(POST/PUT/DELETE) 판별 및 백엔드 화이트리스트(`ALLOWED_ORIGINS`) 설정과 결합된 CSRF 검증은 프록시 룰만으로 완결하기 어려움.
   - **아키텍처 대안 종합 비교**:
     | 비교 항목 | 3중 `@app.middleware` (기존) | 대안 A: 단일 `BaseHTTPMiddleware` | 대안 B: FastAPI `Depends` | 대안 C: L7 프록시 오프로딩 | 선택: 단일 Pure ASGI (`SecurityMiddleware`) |
     |---|---|---|---|---|---|
     | **상태 유실 방지** | 취약 (유실 발생) | 해결 (`env.globals`) | 완벽 해결 | 비해당 | **완벽 해결 (`scope['state']`)** |
     | **HSTS 로컬 예외** | 미구현 (Lockout) | 가능 (`request.url`) | 불가 (헤더 제어 불가) | 해결 (프로덕션만 적용) | **원자적 분기 처리 완료** |
     | **응답 헤더 주입** | 3중 중복 래핑 | 가능 | 불가 (별도 미들웨어 필요) | 완벽 처리 | **`send_wrapper` 단일 일괄 주입** |
     | **스트리밍/태스크 버그** | 잠재 위험 높음 | 잠재 위험 상존 (Starlette 결함) | 위험 없음 | 위험 없음 | **위험 제로 (순수 함수 체인)** |
     | **리소스 오버헤드** | 높음 (3단 중첩) | 중간 (1단 제너레이터) | 최저 | 최저 (앱 부하 제로) | **최저 (나노초 바이트 조작)** |

3. **Rate Limiter: `slowapi` 채택 및 `key_func` 커스텀 연동 (`src/web/limiter.py`)**
   - 엔드포인트별 Rate Limiting 엔진으로 검증된 **`slowapi`**를 그대로 채택함.
   - 단, slowapi의 기본 `get_remote_address`는 L4 TCP 소켓 IP만 보므로, Cloudflare 프록시 뒤에서 모든 사용자가 동일한 Cloudflare 엣지 IP 1개로 집계되어 30회 초과 시 무고한 사용자가 429에 걸리는 DoS(오탐 피해율 70%)가 발생함.
   - 이에 `limiter = Limiter(key_func=get_real_ip)`로 `cf-connecting-ip` 우선 추출 함수를 주입하여 해결함.

4. **CSR(Vanilla JS DOM 조작) vs SSR(FastAPI Jinja2 Templates)**
   - **선택**: Jinja2 기반 Server-Side Rendering (SSR)
   - **기회비용/한계**: 페이지 전환 시 전체 HTML 문서를 재전송받아 초기 네트워크 페이로드가 미세하게 증가하며, 서버 CPU가 템플릿 렌더링 연산을 직접 부담함.
   - **채택 근거**: 클라이언트 사이드 `innerHTML` 방식은 유저 입력 데이터 파싱 과정에서 XSS 취약점에 상시 노출되어 별도의 무거운 클라이언트 새니타이저 라이브러리(DOMPurify) 의존성이 요구됨. 위키/대시보드 특성상 검색엔진 최적화(SEO) 및 즉각적인 초기 로딩이 중요했고, Jinja2의 기본 Auto-escape를 활용하여 런타임 의존성 추가 없이 서버 레벨에서 100% 무결한 XSS 방어선을 확보함.

### 4) 도커 컴포즈 기반 실증 계측 결과
- **정량 실증 보고서 전문**: [`portfolio/benchmarks/PART3_WEB_SECURITY.md`](file:///c:/work/rpg_sync_project/portfolio/benchmarks/PART3_WEB_SECURITY.md)
- **실행 스크립트**: `tests/benchmark_web_security.py` (Docker Compose `rpg-api-dev`, `rpg-redis-dev` 실측)
- **실측 요약**:
  - 실제 구동 중인 Docker Compose API 컨테이너(`rpg-api-dev`)와 Redis 컨테이너(`rpg-redis-dev`)로 실제 HTTP 트래픽을 인입하여 계측함.
  - **Pure ASGI 미들웨어 보안 헤더 및 CSRF 경계 방어**:
    - 정상 Origin(`localhost:8000`)은 통과(HTTP 405 라우터 진입)하는 반면, 접미사 변조(`localhost:8000.attacker.com`) 및 외부 피싱 도메인은 HTTP 403 Forbidden으로 100% 즉각 차단 실증.
    - `host == "localhost"` 요청 시 브라우저 락아웃을 방지하기 위해 `Strict-Transport-Security` 헤더가 응답에서 안전하게 제외됨을 실측.
    - `X-Frame-Options: DENY`, `CSP`, `X-Content-Type-Options: nosniff` 등 보안 헤더 6종 전역 주입 완료.
  - **Cloudflare IP 파싱 기반 Rate Limiting (GET /tips - 30/분 한도)**:
    - 단일 IP 35회 연속 호출 시 30회 정상(200) 후 31회차부터 5회 전건 429 Too Many Requests로 완벽 차단.
    - 서로 다른 10개 IP 유저(`cf-connecting-ip`)의 50회 분산 요청에 대해 동일 소켓 IP임에도 오탐 차단율 0.0%(50회 전건 200 OK)로 유저별 쿼터 격리 실증.
  - **Docker API 컨테이너 렌더링 성능**:
    - 100회 요청 동시성 10 워커 기준 평균 레이턴시 **18.59 ms** (p95 **30.47 ms** / 최대 **37.03 ms**), 처리량 **495.74 RPS** 달성.
  - 상세 테스트베드 사양, 재현 명령어, `docker stats` 메트릭 덤프는 [실증 보고서](file:///c:/work/rpg_sync_project/portfolio/benchmarks/PART3_WEB_SECURITY.md) 전문 참조.

### 5) 면접관 Red Teaming 압박 질문 & 1분 방어 스크립트

#### Q1. "Cloudflare `cf-connecting-ip` 헤더만 파싱하면, 공격자가 오리진 서버의 공인 IP를 직접 알아내어 임의의 IP로 조작한 `cf-connecting-ip` 헤더를 쏘면 Rate Limiting을 완전히 우회할 수 있지 않나요? 애플리케이션 레벨 헤더 파싱만으로 IP 스푸핑을 완벽히 방어했다고 볼 수 있습니까?"
- **1분 구술 방어 (주니어 실전형 트러블슈터 관점)**:
  - "맞습니다. 애플리케이션 레벨에서 `cf-connecting-ip`를 읽는 것만으로는 오리진 직접 타격 시 IP 스푸핑을 막을 수 없습니다.
  - 따라서 실운영에서는 **인프라 방화벽과 L7 프록시의 신뢰 체인을 결합**했습니다. GCP VPC 방화벽 인바운드 룰에서 **Cloudflare 공식 공인 IP 대역(CIDR)만 80/443 포트로 접근을 허용**하고, 공격자가 오리진 공인 IP로 직접 쏘는 트래픽은 L4 커널 레벨에서 즉각 DROP시켰습니다.
  - 또한 Cloudflare 프록시 엣지 노드는 클라이언트가 임의로 조작해 보낸 가짜 `cf-connecting-ip` 헤더를 실제 TCP 소켓 IP로 강제 덮어쓰기(Overwrite)하므로, 오리진에 도달하는 헤더는 100% 신뢰할 수 있게 됩니다.
  - 즉, 앱 레벨에서는 `slowapi`가 Cloudflare 엣지 IP로 모든 유저를 묶지 않도록 실제 IP를 정확히 분발하고, 네트워크 레벨에서는 GCP 방화벽으로 오리진을 은닉하는 2중 방어선으로 문제를 해결했습니다."

#### Q2. "초기에는 FastAPI의 `@app.middleware("http")`를 썼다가 커밋 `b68a434`에서 굳이 순수 ASGI 인터페이스(`async def __call__(scope, receive, send)`)로 `SecurityMiddleware`를 재작성한 진짜 이유가 무엇입니까? 다른 대안은 없었습니까?"
- **1분 구술 방어 (주니어 실전형 트러블슈터 관점)**:
  - "처음에는 저 역시 가장 익숙한 FastAPI의 `@app.middleware("http")` 데코레이터로 전역 변수 주입, CSRF 차단, 보안 헤더 주입 등 3개의 미들웨어를 각각 만들어 등록했습니다.
  - 그런데 실제 로컬 테스트와 배포 과정에서 `request.state` 유실 버그, 로컬 `localhost:8000` HSTS 캐싱 락아웃, 3중 제너레이터 오버헤드라는 세 가지 런타임 결함에 직면했습니다.
  - 리팩토링 당시 두 가지 대안을 면밀히 검토했습니다.
  - 첫째는 **FastAPI의 `Depends` 의존성 주입**이었습니다. 상태 유실은 없지만 응답이 나갈 때 거쳐야 하는 HSTS나 X-Frame-Options 같은 보안 헤더를 주입할 수 없어 결국 별도 미들웨어를 유지해야 했습니다.
  - 둘째는 **단일 `BaseHTTPMiddleware`로 합치고 Jinja2 `env.globals`로 변수를 빼는 방식**이었습니다. 구현은 가장 쉬웠지만, Starlette `BaseHTTPMiddleware` 고유의 태스크 그룹 생성 버그(스트리밍 충돌 및 비정상 연결 해제 시 태스크 누수 이슈)가 여전히 남았습니다.
  - 1GB RAM e2-micro VM이라는 극단적 제약 속에서 외부 라이브러리의 불완전한 추상화에 기대기보다, 단 하나의 **Pure ASGI 인터페이스**로 통합하여 `scope["state"]` 직접 주입, 원자적 HSTS 로컬 분기, 나노초 단위 헤더 일괄 처리를 단 50줄로 명쾌하게 정리했습니다. 대안들의 기술적 한계를 비교 검토한 끝에 내린 가장 견고한 엔지니어링 결정이었습니다."

---

## 5. [파트 4] 비정형 텍스트의 정형화와 대량 동기화 파이프라인 (계층형 버퍼 파서 & 벌크 무결성)

### [세션 자동 실행 앵커 (Target Anchors)]
- **핵심 소스 경로**:
  - 계층형 버퍼 파서: [`src/bot/utils/text_parser.py:L8-L111`](file:///c:/work/rpg_sync_project/src/bot/utils/text_parser.py#L8-L111) (`parse_job_descriptions`, `_flush_job`, 인라인 브래킷 분리)
  - 가변 닉네임 동적 템플릿: [`src/bot/cogs/system/nickname_format_cmd.py:L68-L98`](file:///c:/work/rpg_sync_project/src/bot/cogs/system/nickname_format_cmd.py#L68-L98)
  - 2단계 직업 매칭 및 벌크 업서트: [`src/database/connection.py:L208-L258`](file:///c:/work/rpg_sync_project/src/database/connection.py#L208-L258)
- **검증 인프라 규격**: **Docker Compose 필수** (`rpg-db-dev` PostgreSQL 15 및 `rpg-redis-dev` 연동 실증)
- **테스트 스크립트**: `tests/benchmark_data_integrity.py`

### 1) 기술적 문제 및 원인 분석
1. **운영 워크플로우 보존과 비정형 마크다운의 정형화 한계**
   - 여든 개 이상의 직업 설명, 스킬 수치, 패치노트, 일러스트 데이터가 디스코드 채널 및 쓰레드에 분산되어 있었음.
   - 개발 관점에서는 정형화된 웹 어드민 입력 폼을 구축하는 것이 가장 직관적이고 안전하지만, 모든 기획 회의·유저 소통·밸런스 논의가 이미 디스코드 내부에서 완결되고 있었음.
   - 웹 어드민을 강제할 경우 관리자가 디스코드 논의 내용을 웹 폼으로 복사해야 하는 이중 작업과 플랫폼 전환 피로도가 발생하여 심각한 현장 저항이 예상됨.
   - 따라서 운영자의 기존 디스코드 작성 환경을 보존하되, 백엔드 파서로 데이터를 정형화하는 타협안을 채택함.
2. **단순 키워드 검색의 파탄과 서사 텍스트 간섭**
   - 초기 파서는 본문 텍스트 내 키워드(`영웅`, `빌런`) 단순 검색에 의존함.
   - 직업 서사 텍스트가 길어지면서 "과거에는 영웅이었으나 타락하여 빌런이 되었다"와 같은 문장에서 앞에 위치한 '영웅'을 먼저 감지해 빌런 캐릭터가 영웅 진영으로 오분류되는 치명적 결함 발생.
   - 단순 거대 정규식(Monolithic Regex)은 개행 수 불일치와 백트래킹 오버헤드로 인해 게이트 경계에서 직업 누락(벤치마크 기준 50% 누락) 발생.
   - 이를 해결하기 위해 거창한 컴파일러 상태 머신 대신, 마크다운 헤더(`##`, `###`)를 만날 때마다 이전 버퍼를 원자적으로 배출하는 **`_flush_job` 기반 계층형 컨텍스트 버퍼 파서**와 본문 간섭을 차단하는 **명시적 브래킷 문법(`[영웅]`, `<<조건문>>`)**을 운영진과 합의하여 도입함.
3. **가변 닉네임과 도메인 특수성(세계관 인명 축약)에 따른 동기화 충돌**
   - 디스코드 닉네임 수정 권한을 운영자로 통제했으나, 운영진 스스로가 합의된 규칙을 변형하는 휴먼 에러 빈번.
   - 신규 유저(닉네임/직업 2파트)부터 후원 이모지, 길드명(최대 5자), 스태프 식별자가 결합된 유저(최대 5파트)까지 구분자 개수와 위치가 유동적이라 하드코딩 파서가 무력화됨.
   - 직업명이 일반 RPG 클래스가 아닌 '스토리 속 주인공 고유 인명'으로 구성되어, 커뮤니티는 관습적으로 라스트 네임(5자 이내)만 축약 표기함.
   - 동일 가문명/성씨를 공유하는 캐릭터들이 다수 존재하여, 단순 부분 일치 적용 시 엉뚱한 캐릭터로 오매핑될 위험이 상존함.

---

### 2) 핵심 해결 코드 및 아키텍처
- **계층형 컨텍스트 버퍼 파서 ([`src/bot/utils/text_parser.py:L8-L111`](file:///c:/work/rpg_sync_project/src/bot/utils/text_parser.py#L8-L111))**:
  ```python
  def parse_job_descriptions(raw_text: str) -> List[Dict[str, Any]]:
      jobs_data = []
      current_gate = "정보 없음"
      current_group = "정보 없음"
      current_job_name = None
      current_desc_lines = []

      def _flush_job():
          nonlocal current_job_name, current_desc_lines
          if current_job_name:
              desc_str = "\n".join(current_desc_lines).strip()
              
              # 1. 메타데이터 브래킷 [] 기반 타입 식별 (서사 텍스트 내 키워드 오탐 차단)
              job_type = "정보 없음"
              bracket_matches = re.findall(r"\[(.*?)\]", desc_str)
              for bracket_text in bracket_matches:
                  if "영웅" in bracket_text: job_type = "영웅"; break
                  elif "빌런" in bracket_text: job_type = "빌런"; break

              # 2. 범용 캡슐화 태그 << >> 분리 (설명문 컬럼 오염 방지)
              req_condition = "정보 없음"
              cond_match = re.search(r"<<(.*?)>>", desc_str)
              if cond_match:
                  req_condition = cond_match.group(1).strip()
                  desc_str = desc_str.replace(cond_match.group(0), "").strip()

              is_limit = 'Y' if '1인 제한' in req_condition or '1인 제한' in desc_str else 'N'
              clean_job_id = re.sub(r"\s+", "", current_job_name)

              jobs_data.append({
                  "name": clean_job_id, "display_name": current_job_name.strip(),
                  "gate": current_gate, "job_group": current_group,
                  "description": desc_str, "job_type": job_type,
                  "is_limit": is_limit, "req_condition": req_condition
              })
              current_job_name = None
              current_desc_lines = []

      # 헤더 계층 기반 라인 버퍼 순회
      for line in raw_text.split('\n'):
          line = line.strip()
          if not line: continue
          if line.startswith("## "):
              _flush_job()
              # 게이트 및 그룹 헤더 파싱...
          elif line.startswith("### "):
              _flush_job()
              current_job_name = line[4:].strip()
          elif current_job_name:
              current_desc_lines.append(line)

      _flush_job()
      return jobs_data
  ```
- **가변 닉네임 동적 템플릿 ([`src/bot/cogs/system/nickname_format_cmd.py:L68-L98`](file:///c:/work/rpg_sync_project/src/bot/cogs/system/nickname_format_cmd.py#L68-L98))**:
  - 관리자가 `/닉네임양식설정` 슬래시 커맨드로 파트 수, 구분자, 인덱스를 동적으로 등록.
  - `system_configs` JSONB 컬럼에 영속화하고 봇 프로세스 메모리(`bot.nickname_formats`)에 전역 캐싱하여 매 파싱마다 DB 호출을 배제.
- **2단계 직업 매칭 및 사전 검증 벌크 업서트 ([`src/database/connection.py:L208-L258`](file:///c:/work/rpg_sync_project/src/database/connection.py#L208-L258))**:
  ```python
  # 1. 메모리 캐싱용 직업 리스트 생성 (DB 반복 I/O 병목 원천 차단)
  cursor.execute("SELECT job_id, LOWER(REPLACE(name, ' ', '')), LOWER(REPLACE(display_name, ' ', '')) FROM jobs")
  cached_jobs = [{"id": row[0], "name": row[1] or "", "display": row[2] or ""} for row in cursor.fetchall()]

  valid_users = []
  for user in users_data:
      job_name = user.pop('job_name', None)
      matched_job_id = None
      is_collision = False

      if job_name:
          # 2단계 매칭: 1차 완전 일치 우선 탐색
          exact_match = next((j["id"] for j in cached_jobs if job_name == j["name"] or job_name == j["display"]), None)
          if exact_match:
              matched_job_id = exact_match
          else:
              # 2차 부분 일치 탐색 (라스트 네임 축약 대응)
              partial_matches = [j for j in cached_jobs if job_name in j["name"] or job_name in j["display"]]
              if len(partial_matches) >= 2:
                  # 동일 가문명 충돌 시 안전 탈락 처리 및 옵저버빌리티 리포트
                  candidate_names = ", ".join(j["display"] for j in partial_matches)
                  failed_users.append({
                      "discord_id": user["discord_id"],
                      "nickname": user["nickname"],
                      "reason": f"직업 중복 매칭 (후보군: {candidate_names})"
                  })
                  is_collision = True
              elif len(partial_matches) == 1:
                  matched_job_id = partial_matches[0]["id"]

      if not is_collision:
          user['current_job_id'] = matched_job_id
          valid_users.append(user)

  # 검증된 레코드만 원자적 일괄 업서트
  if valid_users:
      upsert_sql = """
          INSERT INTO USERS (DISCORD_ID, NICKNAME, SERVER_ROLE, CURRENT_JOB_ID)
          VALUES (%(discord_id)s, %(nickname)s, %(server_role)s, %(current_job_id)s)
          ON CONFLICT (DISCORD_ID) DO UPDATE SET
              NICKNAME = EXCLUDED.NICKNAME,
              SERVER_ROLE = EXCLUDED.SERVER_ROLE,
              CURRENT_JOB_ID = EXCLUDED.CURRENT_JOB_ID
      """
      cursor.executemany(upsert_sql, valid_users)
  ```

---

### 3) 설계 트레이드오프 및 실무적 타협
1. **웹 어드민 폼 강제 vs 디스코드 텍스트 파서 수용 (운영 저항 타협)**
   - **기회비용**: 웹 폼 대비 정규화되지 않은 텍스트 파싱 로직 및 예외 처리 비용 수반.
   - **타협 근거**: 기획·소통·운영이 디스코드 채널 안에서 완결되는 커뮤니티 특성상, 웹 어드민 도입은 이중 작업과 피로를 유발해 현장 정착 실패로 이어짐. 운영자의 기존 동선을 보존하되 최소한의 규칙(`[ ]`, `<< >>`)을 가이드라인으로 배포하여 코드와 프로세스가 상호 보완하도록 설계.
2. **무거운 AST 라이브러리 vs 표준 라이브러리 기반 경량 버퍼 파서**
   - **선택**: 외부 AST 의존성을 배제한 순수 파이썬 라인 순회 버퍼 파서(`_flush_job`)
   - **타협 근거**: 클라우드 프리티어 1GB RAM VM 환경에서 메모리 오버헤드를 유발하는 외부 마크다운 AST 라이브러리를 배제하고, 마크다운 헤더 구조에 특화된 경량 단일 루프로 $O(N)$ 선형 시간 복잡도와 낮은 메모리 점유율을 달성.
3. **직업 매칭 시 부분 일치 전면 허용 vs 충돌 시 탈락 및 옵저버빌리티 리포트**
   - **선택**: 2개 이상 후보 검출 시 즉시 동기화 제외 및 스태프 채널 리포트
   - **타협 근거**: 관습적 라스트 네임 축약을 수용하면서도, 동일 가문명 인물이 엉뚱한 캐릭터로 오매핑되는 치명적 데이터 오염을 방지. 실패한 계정과 후보군 목록을 스태프 채널로 즉시 리포팅(최대 15명)하여 조용한 누락 없이 관리자가 수동 보정할 수 있게 함.

---

### 4) 도커 컴포즈 기반 실증 계측 결과
- **정량 실증 보고서 전문**: [`portfolio/benchmarks/PART4_DATA_INTEGRITY_AND_PARSER.md`](file:///c:/work/rpg_sync_project/portfolio/benchmarks/PART4_DATA_INTEGRITY_AND_PARSER.md)
- **실행 스크립트**: `tests/benchmark_data_integrity.py` (Docker Compose `rpg-db-dev`, `rpg-redis-dev` 실측)
- **실측 요약**:
  - 실제 구동 중인 Docker PostgreSQL 15 컨테이너(`rpg-db-dev`)를 대상으로 계층형 버퍼 파서 적재 및 벌크 동기화 파이프라인의 무결성을 계측함.
  - **디스코드 비정규 마크다운 파싱 및 PostgreSQL jobs 테이블 실적재**:
    - Naive Regex 파싱의 50.0% 직업 누락 및 본문 오염을 방어하여 4개 직업 100% 완전 복원 및 `[빌런]`, `<<조건문>>` 메타데이터 분리 달성.
    - PostgreSQL 15 `jobs` 테이블 일괄 UPSERT(100회 커밋) 시 평균 **3.86 ms/배치** (처리량 **258.77 배치 RPS**) 실측.
  - **가변 닉네임 동적 템플릿과 system_configs JSONB 영속화**:
    - `system_configs` 테이블에 3개 포맷 JSONB 저장 및 로드 후 5,000회 파싱 검증 결과, 스태프 권한(STF/OWN/🌈) 탐지율 100.0% 및 평균 레이턴시 **4.80 us/op** 달성.
  - **2단계 직업 매칭 및 대량 벌크 동기화 (유저 40명 실측)**:
    - **Naive 방식 (매 유저 SELECT + 단순 부분 일치 + 단건 INSERT)**: 총 36.74 ms, DB 질의 80회, 동일 가문명 유저 10건 전건 오매핑(데이터 오염률 100.0%).
    - **프로젝트 적용 (사전 캐싱 1회 + 2단계 매칭 충돌 격리 + executemany 일괄 업서트 1회)**: 총 **14.23 ms** (-61.3% 단축), DB 질의 **2회** (-97.5% 질의 제거), 처리량 **2810.39 RPS** (+158.2% 향상).
    - 동일 가문명 충돌 유저 10명 전건 안전 탈락 및 스태프 채널 실시간 옵저버빌리티 리포트 발송 확인 (오매핑 0건, 무결성 100.0% 방어).
  - 상세 테스트베드 사양, 재현 명령어, `docker stats` 메트릭 덤프는 [실증 보고서](file:///c:/work/rpg_sync_project/portfolio/benchmarks/PART4_DATA_INTEGRITY_AND_PARSER.md) 전문 참조.

---

### 5) 면접관 Red Teaming 압박 질문 & 1분 방어 스크립트

#### Q1. "디스코드 텍스트를 파싱하는 복잡한 버퍼 파서를 만들 바에는, 관리자 전용 웹 어드민 폼을 만들어 정형 데이터를 직접 입력받는 게 엔지니어링 관점에서 훨씬 안전하지 않았습니까? 왜 굳이 비정형 텍스트 파싱이라는 불안정한 길을 택했습니까?"
- **1분 구술 방어 (주니어 실전형 트러블슈터 관점)**:
  - "엔지니어링의 순수한 기술적 관점만 본다면 웹 어드민 폼을 구축해 완벽히 검증된 JSON 데이터를 받는 것이 가장 결함 가능성이 낮고 직관적인 접근이 맞습니다.
  - 하지만 운영 현장의 현실은 완전히 달랐습니다. 기획 회의, 유저 소통, 직업 밸런스 패치 논의가 이미 100% 디스코드 채널 내부에서 이루어지고 있었습니다. 만약 웹 어드민을 분리했다면 운영진은 디스코드에서 논의를 마친 뒤 웹 폼에 똑같은 내용을 복사해서 다시 입력해야 하는 이중 작업과 플랫폼 전환 피로를 겪어야 했고, 이는 필연적으로 현장의 거센 반발과 데이터 갱신 지연으로 이어질 상황이었습니다.
  - 따라서 엔지니어링 편의를 사용자에게 강요하기보다, 운영진의 기존 업무 맥락을 온전히 보존하면서 비정형 텍스트를 백엔드에서 정형화하는 타협안을 택했습니다. 본문 서사와 메타데이터의 간섭을 막기 위해 `[영웅]`, `<<조건문>>`이라는 최소한의 브래킷 가이드라인만 운영진에게 배포하여 프로세스 차원에서 협의했고, 백엔드에서는 마크다운 헤더를 만날 때마다 버퍼를 비워내는 가벼운 계층형 버퍼 파서(`_flush_job`)로 1GB RAM 환경에서도 $O(N)$ 선형 순회로 안전하게 데이터를 정형화했습니다. 기술적 이상론보다 현장의 운영 마찰을 최소화한 실전적 엔지니어링 결정이었습니다."

#### Q2. "유저 닉네임 대량 동기화(Bulk Sync) 시 직업명이 스토리 인명이라 라스트 네임 축약 표기를 2단계 부분 일치로 처리하셨는데, 동일 가문명을 가진 인물이 여럿 존재할 경우 엉뚱한 캐릭터로 덮어씌워질 위험을 어떻게 방어했습니까? 그리고 수십 명을 순회할 때 DB 부하는 어떻게 제어했습니까?"
- **1분 구술 방어 (주니어 실전형 트러블슈터 관점)**:
  - "이 프로젝트에서 직업명은 '전사', '마법사' 같은 일반 클래스가 아니라 세계관 서사 속 주인공들의 고유 인명이었고, 커뮤니티는 관습적으로 5자 이내의 라스트 네임만 축약 표기하고 있었습니다. 문제는 서양식/동양식 가문명이 겹치는 인물들이 다수 존재한다는 점이었습니다.
  - 만약 단순 부분 일치를 무비판적으로 적용했다면 동일 가문명을 가진 유저가 전혀 엉뚱한 캐릭터의 `job_id`로 매핑되는 심각한 데이터 오염이 발생할 수 있었습니다.
  - 이를 방어하기 위해 2단계 검증과 실패 격리 메커니즘을 설계했습니다. 유저 순회 전 단 1회의 쿼리로 전체 직업 목록을 메모리에 선캐싱하여 반복 질의에 따른 DB I/O 병목을 원천 차단했습니다. 그 후 1차 완전 일치를 우선 확인하고, 없을 경우에만 2차 부분 일치를 수행하되, 부분 일치 후보군이 2개 이상 검출되면 매핑을 즉시 포기하고 동기화 대상에서 안전하게 탈락시켰습니다.
  - 탈락된 유저는 조용히 누락되지 않도록 '직업 중복 매칭(후보군 목록)' 사유와 함께 스태프 관리 채널로 즉시 리포팅하여 관리자가 직접 닉네임을 보정할 수 있게 관제했습니다. 마지막으로 검증을 통과한 유저군만 선별하여 `executemany` 기반의 `ON CONFLICT DO UPDATE`로 원자적 일괄 업서트를 수행함으로써 데이터 무결성과 가용성을 모두 확보했습니다."

---

## 6. [파트 5] 크로스 플랫폼 분산 이벤트 브로커와 메시지 무결성 (Redis Pub/Sub & 멱등성)

### [세션 자동 실행 앵커 (Target Anchors)]
- **핵심 소스 경로**:
  - 수신 리스너: [`src/bot/main.py:L129-L185`](file:///c:/work/rpg_sync_project/src/bot/main.py#L129-L185) (`listen_to_redis`, `handle_onboarding_complete`, `sleep(0.01)`)
  - 송신 발행자: [`src/database/cache.py:L135-L149`](file:///c:/work/rpg_sync_project/src/database/cache.py#L135-L149) (`publish_message`), [`src/web/routers/auth.py:L30-L42`](file:///c:/work/rpg_sync_project/src/web/routers/auth.py#L30-L42)
  - 2차 상태 검증(멱등성): [`src/database/auth.py:L94-L126`](file:///c:/work/rpg_sync_project/src/database/auth.py#L94-L126) (`is_guide_completed`, `update_guide_completion`)
- **관련 Git 커밋 해시**: `c6cc131` (Redis Pub/Sub 도입 및 마인크래프트-디스코드 실시간 이벤트 연동)
- **검증 인프라 규격**: **Docker Compose 필수** (`rpg-redis-dev`, `rpg-db-dev`, `rpg-api-dev` 실측)
- **테스트 스크립트**: `tests/benchmark_pubsub.py`

### 1) 기술적 문제 및 원인 분석
1. **Redis Pub/Sub의 본질적 한계: Fire-and-Forget (At-most-once Delivery)과 영속성 결여**
   - Redis Pub/Sub은 인메모리 채널 브로드캐스팅 방식으로 메시지를 보관하는 큐(Queue)나 오프셋(Offset)이 없음.
   - 발행 시점에 구독자(Subscriber) 소켓이 열려있지 않거나 일시적 네트워크 순단으로 재연결 대기 중이면 메시지는 아무런 흔적 없이 영구 소멸(Silent Loss)됨.
2. **이종 플랫폼(FastAPI Web - Discord Bot - Minecraft) 간 네트워크 파티션과 상태 불일치**
   - 웹 브라우저에서 신규 유저가 가이드 서약을 완료하면 FastAPI가 `onboarding:complete` 이벤트를 발행하고, 디스코드 봇은 이를 수신하여 '뉴비' 역할을 회수하고 '멤버' 역할을 부여함.
   - 봇 배포 중이거나 게이트웨이 재연결 중일 때 발생한 이벤트는 봇에 도달하지 못해, 웹에서는 "인증 완료"이나 디스코드에서는 여전히 "뉴비"로 방치되는 분산 상태 불일치가 유발됨.
3. **TOCTOU(Time-of-Check to Time-of-Use) 레이스 컨디션과 중복 이벤트 폭주**
   - 사용자 더블 클릭이나 네트워크 재시도로 동일 완료 요청이 동시 인입될 때, 애플리케이션 레벨의 단순 `SELECT` 후 `UPDATE` 패턴은 두 요청 모두 미완료 상태로 읽어 중복 UPDATE 및 중복 Redis 이벤트를 발생시킴.
   - 이로 인해 디스코드 API에 중복 역할 변경 및 스레드 삭제 요청이 폭주하여 `429 Too Many Requests` 레이트리밋과 404 Unknown Member 예외를 유발함.

### 2) 핵심 해결 코드 및 아키텍처
- **자가 치유 Redis Pub/Sub 리스너 및 비동기 태스크 디스패치 ([`src/bot/main.py:L129-L178`](file:///c:/work/rpg_sync_project/src/bot/main.py#L129-L178))**:
  ```python
  async def listen_to_redis(self):
      while True:
          try:
              if not cache.redis_client:
                  await asyncio.sleep(1)
                  continue

              pubsub = cache.redis_client.pubsub()
              async with pubsub as ps:
                  await ps.subscribe("onboarding:complete", "rpgsync:reason_submitted")
                  while True:
                      message = await ps.get_message(ignore_subscribe_messages=True, timeout=10.0)
                      if message:
                          channel = message.get("channel")
                          data_str = message.get("data")
                          if channel == "onboarding:complete":
                              data = json.loads(data_str)
                              # 1. 메인 리스너 루프 블로킹 방지를 위한 비동기 태스크 즉각 분기
                              asyncio.create_task(self.handle_onboarding_complete(data))
                      # 2. CPU 과점 방지 및 이벤트 루프 협력적 양보
                      await asyncio.sleep(0.01)
          except Exception as e:
              # 3. 소켓 단절 시 5초 백오프 후 무한 자가 치유 재연결
              print(f"[REDIS] Listener error: {e}. Reconnecting in 5s...", flush=True)
              await asyncio.sleep(5)
  ```
- **2단계 방어선: PostgreSQL DB 선영속화 + 원자적 조건부 갱신 (Compare-and-Set)**:
  ```python
  # 1. DB 레벨 원자적 조건부 갱신 (TOCTOU 레이스 컨디션 차단)
  sql = """
      UPDATE public.users 
      SET is_guide_completed = true 
      WHERE discord_id = %s AND is_guide_completed = false;
  """
  cursor.execute(sql, (discord_id,))
  # rowcount == 1인 최초 요청만 Redis 발행 트리거
  if cursor.rowcount > 0:
      await publish_message("onboarding:complete", {"discord_id": discord_id})
  ```
  - Redis Pub/Sub은 1.42ms급 초저지연 실시간 시그널링 용도로만 사용하고, 시스템 원천 진실(Single Source of Truth)은 PostgreSQL 트랜잭션이 전담.
  - 봇 재기동 시 단 1회의 대사 쿼리(`WHERE is_guide_completed = true AND server_role = 'NEWBIE'`)로 미반영 유저를 100% 자동 검출하여 원자적 일괄 대사(Reconciliation) 완결.

### 3) 설계 트레이드오프 및 아키텍처 대안 분석
- **Redis Pub/Sub vs Redis Streams vs RabbitMQ/Kafka**:
  | 비교 항목 | Redis Pub/Sub + DB 대사 (채택) | Redis Streams (`XADD`/`XREADGROUP`) | RabbitMQ / Kafka |
  |---|---|---|---|
  | **메시지 영속성** | 없음 (DB가 영속성 보완) | 인메모리 로그 영속화 | 디스크/분산 로그 영속화 |
  | **전달 보장 수준** | At-most-once (실시간) + 대사 복구 | At-least-once (ACK 기반) | At-least-once / Exactly-once |
  | **추가 메모리 비용** | **0 MB (기존 프로세스 재활용)** | 미소비 메시지 누적 시 수십 MB 증가 | 수백 MB ~ 수 GB (OOM 크래시) |
  | **구현 복잡도** | **최저 (단 50줄 구현)** | 중간 (XACK, Pending List 관리 필요) | 최고 (별도 클러스터/브로커 관리) |
  | **1GB VM 적합도** | **최적 (FinOps 0원 유지)** | 주의 (LRU 방출 충돌 위험) | **부적합 (즉시 메모리 고갈)** |
- **채택 근거**:
  - 1GB RAM 단일 VM 환경에서 추가 메시지 브로커 데몬 구동은 즉각적인 OOM 크래시를 초래함.
  - Redis Streams 역시 미처리 메시지 누적 시 인메모리 용량을 점유하여 Redis 50MB 상한에 위협이 됨.
  - 이에 따라 **'Redis Pub/Sub은 실시간 트리거로만 쓰고, 영속화와 복구는 기존 PostgreSQL의 인덱스 대사 쿼리로 해결'**하는 2계층 구조를 택해 추가 리소스 소모 0으로 시스템 무결성을 달성함.

### 4) 도커 컴포즈 기반 실증 계측 결과
- **정량 실증 보고서 전문**: [`portfolio/benchmarks/PART5_DISTRIBUTED_PUBSUB.md`](file:///c:/work/rpg_sync_project/portfolio/benchmarks/PART5_DISTRIBUTED_PUBSUB.md)
- **실행 스크립트**: `tests/benchmark_pubsub.py` (Docker Compose `rpg-redis-dev`, `rpg-db-dev`, `rpg-api-dev` 실측)
- **실측 요약**:
  - 실제 구동 중인 Docker Redis 7과 PostgreSQL 15 컨테이너를 대상으로 실시간 발행/수신, 봇 다운 시 유실 복구, 멱등성 방어 계측.
  - **Redis Pub/Sub 실시간 디스패치 성능 (50회 연속 발행)**:
    - 수신 성공률 **100.0%** (50/50건), 평균 레이턴시 **1.42 ms** (p95 **3.28 ms** / 최대 **9.84 ms**), 처리량 **61.62 RPS** 달성.
  - **봇 오프라인 단절 시 메시지 유실 및 DB 상태 대사 (20건 실측)**:
    - **Naive 방식 (Redis Pub/Sub 단일 의존)**: 20건 전량 수신 실패 (**메시지 유실률 100.0%**, 영구 상태 불일치 발생).
    - **Hardened 방식 (PostgreSQL 선영속화 + 대사)**: DB에 20건 전원 선영속화 완료. 봇 재기동 시 단 **23.58 ms** 만에 미반영 유저 20건 100.0% 검출 및 일괄 복구 완료 (복구율 **100.0%**).
  - **동일 유저 동시 요청 폭주 멱등성 방어 (동시 20건 경합)**:
    - **Naive 방식 (SELECT 후 UPDATE)**: TOCTOU 레이스 컨디션으로 20건 전건 중복 실행 (**결함률 95.0%**, 평균 77.24 ms).
    - **Hardened 방식 (원자적 조건부 UPDATE)**: 단 1건만 성공(rowcount=1), 19건 즉시 차단 (**결함률 0.0%**, 무결성 100% 방어, 평균 **38.65 ms**, -50.0% 단축).
  - 상세 테스트베드 사양, 재현 명령어, `docker stats` 메트릭 덤프는 [실증 보고서](file:///c:/work/rpg_sync_project/portfolio/benchmarks/PART5_DISTRIBUTED_PUBSUB.md) 전문 참조.

### 5) 면접관 Red Teaming 압박 질문 & 1분 방어 스크립트

#### Q1. "Redis Pub/Sub은 At-most-once Delivery 특성상 메시지 영속성이 없어, 봇이 재부팅 중일 때 웹에서 들어온 온보딩 완료 이벤트는 그대로 유실(Silent Loss)됩니다. 왜 Redis Streams나 RabbitMQ 같은 영속적 메시지 큐를 쓰지 않았습니까?"
- **1분 구술 방어 (주니어 실전형 트러블슈터 관점)**:
  - "기술적으로 메시지 무손실을 보장하기 위해 Redis Streams나 RabbitMQ 같은 큐 시스템을 도입하는 것이 정석이라는 점에 깊이 공감합니다.
  - 하지만 제가 배포해야 했던 환경은 **GCP Free Tier 1GB RAM VM(FinOps 0원)** 단일 노드였습니다. 별도 큐 브로커를 올리는 것은 즉각적인 OOM 크래시를 유발했고, Redis Streams 역시 미소비 메시지가 누적되면 Redis에 설정된 50MB 메모리 상한을 위협하는 구조적 한계가 있었습니다.
  - 따라서 저는 **'Redis Pub/Sub은 1.42ms급 실시간 트리거로만 사용하고, 영속성과 원천 진실(Single Source of Truth)은 PostgreSQL 트랜잭션이 전담'**하는 2계층 하이브리드 아키텍처를 선택했습니다. 웹에서 먼저 DB의 `is_guide_completed`를 영속화한 뒤에만 이벤트를 발행하도록 설계했습니다.
  - 실제 도커 환경에서 봇 오프라인 상태로 20건의 이벤트를 발생시킨 결과, 단순 Pub/Sub은 100% 유실되었지만 제 아키텍처에서는 봇 재기동 시 단 23.58ms의 단일 대사(Reconciliation) 쿼리로 20건 전원을 완벽히 100% 복구해냈습니다. 무거운 인프라를 무비판적으로 늘리지 않고, DB 원천 진실을 통해 자원 한계 속에서 무결성을 완벽히 방어한 실전적 트러블슈팅이었습니다."

#### Q2. "웹 라우터에서 `is_guide_completed`를 확인하고 업데이트하는 방식은 사용자가 광클하거나 네트워크 재시도로 동시 다중 요청이 몰릴 때 TOCTOU 레이스 컨디션이 발생합니다. 분산 락 없이 이 동시성 문제를 어떻게 해결했습니까?"
- **1분 구술 방어 (주니어 실전형 트러블슈터 관점)**:
  - "정확한 지적이십니다. 애플리케이션 레벨에서 단순히 `if is_guide_completed:`를 검사한 뒤 `UPDATE`를 실행하는 구조는 동시 요청이 몰릴 때 모든 코루틴이 False를 읽어버리는 전형적인 TOCTOU 레이스 컨디션을 유발합니다. 실제로 20건 동시 요청 실측 시 19건의 중복 실행(결함률 95%)이 관측되었습니다.
  - 이를 해결하기 위해 무거운 분산 락 대신, DB 레벨의 **원자적 조건부 갱신(Compare-and-Set)** 패턴인 `UPDATE users SET is_guide_completed = true WHERE discord_id = %s AND is_guide_completed = false`를 적용했습니다.
  - RDBMS의 행 레벨 배타 락 덕분에 20개 요청이 동시에 몰려도 데이터베이스 엔진 수준에서 단 1건의 트랜잭션만 `rowcount = 1`을 반환하고, 나머지 19건은 영향 행 0건으로 즉각 탈락합니다. 그리고 `rowcount == 1`을 획득한 단 한 번의 호출만 Redis Pub/Sub 발행을 트리거하므로, 디스코드 API로의 중복 요청 폭주를 결함률 0.0%로 원천 차단하고 응답 지연시간도 77.24ms에서 38.65ms로 절반 단축했습니다. 복잡한 외부 의존성 없이 DBMS 엔진의 원자성을 100% 활용한 가장 간결하고 견고한 방어선이었습니다."

---

## 7. [파트 6] Passwordless 매직 링크와 단 1회 소비(Consume-on-verify) 보안 세션

### [세션 자동 실행 앵커 (Target Anchors)]
- **핵심 소스 경로**:
  - 토큰 발급 & 1회성 소비 DB 트랜잭션: [`src/database/auth.py:L20-L75`](file:///c:/work/rpg_sync_project/src/database/auth.py#L20-L75) (`create_magic_token`, `verify_and_consume_magic_token`)
  - 웹 인증 및 세션 쿠키 발급: [`src/web/routers/auth.py:L49-L120`](file:///c:/work/rpg_sync_project/src/web/routers/auth.py#L49-L120) (`auto_login_form`, `authenticate_token`)
  - 디스코드 인앱 발급 커맨드: [`src/bot/cogs/auth/auth_cmd.py`](file:///c:/work/rpg_sync_project/src/bot/cogs/auth/auth_cmd.py)
- **관련 Git 커밋 해시**: `6afe4bc` (Passwordless 매직 링크 및 JWT 세션 도입), `c05a260` (토큰 1회 소비 원자성 강화)
- **검증 인프라 규격**: **Docker Compose 필수** (PostgreSQL 트랜잭션 및 Redis 캐시 연동 실증)
- **테스트 스크립트**: `tests/benchmark_magic_token.py`

### 1) 기술적 문제 및 원인 분석 (진행 대기)
<!-- 세션 실행 시 자동 작성: ID/PW 가입 UX 이탈, Discord OAuth2의 복잡한 Redirect/외부 의존성, 매직 링크 탈취 및 재전송 공격(Replay Attack)과 동시 요청 경쟁 상태(Race Condition) -->

### 2) 핵심 해결 코드 및 아키텍처 (진행 대기)
<!-- 세션 실행 시 자동 작성: secrets.token_urlsafe(32) 엔트로피, 5분 만료 TTL, SELECT와 DELETE를 단일 DB 트랜잭션으로 원자화, JWT HttpOnly/SameSite=Lax 쿠키 발급 및 RBAC 권한 분리 -->

### 3) 설계 트레이드오프 및 아키텍처 대안 분석 (진행 대기)
<!-- 세션 실행 시 자동 작성: Discord OAuth2 vs Magic Link vs Session DB, JWT 무상태 vs Stateful SessionStore 메모리 오버헤드 비교 -->

### 4) 인프라 실증 벤치마크 및 정량적 검증 결과 (진행 대기)
<!-- 세션 실행 시 자동 작성: 1개 매직 토큰에 대한 10~50건 동시 HTTP GET/POST 경합 시 중복 로그인 차단율(100%), 토큰 발급/검증 레이턴시 계측 -->

### 5) 면접관 Red Teaming 압박 질문 & 1분 방어 스크립트 (진행 대기)
<!-- 세션 실행 시 자동 작성: 1. OAuth2 대신 매직 링크를 썼을 때의 보안 취약점(링크 유출) 방어, 2. JWT 세션 무효화(블랙리스트) 부재에 대한 1분 방어 -->

---

## 8. [파트 7] 극단적 리소스 제약(1GB VM FinOps 0원) 컨테이너 거버넌스, 옵저버빌리티 및 백업 파이프라인

### [세션 자동 실행 앵커 (Target Anchors)]
- **핵심 소스 경로**:
  - 도커 오케스트레이션 및 메모리 상한: [`docker-compose.yml`](file:///c:/work/rpg_sync_project/docker-compose.yml), [`Dockerfile`](file:///c:/work/rpg_sync_project/Dockerfile)
  - Cloudflare R2 스토리지 & L7 바이트 시그니처 검증: [`src/bot/utils/s3_client.py:L7-L49`](file:///c:/work/rpg_sync_project/src/bot/utils/s3_client.py#L7-L49)
  - 정기 DB/이미지 아카이빙 파이프라인: [`db_backup.py:L29-L70`](file:///c:/work/rpg_sync_project/db_backup.py#L29-L70)
- **관련 Git 커밋 해시**: `e7c8c78` (컨테이너화 및 안정화), `35b7c9b` (R2 연동 및 마이그레이션), `fbafdbb` (단일 노드 리소스 최적화)
- **검증 인프라 규격**: **Docker Compose 필수** (`docker stats` 기반 Web+Bot+Redis 동시 구동 메모리 피크치 및 cgroups 제약 실측)
- **테스트 스크립트**: `tests/benchmark_container_governance.py`

### 1) 기술적 문제 및 원인 분석 (진행 대기)
<!-- 세션 실행 시 자동 작성: GCP e2-micro 1GB RAM 환경에서의 OOM Killer 연쇄 크래시, Docker HEALTHCHECK 부재에 따른 좀비 컨테이너 방치 위험, Cloudflare R2 Egress 0원 FinOps 선택, 확장자 위조(MIME Spoofing) 웹셸 공격 표면, Supabase Free Tier 7일 미사용 정지(Pause) 리스크 -->

### 2) 핵심 해결 코드 및 아키텍처 (진행 대기)
<!-- 세션 실행 시 자동 작성: Redis maxmemory 50mb volatile-lru, 호스트 OS 2GB Swap + vm.swappiness=10 거버넌스, python-magic(libmagic1) 파일 헤더 매직 바이트 검증, db_backup.py의 JSONB 정규화 및 R2 이미지 로컬 백업 파이프라인 -->

### 3) 설계 트레이드오프 및 아키텍처 대안 분석 (진행 대기)
<!-- 세션 실행 시 자동 작성: AWS S3 vs Cloudflare R2 FinOps 비용 분석, systemd 개별 데몬 vs Docker Compose cgroups 오버헤드, 모니터링 Prometheus/Grafana vs 경량 로그 로테이션 트레이드오프 -->

### 4) 인프라 실증 벤치마크 및 정량적 검증 결과 (진행 대기)
<!-- 세션 실행 시 자동 작성: docker stats 실시간 메모리 점유율 표(Web/Bot/Redis), Redis 50MB 초과 시 LRU 키 방출 동작 실측, magic byte 위조 파일 차단율 계측 -->

### 5) 면접관 Red Teaming 압박 질문 & 1분 방어 스크립트 (진행 대기)
<!-- 세션 실행 시 자동 작성: 1. 단일 노드 1GB VM에서 OOM 발생 시 단일 장애점(SPOF) 대응 방어, 2. 컨테이너 HEALTHCHECK와 프로메테우스 없이 프로덕션 가용성을 어떻게 보장했는지에 대한 1분 방어 -->

---
