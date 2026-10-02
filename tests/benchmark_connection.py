import os
import sys
import time
import random
import json
import re
import psycopg2
from psycopg2 import pool, OperationalError
import redis

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 로컬 도커 환경변수 강제 주입
os.environ["DATABASE_URL"] = "postgresql://dev_user:dev_password@localhost:5432/rpg_dev_db"
os.environ["REDIS_URL"] = "redis://:dev_redis_pw@localhost:6379/0"

from src.database.connection import db_retry

# ---------------------------------------------------------------------
# 1. 테스트베드 연결 풀 초기화
# ---------------------------------------------------------------------
DB_DSN = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]

db_pool = pool.ThreadedConnectionPool(
    2, 10,
    dsn=DB_DSN,
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=5
)

redis_client = redis.from_url(REDIS_URL, decode_responses=True)
JOB_NAMES = []

# ---------------------------------------------------------------------
# 2. data.js 원천 JSON 파싱 및 테스트베드 시딩
# ---------------------------------------------------------------------
def parse_jobs_from_data_js() -> list[dict]:
    """극초기 data.js에 하드코딩되었던 실제 직업 71종 데이터를 정규식으로 정밀 파싱"""
    data_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data.js"))
    with open(data_js_path, "r", encoding="utf-8") as f:
        text = f.read()

    jobs = []
    for line in text.splitlines():
        line = line.strip().lstrip('/').strip()
        if not line.startswith('{ name:'):
            continue
        name_m = re.search(r'name:\s*"([^"]+)"', line)
        if not name_m:
            continue
        name = name_m.group(1)
        gate = (re.search(r'gate:\s*"([^"]+)"', line) or [None, '정보 없음'])[1]
        group = (re.search(r'group:\s*"([^"]+)"', line) or [None, '일반'])[1]
        desc = (re.search(r'desc:\s*"([^"]+)"', line) or [None, ''])[1]
        range_t = (re.search(r'range:\s*"([^"]+)"', line) or [None, '정보 없음'])[1]
        pos = (re.search(r'position:\s*"([^"]+)"', line) or [None, '정보 없음'])[1]
        res = (re.search(r'resource:\s*"([^"]+)"', line) or [None, '정보 없음'])[1]
        is_limit = 'Y' if re.search(r'limit:\s*true', line) else 'N'

        jobs.append({
            'name': name,
            'display_name': name,
            'gate': gate,
            'job_group': group,
            'description': desc,
            'range_type': range_t,
            'position': pos,
            'resource_type': res,
            'is_limit': is_limit
        })
    return jobs

def setup_seed_data():
    global JOB_NAMES
    jobs = parse_jobs_from_data_js()
    JOB_NAMES = [j['name'] for j in jobs]
    print(f"[*] data.js 원천 데이터 파싱 완료: 총 {len(jobs)}개 실제 직업 로드")

    conn = db_pool.getconn()
    try:
        cur = conn.cursor()
        upsert_sql = """
            INSERT INTO JOBS (NAME, DISPLAY_NAME, GATE, JOB_GROUP, DESCRIPTION, RANGE_TYPE, POSITION, RESOURCE_TYPE, IS_LIMIT)
            VALUES (%(name)s, %(display_name)s, %(gate)s, %(job_group)s, %(description)s, %(range_type)s, %(position)s, %(resource_type)s, %(is_limit)s)
            ON CONFLICT (NAME) DO UPDATE SET
                DISPLAY_NAME = EXCLUDED.DISPLAY_NAME,
                GATE = EXCLUDED.GATE,
                JOB_GROUP = EXCLUDED.JOB_GROUP,
                DESCRIPTION = EXCLUDED.DESCRIPTION,
                RESOURCE_TYPE = EXCLUDED.RESOURCE_TYPE;
        """
        for job in jobs:
            cur.execute(upsert_sql, job)
        conn.commit()
        cur.close()
        print(f"[*] PostgreSQL rpg_dev_db: JOBS 테이블 {len(jobs)}건 시딩 완료")
    finally:
        db_pool.putconn(conn)

    # Redis 캐시 예열 (Fast-Path: 71개 전체 직업 JSON 캐싱)
    pipe = redis_client.pipeline()
    for job in jobs:
        pipe.set(f"rpgsync:job:{job['name']}", json.dumps(job, ensure_ascii=False))
    pipe.execute()
    print(f"[*] Redis rpg-redis-dev: Fast Path 직업 캐시 {len(jobs)}건 예열 완료")

