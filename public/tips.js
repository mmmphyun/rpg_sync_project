let currentCategory = 'BUILD';
let currentPage = 1;
let currentEditingId = null;
let currentUser = null;
let openAccordionIds = new Set();

document.addEventListener('DOMContentLoaded', () => {
    loadTips();
    setupFilters();
});

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g,
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

function setupFilters() {
    const buttons = document.querySelectorAll('.tag-btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            buttons.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');

            currentCategory = e.target.getAttribute('data-category');
            currentPage = 1;
            openAccordionIds.clear();

            const writeBtn = document.getElementById('writeTipBtn');
            writeBtn.style.display = (currentCategory === 'QNA') ? 'block' : 'none';

            loadTips();
        });
    });
}

async function loadTips() {
    if (!currentUser) {
        const userResp = await fetch('/api/v1/auth/me');
        currentUser = await userResp.json();
    }

    const response = await fetch(`/api/v1/tips/?category=${currentCategory}&page=${currentPage}`);
    const data = await response.json();
    renderTips(data.tips);
}

function renderTips(tips) {
    const feedArea = document.getElementById('feedArea');
    if (!tips || tips.length === 0) {
        feedArea.innerHTML = '<p style="color: #888; text-align: center;">등록된 게시글이 없습니다.</p>';
        return;
    }

    feedArea.innerHTML = tips.map(tip => {
        const dateStr = new Date(tip.created_at).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
        const isAuthor = String(currentUser.discord_id) === String(tip.author_id);
        const isAdmin = currentUser.server_role === 'admin';

        // 버튼 노출 제어
        const showControls = (tip.category === 'QNA' && (isAuthor || isAdmin));
        const controlButtons = showControls ? `
            <div style="display: flex; gap: 10px; align-items: center;">
                ${isAuthor ? `<span onclick="openEditModal(event, ${tip.tip_id}, \`${escapeHTML(tip.title)}\`, \`${escapeHTML(tip.content)}\`)" style="cursor:pointer; color:#3498db; font-size:0.8rem;">수정</span>` : ''}
                <span onclick="deleteTip(${tip.tip_id})" style="cursor:pointer; color:#e74c3c; font-size:0.8rem;">삭제</span>
            </div>
        ` : '';

        // 유튜브 iframe 임베드 생성
        let youtubeHtml = '';
        if (tip.youtube_urls && Array.isArray(tip.youtube_urls) && tip.youtube_urls.length > 0) {
            youtubeHtml = tip.youtube_urls.map(url => {
                const videoIdMatch = url.match(/(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))([^&?\n]+)/);
                if (videoIdMatch && videoIdMatch[1]) {
                    return `<iframe width="100%" height="315" src="https://www.youtube.com/embed/${videoIdMatch[1]}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="margin-top: 10px; border-radius: 8px;"></iframe>`;
                }
                return '';
            }).join('');
        }

        // 본문 마크다운 파싱 적용
        const parsedContent = marked.parse(tip.content, { breaks: true });

        return `
            <div class="tip-card" style="background: #15151e; border: 1px solid #2a2a3a; border-radius: 8px; overflow: hidden; margin-bottom: 10px;">
                <div class="tip-header" style="padding: 15px 20px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; background: #1a1a24;">
                    <div onclick="toggleAccordion(${tip.tip_id})" style="flex-grow: 1;">
                        <strong style="color: #fff; font-size: 1.05rem;">${escapeHTML(tip.title)}</strong>
                        <span style="color: #999; font-size: 0.85rem; margin-left: 15px;">${escapeHTML(tip.author_nickname)}</span>
                        <span style="color: #666; font-size: 0.85rem; margin-left: 10px;">${dateStr}</span>
                    </div>
                    ${controlButtons}
                </div>
                <div id="tip-body-${tip.tip_id}" style="display: none; padding: 20px; border-top: 1px solid #2a2a3a; color: #ccc;">
                    <div class="tip-content">${parsedContent}</div>
                    ${youtubeHtml}

                    <hr style="border: 0; border-top: 1px solid #2a2a3a; margin: 20px 0;">
                    <div id="comment-area-${tip.tip_id}">
                        <div id="comment-list-${tip.tip_id}" style="margin-bottom: 15px;"></div>
                        <div style="display: flex; gap: 10px;">
                            <input type="text" id="comment-input-${tip.tip_id}" placeholder="댓글을 남겨보세요" style="flex-grow: 1; padding: 8px; background: #0f0f15; color: #fff; border: 1px solid #333; border-radius: 4px;" onkeypress="if(event.key==='Enter') submitComment(${tip.tip_id})">
                            <button onclick="submitComment(${tip.tip_id})" style="padding: 8px 16px; background: #3498db; color: #fff; border: none; border-radius: 4px; cursor: pointer;">등록</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    openAccordionIds.forEach(id => {
        const body = document.getElementById(`tip-body-${id}`);
        if (body) {
            body.style.display = 'block';
            loadComments(id);
        }
    });
}

function toggleAccordion(tipId) {
    const body = document.getElementById(`tip-body-${tipId}`);
    if (body.style.display === 'none' || body.style.display === '') {
        body.style.display = 'block';
        openAccordionIds.add(tipId);
        loadComments(tipId);
    } else {
        body.style.display = 'none';
        openAccordionIds.delete(tipId);
    }
}

function openWriteModal() {
    currentEditingId = null;
    document.getElementById('writeModal').style.display = 'flex';
    document.querySelector('#writeModal h3').innerText = "Q&A 작성";

    const submitBtn = document.querySelector('#writeModal button[onclick="submitTip()"]');
    if (submitBtn) submitBtn.innerText = "등록하기";
}

function openEditModal(event, tipId, title, content) {
    event.stopPropagation();

    currentEditingId = tipId;
    document.getElementById('tipTitleInput').value = title;
    document.getElementById('tipContentInput').value = content;
    document.getElementById('writeModal').style.display = 'flex';
    document.querySelector('#writeModal h3').innerText = "게시글 수정";

    const submitBtn = document.querySelector('#writeModal button[onclick="submitTip()"]');
    if (submitBtn) submitBtn.innerText = "수정 적용";
}

function closeWriteModal() {
    document.getElementById('writeModal').style.display = 'none';
    document.getElementById('tipTitleInput').value = '';
    document.getElementById('tipContentInput').value = '';
}

async function submitTip() {
    const title = document.getElementById('tipTitleInput').value.trim();
    const content = document.getElementById('tipContentInput').value.trim();

    const method = currentEditingId ? 'PATCH' : 'POST';
    const url = currentEditingId ? `/api/v1/tips/${currentEditingId}` : '/api/v1/tips/';

    if (!title || !content) {
        alert("제목과 본문을 모두 입력해주세요.");
        return;
    }

    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content })
        });

        if (response.ok) {
            alert(currentEditingId ? "수정되었습니다." : "등록되었습니다.");
            closeWriteModal();
            loadTips();
        } else {
            const err = await response.json();
            alert(`오류: ${err.detail || "등록 실패"}`);
        }
    } catch (error) {
        console.error("Submit error:", error);
        alert("네트워크 오류가 발생했습니다.");
    }
}

async function loadComments(tipId) {
    try {
        const response = await fetch(`/api/v1/tips/${tipId}/comments`);
        const data = await response.json();
        const listArea = document.getElementById(`comment-list-${tipId}`);

        if (!data.comments || data.comments.length === 0) {
            listArea.innerHTML = '<p style="color: #666; font-size: 0.85rem;">첫 번째 댓글을 남겨보세요.</p>';
            return;
        }

        listArea.innerHTML = data.comments.map(c => {
            const isCommentAuthor = currentUser && String(currentUser.discord_id) === String(c.author_id);
            const isAdmin = currentUser && currentUser.server_role === 'admin';
            return `
                <div style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px dotted #2a2a3a;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <strong style="color: #bbb; font-size: 0.9rem;">${escapeHTML(c.author_nickname)}</strong>
                        <span style="color: #666; font-size: 0.8rem;">${c.created_at}</span>
                    </div>
                    <div style="color: #ddd; font-size: 0.95rem;">
                        ${escapeHTML(c.content)}
                        ${(isCommentAuthor || isAdmin) ? `<span onclick="deleteComment(${c.comment_id}, ${tipId})" style="cursor:pointer; color:#e74c3c; margin-left:10px; font-size: 0.8rem;">[삭제]</span>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) {
        console.error(e);
    }
}

async function submitComment(tipId) {
    const input = document.getElementById(`comment-input-${tipId}`);
    const content = input.value.trim();
    if (!content) return;

    try {
        const response = await fetch(`/api/v1/tips/${tipId}/comments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content })
        });

        if (response.ok) {
            input.value = '';
            loadComments(tipId); // 페이지 전체 리로드 없이 댓글 영역만 갱신
        } else {
            alert("댓글 등록에 실패했습니다.");
        }
    } catch (error) {
        console.error(error);
    }
}

async function deleteTip(tipId) {
    if (!confirm("게시글을 삭제하시겠습니까?")) return;
    try {
        const response = await fetch(`/api/v1/tips/${tipId}`, { method: 'DELETE' });
        if (response.ok) {
            openAccordionIds.delete(tipId); // 삭제 시 상태 해제
            loadTips();
        } else {
            alert("삭제 권한이 없거나 실패했습니다.");
        }
    } catch (e) {
        console.error(e);
    }
}

async function deleteComment(commentId, tipId) {
    if (!confirm("댓글을 삭제하시겠습니까?")) return;
    const resp = await fetch(`/api/v1/tips/${tipId}/comments/${commentId}`, { method: 'DELETE' });
    if (resp.ok) loadComments(tipId);
}