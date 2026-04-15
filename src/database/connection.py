import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """PostgreSQL DB 연결 객체를 반환합니다."""
    try:
        connection = psycopg2.connect(os.getenv("DATABASE_URL"))
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        raise


def sync_jobs_to_db(jobs_data: list[dict]):
    """
    파싱된 직업 데이터를 DB에 병합(UPSERT)합니다.
    PostgreSQL의 INSERT ... ON CONFLICT 구문을 사용합니다.
    """
    upsert_sql = """
        INSERT INTO JOBS (NAME, DISPLAY_NAME, GATE, JOB_GROUP, DESCRIPTION, RESOURCE_TYPE, IS_LIMIT, REQ_CONDITION)
        VALUES (%(name)s, %(display_name)s, %(gate)s, %(job_group)s, %(description)s, %(resource_type)s, %(is_limit)s, %(req_condition)s)
        ON CONFLICT (NAME) DO UPDATE SET
            DISPLAY_NAME = EXCLUDED.DISPLAY_NAME,
            GATE = EXCLUDED.GATE,
            JOB_GROUP = EXCLUDED.JOB_GROUP,
            DESCRIPTION = EXCLUDED.DESCRIPTION,
            RESOURCE_TYPE = EXCLUDED.RESOURCE_TYPE,
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
        conn.close()