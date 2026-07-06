# src/bot/utils/text_parser.py
import re
from typing import Optional, List, Dict, Any

RESOURCE_KEYWORDS = ["기력", "마나", "체력", "에너지"]


def parse_job_descriptions(raw_text: str) -> List[Dict[str, Any]]:
    """
    [직업 설명 쓰레드] 파서
    포맷:
    ## 게이트명 [ 그룹명 ]
    ### 직업명
    설명(마나, 기력 등의 코스트 키워드, 영웅 또는 빌런의 타입 키워드가 포함되면 자동으로 인식)
    << 1인 제한, 2차 각성 필요 등의 조건 >>
    """
    jobs_data = []

    current_gate = "정보 없음"
    current_group = "정보 없음"
    current_job_name = None
    current_desc_lines = []

    lines = raw_text.split('\n')

    def _flush_job():
        nonlocal current_job_name, current_desc_lines

        if current_job_name:
            desc_str = "\n".join(current_desc_lines).strip()

            # 코스트 자원 식별
            resource_type = "정보 없음"
            for res in RESOURCE_KEYWORDS:
                if res in desc_str:
                    resource_type = res
                    break

            # 타입 식별 (Hero/Villain)
            job_type = "정보 없음"
            bracket_matches = re.findall(r"\[(.*?)\]", desc_str)
            for bracket_text in bracket_matches:
                if "영웅" in bracket_text:
                    job_type = "영웅"
                    break
                elif "빌런" in bracket_text:
                    job_type = "빌런"
                    break

            # 조건(req_condition) 파싱 및 설명문 정제
            req_condition = "정보 없음"
            condition_match = re.search(r"<<(.*?)>>", desc_str)
            if condition_match:
                req_condition = condition_match.group(1).strip()
                # DB 적재 시 설명 컬럼 중복 방지를 위한 태그 제거
                desc_str = desc_str.replace(condition_match.group(0), "").strip()

            # 1인 제한 여부 식별 (조건문, 설명문, 직업명 모두 검사)
            is_limit = 'Y' if '1인 제한' in req_condition or '1인 제한' in desc_str or '1인 제한' in current_job_name else 'N'

            # 공백을 제거한 고유 ID 생성 및 표시명 분리
            clean_job_id = re.sub(r"\s+", "", current_job_name)
            clean_display_name = current_job_name.strip()

            jobs_data.append({
                "name": clean_job_id,
                "display_name": clean_display_name,
                "gate": current_gate,
                "job_group": current_group,
                "description": desc_str,
                "resource_type": resource_type,
                "job_type": job_type,
                "is_limit": is_limit,
                "req_condition": req_condition
            })

            current_job_name = None
            current_desc_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 1. Gate & Group (H2)
        if line.startswith("## "):
            _flush_job()
            header_content = line[3:].strip()

            # 대괄호 존재 여부로 그룹 추출
            group_match = re.search(r"\[(.*?)\]", header_content)
            if group_match:
                current_group = group_match.group(1).strip()
                current_gate = header_content[:group_match.start()].strip()
            else:
                current_gate = header_content
                current_group = "정보 없음"
            continue

        # 2. 직업명 (H3)
        if line.startswith("### "):
            _flush_job()
            current_job_name = line[4:].strip()
            continue

        # 3. 설명문 버퍼링
        if current_job_name:
            current_desc_lines.append(line)

    _flush_job()
    return jobs_data


def parse_job_patches(raw_text: str, created_at: str, message_id: int) -> Optional[Dict[str, str]]:
    """
    [직업 패치노트 채널] 파서
    포맷:
    ## 직업명
    - 설명1
    """
    lines = raw_text.split('\n')
    job_name = None
    notes = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("## "):
            job_name = line[3:].strip()
        else:
            # '-', '*' 불릿 기호를 유지하거나 일반 텍스트 모두 notes 배열로 병합
            notes.append(line)

    if job_name:
        clean_job_id = re.sub(r"\s+", "", job_name)
        return {
            "name": clean_job_id,
            "patch_date": created_at,
            "message_id": message_id,
            "notes": "\n".join(notes).strip()
        }
    return None


