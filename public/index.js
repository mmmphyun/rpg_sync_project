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