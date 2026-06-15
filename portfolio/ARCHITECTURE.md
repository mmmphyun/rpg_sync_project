# Architecture & Engineering Strategy

RPG Sync Project의 시스템 설계와 기술적 결정의 근거를 정리한 문서입니다. 본 프로젝트는 **"제한된 리소스(Free Tier) 환경에서의 단일 노드 내 다중 프로세스 격리 아키텍처 구축"**을 목표로 설계되었습니다.

## 🏗️ 전체 시스템 구성 (System Topology)
시스템은 독립적인 3개의 핵심 서비스와 데이터 레이어로 구성됩니다.
1.  **FastAPI (Web)**: Jinja2 기반 SSR을 통해 보안과 검색 엔진 최적화(SEO)를 달성한 대시보드.
2.  **discord.py (Bot)**: 대량의 실시간 이벤트를 비동기로 처리하는 이벤트 리스너 및 관리 툴.
3.  **Redis (State Broker)**: 분산된 서비스 간의 상태 공유 및 실시간 메시지 교환(Pub/Sub) 담당.
4.  **PostgreSQL (Persistence)**: Supabase를 활용한 관계형 데이터 저장소.

## 🚀 핵심 최적화 전략 (Engineering Deep-Dive)

### 1. 지연 시간 극복을 위한 네트워크 엔지니어링
- **GCP VM(US) - Supabase(Korea)** 간의 물리적 거리를 극복하기 위해 다음을 적용했습니다.
- **TCP Keepalive**: 유휴 연결의 강제 종료를 막기 위해 소켓 레벨의 세션을 유지합니다.
- **Connection Pre-warming & Fast Path**: 물리적 거리(RTT 200ms) 극복을 위해 TCP Keepalive 및 커넥션 풀을 미리 예열(Pre-warming)하고 핵심 도메인 정보를 메모리 캐싱(Fast Path)하여 네트워크 핸드셰이크 지연을 최소화합니다.

### 2. 하이브리드 동시성 제어 (Async-Sync Hybrid)
- `discord.py`의 단일 스레드 비동기 루프를 보호하기 위해, 동기식 DB 작업은 전용 **ThreadPoolExecutor**로 격리했습니다.
- 이를 통해 I/O 작업이 CPU를 점유하지 않도록 설계하여 봇의 실시간성을 보장했습니다.

### 3. Redis 기반 분산 상태 관리
- 컨테이너가 분리된 구조에서 `In-memory` 저장소의 한계를 극복하기 위해 Redis를 도입했습니다.
- **Pub/Sub**: 마인크래프트 서버의 이벤트를 봇이 즉각 수신하도록 설계했습니다.
- **Distributed Lock**: Redis의 원자적 연산을 활용해 분산 환경에서도 데이터 무결성을 보장합니다.

## 🛡️ 보안 설계 (Security Architecture)
- **Identity Proxy**: Cloudflare WAF를 최전방에 배치하고, 실제 유저 IP를 추적하여 Rate Limiting을 수행합니다.
- **Passwordless Auth**: 매직 링크와 JWT를 결합하여 사용자 편의성을 높이면서도 강력한 인증 체계를 구축했습니다.
- **Data Integrity**: 모든 DB 쿼리는 파라미터 바인딩을 강제하며, DB 수준의 강력한 제약 조건을 통해 데이터 오염을 방지합니다.
