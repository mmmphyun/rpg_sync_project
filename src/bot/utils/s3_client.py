import os
import uuid
import boto3
from botocore.exceptions import ClientError

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
    s3 = get_r2_client()
    bucket_name = os.getenv('R2_BUCKET_NAME')
    public_domain = os.getenv('R2_PUBLIC_DOMAIN', '').rstrip('/')

    ext = filename.split('.')[-1] if '.' in filename else 'png'
    unique_filename = f"{folder_name}/{uuid.uuid4().hex}.{ext}"

    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=unique_filename,
            Body=file_bytes,
            ContentType=content_type
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
    public_domain = os.getenv('R2_PUBLIC_DOMAIN', '').rstrip('/')

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