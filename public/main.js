/**
 * View Controller & Event Listeners
 * API 연동 기반 DOM 조작 및 사용자 인터랙션 처리
 */

// =============================================
//  Constants & Utility Functions
// =============================================
const RANGE_CLS = { "근거리": "t-melee", "원거리": "t-ranged", "근거리, 원거리": "t-hybrid", "정보 없음": "t-unknown" };
const POS_CLS   = { "탱": "t-tank", "물리": "t-phys", "마법": "t-magic", "혼합": "t-hybrid-dmg", "힐": "t-heal", "유틸": "t-util", "정보 없음": "t-unknown" };
const RES_CLS   = { "기력": "t-ki", "마나": "t-mana", "체력": "t-hp", "에너지": "t-hp", "정보 없음": "t-unknown" }; // 에너지 추가
const POS_BG    = { "탱": "bg-tank", "딜": "bg-deal", "힐": "bg-heal", "유틸": "bg-util", "정보 없음": "bg-unknown" };
const WEAPON_ICONS = {
    "대검": "ra ra-large-weapon",
    "카타나": "ra ra-sword",
    "검": "ra ra-sword",
    "단검": "ra ra-daggers",
    "활": "ra ra-bow",
    "석궁": "ra ra-crossbow",
    "지팡이": "ra ra-wand",
    "도끼": "ra ra-axe",
    "망치": "ra ra-hammer",
    "부채": "ra ra-feather-wing",
    "건틀릿": "ra ra-hand",
    "저격총": "ra ra-musket",
    "소총": "ra ra-musket",
    "권총": "ra ra-revolver",
    "표창": "ra ra-kunai",
    "창": "ra ra-spear",
    "방패": "ra ra-shield",
    "낫": "ra ra-scythe",
    "게임패드": "fa-solid fa-gamepad"
};

function posTag(pos) {
    if (!pos) return "";
    return pos.split("/").map(p => {
        const cls = POS_CLS[p] || "t-unknown";
        return `<span class="mini-tag ${cls}">${p}</span>`;
    }).join("");
}

function posTagFull(pos) {
    if (!pos) return "";
    return pos.split("/").map(p => {
        const cls = POS_CLS[p] || "t-unknown";
        return `<span class="sidebar-tag ${cls}">${p}</span>`;
    }).join("");
}

function posBg(pos) {
    if (!pos) return "bg-unknown";
    const first = pos.split("/")[0];
    return POS_BG[first] || "bg-unknown";
}

function getInitials(name) {
    const clean = name.replace(/[«»()\s]/g, "");
    return clean.slice(0, 2);
}

function escapeHTML(str) {
    if (!str) return "";
    return String(str).replace(/[&<>'"]/g, match => {
        const escapeMap = { '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' };
        return escapeMap[match];
    });
}

function formatRangeDisplay(range) {
    if (range === "근거리, 원거리" || range === "근거리,원거리") {
        return "근/원거리";
    }
    return range;
}

function getWeaponIconClass(type) {
    return WEAPON_ICONS[type] || "ra ra-sword"; // 매핑 안 된 무기는 기본 검 아이콘
}

// =============================================
//  State & DOM References
// =============================================
let JOBS = [];
const app = document.getElementById("app");
const sidebar = document.getElementById("sidebar");
const sidebarContent = document.getElementById("sidebarContent");

let currentSort = "range";
let activeFilters = {};
let selectedIdx = -1;

let currentJobReviewsPromise = null;
let currentUserNickname = null;

let currentSearchQuery = "";

// =============================================
//  Core Logic
// =============================================
function getFiltered() {
    return JOBS.filter(j => {
        if (currentSearchQuery) {
            const nameMatch = j.name.toLowerCase().includes(currentSearchQuery.toLowerCase());
            const searchNameMatch = j.searchName && j.searchName.toLowerCase().includes(currentSearchQuery.toLowerCase());

            if (!nameMatch && !searchNameMatch) return false;
        }
        for (const [key, val] of Object.entries(activeFilters)) {
            const v = j[key] || "정보 없음";
            if (key === "position" || key === "range") {
                if (!v.includes(val)) return false;
            } else {
                if (v !== val) return false;
            }
        }
        return true;
    });
}

