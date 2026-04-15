import os
import oracledb
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


def get_connection():
    """Oracle DB 연결 객체를 반환합니다."""
    try:
        connection = oracledb.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            dsn=os.getenv("DB_DSN")
        )
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        raise


def sync_jobs_to_db(jobs_data: list[dict]):
    """
    파싱된 직업 데이터(jobs_data)를 DB에 병합(UPSERT)합니다.
    """
    merge_sql = """
        MERGE INTO JOBS j
        USING (
            SELECT :name AS NAME,
                   :display_name AS DISPLAY_NAME,
                   :gate AS GATE,
                   :job_group AS JOB_GROUP,
                   :description AS DESCRIPTION,
                   :resource_type AS RESOURCE_TYPE,
                   :is_limit AS IS_LIMIT,
                   :req_condition AS REQ_CONDITION
            FROM DUAL
        ) src
        ON (j.NAME = src.NAME)
        WHEN MATCHED THEN
            UPDATE SET
                j.DISPLAY_NAME = src.DISPLAY_NAME,
                j.GATE = src.GATE,
                j.JOB_GROUP = src.JOB_GROUP,
                j.DESCRIPTION = src.DESCRIPTION,
                j.RESOURCE_TYPE = src.RESOURCE_TYPE,
                j.IS_LIMIT = src.IS_LIMIT,
                j.REQ_CONDITION = src.REQ_CONDITION
        WHEN NOT MATCHED THEN
            INSERT (NAME, DISPLAY_NAME, GATE, JOB_GROUP, DESCRIPTION, RESOURCE_TYPE, IS_LIMIT, REQ_CONDITION)
            VALUES (src.NAME, src.DISPLAY_NAME, src.GATE, src.JOB_GROUP, src.DESCRIPTION, src.RESOURCE_TYPE, src.IS_LIMIT, src.REQ_CONDITION)
    """

    conn = get_connection()
    cursor = conn.cursor()

    success_count = 0
    try:
        for job in jobs_data:
            cursor.execute(merge_sql, {
                "name": job["name"],
                "display_name": job["display_name"],
                "gate": job["gate"],
                "job_group": job["job_group"],
                "description": job["description"],
                "resource_type": job["resource_type"],
                "is_limit": job["is_limit"],
                "req_condition": job["req_condition"]
            })
            success_count += 1

        conn.commit()
        print(f"[{success_count}/{len(jobs_data)}] 직업 데이터 동기화 성공")

    except Exception as e:
        conn.rollback()
        print(f"데이터 동기화 중 오류 발생: {e}")
    finally:
        cursor.close()
        conn.close()