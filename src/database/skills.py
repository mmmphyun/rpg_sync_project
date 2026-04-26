import psycopg2
from src.database.connection import get_connection, release_connection


def upsert_weapon_and_skill(
        job_name: str, weapon_type: str, weapon_name: str, command_key: str, skill_name: str,
        description: str, cooldown: str, cost_value: str, coefficient_combined: str, is_mobility: str
) -> bool:
    """무기 및 스킬 정보 수동 UPSERT (스키마 구조 반영)"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. 직업 ID 조회
        cursor.execute("SELECT job_id FROM jobs WHERE name = %s", (job_name,))
        job_row = cursor.fetchone()
        if not job_row:
            raise ValueError(f"직업 '{job_name}'을(를) 찾을 수 없습니다.")
        job_id = job_row[0]

        # 2. 무기 정보 적재
        cursor.execute("SELECT weapon_id FROM weapons WHERE job_id = %s AND weapon_name = %s", (job_id, weapon_name))
        weapon_row = cursor.fetchone()

        if weapon_row:
            weapon_id = weapon_row[0]
            cursor.execute(
                "UPDATE weapons SET weapon_type = %s WHERE weapon_id = %s",
                (weapon_type, weapon_id)
            )
        else:
            cursor.execute(
                "INSERT INTO weapons (job_id, weapon_name, weapon_type) VALUES (%s, %s, %s) RETURNING weapon_id",
                (job_id, weapon_name, weapon_type)
            )
            weapon_id = cursor.fetchone()[0]

        # 3. 스킬 정보 적재
        cursor.execute("SELECT skill_id FROM skills WHERE weapon_id = %s AND command_key = %s",
                       (weapon_id, command_key))
        skill_row = cursor.fetchone()

        if skill_row:
            cursor.execute("""
                UPDATE skills SET
                    skill_name = %s, description = %s, cooldown = %s, cost_value = %s, coefficient = %s, is_mobility = %s
                WHERE skill_id = %s
            """, (skill_name, description, cooldown, cost_value, coefficient_combined, is_mobility, skill_row[0]))
        else:
            cursor.execute("""
                INSERT INTO skills (weapon_id, command_key, skill_name, description, cooldown, cost_value, coefficient, is_mobility)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (weapon_id, command_key, skill_name, description, cooldown, cost_value, coefficient_combined,
                  is_mobility))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] upsert_weapon_and_skill: {e}")
        if isinstance(e, ValueError):
            raise
        return False
    finally:
        cursor.close()
        release_connection(conn)