/**
 * Index Page Controller
 * 메인 대시보드 구성 요소 및 데이터 바인딩 관리
 */

document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

function initDashboard() {
    // 모든 페이지 공통 실행
    updateUserAuthUI();

    // 메인 대시보드(index.html)에서만 실행
    if (document.getElementById('status-indicator')) updateServerStatus();
    if (document.getElementById('latest-posts')) loadLatestPosts();
    if (document.getElementById('recent-reviews')) loadRecentReviews();
}

/**
 * 서버 통계 데이터 업데이트
 */
async function updateServerStatus() {
    try {
        const response = await fetch('/api/v1/server/status');
        const data = await response.json();

        const statusEl = document.getElementById('status-indicator');
        const playerEl = document.getElementById('player-count');

        if (data.online) {
            statusEl.textContent = 'ONLINE';
            statusEl.classList.add('online');
            playerEl.textContent = `${data.players.online} / ${data.players.max}`;
        } else {
            statusEl.textContent = 'OFFLINE';
            statusEl.classList.add('offline');
        }
    } catch (error) {
        console.error('Server status fetch failed');
    }
}

/**
 * 마크다운 문법 제거 유틸리티
 */
function stripMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/(\*\*|__)(.*?)\1/g, '$2') // 굵게/기울임
        .replace(/~~(.*?)~~/g, '$1') // 취소선
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1') // 링크 텍스트
        .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '') // 이미지
        .replace(/#{1,6}\s?/g, '') // 헤더
        .replace(/>\s?/g, '') // 인용구
        .replace(/`{1,3}[^`]*`{1,3}/g, '') // 코드 블럭
        .replace(/\n/g, ' ') // 줄바꿈을 공백으로
        .trim();
}

/**
 * 사이드바 최신 글 요약 로드
 */
async function loadLatestPosts() {
    const container = document.getElementById('latest-posts');
    try {
        const response = await fetch('/api/v1/boards/recent');
        if (!response.ok) throw new Error('Network response error');
        const posts = await response.json();

        if (posts.length === 0) {
            container.innerHTML = '<li class="placeholder">최근 업데이트가 없습니다.</li>';
            return;
        }

        container.innerHTML = posts.map(post => {
            const dateStr = new Date(post.created_at).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' });
            const tagLabel = post.type === 'notice' ? `[${post.tag}]` : '[이벤트]';
            const cleanText = stripMarkdown(post.content);
            const snippet = cleanText.length > 35 ? cleanText.substring(0, 35) + '...' : cleanText;
            const targetUrl = post.type === 'notice' ? '/notice' : '/event';

            return `
                <li style="cursor: pointer; padding: 10px 0; border-bottom: 1px solid #1e1e3a;" onclick="location.href='${targetUrl}'">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                        <span style="color: #c89b3c; font-size: 0.8rem; font-weight: bold;">${tagLabel}</span>
                        <span style="color: #666; font-size: 0.75rem;">${dateStr}</span>
                    </div>
                    <div style="color: #ccc; font-size: 0.85rem; line-height: 1.4;">${snippet}</div>
                </li>
            `;
        }).join('');
    } catch (error) {
        container.innerHTML = '<li class="placeholder" style="color: #e74c3c;">업데이트를 불러오지 못했습니다.</li>';
    }
}

/**
 * 사이드바 최근 직업 평가 로드 (최대 3개)
 */
async function loadRecentReviews() {
    const container = document.getElementById('recent-reviews');
    try {
        const response = await fetch('/api/v1/jobs/reviews/recent');
        if (!response.ok) throw new Error('Network response error');
        const reviews = await response.json();

        if (reviews.length === 0) {
            container.innerHTML = '<p class="placeholder">최근 평가가 없습니다.</p>';
            return;
        }

        container.innerHTML = reviews.map(r => {
            const dateStr = new Date(r.created_at).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' });
            return `
                <div class="review-card" style="padding: 12px; background: #13132b; border: 1px solid #1e1e3a; border-radius: 8px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <div>
                            <span style="color: #c89b3c; font-size: 0.85rem;">${'★'.repeat(r.rating)}</span>
                            <span style="color: #888; font-size: 0.8rem; margin-left: 6px;">${r.job_name}</span>
                        </div>
                        <span style="color: #666; font-size: 0.75rem;">${dateStr}</span>
                    </div>
                    <div style="color: #eee; font-size: 0.85rem; line-height: 1.4; margin-bottom: 6px;">
                        ${r.comment}
                    </div>
                    <div style="text-align: right; color: #555; font-size: 0.75rem;">
                        - ${r.nickname}
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        container.innerHTML = '<p class="placeholder" style="color: #e74c3c;">평가를 불러오지 못했습니다.</p>';
    }
}

/**
 * 로그인 상태에 따른 헤더 UI 전환
 */
async function updateUserAuthUI() {
    const area = document.getElementById('user-status-area');

    try {
        const response = await fetch('/api/v1/auth/me');
        const session = await response.json();

        if (session.is_logged_in) {
            area.innerHTML = `
                <div class="user-card logged-in">
                    <div class="user-meta" style="display: flex; gap: 8px; align-items: center;">
                        <span class="user-job-tag" style="color: #c89b3c; font-size: 0.75rem; border: 1px solid #c89b3c; padding: 2px 6px; border-radius: 4px;">${session.job_name}</span>
                        <span class="user-nick" style="font-weight: bold;">${session.nickname}</span>
                        <button onclick="logout()" style="background: none; border: none; color: #8b8b8b; font-size: 0.7rem; cursor: pointer; margin-left: 8px;">로그아웃</button>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Auth check failed:', error);
    }
}

/**
 * 로그아웃 처리
 */
async function logout() {
    try {
        const response = await fetch('/api/v1/auth/logout', {
            method: 'POST'
        });

        if (response.ok) {
            location.reload();
        } else {
            console.error('Logout failed');
        }
    } catch (error) {
        console.error('Network error during logout:', error);
    }
}