# SPEC

§G: system_configs 테이블 닉네임 양식 JSON 설정 기반 동적 파싱 & 관리 슬래시 명령어 추가

§C
- system_configs table: key VARCHAR PK & value JSONB
- auto insert default config (part_count=2, delimiter='ㅣ', nickname_index=1, job_index=2) on startup
- parse target: nickname & current_job_id & server_role ONLY. other parts (e.g. life job) → skip
- cross verify staff role with Discord API
- !유저동기화 → keep minecraft_uuid, minecraft_username, is_guide_completed, bypass_voice_check
- job parsing None → keep db current_job_id (prevent NULL overwrite)

§I
- cmd: `/닉네임양식설정 <part_count> <nickname_index> <job_index> [delimiter] [staff_index]` (STAFF only)
- cmd: `!유저동기화` (ADMIN only)
- db: public.system_configs table

§V
- V1: config change → update memory cache immediately
- V2: parsed job None → keep existing current_job_id in db
- V3: part_count mismatch → skip member sync, prevent crash
- V4: STAFF verify → check Discord role STAFF_ROLE_ID

§T
id|status|task|cites
T1|x|create system_configs table & init default config|C
T2|x|impl nickname_format db query in nickname_format.py|C
T3|x|refactor text_parser.py parse_user_nickname using dynamic config|C,V2
T4|x|impl /닉네임양식설정 slash command & reload cache|I,V1,V4
T5|.|refactor bulk_sync_cmd.py for skip mismatch & protect data|I,V2,V3
T6|.|mount /닉네임양식설정 cog & load cache on bot startup|V1

§B
id|date|cause|fix
