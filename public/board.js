/**
 * Board Controller (Notice & Event)
 */

// =============================================
//  State & Configurations
// =============================================
const API_BASE = '/api/v1/boards';
const BOARD_TYPE = window.BOARD_TYPE; // 'notice' or 'event'
let currentPage = 1;
let currentTag = "";
let isAdmin = false;

// =============================================
//  Core Logic
// =============================================

async function checkAuthAndLoad() {
    try {
        const res = await fetch('/api/v1/auth/me');
        const auth = await res.json();
        // server_role이 STAFF 또는 주인장인 경우 관리자로 판정
        if (auth.is_logged_in && (auth.server_role === "STAFF" || auth.server_role === "주인장")) {
            isAdmin = true;
        }
    } catch (e) {
        console.error("권한 확인 실패", e);
    }
    loadFeed(1);
}

async function loadFeed(page) {
    const feedArea = document.getElementById("feedArea");
    feedArea.innerHTML = '<div style="text-align:center; color:#888;">게시글을 불러오는 중입니다...</div>';

    let url = `${API_BASE}/${BOARD_TYPE}?page=${page}`;
    if (currentTag) url += `&tag=${encodeURIComponent(currentTag)}`;

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error("API 요청 실패");
        const data = await res.json();

        renderFeed(data.notices);
        renderPagination(data.page, data.notices.length < 5); // 5개 미만이면 다음 페이지 없음
        currentPage = page;

    } catch (e) {
        feedArea.innerHTML = '<div style="text-align:center; color:#e74c3c;">게시글을 불러오지 못했습니다.</div>';
    }
}

function renderFeed(notices) {
    const feedArea = document.getElementById("feedArea");
    if (!notices || notices.length === 0) {
        feedArea.innerHTML = '<div style="text-align:center; color:#555; padding: 40px; background: #13132b; border-radius: 8px;">게시글이 없습니다.</div>';
        return;
    }

    // marked.js 옵션 설정 (안전한 렌더링)
    marked.setOptions({
        breaks: true, // 줄바꿈 허용
        gfm: true
    });

    const html = notices.map(notice => {
        const dateStr = new Date(notice.created_at).toLocaleString('ko-KR');
        const parsedContent = marked.parse(notice.content || "");

        let imagesHtml = "";
        if (notice.image_urls && notice.image_urls.length > 0) {
            imagesHtml = `<div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:15px;">
                ${notice.image_urls.map(url => `<img src="${url}" style="max-width:200px; max-height:200px; border-radius:8px; cursor:pointer;" onclick="openLightbox('${url}')">`).join('')}
            </div>`;
        }

        // 관리자용 컨트롤 패널
        let adminPanel = "";
        if (isAdmin) {
            const oppositeType = BOARD_TYPE === 'notice' ? 'event' : 'notice';
            const oppositeLabel = BOARD_TYPE === 'notice' ? '이벤트로 이관' : '공지로 이관';

            adminPanel = `
                <div style="margin-top: 15px; padding-top: 10px; border-top: 1px solid #333; display: flex; gap: 10px; justify-content: flex-end;">
                    <button onclick="changeNoticeType(${notice.notice_id}, '${oppositeType}')" style="background: #27ae60; color: #fff; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">${oppositeLabel}</button>
                    ${BOARD_TYPE === 'notice' ? `<button onclick="promptTagChange(${notice.notice_id}, '${notice.tag}')" style="background: #3498db; color: #fff; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">태그 변경</button>` : ''}
                    <button onclick="deleteNotice(${notice.notice_id})" style="background: #e74c3c; color: #fff; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">삭제</button>
                </div>
            `;
        }

        return `
            <div class="card" style="padding: 24px; background: #13132b; border: 1px solid #1e1e3a; border-radius: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 15px; border-bottom: 1px solid #1e1e3a; padding-bottom: 10px;">
                    <span style="color: #c89b3c; font-weight: bold; font-size: 0.85rem;">
                        ${BOARD_TYPE === 'notice' ? `[${notice.tag}]` : 'EVENT'}
                    </span>
                    <span style="color: #666; font-size: 0.8rem;">${dateStr}</span>
                </div>
                <div style="color: #ccc; line-height: 1.6; font-size: 0.95rem;">
                    ${parsedContent}
                </div>
                ${imagesHtml}
                ${adminPanel}
            </div>
        `;
    }).join("");

    feedArea.innerHTML = html;
}

