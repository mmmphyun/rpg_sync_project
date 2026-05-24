/**
 * Fossil Server Guide Page Premium Interactivity Handler
 * Est. 2026
 */
document.addEventListener('DOMContentLoaded', function() {
    // === 1. 탭 시스템 전환 및 읽기 락(Lock) 검증 로직 ===
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const promiseInput = document.getElementById('promise-input');
    const lockNotice = document.getElementById('lock-notice');
    
    // 읽은 탭 추적 Set 객체 (기본 시작은 tab-wild가 이미 열려 있으므로 1개로 시작)
    const visitedTabs = new Set(['tab-wild']);
    const totalTabs = 4;

    function checkAllTabsVisited() {
        if (!promiseInput || !lockNotice) return; // 뉴비가 아닌 상태 (이미 멤버/게스트) 예외 처리
        
        const count = visitedTabs.size;
        lockNotice.innerHTML = `<i class="fas fa-lock"></i> 가이드의 모든 탭을 차례로 읽으셔야 작성이 가능합니다. (확인 완료: ${count}/${totalTabs})`;
        
        if (count === totalTabs) {
            promiseInput.disabled = false;
            promiseInput.placeholder = "위 문구를 정확하게 입력하고 버튼을 눌러주세요!";
            lockNotice.style.color = "var(--accent-hero)";
            lockNotice.innerHTML = `<i class="fas fa-unlock"></i> 가이드 완료!`;
        }
    }

    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');

            // 버튼 active 토글
            tabButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');

            // 콘텐츠 active 토글
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === targetTab) {
                    content.classList.add('active');
                }
            });

            // 탭 읽음 추적 추가
            visitedTabs.add(targetTab);
            checkAllTabsVisited();
        });
    });

    // 얌체 유저 방지 락 (F12 등으로 disabled 강제 제거 시 2차 차단 방어막)
    if (promiseInput) {
        promiseInput.addEventListener('keydown', function(e) {
            if (visitedTabs.size < totalTabs) {
                e.preventDefault();
                this.value = '';
                this.blur();
                alert('가이드의 4개 탭을 모두 위에서부터 차례로 누르고 확인해 주시기 바랍니다.');
            }
        });
    }

    // === 2. 마인크래프트 인벤토리 시뮬레이터 로직 ===
    const invSlots = document.querySelectorAll('.inventory-slot:not(.slot-empty)');
    const menuTitle = document.getElementById('menu-title');
    const menuBadge = document.getElementById('menu-badge');
    const menuDesc = document.getElementById('menu-desc');

    function updateDetailCard(name, badge, desc) {
        menuTitle.innerHTML = `${name} <span class="badge-mono" id="menu-badge">${badge}</span>`;
        menuDesc.textContent = desc;
    }

    invSlots.forEach(slot => {
        slot.addEventListener('mouseenter', function() {
            invSlots.forEach(s => s.classList.remove('active'));
            this.classList.add('active');
            
            const name = this.getAttribute('data-name');
            const badge = this.getAttribute('data-badge');
            const desc = this.getAttribute('data-desc');
            updateDetailCard(name, badge, desc);
        });
    });

    // === 3. 서약 동의 실시간 타이핑 검증 (복사/붙여넣기 차단) ===
    if (promiseInput) {
        const completeBtn = document.getElementById('complete-btn');
        const modal = document.getElementById('complete-modal');
        const closeBtn = document.getElementById('modal-close-btn');

        const targetText = "미숙지로 인한 불이익은 본인 책임임을 동의합니다";

        // 직접 기입 텍스트 실시간 검증
        promiseInput.addEventListener('input', function() {
            const userInput = this.value.trim().replace(/\s+/g, ' ');
            
            if (userInput === targetText) {
                completeBtn.disabled = false;
                completeBtn.classList.add('glow-active');
                promiseInput.classList.add('glow-active');
            } else {
                completeBtn.disabled = true;
                completeBtn.classList.remove('glow-active');
                promiseInput.classList.remove('glow-active');
            }
        });

        // 붙여넣기 시도 시 알림 및 이벤트 완전 차단
        promiseInput.addEventListener('paste', function(e) {
            e.preventDefault();
            alert('복사/붙여넣기는 조금 서운하네요.. 직접 타이핑해주세요!');
            return false;
        });

        // 완료 버튼 클릭 시 API 호출
        completeBtn.addEventListener('click', async function() {
            if (completeBtn.disabled) return;

            const btnText = completeBtn.querySelector('span');
            const btnIcon = completeBtn.querySelector('i');
            
            const originalText = btnText.textContent;
            const originalIconClass = btnIcon.className;

            completeBtn.disabled = true;
            completeBtn.classList.remove('glow-active');
            btnText.textContent = '처리 중...';
            btnIcon.className = 'fas fa-spinner fa-spin';

            try {
                const response = await fetch('/api/v1/auth/complete', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const result = await response.json();

                if (response.ok && result.message === 'success') {
                    modal.classList.remove('hidden');
                    modal.classList.add('open');
                } else {
                    alert(result.detail || '가이드 완료 처리 중 오류가 발생했습니다.');
                    completeBtn.disabled = false;
                    completeBtn.classList.add('glow-active');
                    btnText.textContent = originalText;
                    btnIcon.className = originalIconClass;
                }
            } catch (error) {
                console.error('API 호출 에러:', error);
                alert('네트워크 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.');
                completeBtn.disabled = false;
                completeBtn.classList.add('glow-active');
                btnText.textContent = originalText;
                btnIcon.className = originalIconClass;
            }
        });

        // 모달 닫기 및 홈으로 리다이렉트
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                modal.classList.remove('open');
                modal.classList.add('hidden');
                window.location.href = '/';
            });
        }
    }
});