function renderTile(job, idx) {
    const sel = idx === selectedIdx ? " selected" : "";

    const portrait = job.img
        ? `<img src="${job.img}" alt="${job.name}">`
        : getInitials(job.name);

    const lim = job.limit ? `<span class="mini-tag t-limit">1인</span>` : "";

    const hasPlayers = job.players && job.players.length > 0;
    const dot = hasPlayers ? `<div class="active-dot"></div>` : "";
    const tooltip = hasPlayers ? `<div class="player-tooltip">${job.players.join(", ")}</div>` : "";

    let typeClass = "";
    if (job.type === "영웅") typeClass = "type-hero";
    else if (job.type === "빌런") typeClass = "type-villain";

    return `<div class="champ-tile${sel}" data-idx="${idx}">
      <div class="champ-portrait ${posBg(job.position)} ${typeClass}">${portrait}${dot}</div>
      ${tooltip}
      <div class="champ-name">${job.name}</div>
      <div class="champ-mini-tags">
        <span class="mini-tag ${RANGE_CLS[job.range] || "t-unknown"}">${formatRangeDisplay(job.range)}</span>
        ${posTag(job.position)}
      </div>
      ${lim ? `<div class="champ-mini-tags">${lim}</div>` : ""}
    </div>`;
}

function renderGrid() {
    const jobs = getFiltered();
    jobs.sort((a, b) => a.name.localeCompare(b.name, 'ko'));
    document.getElementById("jobCount").textContent = jobs.length + "개 직업";

    const groupOrders = {
        gate: null,
        range: ["근거리", "원거리", "근거리, 원거리", "정보 없음"],
        position: ["탱", "물리", "마법", "혼합", "힐", "유틸", "정보 없음"],
        resource: ["기력", "마나", "체력", "에너지", "정보 없음"],
    };

    const key = currentSort;
    let html = "";

    if (key === "gate") {
        const gateMap = new Map();
        jobs.forEach(j => {
            const gateKey = j.gate || "정보 없음";
            if (!gateMap.has(gateKey)) gateMap.set(gateKey, []);
            gateMap.get(gateKey).push(j);
        });

        const gates = [...gateMap.keys()].sort((a, b) => a.localeCompare(b, "ko"));

        gates.forEach(g => {
            html += `<div class="group-label">${g} (${gateMap.get(g).length})</div>`;
            html += `<div class="champ-grid">${gateMap.get(g).map(j => renderTile(j, JOBS.indexOf(j))).join("")}</div>`;
        });
    } else {
        const order = groupOrders[key];
        const groups = new Map();
        order.forEach(v => groups.set(v, []));

        jobs.forEach(j => {
            const v = j[key] || "정보 없음";
            if (key === "position") {
                v.split("/").forEach(p => {
                    if (!groups.has(p)) groups.set(p, []);
                    groups.get(p).push(j);
                });
            } else {
                if (!groups.has(v)) groups.set(v, []);
                groups.get(v).push(j);
            }
        });

        groups.forEach((list, groupKey) => {
            if (list.length === 0) return;
            html += `<div class="group-label">${groupKey} (${list.length})</div>`;
            html += `<div class="champ-grid">${list.map(j => renderTile(j, JOBS.indexOf(j))).join("")}</div>`;
        });
    }

    app.innerHTML = html;
}

