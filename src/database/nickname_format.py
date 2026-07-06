import json
import psycopg2
from src.database.connection import get_connection, release_connection, db_retry

DEFAULT_FORMATS = [
    {
        "part_count": 2,
        "delimiter": "ㅣ",
        "nickname_index": 1,
        "job_index": 2,
        "staff_index": -1
    }
]

@db_retry(max_retries=2)
def get_nickname_formats() -> list[dict]:
    """system_configs 테이블에서 닉네임 파싱 설정들을 조회하여 반환합니다."""
    sql = "SELECT config_value FROM public.system_configs WHERE config_key = 'nickname_formats'"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        row = cursor.fetchone()
        if row and row[0]:
            val = row[0]
            if isinstance(val, str):
                return json.loads(val)
            return val
        
        # 데이터가 없으면 기본값 적재 후 반환
        save_nickname_formats(DEFAULT_FORMATS)
        return DEFAULT_FORMATS
    except Exception as e:
        print(f"[DB Error] get_nickname_formats 조회 오류: {e}")
        return DEFAULT_FORMATS
    finally:
        cursor.close()
        release_connection(conn)

@db_retry(max_retries=2)
def save_nickname_formats(formats: list[dict]) -> bool:
    """system_configs 테이블에 닉네임 파싱 설정들을 저장(UPSERT)합니다."""
    sql = """
        INSERT INTO public.system_configs (config_key, config_value)
        VALUES ('nickname_formats', %s::jsonb)
        ON CONFLICT (config_key) DO UPDATE SET
            config_value = EXCLUDED.config_value,
            updated_at = CURRENT_TIMESTAMP
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        json_str = json.dumps(formats, ensure_ascii=False)
        cursor.execute(sql, (json_str,))
        conn.commit()
        return cursor.rowcount > 0
    except psycopg2.Error as e:
        conn.rollback()
        print(f"[DB Error] save_nickname_formats 저장 오류: {e}")
        return False
    finally:
        cursor.close()
        release_connection(conn)