function renderPagination(currentPage, isLastPage) {
    const pageArea = document.getElementById("paginationArea");
    let html = "";

    // 이전 페이지
    if (currentPage > 1) {
        html += `<button onclick="loadFeed(${currentPage - 1})" style="padding: 6px 12px; background: #1e1e3a; color: #fff; border: 1px solid #333; border-radius: 4px; cursor: pointer;">&lt; 이전</button>`;
    }

    // 현재 페이지 표시
    html += `<button style="padding: 6px 12px; background: #c89b3c; color: #0a0a1a; border: 1px solid #c89b3c; border-radius: 4px; font-weight: bold;">${currentPage}</button>`;

    // 다음 페이지 (API에서 total count를 주지 않으므로, 받아온 배열 크기가 5개 미만이면 마지막 페이지로 간주)
    if (!isLastPage) {
         html += `<button onclick="loadFeed(${currentPage + 1})" style="padding: 6px 12px; background: #1e1e3a; color: #fff; border: 1px solid #333; border-radius: 4px; cursor: pointer;">다음 &gt;</button>`;
    }

    pageArea.innerHTML = html;
}

// =============================================
//  Admin API Calls
// =============================================
let currentEditNoticeId = null

async function changeNoticeType(id, targetType) {
    if (!confirm(`이 게시글을 ${targetType === 'event' ? '이벤트' : '공지사항'} 게시판으로 이동하시겠습니까?`)) return;
    try {
        const res = await fetch(`${API_BASE}/${id}/type?target_type=${targetType}`, { method: 'PUT' });
        if (res.ok) loadFeed(currentPage);
        else alert("권한이 없거나 처리 중 오류가 발생했습니다.");
    } catch (e) { alert("통신 오류가 발생했습니다."); }
}

function promptTagChange(id, currentTag) {
    currentEditNoticeId = id;
    const select = document.getElementById("newTagSelect");

    const options = Array.from(select.options);
    const exists = options.some(opt => opt.value === currentTag);
    if (exists) select.value = currentTag;
    else select.selectedIndex = 0;

    document.getElementById("tagModal").classList.add("open");
}

function closeTagModal() {
    document.getElementById("tagModal").classList.remove("open");
    currentEditNoticeId = null;
}

async function submitTagChange() {
    if (!currentEditNoticeId) return;
    const newTag = document.getElementById("newTagSelect").value;

    try {
        const res = await fetch(`${API_BASE}/${currentEditNoticeId}/tag?target_tag=${encodeURIComponent(newTag)}`, { method: 'PUT' });
        if (res.ok) {
            closeTagModal();
            loadFeed(currentPage);
        } else {
            alert("권한이 없거나 처리 중 오류가 발생했습니다.");
        }
    } catch (e) {
        alert("통신 오류가 발생했습니다.");
    }
}

async function deleteNotice(id) {
    if (!confirm("정말 이 게시글을 삭제하시겠습니까?\n(데이터베이스와 스토리지가 최적화됩니다)")) return;
    try {
        const res = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' });
        if (res.ok) loadFeed(currentPage);
        else alert("권한이 없거나 삭제 중 오류가 발생했습니다.");
    } catch (e) { alert("통신 오류가 발생했습니다."); }
}

// =============================================
//  Event Listeners
// =============================================

// 태그 필터 버튼 클릭 이벤트
document.querySelectorAll(".tag-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tag-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentTag = btn.dataset.tag;
        loadFeed(1);
    });
});

// Lightbox
function openLightbox(src) {
    const lb = document.getElementById("lightbox");
    lb.querySelector("img").src = src;
    lb.classList.add("open");
}

document.addEventListener("click", e => {
    if (e.target.closest(".lightbox")) {
        document.getElementById("lightbox").classList.remove("open");
    }
});

// Initialize
document.addEventListener("DOMContentLoaded", checkAuthAndLoad);