function renderWeaponsSection(jobIdx, activeWeaponIdx) {
    const job = JOBS[jobIdx];
    const weapons = job.weapons || [];

    if (weapons.length === 0) {
        return `<div style="padding: 15px; color: #888; text-align: center; background: #16161e; border-radius: 6px; margin-top: 15px;">등록된 무기 및 스킬 정보가 없습니다.</div>`;
    }

    const activeWeapon = weapons[activeWeaponIdx];

    // 1. 무기 선택 아이콘 그리드
    let tabsHtml = `<div style="display: flex; gap: 10px; margin-top: 20px; margin-bottom: 15px; overflow-x: auto; padding-bottom: 5px;">`;
    weapons.forEach((w, wIdx) => {
        const isAct = wIdx === activeWeaponIdx;
        const iconCls = getWeaponIconClass(w.weapon_type);

        tabsHtml += `
            <div onclick="changeWeapon(${jobIdx}, ${wIdx})"
                 style="flex: 1; min-width: 60px; text-align: center; padding: 10px 5px; border-radius: 8px; cursor: pointer; transition: all 0.2s;
                        background: ${isAct ? '#2a2a35' : '#16161e'};
                        border: 1px solid ${isAct ? '#c89b3c' : '#222'};">
                <i class="${iconCls}" style="font-size: 24px; color: ${isAct ? '#c89b3c' : '#666'};"></i>
                <div style="font-size: 0.7rem; margin-top: 6px; color: ${isAct ? '#ddd' : '#888'}; letter-spacing: -0.5px;">
                    ${escapeHTML(w.weapon_name)}
                </div>
            </div>
        `;
    });
    tabsHtml += `</div>`;

    // 2. 선택된 무기의 스킬 리스트 (최대 5개)
    let skillsHtml = `<div><h4 style="color: #eee; margin-bottom: 10px; font-size: 0.95rem;">보유 스킬</h4>`;
    if (activeWeapon.skills && activeWeapon.skills.length > 0) {
        const displaySkills = activeWeapon.skills.slice(0, 5); // 5개 제한
        displaySkills.forEach(s => {
            skillsHtml += `
                <div style="background: #1a1a24; border: 1px solid #2a2a35; border-radius: 6px; padding: 12px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #2a2a35; padding-bottom: 6px; margin-bottom: 8px;">
                        <strong style="color: #c89b3c; font-size: 0.9rem;">[${escapeHTML(s.command_key)}] ${escapeHTML(s.skill_name)}</strong>
                        <div style="font-size: 0.75rem; color: #888;">
                            <span style="margin-right: 8px;">⏱ ${escapeHTML(s.cooldown)}</span>
                            <span>💧 ${escapeHTML(s.cost_value)}</span>
                        </div>
                    </div>
                    <div style="font-size: 0.85rem; color: #ccc; line-height: 1.4; margin-bottom: 8px;">
                        ${escapeHTML(s.description)}
                    </div>
                    <div style="font-size: 0.75rem; color: #888; display: flex; justify-content: space-between;">
                        <span>🗡 계수: <span style="color: #aaa;">${escapeHTML(s.coefficient)}</span></span>
                        ${s.is_mobility === 'Y' ? `<span style="color: #3498db;">🏃 이동기</span>` : ''}
                    </div>
                </div>
            `;
        });
    } else {
        skillsHtml += `<div style="color:#888; font-size:0.85rem; text-align:center; padding: 15px; background: #16161e; border-radius: 6px;">스킬이 등록되지 않았습니다.</div>`;
    }
    skillsHtml += `</div>`;

    return tabsHtml + skillsHtml;
}

window.changeWeapon = function(jobIdx, weaponIdx) {
    const container = document.getElementById("weaponsAndSkillsContainer");
    if (container) {
        container.innerHTML = renderWeaponsSection(jobIdx, weaponIdx);
    }
};

function openSidebar(idx) {
    const job = JOBS[idx];
    selectedIdx = idx;
    renderGrid();

    const sidePortrait = job.img
        ? `<img src="${job.img}" alt="${job.name}">`
        : getInitials(job.name);

    const gallery = job.photos && job.photos.length > 0
        ? `<div class="sidebar-gallery">${job.photos.map(p => `<img src="${p}" alt="${job.name}" onclick="openLightbox('${p}')">`).join("")}</div>`
        : "";

    // 줄바꿈 보존을 위해 white-space: pre-wrap 적용 클래스 추가 또는 replace 활용
    const formattedDesc = job.desc ? job.desc.replace(/\n/g, '<br>') : "설명이 없습니다.";
    const reqCondition = (job.req_condition && job.req_condition !== "정보 없음")
        ? `<div style="margin-top:10px; color:#e74c3c; font-size:0.85em; font-weight:bold;">[ 조건: ${job.req_condition} ]</div>`
        : "";

    const reviewSummaryHtml = `
      <div class="sidebar-review-summary" style="margin: 10px 0; padding: 10px; background: #16161e; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;">
        <span id="sideAvgRating" style="color: #c89b3c; font-weight: bold; font-size: 0.9rem;">평점 로딩 중...</span>
        <button onclick="openReviewModal(${job.job_id}, '${job.name}')" style="background: #333; color: #fff; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">평가 보기/작성</button>
      </div>
    `;

    sidebarContent.innerHTML = `
      <button class="sidebar-close" onclick="closeSidebar()">&times;</button>
      <div class="sidebar-portrait ${posBg(job.position)}">${sidePortrait}</div>
      <div class="sidebar-name">${job.name}</div>
      ${reviewSummaryHtml}
      <div class="sidebar-gate">${job.gate}${job.group && job.group !== "정보 없음" ? ` · ${job.group}` : ""}</div>
      <div class="sidebar-tags">
        <span class="sidebar-tag ${RANGE_CLS[job.range] || "t-unknown"}">${formatRangeDisplay(job.range)}</span>
        ${posTagFull(job.position)}
        <span class="sidebar-tag ${RES_CLS[job.resource] || "t-unknown"}">${job.resource}</span>
        ${job.limit ? `<span class="sidebar-tag t-limit">1인 제한</span>` : ""}
      </div>
      <div class="sidebar-desc">${formattedDesc}${reqCondition}</div>
      ${job.patches && job.patches.length > 0 ? `
      <div class="sidebar-patches">
        <h4>패치노트</h4>
        ${job.patches.map(p => `<div class="patch-entry">
          <div class="patch-date">${p.date}</div>
          <div class="patch-notes">${p.notes.replace(/\n/g, "<br>")}</div>
        </div>`).join("")}
      </div>` : ""}
      ${gallery}
      <div id="weaponsAndSkillsContainer">
        ${renderWeaponsSection(idx, 0)} </div>`;

    currentJobReviewsPromise = fetch(`/api/v1/jobs/${job.job_id}/reviews`)
        .then(res => res.json());

    currentJobReviewsPromise
        .then(data => {
            document.getElementById('sideAvgRating').textContent = `★ ${data.avg_rating}`;
        })
        .catch(e => {
            document.getElementById('sideAvgRating').textContent = `평가 없음`;
        });

    sidebar.classList.add("open");
}

