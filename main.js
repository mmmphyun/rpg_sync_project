/**
 * View Controller & Event Listeners
 * API 연동 기반 DOM 조작 및 사용자 인터랙션 처리
 */

// =============================================
//  Constants & Utility Functions
// =============================================
// 백엔드 기본값을 "정보 없음"으로 설정했으므로 매핑 키를 업데이트합니다.
const RANGE_CLS = { "근거리": "t-melee", "원거리": "t-ranged", "정보 없음": "t-unknown" };
const POS_CLS   = { "탱": "t-tank", "딜": "t-deal", "힐": "t-heal", "유틸": "t-util", "정보 없음": "t-unknown" };
const RES_CLS   = { "기력": "t-ki", "마나": "t-mana", "체력": "t-hp", "에너지": "t-hp", "정보 없음": "t-unknown" }; // 에너지 추가
const POS_BG    = { "탱": "bg-tank", "딜": "bg-deal", "힐": "bg-heal", "유틸": "bg-util", "정보 없음": "bg-unknown" };

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

// =============================================
//  Core Logic
// =============================================
function getFiltered() {
    return JOBS.filter(j => {
        for (const [key, val] of Object.entries(activeFilters)) {
            const v = j[key] || "정보 없음";
            if (key === "position") {
                if (!v.split("/").includes(val)) return false;
            } else {
                if (v !== val) return false;
            }
        }
        return true;
    });
}

function renderTile(job, idx) {
    const sel = idx === selectedIdx ? " selected" : "";

    // DB의 이미지는 URL로 저장되므로 resources/ 경로 대신 직접 사용 (이미지가 없는 경우 initials)
    const portrait = job.img
        ? `<img src="${job.img}" alt="${job.name}">`
        : getInitials(job.name);

    const lim = job.limit ? `<span class="mini-tag t-limit">1인</span>` : "";

    // API에 players 배열, mobility 등 누락된 기능은 차후 DB 확장 시 연동
    const hasPlayers = job.players && job.players.length > 0;
    const dot = hasPlayers ? `<div class="active-dot"></div>` : "";
    const tooltip = hasPlayers ? `<div class="player-tooltip">${job.players.join(", ")}</div>` : "";

    return `<div class="champ-tile${sel}" data-idx="${idx}">
      <div class="champ-portrait ${posBg(job.position)}">${portrait}${dot}</div>
      ${tooltip}
      <div class="champ-name">${job.name}</div>
      <div class="champ-mini-tags">
        <span class="mini-tag ${RANGE_CLS[job.range] || "t-unknown"}">${job.range}</span>
        ${posTag(job.position)}
      </div>
      ${lim ? `<div class="champ-mini-tags">${lim}</div>` : ""}
    </div>`;
}

function renderGrid() {
    const jobs = getFiltered();
    document.getElementById("jobCount").textContent = jobs.length + "개 직업";

    const groupOrders = {
        gate: null,
        range: ["근거리", "원거리", "정보 없음"],
        position: ["탱", "딜", "힐", "유틸", "정보 없음"],
        resource: ["기력", "마나", "체력", "에너지", "정보 없음"],
    };

    const key = currentSort;
    let html = "";

    if (key === "gate") {
        const gateMap = new Map();
        jobs.forEach(j => {
            // DB에서 "게이트 -C", "고대 게이트" 형식으로 그대로 넘어옴
            const gateKey = j.gate || "정보 없음";
            if (!gateMap.has(gateKey)) gateMap.set(gateKey, []);
            gateMap.get(gateKey).push(j);
        });

        // 게이트 이름 정렬 로직 (간소화)
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

    sidebarContent.innerHTML = `
      <button class="sidebar-close" onclick="closeSidebar()">&times;</button>
      <div class="sidebar-portrait ${posBg(job.position)}">${sidePortrait}</div>
      <div class="sidebar-name">${job.name}</div>
      <div class="sidebar-gate">${job.gate}${job.group && job.group !== "정보 없음" ? ` · ${job.group}` : ""}</div>
      <div class="sidebar-tags">
        <span class="sidebar-tag ${RANGE_CLS[job.range] || "t-unknown"}">${job.range}</span>
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
      ${gallery}`;

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

// =============================================
//  Initialize
// =============================================
async function initApp() {
    try {
        // 실제 서버가 구동 중인 URL/IP로 변경 필요
        const response = await fetch("/api/jobs");
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        JOBS = await response.json();
        renderGrid();
    } catch (error) {
        console.error("데이터를 불러오는 중 오류가 발생했습니다:", error);
        app.innerHTML = `<div style="text-align:center; padding:50px; color:#e74c3c;">데이터베이스 연결에 실패했습니다.</div>`;
    }
}

initApp();