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