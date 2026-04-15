#!/bin/bash

# 디스코드 봇 백그라운드 구동
python -m src.bot.main &

# FastAPI 웹 서버 포그라운드 구동
# Koyeb 환경변수 PORT(기본 8000)를 수용하여 포트 바인딩 충돌 방지
uvicorn src.web.main:app --host 0.0.0.0 --port ${PORT:-8000}