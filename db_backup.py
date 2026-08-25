import os
import re
import json
import datetime
from urllib.parse import urlparse
import urllib.request
import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 상수 및 설정 정의
DATABASE_URL = os.getenv("DATABASE_URL")
R2_PUBLIC_DOMAIN = os.getenv("R2_PUBLIC_DOMAIN", "")

BACKUP_DIR = "backup"
ARCHIVE_DIR = "public/archive"
IMAGES_DIR = os.path.join(BACKUP_DIR, "images")

# 날짜/시간 데이터의 JSON 직렬화를 위한 커스텀 인코더
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super(DateTimeEncoder, self).default(obj)

def initialize_directories():
    """백업 및 아카이브 디렉토리 초기화 생성"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    print(f"[System] 백업 디렉토리 생성 완료: {BACKUP_DIR}, {ARCHIVE_DIR}, {IMAGES_DIR}")

def extract_and_download_images(data_list, fields):
    """
    DB 데이터 리스트에서 이미지 URL을 추출하여 물리 다운로드 백업
    R2 도메인 매칭 필터를 사용해 안전한 이미지 파일만 백업합니다.
    """
    if not R2_PUBLIC_DOMAIN:
        print("[Warning] R2_PUBLIC_DOMAIN 설정이 비어있어 이미지 필터링 및 백업을 건너뜁니다.")
        return

    # R2 퍼블릭 도메인을 기반으로 하는 안전한 이미지 주소 추출 정규식
    # 예: https://example.r2.dev/images/foo.png 또는 https://r2-domain.com/path/bar.jpg
    r2_pattern = re.compile(rf"https?://{re.escape(R2_PUBLIC_DOMAIN)}/[a-zA-Z0-9_./-]+", re.IGNORECASE)

    download_count = 0
    skipped_count = 0

    for row in data_list:
        for field in fields:
            val = row.get(field)
            if not val:
                continue

            # JSONB 데이터의 경우 문자열로 파싱해 탐색
            if isinstance(val, (list, dict)):
                urls = r2_pattern.findall(json.dumps(val))
            else:
                urls = r2_pattern.findall(str(val))

            for url in urls:
                try:
                    # 파일명 파싱 (마지막 컴포넌트)
                    parsed_url = urlparse(url)
                    filename = os.path.basename(parsed_url.path)
                    if not filename:
                        continue

                    local_filepath = os.path.join(IMAGES_DIR, filename)

                    # 이미 다운로드된 파일은 생략
                    if os.path.exists(local_filepath):
                        skipped_count += 1
                        continue

                    # 다운로드 진행 (타임아웃 5초 제한)
                    print(f" -> Downloading R2 image: {url} ...")
                    req = urllib.request.Request(url, headers={'User-Agent': 'RPGSyncBackupAgent/1.0'})
                    with urllib.request.urlopen(req, timeout=5.0) as response:
                        with open(local_filepath, 'wb') as f:
                            f.write(response.read())
                    download_count += 1

                except Exception as img_err:
                    # 네트워크 타임아웃, 404 에러 등으로 스크립트가 중단되지 않도록 강력한 안전가드 격리
                    print(f"[Warning] R2 이미지 다운로드 실패 ({url}): {img_err}")

    print(f"[Image Backup Success] 신규 다운로드: {download_count}개, 기 존재 스킵: {skipped_count}개")


def backup_table(conn, table_name, is_secure=True, image_fields=None):
    """지정한 Supabase 테이블의 전체 데이터를 JSON으로 저장하고, 이미지 정밀 추출"""
    cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
    
    try:
        # magic_tokens 및 tokens 테이블 제외 검증 (안전장치)
        if table_name.lower() in ["magic_tokens", "tokens"]:
            print(f"[Security Warning] {table_name}은 기밀 유출 방지를 위해 백업하지 않습니다.")
            return None

        print(f"[*] 테이블 백업 시작: {table_name}")
        cursor.execute(f'SELECT * FROM public."{table_name}"')
        rows = cursor.fetchall()
        
        # 저장 경로 이원화
        if is_secure:
            filepath = os.path.join(BACKUP_DIR, f"{table_name}.json")
        else:
            filepath = os.path.join(ARCHIVE_DIR, f"{table_name}.json")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=4, ensure_ascii=False, cls=DateTimeEncoder)

        print(f"[Backup Success] {table_name} -> {filepath} ({len(rows)} rows)")

        # 이미지 리소스 추출 및 다운로드 백업
        if image_fields and rows:
            extract_and_download_images(rows, image_fields)

        return rows
    except Exception as e:
        print(f"[Critical Error] {table_name} 백업 중 오류 발생: {e}")
        raise e
    finally:
        cursor.close()

def cleanup_legacy_data(conn):
    """
    기존 시즌 레거시 직업 데이터 안전 비우기
    PostgreSQL의 외래 키 제약 조건(Foreign Key Constraints)을 우회할 수 있도록 
    반드시 안전한 종속성 역순으로 삭제/수정을 트랜잭션 단위로 진행합니다.
    """
    cursor = conn.cursor()
    try:
        print("\n[*] =========================================")
        print("[*] 새 시즌 준비를 위한 기존 직업 데이터 비우기(정리) 시작")
        print("[*] =========================================")

        # 1. 2차 종속 테이블: skills 삭제 (weapons 참조)
        print(" -> [1/6] skills 테이블 정리...")
        cursor.execute("DELETE FROM public.skills")

        # 2. 1차 종속 테이블: weapons 삭제 (jobs 참조)
        print(" -> [2/6] weapons 테이블 정리...")
        cursor.execute("DELETE FROM public.weapons")

        # 3. 1차 종속 테이블: job_reviews 삭제 (jobs, users 참조)
        print(" -> [3/6] job_reviews 테이블 정리...")
        cursor.execute("DELETE FROM public.job_reviews")

        # 4. 1차 종속 테이블: job_patches 삭제 (jobs 참조)
        print(" -> [4/6] job_patches 테이블 정리...")
        cursor.execute("DELETE FROM public.job_patches")

        # 5. 1차 종속 테이블 관계 단절: users의 current_job_id NULL 업데이트 (유저 계정 자체는 보존)
        print(" -> [5/6] users 테이블 내 직업 의존성 해제 (NULL화)...")
        cursor.execute("UPDATE public.users SET current_job_id = NULL")

        # 6. 최상위 독립 테이블: jobs 삭제
        print(" -> [6/6] jobs 테이블 정리...")
        cursor.execute("DELETE FROM public.jobs")

        # 모든 쿼리가 무사히 실행되었을 때만 디비에 최종 반영(커밋)
        conn.commit()
        print("[Clean Cleanup Success] 새 시즌 진입을 위한 기존 직업 및 종속 데이터 안전 정리 완료!")
    except Exception as e:
        conn.rollback()
        print(f"[Cleanup Failed] 데이터 비우기 중 롤백 발생: {e}")
        raise e
    finally:
        cursor.close()


def main():
    if not DATABASE_URL:
        print("[Error] DATABASE_URL 환경변수가 누락되었습니다. .env 파일을 검증하십시오.")
        return

    initialize_directories()

    print("\n========== [RPG Sync Gate 백업 & 아카이브 마이그레이션 기동] ==========")
    try:
        # DB 연결 수립
        conn = psycopg2.connect(DATABASE_URL)
        print("[System] Supabase Database 연동에 성공하였습니다.")

        # 1. 공개용 정적 데이터 백업 (src/web/static/archive ➔ public/archive/ 에 기입하여 깃 추적 허용)
        # 이미지 다운로드 포함 (jobs.img, photo_1 ~ 4)
        backup_table(conn, "jobs", is_secure=False, image_fields=["img", "photo_1", "photo_2", "photo_3", "photo_4"])
        backup_table(conn, "weapons", is_secure=False)
        backup_table(conn, "skills", is_secure=False)

        # 2. 비공개 보안 데이터 백업 (backup/ 에 기입하여 Git 추적 완전 배제)
        # 이미지 다운로드 포함 (notices.image_urls)
        backup_table(conn, "notices", is_secure=True, image_fields=["image_urls"])
        backup_table(conn, "users", is_secure=True)
        backup_table(conn, "job_patches", is_secure=True)
        backup_table(conn, "job_reviews", is_secure=True)

        print("\n[All Backup Success] 모든 데이터 백업 및 이미지 추출 작업이 성황리에 완료되었습니다.")

        # 3. 신규 시즌을 위한 DB 정리 작업 집행 (백업 성공 시에만 작동)
        cleanup_legacy_data(conn)

    except Exception as err:
        print(f"\n[Migration Interrupted] 중대한 예외 발생으로 데이터 정리 작업이 롤백되거나 중단되었습니다: {err}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("[System] DB 커넥션을 닫았습니다.")

if __name__ == "__main__":
    main()
