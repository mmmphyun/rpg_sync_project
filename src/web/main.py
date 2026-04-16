from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from src.database.queries import get_all_jobs_for_web
import os

app = FastAPI(title="RPG Server API", version="1.0.0")

# CORS 설정 (실무에서는 특정 도메인만 허용하도록 변경)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def serve_index():
    return FileResponse("index.html")

@app.get("/{filename}.html")
def serve_html(filename: str):
    file_path = f"{filename}.html"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"detail": "Not Found"}

@app.get("/{filename}.js")
def serve_js(filename: str):
    file_path = f"{filename}.js"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"detail": "Not Found"}

@app.get("/{filename}.css")
def serve_css(filename: str):
    file_path = f"{filename}.css"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"detail": "Not Found"}

@app.get("/api/jobs")
def read_jobs():
    """
    프론트엔드 렌더링을 위한 전체 직업 목록 반환
    """
    jobs_data = get_all_jobs_for_web()

    formatted_jobs = []
    for row in jobs_data:
        photos = [p for p in [row.get('photo_1'), row.get('photo_2'), row.get('photo_3'), row.get('photo_4')] if p]

        formatted_jobs.append({
            "name": row.get('display_name'),
            "searchName": row.get('name'),
            "gate": row.get('gate'),
            "group": row.get('job_group'),
            "desc": row.get('description'),
            "range": row.get('range_type'),
            "position": row.get('position'),
            "resource": row.get('resource_type'),
            "img": row.get('img', ''),
            "photos": photos,
            "limit": True if row.get('is_limit') == 'Y' else False,
            "req_condition": row.get('req_condition'),
            "patches": row.get('patches', []),  # 추가된 패치노트
            "players": row.get('players', [])    # 추가된 해당 직업 유저 목록
        })

    return formatted_jobs