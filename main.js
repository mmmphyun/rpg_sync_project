/**
 * View Controller & Event Listeners
 * DOM 조작 및 사용자 인터랙션 처리 (데이터는 data.js에 의존)
 */

// =============================================
//  Utility Functions
// =============================================
function posTag(pos) {
    return pos.split("/").map(p => {
        const cls = POS_CLS[p] || "t-unknown";
        return `<span class="mini-tag ${cls}">${p}</span>`;
    }).join("");
}

function posTagFull(pos) {
    return pos.split("/").map(p => {
        const cls = POS_CLS[p] || "t-unknown";
        return `<span class="sidebar-tag ${cls}">${p}</span>`;
    }).join("");
}

function posBg(pos) {
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
            const v = j[key] || "모름";
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
    const portrait = job.img
        ? `<img src="resources/${job.img}" alt="${job.name}">`
        : getInitials(job.name);
    const mob = job.mobility === "있음" ? `<span class="mini-tag t-yes">이동기</span>` : "";
    const lim = job.limit ? `<span class="mini-tag t-limit">1인</span>` : "";
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
      ${mob || lim ? `<div class="champ-mini-tags">${mob}${lim}</div>` : ""}
    </div>`;
}

function renderGrid() {
    const jobs = getFiltered();
    document.getElementById("jobCount").textContent = jobs.length + "개 직업";
  
    const groupOrders = {
        gate: null,
        range: ["근거리", "원거리", "모름"],
        position: ["탱", "딜", "힐", "유틸", "모름"],
        resource: ["기력", "마나", "체력", "없음", "모름"],
    };
  
    const key = currentSort;
    let html = "";
  
    if (key === "gate") {
        const gateMap = new Map();
        jobs.forEach(j => {
            const parts = j.gate.match(/게이트\s+([A-Z](?:\s*,\s*[A-Z])*)/);
            if (parts) {
                parts[1].split(/\s*,\s*/).forEach(letter => {
                    const key = "게이트 " + letter;
                    if (!gateMap.has(key)) gateMap.set(key, []);
                    gateMap.get(key).push(j);
                });
            } else {
                if (!gateMap.has(j.gate)) gateMap.set(j.gate, []);
                gateMap.get(j.gate).push(j);
            }
        });
        
        const gates = [...gateMap.keys()].sort((a, b) => {
            const ga = a.match(/게이트\s*(.)/)?.[1] || "";
            const gb = b.match(/게이트\s*(.)/)?.[1] || "";
            if (!ga && !gb) return a.localeCompare(b, "ko");
            if (!ga) return 1;
            if (!gb) return -1;
            return ga.localeCompare(gb);
        });
        
        gates.forEach(g => {
            html += `<div class="group-label">${g} (${gateMap.get(g).length})</div>`;
            html += `<div class="champ-grid">${gateMap.get(g).map(j => renderTile(j, JOBS.indexOf(j))).join("")}</div>`;
        });
    } else {
        const order = groupOrders[key];
        const groups = new Map();
        order.forEach(v => groups.set(v, []));
        jobs.forEach(j => {
            const v = j[key] || "모름";
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
        ? `<img src="resources/${job.img}" alt="${job.name}">`
        : getInitials(job.name);
        
    const gallery = job.photos.length > 0
        ? `<div class="sidebar-gallery">${job.photos.map(p => `<img src="resources/${p}" alt="${job.name}" onclick="openLightbox('resources/${p}')">`).join("")}</div>`
        : "";
        
    sidebarContent.innerHTML = `
      <button class="sidebar-close" onclick="closeSidebar()">&times;</button>
      <div class="sidebar-portrait ${posBg(job.position)}">${sidePortrait}</div>
      <div class="sidebar-name">${job.name}</div>
      <div class="sidebar-gate">${job.gate}${job.group ? ` · ${job.group}` : ""}${job.players && job.players.length ? ` &nbsp;|&nbsp; <span style="color:#2ecc71">● ${job.players.join(", ")}</span>` : ""}</div>
      <div class="sidebar-tags">
        <span class="sidebar-tag ${RANGE_CLS[job.range] || "t-unknown"}">${job.range}</span>
        ${posTagFull(job.position)}
        <span class="sidebar-tag ${RES_CLS[job.resource] || "t-unknown"}">${job.resource}</span>
        ${job.mobility === "있음" ? `<span class="sidebar-tag t-yes">이동기</span>` : ""}
        ${job.aoe === "있음" ? `<span class="sidebar-tag t-yes">광역기</span>` : ""}
        ${job.limit ? `<span class="sidebar-tag t-limit">1인 제한</span>` : ""}
      </div>
      <div class="sidebar-desc">${job.desc}</div>
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

// 리스트 타일 클릭 위임
app.addEventListener("click", e => {
    const tile = e.target.closest(".champ-tile");
    if (!tile) return;
    const idx = parseInt(tile.dataset.idx);
    if (idx === selectedIdx) { closeSidebar(); return; }
    openSidebar(idx);
});

// 상단 분류 탭 이벤트
document.querySelectorAll(".filter-btn:not(.tag-filter)").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".filter-btn:not(.tag-filter)").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentSort = btn.dataset.sort;
        renderGrid();
    });
});

// 태그 필터(토글) 이벤트
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

// 라이트박스 닫기 이벤트
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
        // FastAPI 서버 주소 호출
        const response = await fetch("http://localhost:8000/api/jobs");
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        JOBS = await response.json();

        // 데이터 로드 완료 후 화면 그리기
        renderGrid();
    } catch (error) {
        console.error("데이터를 불러오는 중 오류가 발생했습니다:", error);
        app.innerHTML = `<div style="text-align:center; padding:50px; color:#e74c3c;">데이터베이스 연결에 실패했습니다.</div>`;
    }
}

// 앱 실행
initApp();