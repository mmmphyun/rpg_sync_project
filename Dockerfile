FROM python:3.11-slim

# 보안 업데이트 및 패키지 캐시 정리
RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 패키지 우선 복사 및 설치 (레이어 캐싱)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스코드 전체 복사
COPY . .

# 쉘 스크립트 실행 권한 부여
RUN chmod +x start.sh

# 컨테이너 시작 명령
CMD ["./start.sh"]