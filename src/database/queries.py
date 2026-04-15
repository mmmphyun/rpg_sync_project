import oracledb
from src.database.connection import get_connection


def update_job_single_column(job_name: str, column_name: str, value: str) -> int:
    """
    Updates a specific column for a given job.

    Args:
        job_name (str): PK mapped job name (spaces removed)
        column_name (str): Target column name
        value (str): Value to update

    Returns:
        int: Number of affected rows
    """
    # Allowed columns to prevent SQL Injection
    allowed_columns = {
        "range": "RANGE_TYPE",
        "position": "POSITION",
        "resource": "RESOURCE_TYPE",
        "img": "IMG",
        "photo1": "PHOTO_1",
        "photo2": "PHOTO_2",
        "photo3": "PHOTO_3",
        "photo4": "PHOTO_4"
    }

    target_col = allowed_columns.get(column_name.lower())
    if not target_col:
        raise ValueError(f"Invalid column name: {column_name}")

    clean_job_name = job_name.replace(" ", "")

    sql = f"UPDATE JOBS SET {target_col} = :val WHERE NAME = :name"

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, val=value, name=clean_job_name)
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows
    except oracledb.Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def get_all_jobs_for_web() -> list[dict]:
    """
    웹 프론트엔드에 제공할 모든 직업 정보를 조회합니다.
    """
    sql = """
        SELECT NAME, DISPLAY_NAME, GATE, JOB_GROUP, DESCRIPTION, 
               RANGE_TYPE, POSITION, RESOURCE_TYPE, IS_LIMIT, 
               REQ_CONDITION, IMG, PHOTO_1, PHOTO_2, PHOTO_3, PHOTO_4
        FROM JOBS
        ORDER BY GATE, DISPLAY_NAME
    """

    conn = get_connection()
    # 딕셔너리 형태로 결과를 반환받기 위해 rowfactory 설정
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        cursor.execute(sql)
        # 컬럼명을 소문자 키로 가지는 딕셔너리 리스트 생성
        columns = [col[0].lower() for col in cursor.description]
        cursor.rowfactory = lambda *args: dict(zip(columns, args))

        jobs = cursor.fetchall()
        return jobs
    except oracledb.Error as e:
        print(f"조회 중 오류 발생: {e}")
        return []
    finally:
        cursor.close()
        conn.close()