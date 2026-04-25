import psycopg2
from src.database.connection import get_connection, release_connection

def upsert_weapon_and_skill(job_name: str, weapon_name: str, command_key: str, skill_name: str,
                            description: str, cooldown: str, cost_value: str,
                            coefficient: str, is_mobility: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT job_id FROM jobs WHERE name = %s OR display_name = %s LIMIT 1",
            (job_name, job_name)
        )
        job_res = cursor.fetchone()
        if not job_res:
            raise ValueError(f"대상 직업을 찾을 수 없습니다: {job_name}")
        job_id = job_res[0]

        cursor.execute(
            "SELECT weapon_id FROM weapons WHERE job_id = %s AND weapon_name = %s",
            (job_id, weapon_name)
        )
        weapon_res = cursor.fetchone()

        if weapon_res:
            weapon_id = weapon_res[0]
        else:
            cursor.execute(
                "INSERT INTO weapons (job_id, weapon_name) VALUES (%s, %s) RETURNING weapon_id",
                (job_id, weapon_name)
            )
            weapon_id = cursor.fetchone()[0]

        cursor.execute(
            "SELECT skill_id FROM skills WHERE weapon_id = %s AND command_key = %s",
            (weapon_id, command_key)
        )
        skill_res = cursor.fetchone()

        if skill_res:
            cursor.execute("""
                UPDATE skills
                SET skill_name = %s, description = %s, cooldown = %s, cost_value = %s, coefficient = %s, is_mobility = %s
                WHERE skill_id = %s
            """, (skill_name, description, cooldown, cost_value, coefficient, is_mobility, skill_res[0]))
        else:
            cursor.execute("""
                INSERT INTO skills (weapon_id, command_key, skill_name, description, cooldown, cost_value, coefficient, is_mobility)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (weapon_id, command_key, skill_name, description, cooldown, cost_value, coefficient, is_mobility))

        conn.commit()
        return True

    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Weapon/Skill 트랜잭션 오류: {e}")
    finally:
        cursor.close()
        release_connection(conn)