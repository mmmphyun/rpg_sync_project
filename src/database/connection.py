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
        conn.close()

def sync_users_to_db(users_data: list[dict]) -> int:
    """
    디스코드 서버 유저 목록을 DB에 병합(UPSERT).
    진행 중인 직업이나 마지막 음성채널 퇴장 시간은 덮어쓰지 않음.
    """
    upsert_sql = """
        INSERT INTO USERS (DISCORD_ID, NICKNAME, SERVER_ROLE, CURRENT_JOB_ID)
        VALUES (
            %(discord_id)s, 
            %(nickname)s, 
            %(server_role)s,
            (
                SELECT JOB_ID 
                FROM JOBS 
                WHERE NULLIF(%(job_name)s, '') IS NOT NULL 
                  AND REPLACE(NAME, ' ', '') LIKE CONCAT('%%', %(job_name)s, '%%')
                ORDER BY 
                    CASE WHEN REPLACE(NAME, ' ', '') = %(job_name)s THEN 1 ELSE 2 END ASC,
                    LENGTH(NAME) ASC
                LIMIT 1
            )
        )
        ON CONFLICT (DISCORD_ID) DO UPDATE SET
            NICKNAME = EXCLUDED.NICKNAME,
            SERVER_ROLE = EXCLUDED.SERVER_ROLE,
            CURRENT_JOB_ID = EXCLUDED.CURRENT_JOB_ID
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