function closeSidebar() {
    sidebar.classList.remove("open");
    selectedIdx = -1;
    renderGrid();
}

function openLightbox(src) {
    const lb = document.getElementById("lightbox");
    lb.querySelector("img").src = src;
    lb.classList.add("open");
}

// =============================================
//  Review System Logic
// =============================================

/**
 * 리뷰 모달 열기 및 데이터 로드
 */
async function openReviewModal(jobId, jobName) {
    const modal = document.getElementById('reviewModal');
    const listContainer = document.getElementById('reviewList');
    const form = document.getElementById('reviewForm');
    const blocker = document.getElementById('reviewAuthBlocker');

    document.getElementById('reviewModalTitle').textContent = `${jobName} 한줄평`;
    modal.dataset.jobId = jobId;
    modal.classList.add('open');

    listContainer.innerHTML = '<div style="text-align:center; color:#888; padding:20px;">리뷰를 불러오는 중입니다...</div>';

    // 1. 로그인 상태 확인 (작성 폼 제어)
    try {
        const authRes = await fetch('/api/v1/auth/me');
        const auth = await authRes.json();

        if (auth.is_logged_in) {
            currentUserNickname = auth.nickname;
            blocker.style.display = 'none';
            form.style.display = 'flex';
        } else {
            currentUserNickname = null;
            blocker.style.display = 'block';
            form.style.display = 'none';
        }
    } catch (e) { console.error("Auth check failed", e); }

    // 2. 리뷰 목록 렌더링
    if (currentJobReviewsPromise) {
        try {
            const data = await currentJobReviewsPromise;
            renderReviewList(data);
        } catch (e) {
            listContainer.innerHTML = '<div style="color:#e74c3c; text-align:center; padding:20px;">리뷰를 불러오지 못했습니다.</div>';
        }
    } else {
        loadReviews(jobId);
    }
}

function closeReviewModal() {
    document.getElementById('reviewModal').classList.remove('open');
}

/**
 * 리뷰 목록 렌더링
 */
function renderReviewList(data) {
    const listContainer = document.getElementById('reviewList');

    if (!data.reviews || data.reviews.length === 0) {
        listContainer.innerHTML = '<div style="text-align:center; color:#555; padding:20px;">첫 번째 평점을 남겨보세요!</div>';
        return;
    }

    listContainer.innerHTML = data.reviews.map(r => `
        <div class="review-item" data-nickname="${escapeHTML(r.nickname)}" style="padding: 10px; border-bottom: 1px solid #222;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span class="review-rating" style="color:#c89b3c; font-size:0.85rem;">${'★'.repeat(r.rating)}</span>
                <span style="color:#666; font-size:0.75rem;">${escapeHTML(r.nickname)}</span>
            </div>
            <div class="review-comment-text" style="color:#eee; font-size:0.9rem; line-height:1.4;">${escapeHTML(r.comment)}</div>
        </div>
    `).join('');
}

async function loadReviews(jobId) {
    const listContainer = document.getElementById('reviewList');
    listContainer.innerHTML = '<div style="text-align:center; color:#888;">로딩 중...</div>';

    try {
        const res = await fetch(`/api/v1/jobs/${jobId}/reviews`);
        const data = await res.json();
        currentJobReviewsCache = data;
        renderReviewList(data);
    } catch (e) {
        listContainer.innerHTML = '<div style="color:#e74c3c;">리뷰를 불러오지 못했습니다.</div>';
    }
}

