-- 1. 독립 테이블 (다른 테이블을 참조하지 않음)
CREATE TABLE IF NOT EXISTS public.jobs (
    job_id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    display_name VARCHAR NOT NULL,
    gate VARCHAR,
    job_group VARCHAR,
    description TEXT,
    range_type VARCHAR DEFAULT '정보 없음',
    position VARCHAR DEFAULT '정보 없음',
    resource_type VARCHAR DEFAULT '정보 없음',
    is_limit CHAR DEFAULT 'N',
    req_condition VARCHAR,
    img VARCHAR,
    photo_1 VARCHAR,
    photo_2 VARCHAR,
    photo_3 VARCHAR,
    photo_4 VARCHAR,
    type VARCHAR DEFAULT '정보 없음'
);

CREATE TABLE IF NOT EXISTS public.notices (
    notice_id SERIAL PRIMARY KEY,
    type VARCHAR NOT NULL DEFAULT 'notice',
    tag VARCHAR NOT NULL DEFAULT '일반 공지',
    content TEXT NOT NULL,
    image_urls JSONB DEFAULT '[]'::jsonb,
    discord_message_id VARCHAR NOT NULL UNIQUE,
    author_id VARCHAR NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. 1차 종속 테이블 (jobs를 참조)
CREATE TABLE IF NOT EXISTS public.users (
    discord_id VARCHAR NOT NULL PRIMARY KEY,
    nickname VARCHAR NOT NULL,
    server_role VARCHAR,
    current_job_id INTEGER REFERENCES public.jobs(job_id),
    last_voice_exit TIMESTAMP WITHOUT TIME ZONE,
    is_guide_completed BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS public.job_patches (
    patch_id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES public.jobs(job_id),
    patch_date VARCHAR,
    notes TEXT,
    discord_message_id BIGINT UNIQUE
);

CREATE TABLE IF NOT EXISTS public.weapons (
    weapon_id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES public.jobs(job_id),
    weapon_name VARCHAR NOT NULL
);

-- 3. 2차 종속 테이블 (users, jobs, weapons 등을 참조)
CREATE TABLE IF NOT EXISTS public.job_reviews (
    review_id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES public.jobs(job_id),
    discord_id VARCHAR NOT NULL REFERENCES public.users(discord_id),
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.magic_tokens (
    token VARCHAR NOT NULL PRIMARY KEY,
    discord_id VARCHAR NOT NULL REFERENCES public.users(discord_id),
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS public.skills (
    skill_id SERIAL PRIMARY KEY,
    weapon_id INTEGER REFERENCES public.weapons(weapon_id),
    command_key VARCHAR NOT NULL,
    skill_name VARCHAR,
    description TEXT,
    cooldown VARCHAR,
    cost_value VARCHAR,
    coefficient VARCHAR,
    is_mobility CHAR DEFAULT 'N'
);