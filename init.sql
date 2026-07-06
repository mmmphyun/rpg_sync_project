-- 1. 독립 테이블 (다른 테이블을 참조하지 않음)
CREATE TABLE IF NOT EXISTS public.jobs (
    job_id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    display_name VARCHAR NOT NULL,
    gate VARCHAR,
    job_group VARCHAR,
    description TEXT,
    range_type VARCHAR DEFAULT '정보 없음'::character varying,
    position VARCHAR DEFAULT '정보 없음'::character varying,
    resource_type VARCHAR DEFAULT '정보 없음'::character varying,
    is_limit CHAR DEFAULT 'N'::bpchar,
    req_condition VARCHAR,
    img VARCHAR,
    photo_1 VARCHAR,
    photo_2 VARCHAR,
    photo_3 VARCHAR,
    photo_4 VARCHAR,
    type VARCHAR DEFAULT '정보 없음'::character varying
);

CREATE TABLE IF NOT EXISTS public.notices (
    notice_id SERIAL PRIMARY KEY,
    type VARCHAR NOT NULL DEFAULT 'notice'::character varying,
    tag VARCHAR NOT NULL DEFAULT '일반 공지'::character varying,
    content TEXT NOT NULL,
    image_urls JSONB DEFAULT '[]'::jsonb,
    discord_message_id VARCHAR NOT NULL UNIQUE,
    author_id VARCHAR NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    title VARCHAR DEFAULT NULL::character varying
);

CREATE TABLE IF NOT EXISTS public.banners (
    id SERIAL PRIMARY KEY,
    image_url TEXT NOT NULL,
    link_url TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.tips (
    tip_id SERIAL PRIMARY KEY,
    category VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    content TEXT NOT NULL,
    image_urls JSONB DEFAULT '[]'::jsonb,
    youtube_urls JSONB DEFAULT '[]'::jsonb,
    discord_thread_id VARCHAR UNIQUE DEFAULT NULL::character varying,
    author_id VARCHAR NOT NULL,
    is_deleted BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. 1차 종속 테이블 (jobs 및 tips 테이블을 참조)
CREATE TABLE IF NOT EXISTS public.users (
    discord_id VARCHAR NOT NULL PRIMARY KEY,
    nickname VARCHAR NOT NULL,
    server_role VARCHAR,
    current_job_id INTEGER REFERENCES public.jobs(job_id),
    is_guide_completed BOOLEAN DEFAULT false,
    minecraft_uuid VARCHAR UNIQUE,
    minecraft_username VARCHAR UNIQUE,
    bypass_voice_check BOOLEAN DEFAULT false
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
    weapon_name VARCHAR NOT NULL,
    weapon_type VARCHAR DEFAULT '기타'::character varying
);

CREATE TABLE IF NOT EXISTS public.tip_comments (
    comment_id SERIAL PRIMARY KEY,
    tip_id INTEGER NOT NULL REFERENCES public.tips(tip_id) ON DELETE CASCADE,
    parent_comment_id INTEGER REFERENCES public.tip_comments(comment_id) ON DELETE CASCADE,
    author_id VARCHAR NOT NULL,
    content TEXT NOT NULL,
    is_deleted BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. 2차 종속 테이블 (users, jobs, weapons 등을 참조)
CREATE TABLE IF NOT EXISTS public.job_reviews (
    review_id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES public.jobs(job_id),
    discord_id VARCHAR NOT NULL REFERENCES public.users(discord_id),
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_job_user_review UNIQUE (job_id, discord_id)
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
    is_mobility CHAR DEFAULT 'N'::bpchar,
    form_name VARCHAR
);

CREATE TABLE IF NOT EXISTS public.system_configs (
    config_key VARCHAR NOT NULL PRIMARY KEY,
    config_value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);