def parse_job_illustration(raw_text: str) -> Optional[str]:
    """
    [직업 종류(일러스트) 쓰레드] 텍스트 파서
    포맷: << 직업이름 >>
    첨부파일(이미지) 자체는 discord.py의 message.attachments를 통해 Event Listener 측에서 처리해야 함.
    """
    match = re.search(r"<<\s*(.*?)\s*>>", raw_text)
    if match:
        raw_extracted = match.group(1).strip()
        job_name = raw_extracted.split(':')[-1]
        # DB 조회를 위해 공백이 제거된 ID 형태 반환
        return re.sub(r"\s+", "", job_name)
    return None


def parse_user_nickname(display_name: str, formats: list = None) -> dict:
    """
    유저 닉네임 문자열을 파싱하여 실제 닉네임, 서버 역할, 직업명을 추출합니다.
    """
    if not display_name:
        return {
            "nickname": "",
            "server_role": "유저",
            "job_name": None
        }

    # 1. 스태프 식별 (대소문자 무관 STF/OWN 또는 이모지 🌈)
    lower_name = display_name.lower()
    is_staff = "stf" in lower_name or "own" in lower_name or "🌈" in display_name
    server_role = "STAFF" if is_staff else "유저"

    # 2. 스태프 관련 키워드 및 대괄호/괄호 노이즈 제거
    cleaned = re.sub(r'[\(\[\{]?(?:STF|stf)[\)\]\}]?|🌈', '', display_name)

    # 기본 포맷 설정 (전달되지 않았을 때의 폴백)
    if not formats:
        formats = [
            {
                "part_count": 2,
                "delimiter": "ㅣ",
                "nickname_index": 1,
                "job_index": 2,
                "staff_index": -1
            }
        ]

    # 각 포맷에 대해 닉네임을 split하여 매칭 시도
    matched_fmt = None
    parts = []
    
    for fmt in formats:
        delim = fmt.get("delimiter", "ㅣ")
        pattern = re.escape(delim)
        temp_parts = [p.strip() for p in re.split(pattern, cleaned) if p.strip()]
        
        if len(temp_parts) == fmt.get("part_count"):
            matched_fmt = fmt
            parts = temp_parts
            break

    # 매칭되는 포맷을 찾지 못한 경우 폴백 처리
    if not matched_fmt:
        # 기존 하드코딩 룰을 폴백으로 적용
        parts = [p.strip() for p in re.split(r'[ㅣ\|]', cleaned) if p.strip()]
        part_count = len(parts)
        
        actual_nickname = display_name.strip()
        job_name = None
        
        if part_count == 1:
            actual_nickname = parts[0]
        elif part_count == 2:
            actual_nickname = parts[0]
        elif part_count >= 3:
            actual_nickname = parts[-2]
            job_name = parts[-1].replace(" ", "").lower()
    else:
        # 매칭된 포맷 규칙에 따라 파싱 (1-based index 이므로 -1 처리)
        nickname_idx = matched_fmt["nickname_index"] - 1
        job_idx = matched_fmt["job_index"] - 1
        staff_idx = matched_fmt.get("staff_index", -1) - 1

        actual_nickname = display_name.strip()
        job_name = None

        if 0 <= nickname_idx < len(parts):
            actual_nickname = parts[nickname_idx]
        if 0 <= job_idx < len(parts):
            job_name = parts[job_idx].replace(" ", "").lower()
        if 0 <= staff_idx < len(parts):
            val = parts[staff_idx].lower()
            if "stf" in val or "own" in val or "staff" in val:
                server_role = "STAFF"

    if job_name and not job_name.strip():
        job_name = None

    return {
        "nickname": actual_nickname,
        "server_role": server_role,
        "job_name": job_name
    }