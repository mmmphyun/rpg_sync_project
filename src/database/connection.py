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


def sync_job_patch_to_db(patch_data: dict):
    """
    파싱된 패치노트를 DB에 삽입.
    JOBS 테이블의 NAME 컬럼으로 매핑하여 JOB_ID 외래키를 조회 후 적재함.
    """
    sql = """
        INSERT INTO JOB_PATCHES (JOB_ID, PATCH_DATE, NOTES)
        SELECT JOB_ID, TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'), %(notes)s
        FROM JOBS
        WHERE NAME = %(name)s
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
        conn.close()

def sync_users_to_db(users_data: list[dict]) -> int:
    """
    디스코드 서버 유저 목록을 DB에 병합(UPSERT).
    진행 중인 직업이나 마지막 음성채널 퇴장 시간은 덮어쓰지 않음.
    """
    upsert_sql = """
        INSERT INTO USERS (DISCORD_ID, NICKNAME, SERVER_ROLE)
        VALUES (%(discord_id)s, %(nickname)s, %(server_role)s)
        ON CONFLICT (DISCORD_ID) DO UPDATE SET
            NICKNAME = EXCLUDED.NICKNAME,
            SERVER_ROLE = EXCLUDED.SERVER_ROLE
    """

    conn = get_connection()
    cursor = conn.cursor()
    success_count = 0

    try:
        for user in users_data:
            cursor.execute(upsert_sql, user)
            success_count += 1

        conn.commit()
        return success_count
    except Exception as e:
        conn.rollback()
        print(f"유저 동기화 중 오류 발생: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()