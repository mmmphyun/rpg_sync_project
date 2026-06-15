import os
import psycopg2
from psycopg2.extras import DictCursor


def insert_banner(banner_data: dict) -> int:
    """
    배너 메타데이터 DB 적재

    :param banner_data: dict containing image_url, link_url, sort_order, is_active
    :return: inserted banner id
    """
    # 실제 프로젝트의 DB 커넥션 획득 로직(Pool 등)이 있다면 해당 모듈로 대체하십시오.
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set.")

    query = """
        INSERT INTO banners (image_url, link_url, sort_order, is_active)
        VALUES (%(image_url)s, %(link_url)s, %(sort_order)s, %(is_active)s)
        RETURNING id;
    """

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(query, banner_data)
                inserted_id = cur.fetchone()['id']
                conn.commit()
                return inserted_id
    except psycopg2.Error as e:
        print(f"[DB Error] Failed to insert banner: {e}")
        raise e

def get_active_banners() -> list[dict]:
    """
    활성화된 배너 목록 조회 (우선순위 내림차순, 최신순)
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set.")

    query = """
        SELECT id, image_url, link_url, sort_order
        FROM banners
        WHERE is_active = TRUE
        ORDER BY sort_order DESC, created_at DESC;
    """

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(query)
                rows = cur.fetchall()
                # DictCursor 결과를 순수 dict로 변환하여 반환
                return [dict(row) for row in rows]
    except psycopg2.Error as e:
        print(f"[DB Error] Failed to fetch banners: {e}")
        return []


def get_all_banner_urls() -> list[str]:
    """
    모든 배너의 image_url 목록 조회
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set.")

    query = """
        SELECT image_url
        FROM banners;
    """

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                return [row[0] for row in rows]
    except psycopg2.Error as e:
        print(f"[DB Error] Failed to fetch all banner urls: {e}")
        return []


def delete_all_banners() -> int:
    """
    모든 배너 삭제 및 삭제된 행의 개수 반환
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set.")

    query = """
        DELETE FROM banners;
    """

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                deleted_rows = cur.rowcount
                conn.commit()
                return deleted_rows
    except psycopg2.Error as e:
        print(f"[DB Error] Failed to delete all banners: {e}")
        raise e