import os
import uuid
import boto3
import magic
from botocore.exceptions import ClientError

ALLOWED_MAGIC_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
        region_name='auto'
    )

def upload_to_r2(file_bytes: bytes, filename: str, content_type: str, folder_name: str = "jobs") -> str | None:
    """
    R2 스토리지 파일 업로드 및 Public URL 반환
    """
    actual_mime = magic.from_buffer(file_bytes, mime=True)
    if actual_mime not in ALLOWED_MAGIC_MIMES:
        print(f"[Security Block] 허용되지 않은 파일 형식 업로드 시도: 주장={content_type}, 실제={actual_mime}")
        return None

    s3 = get_r2_client()
    bucket_name = os.getenv('R2_BUCKET_NAME')
    domain_env = os.getenv('R2_PUBLIC_DOMAIN') or os.getenv('R2_PUBLIC_DOMAIN_DEV')
    if not domain_env:
        raise ValueError("R2 도메인 환경 변수가 설정되지 않았습니다.")

    public_domain = domain_env.rstrip('/')

    ext = actual_mime.split('/')[-1]
    unique_filename = f"{folder_name}/{uuid.uuid4().hex}.{ext}"

    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=unique_filename,
            Body=file_bytes,
            ContentType=actual_mime
        )
        return f"{public_domain}/{unique_filename}"
    except ClientError as e:
        print(f"[R2 Upload Error] {e}")
        return None

def delete_from_r2(image_url: str) -> bool:
    """R2 Object 단건 삭제"""
    if not image_url:
        return False

    s3 = get_r2_client()
    bucket_name = os.getenv('R2_BUCKET_NAME')
    domain_env = os.getenv('R2_PUBLIC_DOMAIN') or os.getenv('R2_PUBLIC_DOMAIN_DEV')
    if not domain_env:
        raise ValueError("R2 도메인 환경 변수가 설정되지 않았습니다.")

    public_domain = domain_env.rstrip('/')

    try:
        object_key = image_url.replace(f"{public_domain}/", "")
        s3.delete_object(
            Bucket=bucket_name,
            Key=object_key
        )
        return True
    except ClientError as e:
        print(f"[R2 Delete Error] {e}")
        return False