# ---------------------------------------------------------------------
# 3. 실증 A: pg_terminate_backend를 통한 Stale Socket & 자가 치유 검증
# ---------------------------------------------------------------------
def test_stale_socket_self_healing():
    print("\n----------------------------------------------------------------")
    print(" [실증 1] pg_terminate_backend 소켓 강제 종료 및 자가 치유 실측")
    print("----------------------------------------------------------------")
    
    # 1. 작업 대상 커넥션 획득
    target_conn = db_pool.getconn()
    target_pid = target_conn.get_backend_pid()
    print(f"[*] 타겟 DB 커넥션 획득 성공 (Backend PID: {target_pid})")

    # 2. 별도 관리자 커넥션으로 대상 세션 강제 종료 (Supabase 세션 드랍 모사)
    admin_conn = psycopg2.connect(DB_DSN)
    admin_cur = admin_conn.cursor()
    admin_cur.execute(f"SELECT pg_terminate_backend({target_pid});")
    admin_conn.commit()
    admin_cur.close()
    admin_conn.close()
    print(f"[*] pg_terminate_backend({target_pid}) 실행 완료 (원격 소켓 강제 단절 주입)")

    # 3. 클라이언트 메모리 플래그 conn.closed 확인
    print(f"[!] 서버 측 세션 종료 직후 target_conn.closed 값: {target_conn.closed}")
    assert target_conn.closed == 0, "conn.closed는 소켓 강제 종료를 감지하지 못해야 합니다."
    print(" -> [실증 확인] conn.closed는 여전히 0 (정상으로 오인). 메모리 플래그의 한계 입증.")

    # 4. db_retry 데코레이터를 통한 자가 치유 실행
    @db_retry(max_retries=1)
    def execute_with_self_healing(conn_holder, job_name):
        cur = conn_holder[0].cursor()
        try:
            cur.execute("SELECT NAME, DISPLAY_NAME, GATE, JOB_GROUP FROM JOBS WHERE NAME = %s;", (job_name,))
            row = cur.fetchone()
            return row
        except (OperationalError, psycopg2.DatabaseError) as e:
            # Stale 소켓 폐기 및 새 커넥션 획득
            db_pool.putconn(conn_holder[0], close=True)
            conn_holder[0] = db_pool.getconn()
            raise e
        finally:
            cur.close()

    holder = [target_conn]
    start = time.time()
    try:
        sample_job = "다크 메이지"
        result = execute_with_self_healing(holder, sample_job)
        elapsed = (time.time() - start) * 1000
        print(f"[+] 자가 치유 완료! 1회 재연결 후 쿼리 성공: {result} (소요 시간: {elapsed:.2f}ms)")
        print(f" -> 새 커넥션 Backend PID: {holder[0].get_backend_pid()} (새 소켓으로 자동 교체됨)")
    finally:
        db_pool.putconn(holder[0])

# ---------------------------------------------------------------------
# 4. 실증 B: 대륙 간 지연(RTT 200ms) 환경 3대 전략 정량 계측 (data.js 랜덤 질의)
# ---------------------------------------------------------------------
RTT_LATENCY_SEC = 0.20  # GCP US ↔ Supabase KR 왕복 지연 (200ms)

def run_strategy_naive_select1(num_requests: int = 50):
    """전략 A (Naive): 매 요청마다 실제 SELECT 1 검증 후 실제 쿼리 실행 (RTT 2회 발생)"""
    latencies = []
    for _ in range(num_requests):
        target_name = random.choice(JOB_NAMES)
        start = time.time()
        # RTT 1회차: SELECT 1 사전 질의
        time.sleep(RTT_LATENCY_SEC)
        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.fetchone()

        # RTT 2회차: 실제 data.js 직업 쿼리 실행
        time.sleep(RTT_LATENCY_SEC)
        cur.execute("SELECT NAME, DISPLAY_NAME, GATE, JOB_GROUP FROM JOBS WHERE NAME = %s;", (target_name,))
        _ = cur.fetchone()
        cur.close()
        db_pool.putconn(conn)
        latencies.append((time.time() - start) * 1000)
    return latencies

def run_strategy_hardened_dbretry(num_requests: int = 50, stale_rate: float = 0.08):
    """전략 B (Hardened): 사전 검증 없이 실제 쿼리 즉시 실행 + Stale 발생 시 db_retry 복구"""
    latencies = []
    recovered_count = 0

    for _ in range(num_requests):
        target_name = random.choice(JOB_NAMES)
        start = time.time()
        conn = db_pool.getconn()
        
        # 8% 확률로 세션 강제 종료 주입
        if random.random() < stale_rate:
            admin_conn = psycopg2.connect(DB_DSN)
            ac = admin_conn.cursor()
            ac.execute(f"SELECT pg_terminate_backend({conn.get_backend_pid()});")
            admin_conn.commit()
            ac.close()
            admin_conn.close()

        # db_retry 로직
        max_retries = 1
        for attempt in range(max_retries + 1):
            time.sleep(RTT_LATENCY_SEC)  # 네트워크 RTT 1회
            try:
                cur = conn.cursor()
                cur.execute("SELECT NAME, DISPLAY_NAME, GATE, JOB_GROUP FROM JOBS WHERE NAME = %s;", (target_name,))
                _ = cur.fetchone()
                cur.close()
                db_pool.putconn(conn)
                break
            except (OperationalError, psycopg2.DatabaseError):
                db_pool.putconn(conn, close=True)
                recovered_count += 1
                if attempt == max_retries:
                    raise
                conn = db_pool.getconn()

        latencies.append((time.time() - start) * 1000)
    return latencies, recovered_count

