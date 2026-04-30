/**
 * Index Page Controller
 * 메인 대시보드 컴포넌트 렌더링 및 Fetch 체이닝
 */
document.addEventListener('DOMContentLoaded', () => {
    // 1. 초기 스켈레톤 렌더링
    renderSkeletons();

    // 2. 체이닝 방식 로드 (네트워크 스파이크 방지)
    // 배너 로드 -> 완료 후 서버 상태 로드 -> 완료 후 최신글 로드 -> 완료 후 리뷰 로드
    loadBanner()
        .then(() => loadServerStatus())
        .then(() => loadLatestPosts())
        .then(() => loadRecentReviews())
        .catch(err => console.error("Dashboard Load Error:", err));
});

function renderSkeletons() {
    document.getElementById('latest-posts').innerHTML = '<li class="skeleton" style="height: 20px; margin-bottom: 10px;"></li>'.repeat(5);
    document.getElementById('recent-reviews').innerHTML = '<div class="skeleton" style="height: 60px; margin-bottom: 10px;"></div>'.repeat(3);
}

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[tag] || tag));
}

// ---------------------------------------------------------
// 위젯 로드 함수
// ---------------------------------------------------------

async function loadBanner() {
    const wrapper = document.getElementById('banner-wrapper');

    try {
        const response = await fetch('/api/v1/banners/');
        if (!response.ok) throw new Error('Banner load failed');

        const data = await response.json();

        if (!data.banners || data.banners.length === 0) {
            wrapper.innerHTML = '<div class="swiper-slide" style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--text-muted); background:var(--bg-surface);">표시할 배너가 없습니다.</div>';
            return;
        }

        wrapper.innerHTML = data.banners.map(b => {
            const bgStyle = `display:block; width:100%; height:100%; background-image:url('${escapeHTML(b.image_url)}'); background-size:cover; background-position:center;`;

            if (b.link_url && b.link_url.trim() !== '') {
                return `
                    <div class="swiper-slide">
                        <a href="${escapeHTML(b.link_url)}" target="_blank" rel="noopener noreferrer" style="${bgStyle} text-decoration:none;"></a>
                    </div>
                `;
            } else {
                return `
                    <div class="swiper-slide">
                        <div style="${bgStyle}"></div>
                    </div>
                `;
            }
        }).join('');

        new Swiper('#hero-swiper', {
            loop: data.banners.length > 1,
            autoplay: {
                delay: 5000,
                disableOnInteraction: false,
            },
            pagination: {
                el: '.swiper-pagination',
                clickable: true,
            },
            navigation: {
                nextEl: '.swiper-button-next',
                prevEl: '.swiper-button-prev',
            },
            effect: 'fade',
            fadeEffect: { crossFade: true }
        });

    } catch (e) {
        console.error("배너 로드 실패:", e);
        wrapper.innerHTML = '<div class="swiper-slide" style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--accent-villain); background:var(--bg-surface);">배너를 불러오지 못했습니다.</div>';
    }
}

async function loadServerStatus() {
    try {
        const response = await fetch('/api/v1/server/status');
        const data = await response.json();

        const container = document.getElementById('server-status-content');
        if (data.online) {
            container.innerHTML = `<div style="color: #00F2FE; font-weight: bold; font-size: 1.2rem;">ONLINE</div>
                                   <div style="margin-top: 8px;">접속자: ${data.players.online} / ${data.players.max}</div>`;
        } else {
            container.innerHTML = `<div style="color: #E60023; font-weight: bold; font-size: 1.2rem;">OFFLINE</div>`;
        }
    } catch (e) {
        console.error("서버 상태 로드 실패");
    }
}

async function loadLatestPosts() {
    const listEl = document.getElementById('latest-posts');
    try {
        const response = await fetch('/api/v1/boards/recent?limit=5');
        const posts = await response.json();

        if (!posts || posts.length === 0) {
            listEl.innerHTML = '<li class="placeholder">최근 업데이트가 없습니다.</li>';
            return;
        }

        listEl.innerHTML = posts.map(post => {
            const dateStr = new Date(post.created_at).toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' });
            const tagColor = post.type === 'event' ? '#E60023' : '#00F2FE';
            const tagText = post.tag || (post.type === 'event' ? '이벤트' : '공지');

            let rawContent = post.content ? post.content.replace(/@[\u200B\s]*(everyone|here)/g, '').replace(/<@[!&]?\d+>/g, '').trim() : '';
            let displayTitle = post.title;

            if (!displayTitle) {
                displayTitle = rawContent.length > 50 ? rawContent.substring(0, 50) : (rawContent || '제목 없음');
            }

            return `
                <li class="widget-list-item" onclick="location.href='/${post.type}?id=${post.notice_id}'">
                    <span style="color: ${tagColor}; border: 1px solid ${tagColor}; padding: 2px 6px; font-size: 0.7rem; border-radius: 4px; margin-right: 8px; flex-shrink: 0;">${escapeHTML(tagText)}</span>
                    <span class="item-title" style="flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.85rem; transition: color 0.2s;">${escapeHTML(displayTitle)}</span>
                    <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 10px; flex-shrink: 0;">${dateStr}</span>
                </li>
            `;
        }).join('');
    } catch (e) {
        listEl.innerHTML = '<li class="placeholder" style="color: #E60023;">로드 실패</li>';
    }
}

async function loadRecentReviews() {
    const container = document.getElementById('recent-reviews');
    try {
        const response = await fetch('/api/v1/jobs/reviews/recent');
        const reviews = await response.json();

        if (!reviews || reviews.length === 0) {
            container.innerHTML = '<div class="placeholder">최근 평가가 없습니다.</div>';
            return;
        }

        container.innerHTML = reviews.map(r => `
            <div style="background: var(--bg-base); padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid var(--border-color);">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="color: #c89b3c; font-size: 0.8rem;">★ ${r.rating} | ${r.job_name}</span>
                </div>
                <div style="font-size: 0.85rem; line-height: 1.4; color: var(--text-main);">${r.comment}</div>
                <div style="text-align: right; font-size: 0.75rem; color: var(--text-muted); margin-top: 8px;">- ${r.nickname}</div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = '<div class="placeholder" style="color: #E60023;">로드 실패</div>';
    }
}