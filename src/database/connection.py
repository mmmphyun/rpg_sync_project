import os
import psycopg2
from psycopg2 import pool, OperationalError
from dotenv import load_dotenv

load_dotenv()

_db_pool = None

def initialize_pool():
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = pool.ThreadedConnectionPool(
                10, 20,
                dsn=os.getenv("DATABASE_URL"),
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
        except Exception as e:
            print("[Critical] Database pool initialization failed. Check configuration.")
            raise


def get_connection():
    """
    PostgreSQL DB 연결 객체를 반환합니다.
    풀에서 꺼낸 커넥션의 유효성을 검증하고, 끊어진 경우 폐기 후 재시도합니다.
    """
    global _db_pool
    if _db_pool is None:
        initialize_pool()

    max_retries = 3
    for attempt in range(max_retries):
        conn = None
        try:
            conn = _db_pool.getconn()

            # 세션 생존 여부 확인
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()

            return conn

        except OperationalError:
            # DB 측 타임아웃 등으로 연결이 끊어진 경우: 풀에서 완전 제거
            if conn:
                _db_pool.putconn(conn, close=True)
            print(f"[Warning] Stale connection dropped. Retrying... ({attempt + 1}/{max_retries})")

        except Exception as e:
            print(f"Database connection error: {e}")
            if conn:
                _db_pool.putconn(conn, close=True)
            raise

    raise Exception("[Critical] Failed to acquire a valid DB connection after retries.")

def release_connection(conn):
    """커넥션을 종료하지 않고 풀로 반환"""
    global _db_pool
    if _db_pool and conn:
        _db_pool.putconn(conn)


def sync_jobs_to_db(jobs_data: list[dict]):
    """
    파싱된 직업 데이터를 DB에 병합(UPSERT)합니다.
    PostgreSQL의 INSERT ... ON CONFLICT 구문을 사용합니다.
    """
    upsert_sql = """
        INSERT INTO JOBS (NAME, DISPLAY_NAME, GATE, JOB_GROUP, DESCRIPTION, RESOURCE_TYPE, TYPE, IS_LIMIT, REQ_CONDITION)
        VALUES (%(name)s, %(display_name)s, %(gate)s, %(job_group)s, %(description)s, %(resource_type)s, %(job_type)s, %(is_limit)s, %(req_condition)s)
        ON CONFLICT (NAME) DO UPDATE SET
            DISPLAY_NAME = EXCLUDED.DISPLAY_NAME,
            GATE = EXCLUDED.GATE,
            JOB_GROUP = EXCLUDED.JOB_GROUP,
            DESCRIPTION = EXCLUDED.DESCRIPTION,
            RESOURCE_TYPE = EXCLUDED.RESOURCE_TYPE,
            TYPE = EXCLUDED.TYPE,
            IS_LIMIT = EXCLUDED.IS_LIMIT,
            REQ_CONDITION = EXCLUDED.REQ_CONDITION
        """

    conn = get_connection()
    cursor = conn.cursor()
    success_count = 0

    try:
        for job in jobs_data:
            cursor.execute(upsert_sql, job)
            success_count += 1

        conn.commit()
        print(f"[{success_count}/{len(jobs_data)}] 직업 데이터 동기화 성공")

    except Exception as e:
        conn.rollback()
        print(f"데이터 동기화 중 오류 발생: {e}")
    finally:
        cursor.close()
        release_connection(conn)


def sync_job_patch_to_db(patch_data: dict):
    """
    파싱된 패치노트를 DB에 삽입.
    수정(Edit) 이벤트 발생 시 중복 적재 방지를 위해 DISCORD_MESSAGE_ID 기준 UPSERT 수행.
    부분 일치 검색을 허용하되, 완전 일치 직업명을 우선 매핑함.
    """
    sql = """
        INSERT INTO JOB_PATCHES (JOB_ID, PATCH_DATE, NOTES, DISCORD_MESSAGE_ID)
        SELECT JOB_ID, %(patch_date)s, %(notes)s, %(message_id)s
        FROM JOBS
        WHERE NULLIF(%(name)s, '') IS NOT NULL 
          AND REPLACE(NAME, ' ', '') LIKE CONCAT('%%', %(name)s, '%%')
        ORDER BY 
            CASE WHEN REPLACE(NAME, ' ', '') = %(name)s THEN 1 ELSE 2 END ASC,
            LENGTH(NAME) ASC
        LIMIT 1
        ON CONFLICT (DISCORD_MESSAGE_ID) 
        DO UPDATE SET 
            NOTES = EXCLUDED.NOTES,
            PATCH_DATE = EXCLUDED.PATCH_DATE
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, patch_data)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"패치노트 동기화 중 오류 발생: {e}")
    finally:
        cursor.close()
        release_connection(conn)


def sync_users_to_db(users_data: list[dict]) -> int:
    """
    디스코드 서버 유저 목록을 DB에 병합(UPSERT).
    진행 중인 직업이나 마지막 음성채널 퇴장 시간은 덮어쓰지 않음.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 메모리 캐싱용 직업 리스트 생성 (DB I/O 병목 방지)
        cursor.execute("SELECT job_id, LOWER(REPLACE(name, ' ', '')), LOWER(REPLACE(display_name, ' ', '')) FROM jobs")
        cached_jobs = [{"id": row[0], "name": row[1] or "", "display": row[2] or ""} for row in cursor.fetchall()]

        # 애플리케이션 계층 매핑 로직 (우선순위: 완전 일치 -> 부분 일치)
        for user in users_data:
            job_name = user.pop('job_name', None)
            matched_job_id = None

            if job_name:
                # 1순위: 완전 일치 검증
                exact_match = next(
                    (job["id"] for job in cached_jobs if job_name == job["name"] or job_name == job["display"]), None)

                if exact_match:
                    matched_job_id = exact_match
                else:
                    # 2순위: 부분 일치 검증 (검색어가 포함된 직업 중 길이가 가장 짧은 것을 우선 적용하여 오탐율 최소화)
                    partial_matches = [
                        job for job in cached_jobs
                        if job_name in job["name"] or job_name in job["display"]
                    ]
                    if partial_matches:
                        partial_matches.sort(key=lambda x: min(len(x["name"]), len(x["display"])))
                        matched_job_id = partial_matches[0]["id"]

            user['current_job_id'] = matched_job_id

        # 서브쿼리가 제거된 단순 UPSERT 쿼리
        upsert_sql = """
            INSERT INTO USERS (DISCORD_ID, NICKNAME, SERVER_ROLE, CURRENT_JOB_ID)
            VALUES (%(discord_id)s, %(nickname)s, %(server_role)s, %(current_job_id)s)
            ON CONFLICT (DISCORD_ID) DO UPDATE SET
                NICKNAME = EXCLUDED.NICKNAME,
                SERVER_ROLE = EXCLUDED.SERVER_ROLE,
                CURRENT_JOB_ID = EXCLUDED.CURRENT_JOB_ID
        """

        cursor.executemany(upsert_sql, users_data)

        success_count = len(users_data)
        conn.commit()
        return success_count
    except Exception as e:
        conn.rollback()
        print(f"유저 동기화 중 오류 발생: {e}")
        return 0
    finally:
        cursor.close()
        release_connection(conn)