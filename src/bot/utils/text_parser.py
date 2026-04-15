import re


def parse_discord_jobs(raw_text: str) -> list[dict]:
    """
    엄격한 표준 양식을 적용한 디스코드 직업 포스트 파서
    - 게이트: '게이트 [-+]알파벳' 또는 '고대 게이트'
    - 그룹: 게이트와 동일한 줄의 [ ] 내부 텍스트
    - 직업: '직업명 :'
    - 조건: 직업 설명 하단의 [ ] 내부 텍스트
    """
    jobs_data = []

    current_gate = "정보 없음"
    current_group = "정보 없음"
    current_job_name = None
    current_desc_lines = []
    current_condition = "정보 없음"

    RESOURCE_KEYWORDS = ["기력", "마나", "체력", "에너지"]

    lines = raw_text.split('\n')

    def _flush_job():
        nonlocal current_job_name, current_desc_lines, current_condition

        if current_job_name:
            desc_str = "\n".join(current_desc_lines).strip()

            # 자원 파싱
            resource_type = "정보 없음"
            for res in RESOURCE_KEYWORDS:
                if res in desc_str:
                    resource_type = res
                    break

            # 1인 제한 확인
            is_limit = 'Y' if '1인 제한' in desc_str or '1인 제한' in current_job_name else 'N'

            # 식별자 정제
            clean_job_id = re.sub(r"\s+", "", current_job_name)
            clean_display_name = current_job_name.strip()

            jobs_data.append({
                "name": clean_job_id,
                "display_name": clean_display_name,
                "gate": current_gate,
                "job_group": current_group,
                "description": desc_str,
                "resource_type": resource_type,
                "is_limit": is_limit,
                "req_condition": current_condition
            })

            # 변수 초기화
            current_job_name = None
            current_desc_lines = []
            current_condition = "정보 없음"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 맺음말 필터링
        if line in ["자세한 설명은 패치노트에 적어두겠습니다", "궁금한점은 DM주세용", "@everyone"]:
            continue

        # 1. Gate & Group 파싱
        # Match ex: "게이트 -C [ 데몬 ]", "게이트 A", "게이트 +B", "고대 게이트"
        gate_match = re.match(r"^(게이트\s*[-+]?[A-Za-z]|고대\s*게이트)", line)
        if gate_match:
            _flush_job()

            raw_gate = gate_match.group(1)
            current_gate = re.sub(r"\s*[-+]\s*", " ", raw_gate).strip()
            current_group = "정보 없음"

            # 같은 줄에 존재하는 그룹명 [ ] 추출
            group_match = re.search(r"\[(.*?)\]", line[len(raw_gate):])
            if group_match:
                current_group = group_match.group(1).strip()
            continue

        # 2. 직업 파싱
        # Match ex: "환신 :", "다크 메이지 :"
        if ":" in line:
            parts = line.split(":", 1)
            left_part = parts[0].strip()
            right_part = parts[1].strip()

            # 문장 내 콜론 예외 처리 (설명문 내의 콜론 배제)
            if len(left_part) <= 20 and "게이트" not in left_part:
                _flush_job()
                current_job_name = left_part
                if right_part:
                    current_desc_lines.append(right_part)
                continue

        # 3. 설명 및 조건 누적 (직업명 인식 이후)
        if current_job_name:
            # 대괄호로 묶인 조건문 파싱 (예: [ 서버내 2차 각성한 계정 필요 ])
            cond_match = re.search(r"\[(.*?)\]", line)
            if cond_match:
                cond = cond_match.group(1).strip()
                if current_condition == "정보 없음":
                    current_condition = cond
                else:
                    current_condition += f" / {cond}"
            else:
                # 대괄호가 없다면 일반 설명문으로 취급
                current_desc_lines.append(line)

    # 마지막 버퍼 처리
    _flush_job()

    return jobs_data