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
 * 서버 통계 데이터 업데이트 (mcstatus 연동 예정)
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
 * 사이드바 최신 글 요약 로드
 */
function loadLatestPosts() {
    const container = document.getElementById('latest-posts');
    // TODO: FastAPI API 연동
}

/**
 * 사이드바 최근 직업 평가 로드 (최대 3개)
 */
function loadRecentReviews() {
    const container = document.getElementById('recent-reviews');
    // TODO: Supabase 연동
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