import re


def parse_discord_jobs(raw_text: str) -> list[dict]:
    """
    디스코드 직업 포스트 텍스트 파싱 모듈
    - State Machine 패턴으로 Gate/Group 컨텍스트 유지
    - 정규식을 활용한 동적 속성(자원, 조건) 추출
    """
    jobs_data = []

    # State Variables
    current_gate = None
    current_group = None
    current_job_name = None
    current_desc_lines = []

    # Constants for parsing
    RESOURCE_KEYWORDS = ["기력", "마나", "체력", "에너지"]
    ISOLATED_GROUPS = ["환신", "집시", "금강", "케이브 행성"]

    lines = raw_text.split('\n')

    def _flush_job():
        """현재 누적된 직업 상태를 딕셔너리로 저장하고 버퍼를 비움"""
        nonlocal current_job_name, current_desc_lines
        if current_job_name:
            desc_str = " ".join(current_desc_lines).strip()

            # 자원(Resource) 파싱
            resource_type = "정보 없음"
            for res in RESOURCE_KEYWORDS:
                if res in desc_str:
                    resource_type = res
                    break

            # 조건(Limit, Requirement) 파싱
            is_limit = 'Y' if '1인 제한' in desc_str or '1인 제한' in current_job_name else 'N'

            req_condition = None
            if '1차 각성' in desc_str:
                req_condition = '1차 각성'
            elif '2차 각성' in desc_str:
                req_condition = '2차 각성'
            elif '초월' in desc_str:
                req_condition = '초월'

            # 식별자(PK 매핑용) 정제
            clean_job_id = re.sub(r"\s+", "", current_job_name)
            clean_display_name = re.sub(r"[<>«»神]", "", current_job_name).strip()

            jobs_data.append({
                "name": clean_job_id,
                "display_name": clean_display_name,
                "gate": current_gate,
                "job_group": current_group,
                "description": desc_str,
                "resource_type": resource_type,
                "is_limit": is_limit,
                "req_condition": req_condition
            })

            current_job_name = None
            current_desc_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 1. Gate Parsing
        # Match ex: "게이트 -C", "게이트 C", "게이트 X , Z", "[ 고대 게이트 ]"
        gate_match = re.search(r"(게이트\s*[-:]?\s*[A-Z](?:\s*,\s*[A-Z])*|고대\s*게이트)", line, re.IGNORECASE)
        if gate_match:
            _flush_job()

            raw_gate = gate_match.group(1)
            # 포맷 정규화: "게이트 -C" -> "게이트 C"
            current_gate = re.sub(r"\s*[-:]\s*", " ", raw_gate).strip()
            current_group = None

            # Gate와 같은 라인에 Group이 선언된 경우 (ex: [ 데몬 ])
            group_match = re.search(r"\[\s*(.+?)\s*\]", line)
            if group_match and "게이트" not in group_match.group(1):
                current_group = group_match.group(1).strip()
            continue

        # 2. Group Parsing (Gate 없이 독립적으로 선언되는 그룹)
        # Match ex: "환신 :", "집시 :"
        is_isolated_group = False
        for ig in ISOLATED_GROUPS:
            if line.startswith(ig):
                _flush_job()
                current_group = line.replace(":", "").strip()
                is_isolated_group = True
                break
        if is_isolated_group:
            continue

        # 3. Job Definition Parsing
        # Match ex: "다크 메이지 :", "<< 김 신 神>> :"
        if ":" in line:
            parts = line.split(":", 1)
            left_part = parts[0].strip()
            right_part = parts[1].strip()

            # 문장 내 콜론(:) 예외 처리 (설명문 내의 콜론 배제)
            if len(left_part) <= 20 and "게이트" not in left_part:
                _flush_job()
                current_job_name = left_part
                if right_part:
                    current_desc_lines.append(right_part)
                continue

        # 4. Description Accumulation
        if current_job_name:
            current_desc_lines.append(line)

    # 파싱 종료 후 마지막 버퍼 처리
    _flush_job()

    return jobs_data

# Usage Example:
# with open('discord_post_raw.txt', 'r', encoding='utf-8') as f:
#     raw_text = f.read()
# parsed_list = parse_discord_jobs(raw_text)
# print(parsed_list)