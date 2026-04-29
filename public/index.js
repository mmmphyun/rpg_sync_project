/**
 * Index Page Controller
 * 메인 대시보드 구성 요소 및 데이터 바인딩 관리
 */

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[tag] || tag));
}

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
    if (document.getElementById('eventPopupModal')) loadEventPopup();
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
        .replace(/`{1,3}/g, '') // 코드 블럭
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
            const hasCustomTitle = post.title && post.title.trim().length > 0;
            const safeTitle = hasCustomTitle ? escapeHTML(post.title) : null;
            const cleanText = stripMarkdown(post.content);
            const bodySnippet = cleanText.length > 35 ? cleanText.substring(0, 35) + '...' : cleanText;
            const displayText = safeTitle || bodySnippet;
            const targetUrl = post.type === 'notice' ? '/notice' : '/event';

            return `
                <li style="cursor: pointer; padding: 10px 0; border-bottom: 1px solid #1e1e3a;" onclick="location.href='${targetUrl}'">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                        <span style="color: #c89b3c; font-size: 0.8rem; font-weight: bold;">${tagLabel}</span>
                        <span style="color: #666; font-size: 0.75rem;">${dateStr}</span>
                    </div>
                    <div style="color: #ccc; font-size: 0.85rem; line-height: 1.4;">
                        ${hasCustomTitle ? `<strong style="color: #fff;">${displayText}</strong>` : displayText}
                    </div>
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
            const isAdminRole = session.server_role === "STAFF" || session.server_role === "주인장";
            const nickColor = isAdminRole ? "#27ae60" : "#fff";

            area.innerHTML = `
                <div class="user-card logged-in">
                    <div class="user-meta" style="display: flex; gap: 8px; align-items: center;">
                        <span class="user-job-tag" style="color: #c89b3c; font-size: 0.75rem; border: 1px solid #c89b3c; padding: 2px 6px; border-radius: 4px;">${session.job_name}</span>
                        <span class="user-nick" style="font-weight: bold; color: ${nickColor};">${session.nickname}</span>
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

/**
 * 메인 이벤트 팝업 로드 및 슬라이더 로직
 */
async function loadEventPopup() {
    // 1. 자정 초기화 타이머 검증
    const hideUntil = localStorage.getItem('hidePopupUntil');
    if (hideUntil && Date.now() < parseInt(hideUntil)) return;

    try {
        const res = await fetch('/api/v1/boards/popup');
        if (!res.ok) return;
        const data = await res.json();

        // 팝업 데이터가 없거나 메시지가 반환된 경우 처리
        if (!data || !data.notice_id) return;

        const modal = document.getElementById('eventPopupModal');
        const imgContainer = document.getElementById('popupImageContainer');
        document.getElementById('popupTitle').textContent = data.title || '진행 중인 이벤트';

        let images = data.image_urls || [];
        if (images.length === 0) return; // 이미지가 없으면 팝업을 띄우지 않음

        // 2. 다중 이미지 처리 (슬라이더) 및 딥링킹 적용
        let imgHtml = '';
        if (images.length > 1) {
            imgHtml = `
                <div id="popupSlider" style="display: flex; transition: transform 0.3s ease-in-out; width: ${images.length * 100}%;">
                    ${images.map(url => `
                        <div style="width: ${100 / images.length}%; flex-shrink: 0; cursor: pointer;" onclick="location.href='/event?id=${data.notice_id}'">
                            <img src="${url}" style="width: 100%; height: auto; display: block; max-height: 400px; object-fit: contain; background: #000;">
                        </div>
                    `).join('')}
                </div>
                <button onclick="movePopupSlide(-1)" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); background: rgba(0,0,0,0.6); color: #fff; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-weight: bold;">&lt;</button>
                <button onclick="movePopupSlide(1)" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: rgba(0,0,0,0.6); color: #fff; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-weight: bold;">&gt;</button>
            `;
        } else {
            imgHtml = `<div style="cursor: pointer;" onclick="location.href='/event?id=${data.notice_id}'">
                <img src="${images[0]}" style="width: 100%; height: auto; display: block; max-height: 400px; object-fit: contain; background: #000;">
            </div>`;
        }

        imgContainer.innerHTML = imgHtml;
        imgContainer.dataset.currentIndex = 0;
        imgContainer.dataset.maxIndex = images.length - 1;

        modal.classList.add('open');
    } catch (e) { console.error('팝업 로드 실패', e); }
}

window.movePopupSlide = function(dir) {
    const container = document.getElementById('popupImageContainer');
    const slider = document.getElementById('popupSlider');
    if (!slider) return;

    let currentIndex = parseInt(container.dataset.currentIndex);
    const maxIndex = parseInt(container.dataset.maxIndex);

    currentIndex += dir;
    if (currentIndex < 0) currentIndex = maxIndex;
    if (currentIndex > maxIndex) currentIndex = 0;

    container.dataset.currentIndex = currentIndex;
    slider.style.transform = `translateX(-${currentIndex * (100 / (maxIndex + 1))}%)`;
};

window.closePopupModal = function() {
    document.getElementById('eventPopupModal').classList.remove('open');
};

window.closePopupForToday = function() {
    const now = new Date();
    // 실무 적용: 내일 00시 00분 00초로 만료 시간 설정
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 0);
    localStorage.setItem('hidePopupUntil', midnight.getTime());
    closePopupModal();
};