/**
 * 리뷰 제출 (UPSERT)
 */
async function submitReview(event) {
    event.preventDefault();
    const modal = document.getElementById('reviewModal');
    const jobId = modal.dataset.jobId;
    const rating = parseInt(document.getElementById('reviewRating').value);
    const comment = document.getElementById('reviewComment').value;

    try {
        const response = await fetch(`/api/v1/jobs/${jobId}/reviews`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rating: rating, comment: comment })
        });

        if (response.ok) {
            alert('평가가 저장되었습니다.');
            document.getElementById('reviewComment').value = '';

            const listContainer = document.getElementById('reviewList');
            const existingReview = listContainer.querySelector(`.review-item[data-nickname="${currentUserNickname}"]`);

            if (existingReview) {
                existingReview.querySelector('.review-rating').textContent = '★'.repeat(rating);
                existingReview.querySelector('.review-comment-text').textContent = comment;
            } else {
                const newReviewHtml = `
                    <div class="review-item" data-nickname="${escapeHTML(currentUserNickname)}" style="padding: 10px; border-bottom: 1px solid #222;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span class="review-rating" style="color:#c89b3c; font-size:0.85rem;">${'★'.repeat(rating)}</span>
                            <span style="color:#666; font-size:0.75rem;">${escapeHTML(currentUserNickname) || '나'}</span>
                        </div>
                        <div class="review-comment-text" style="color:#eee; font-size:0.9rem; line-height:1.4;">${escapeHTML(comment)}</div>
                    </div>
                `;
                if (listContainer.querySelector('div[style*="text-align:center"]')) {
                    listContainer.innerHTML = '';
                }
                listContainer.insertAdjacentHTML('afterbegin', newReviewHtml);
            }

            currentJobReviewsPromise = fetch(`/api/v1/jobs/${jobId}/reviews`).then(res => res.json());
            currentJobReviewsPromise.then(data => {
                document.getElementById('sideAvgRating').textContent = `★ ${data.avg_rating}`;
            });

        } else {
            const err = await response.json();
            alert(err.detail || '저장에 실패했습니다.');
        }
    } catch (e) {
        alert('네트워크 오류가 발생했습니다.');
    }
}

// =============================================
//  Event Listeners
// =============================================
app.addEventListener("click", e => {
    const tile = e.target.closest(".champ-tile");
    if (!tile) return;
    const idx = parseInt(tile.dataset.idx);
    if (idx === selectedIdx) { closeSidebar(); return; }
    openSidebar(idx);
});

document.querySelectorAll(".filter-btn:not(.tag-filter)").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".filter-btn:not(.tag-filter)").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentSort = btn.dataset.sort;
        renderGrid();
    });
});

document.querySelectorAll(".tag-filter").forEach(btn => {
    btn.addEventListener("click", () => {
        const key = btn.dataset.key;
        const val = btn.dataset.val;

        if (activeFilters[key] === val) {
            delete activeFilters[key];
            btn.classList.remove("active");
        } else {
            document.querySelectorAll(`.tag-filter[data-key="${key}"]`).forEach(b => b.classList.remove("active"));
            activeFilters[key] = val;
            btn.classList.add("active");
        }
        closeSidebar();
        renderGrid();
    });
});

document.addEventListener("click", e => {
    if (e.target.closest(".lightbox")) {
        document.getElementById("lightbox").classList.remove("open");
    }
});

const searchInput = document.getElementById("searchInput");
if (searchInput) {
    searchInput.addEventListener("input", (e) => {
        currentSearchQuery = e.target.value.trim();
        closeSidebar(); // 검색어 입력 시 열려있는 상세정보 창 닫기 (UX 표준)
        renderGrid();
    });
}

// =============================================
//  Initialize (SSR Hydration)
// =============================================
function initApp() {
    try {
        // 주입된 전역 변수 참조
        if (window.INITIAL_JOBS_DATA) {
            JOBS = window.INITIAL_JOBS_DATA;
            renderGrid();
        } else {
            throw new Error("서버로부터 초기 데이터를 전달받지 못했습니다.");
        }
    } catch (error) {
        console.error("데이터 초기화 중 오류 발생:", error);
        app.innerHTML = `<div style="text-align:center; padding:50px; color:#e74c3c;">데이터베이스 연결에 실패했습니다.</div>`;
    }
}

initApp();