import psycopg2
from src.database.connection import get_connection, release_connection


def upsert_weapon_and_skill(
        job_name: str, weapon_type: str, weapon_name: str, command_key: str, skill_name: str,
        description: str, cooldown: str, cost_value: str, coefficient_combined: str, is_mobility: str
) -> bool:
    """무기 및 스킬 정보 UPSERT (weapon_type 포함)"""

    weapon_sql = """
        INSERT INTO weapons (job_name, weapon_name, weapon_type)
        VALUES (%s, %s, %s)
        ON CONFLICT (job_name, weapon_name) 
        DO UPDATE SET weapon_type = EXCLUDED.weapon_type
        RETURNING id;
    """

    skill_sql = """
        INSERT INTO skills (
            weapon_id, command_key, skill_name, description, 
            cooldown, cost_value, coefficient, is_mobility
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (weapon_id, command_key)
        DO UPDATE SET
            skill_name = EXCLUDED.skill_name,
            description = EXCLUDED.description,
            cooldown = EXCLUDED.cooldown,
            cost_value = EXCLUDED.cost_value,
            coefficient = EXCLUDED.coefficient,
            is_mobility = EXCLUDED.is_mobility;
    """

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # weapon_type 파라미터 추가 반영
        cursor.execute(weapon_sql, (job_name, weapon_name, weapon_type))
        weapon_id = cursor.fetchone()[0]

        cursor.execute(skill_sql, (
            weapon_id, command_key, skill_name, description,
            cooldown, cost_value, coefficient_combined, is_mobility
        ))

        conn.commit()
        return True
    except psycopg2.Error as e:
        conn.rollback()
        print(f"[DB Error] upsert_weapon_and_skill: {e}")
        return False
    finally:
        cursor.close()
        release_connection(conn)