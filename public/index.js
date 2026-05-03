/**
 * Index Page Controller
 * 메인 대시보드 컴포넌트 렌더링 및 Fetch 체이닝
 */
document.addEventListener('DOMContentLoaded', () => {
    renderSkeletons();

    if (document.getElementById('eventPopupModal')) {
        loadEventPopup();
    }

    loadBanner()
        .then(() => loadLatestPosts())
        .then(() => loadRecentReviews())
        .then(() => loadServerStatus())
        .catch(err => console.error("Dashboard Load Error:", err));
});

function renderSkeletons() {
    const statusContainer = document.getElementById('server-status-content');
    if (statusContainer) {
        statusContainer.style.display = 'flex';
        statusContainer.style.flexDirection = 'column';
        statusContainer.innerHTML = `
            <div>
                <div style="color: var(--text-muted); font-weight: bold; font-size: 1.2rem;">CHECKING...</div>
                <div style="margin-top: 8px; color: var(--text-muted);">서버 상태 확인 중</div>
            </div>
            <div class="server-status-actions" style="opacity: 0.3; pointer-events: none;">
                <div class="status-btn btn-discord-icon" style="background: var(--border-color);">
                    <i class="ra ra-speech-bubble"></i>
                </div>
                <div class="status-btn btn-guide" style="border-color: var(--border-color); color: var(--border-color);">
                    데이터 불러오는 중...
                </div>
            </div>
        `;
    }

    const postsContainer = document.getElementById('latest-posts');
    if (postsContainer) {
        postsContainer.innerHTML = '<li class="skeleton" style="height: 34px; margin-bottom: 8px; border-radius: 4px; list-style: none;"></li>'.repeat(5);
    }

    const reviewsContainer = document.getElementById('recent-reviews');
    if (reviewsContainer) {
        reviewsContainer.innerHTML = '<div class="skeleton" style="height: 97px; margin-bottom: 10px; border-radius: 8px;"></div>'.repeat(2);
    }
}

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[tag] || tag));
}

function stripMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/(\*\*|__)(.*?)\1/g, '$2')
        .replace(/~~(.*?)~~/g, '$1')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')
        .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '')
        .replace(/#{1,6}\s?/g, '')
        .replace(/>\s?/g, '')
        .replace(/`{1,3}/g, '')
        .replace(/\n/g, ' ')
        .trim();
}

function getTagThemeForIndex(tag, type) {
    if (type === 'event') return { color: '#e056fd', bg: 'rgba(224, 86, 253, 0.1)' };
    switch(tag) {
        case '업데이트': return { color: '#2ecc71', bg: 'rgba(46, 204, 113, 0.1)' };
        case '서버 상태 공지': return { color: '#e74c3c', bg: 'rgba(231, 76, 60, 0.1)' };
        case '직업 공지': return { color: '#f1c40f', bg: 'rgba(241, 196, 15, 0.1)' };
        case '시스템 공지': return { color: '#9b59b6', bg: 'rgba(155, 89, 182, 0.1)' };
        case '일반 공지': default: return { color: '#3498db', bg: 'rgba(52, 152, 219, 0.1)' };
    }
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

        container.style.display = 'flex';
        container.style.flexDirection = 'column';

        let statusHtml = `<div>`;
        if (data.online) {
            statusHtml += `<div style="color: var(--accent-hero); font-weight: bold; font-size: 1.2rem;">ONLINE</div>
                           <div style="margin-top: 8px;">접속자: ${data.players.online} / ${data.players.max}</div>`;
        } else {
            statusHtml += `<div style="color: var(--accent-villain); font-weight: bold; font-size: 1.2rem;">OFFLINE</div>`;
        }
        statusHtml += `</div>`;

        statusHtml += `
            <div class="server-status-actions">
                <a href="https://discord.gg/jjqMWF5drb" target="_blank" class="status-btn btn-discord-icon" title="공식 디스코드">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 127.14 96.36" fill="currentColor" style="width: 22px; height: 22px;">
                        <path d="M107.7,8.07A105.15,105.15,0,0,0,81.47,0a72.06,72.06,0,0,0-3.36,6.83A97.68,97.68,0,0,0,49,6.83,72.37,72.37,0,0,0,45.64,0,105.89,105.89,0,0,0,19.39,8.09C2.79,32.65-1.71,56.6.54,80.21h0A105.73,105.73,0,0,0,32.71,96.36,77.7,77.7,0,0,0,39.6,85.25a68.42,68.42,0,0,1-10.85-5.18c.91-.66,1.8-1.34,2.66-2a75.57,75.57,0,0,0,64.32,0c.87.71,1.76,1.39,2.66,2a68.68,68.68,0,0,1-10.87,5.19,77,77,0,0,0,6.89,11.1A105.25,105.25,0,0,0,126.6,80.22h0C129.24,52.84,122.09,29.11,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53s5-12.74,11.43-12.74S54,46,53.89,53,48.84,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.31,60,73.31,53s5-12.74,11.43-12.74S96.1,46,96,53,91,65.69,84.69,65.69Z"/>
                    </svg>
                </a>
                <a href="/guide" class="status-btn btn-guide">
                    서버가 처음이신가요?
                </a>
            </div>
        `;

        container.innerHTML = statusHtml;
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
            const tagText = post.tag || (post.type === 'event' ? '이벤트' : '공지');
            const tagTheme = getTagThemeForIndex(post.tag, post.type);

            let rawContent = post.content ? stripMarkdown(post.content.replace(/@[\u200B\s]*(everyone|here)/g, '').replace(/<@[!&]?\d+>/g, '')) : '';
            let displayTitle = post.title;

            if (!displayTitle) {
                displayTitle = rawContent.length > 50 ? rawContent.substring(0, 50) : (rawContent || '제목 없음');
            }

            return `
                <li class="widget-list-item" onclick="location.href='/${post.type}?id=${post.notice_id}'">
                    <span style="color: ${tagTheme.color}; background: ${tagTheme.bg}; border: 1px solid ${tagTheme.color}40; padding: 2px 6px; font-size: 0.7rem; border-radius: 4px; margin-right: 8px; flex-shrink: 0;">${escapeHTML(tagText)}</span>
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
        const response = await fetch('/api/v1/jobs/reviews/recent?limit=2');
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

async function loadEventPopup() {
    const hideUntil = localStorage.getItem('hidePopupUntil');
    if (hideUntil && Date.now() < parseInt(hideUntil)) return;

    const cachedPopup = sessionStorage.getItem('eventPopupCache');
    if (cachedPopup) {
        renderPopup(JSON.parse(cachedPopup));

        fetch('/api/v1/boards/popup')
            .then(res => res.json())
            .then(data => sessionStorage.setItem('eventPopupCache', JSON.stringify(data)))
            .catch(() => {});
        return;
    }

    try {
        const res = await fetch('/api/v1/boards/popup');
        if (!res.ok) return;

        const data = await res.json();
        if (!data || !data.notice_id) return;

        sessionStorage.setItem('eventPopupCache', JSON.stringify(data));
        renderPopup(data);
    } catch (e) {
        console.error('팝업 로드 실패', e);
    }
}

function renderPopup(data) {
    if (!data || !data.notice_id) return;

    const modal = document.getElementById('eventPopupModal');
    const imgContainer = document.getElementById('popupImageContainer');
    document.getElementById('popupTitle').textContent = data.title || '진행 중인 이벤트';

    let images = data.image_urls || [];
    if (images.length === 0) return;

    let imgHtml = '';
    if (images.length > 1) {
        imgHtml = `
            <div id="popupSlider" style="display: flex; transition: transform 0.4s cubic-bezier(0.25, 0.8, 0.25, 1); width: ${images.length * 100}%;">
                ${images.map(url => `
                    <div style="width: ${100 / images.length}%; flex-shrink: 0; cursor: pointer;" onclick="location.href='/event?id=${data.notice_id}'">
                        <img src="${url}" style="width: 100%; height: auto; display: block; max-height: 400px; object-fit: contain; background: rgba(11, 12, 26, 0.8);">
                    </div>
                `).join('')}
            </div>
            <button onclick="movePopupSlide(-1)" class="popup-nav-btn" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); background: rgba(11, 12, 26, 0.6); backdrop-filter: blur(4px); color: var(--text-main); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 50%; width: 36px; height: 36px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-weight: bold; transition: all 0.2s ease;">&lt;</button>
            <button onclick="movePopupSlide(1)" class="popup-nav-btn" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: rgba(11, 12, 26, 0.6); backdrop-filter: blur(4px); color: var(--text-main); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 50%; width: 36px; height: 36px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-weight: bold; transition: all 0.2s ease;">&gt;</button>
        `;
    } else {
        // 단일 이미지 렌더링
        imgHtml = `<div style="cursor: pointer;" onclick="location.href='/event?id=${data.notice_id}'">
            <img src="${images[0]}" style="width: 100%; height: auto; display: block; max-height: 400px; object-fit: contain; background: rgba(11, 12, 26, 0.8);">
        </div>`;
    }

    imgContainer.innerHTML = imgHtml;
    imgContainer.dataset.currentIndex = 0;
    imgContainer.dataset.maxIndex = images.length - 1;

    modal.classList.add('open');
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
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 0);
    localStorage.setItem('hidePopupUntil', midnight.getTime());
    closePopupModal();
};