def run_strategy_fastpath_cache(num_requests: int = 50, hit_rate: float = 0.85):
    """전략 C (Fast Path): Redis 캐시 적중 시 DB I/O 0회 바이패스 (data.js 71종 키 조회)"""
    latencies = []
    for _ in range(num_requests):
        target_name = random.choice(JOB_NAMES)
        start = time.time()
        if random.random() < hit_rate:
            # Redis 직접 조회 (로컬 도커 왕복 ~1ms)
            cached = redis_client.get(f"rpgsync:job:{target_name}")
            assert cached is not None
        else:
            # Cache Miss 시 실제 DB 조회 (RTT 200ms 소모)
            time.sleep(RTT_LATENCY_SEC)
            conn = db_pool.getconn()
            cur = conn.cursor()
            cur.execute("SELECT NAME, DISPLAY_NAME, GATE, JOB_GROUP FROM JOBS WHERE NAME = %s;", (target_name,))
            _ = cur.fetchone()
            cur.close()
            db_pool.putconn(conn)

        latencies.append((time.time() - start) * 1000)
    return latencies

# ---------------------------------------------------------------------
# 메인 실행 및 계측치 출력
# ---------------------------------------------------------------------
if __name__ == "__main__":
    print("================================================================")
    print(" [도커 컴포즈 기반] 파트 1: DB 커넥션 풀 및 캐싱 정량 실증 계측")
    print(" 대상: PostgreSQL (rpg-db-dev:5432) / Redis (rpg-redis-dev:6379)")
    print(" 데이터셋: data.js 하드코딩 원천 데이터셋 (71개 실제 직업)")
    print("================================================================")

    setup_seed_data()
    test_stale_socket_self_healing()

    NUM_SAMPLES = 40
    print(f"\n[*] 대륙 간 RTT 200ms 환경 실측 벤치마크 시작 (요청 수: {NUM_SAMPLES}회, 71종 직업 랜덤 질의)...")

    # 1. Naive (SELECT 1)
    t0 = time.time()
    lat_naive = run_strategy_naive_select1(NUM_SAMPLES)
    dur_naive = time.time() - t0
    rps_naive = NUM_SAMPLES / dur_naive

    # 2. Hardened (db_retry)
    t0 = time.time()
    lat_hardened, recovered = run_strategy_hardened_dbretry(NUM_SAMPLES, stale_rate=0.08)
    dur_hardened = time.time() - t0
    rps_hardened = NUM_SAMPLES / dur_hardened

    # 3. Fast-Path (Redis)
    t0 = time.time()
    lat_cache = run_strategy_fastpath_cache(NUM_SAMPLES, hit_rate=0.85)
    dur_cache = time.time() - t0
    rps_cache = NUM_SAMPLES / dur_cache

    def calc_metrics(lats):
        s = sorted(lats)
        mean = sum(s) / len(s)
        p95 = s[int(len(s) * 0.95)]
        max_lat = max(s)
        return mean, p95, max_lat

    m_naive = calc_metrics(lat_naive)
    m_hardened = calc_metrics(lat_hardened)
    m_cache = calc_metrics(lat_cache)

    print("\n================================================================")
    print("           정량적 실측 결과 (최종 집계: data.js 71종 실데이터셋)   ")
    print("================================================================")
    print(f"1. 최적화 전 (Naive: 매번 SELECT 1):")
    print(f"   - 평균: {m_naive[0]:.2f} ms | p95: {m_naive[1]:.2f} ms | 최대: {m_naive[2]:.2f} ms | 처리량: {rps_naive:.2f} RPS")
    print(f"2. 프로젝트 적용 (Hardened: db_retry 자가 치유):")
    print(f"   - 평균: {m_hardened[0]:.2f} ms | p95: {m_hardened[1]:.2f} ms | 최대: {m_hardened[2]:.2f} ms | 처리량: {rps_hardened:.2f} RPS")
    print(f"   - 단절 주입 및 자가 치유 성공 횟수: {recovered}회 (성공률 100%)")
    print(f"   - Naive 대비 평균 레이턴시 단축율: -{((m_naive[0] - m_hardened[0]) / m_naive[0]) * 100:.1f}%")
    print(f"   - 처리량(Throughput) 향상율: +{((rps_hardened - rps_naive) / rps_naive) * 100:.1f}%")
    print(f"3. Fast Path 결합 (Redis 캐싱 85% 적중):")
    print(f"   - 평균: {m_cache[0]:.2f} ms | p95: {m_cache[1]:.2f} ms | 최대: {m_cache[2]:.2f} ms | 처리량: {rps_cache:.2f} RPS")
    print(f"   - Naive 대비 평균 레이턴시 단축율: -{((m_naive[0] - m_cache[0]) / m_naive[0]) * 100:.1f}%")
    print("================================================================")

    db_pool.closeall()
    redis_client.close()
