/**
 * Index Page Controller
 * 메인 대시보드 구성 요소 및 데이터 바인딩 관리
 */

document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

function initDashboard() {
    updateServerStatus();
    loadLatestPosts();
    loadRecentReviews();
    updateUserAuthUI();
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
function updateUserAuthUI() {
    const area = document.getElementById('user-status-area');
    // 세션 쿠키 존재 여부 확인 로직 필요
    const session = null;

    if (session) {
        area.innerHTML = `
            <div class="user-card logged-in">
                <img src="${session.avatar_url}" alt="avatar" class="user-avatar">
                <div class="user-meta">
                    <span class="user-nick">${session.nickname}</span>
                    <span class="user-job-tag">${session.job_name}</span>
                </div>
            </div>
        `;
    }
}