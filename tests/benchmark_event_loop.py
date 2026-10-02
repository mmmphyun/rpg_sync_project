import os
import time
import asyncio
import concurrent.futures
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv(".env.dev")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dev_user:dev_password@localhost:5432/rpg_dev_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://:dev_redis_pw@localhost:6379/0")
SIMULATED_RTT_SEC = 0.20  # 대륙 간 RTT (200ms)

# ---------------------------------------------------------------------
# 1. 실제 PostgreSQL 연동 동기 DB 쿼리
# ---------------------------------------------------------------------
def real_blocking_db_query():
    """실제 도커 PostgreSQL에 쿼리 + 200ms 대륙간 RTT 지연 시뮬레이션"""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # 실제 데이터 조회와 함께 네트워크 RTT 반영
        time.sleep(SIMULATED_RTT_SEC)
        cursor.execute("SELECT COUNT(*) AS cnt FROM jobs;")
        row = cursor.fetchone()
        return row['cnt'] if row else 0
    finally:
        cursor.close()
        conn.close()

# ---------------------------------------------------------------------
# 2. Discord Gateway Heartbeat 모니터 (50ms 주기)
# ---------------------------------------------------------------------
async def heartbeat_monitor(stop_event: asyncio.Event, tick_interval: float = 0.05) -> List[float]:
    delays = []
    last_tick = time.perf_counter()
    while not stop_event.is_set():
        await asyncio.sleep(tick_interval)
        current = time.perf_counter()
        elapsed = current - last_tick
        delay_jitter_ms = max(0.0, (elapsed - tick_interval) * 1000)
        delays.append(delay_jitter_ms)
        last_tick = current
    return delays

# ---------------------------------------------------------------------
# 3. Naive 방식: 이벤트 루프 상에서 동기 DB 호출 직접 실행
# ---------------------------------------------------------------------
async def run_naive_blocking_workload(num_requests: int = 10) -> Dict[str, Any]:
    stop_event = asyncio.Event()
    heartbeat_task = asyncio.create_task(heartbeat_monitor(stop_event))
    await asyncio.sleep(0.01)  # 모니터 최초 틱 가동 보장

    request_latencies = []
    start_total = time.perf_counter()

    for _ in range(num_requests):
        req_start = time.perf_counter()
        # 안티패턴: 코루틴 내에서 동기 블로킹 함수 직접 호출 (이벤트 루프 프리징)
        _ = real_blocking_db_query()
        request_latencies.append((time.perf_counter() - req_start) * 1000)
        await asyncio.sleep(0.005)

    stop_event.set()
    heartbeat_delays = await heartbeat_task
    total_elapsed = time.perf_counter() - start_total

    sorted_lat = sorted(request_latencies)
    p95_idx = int(len(sorted_lat) * 0.95)

    return {
        "total_elapsed_sec": total_elapsed,
        "rps": num_requests / total_elapsed,
        "mean_latency_ms": sum(request_latencies) / len(request_latencies),
        "p95_latency_ms": sorted_lat[min(p95_idx, len(sorted_lat) - 1)],
        "max_latency_ms": max(request_latencies),
        "heartbeat_avg_lag_ms": sum(heartbeat_delays) / len(heartbeat_delays) if heartbeat_delays else 0.0,
        "heartbeat_max_lag_ms": max(heartbeat_delays) if heartbeat_delays else 0.0,
    }

# ---------------------------------------------------------------------
# 4. Hardened 방식: ThreadPoolExecutor(max_workers=20) + asyncio.to_thread 격리
# ---------------------------------------------------------------------
async def run_hardened_isolated_workload(num_requests: int = 10) -> Dict[str, Any]:
    stop_event = asyncio.Event()
    heartbeat_task = asyncio.create_task(heartbeat_monitor(stop_event))
    await asyncio.sleep(0.01)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
    loop = asyncio.get_running_loop()
    loop.set_default_executor(executor)

    request_latencies = []
    start_total = time.perf_counter()

    async def worker():
        req_start = time.perf_counter()
        # 최적화: 워커 스레드로 동기 I/O 오프로딩
        _ = await asyncio.to_thread(real_blocking_db_query)
        request_latencies.append((time.perf_counter() - req_start) * 1000)

    # 10개 동시 요청 비동기 병렬 처리
    tasks = [asyncio.create_task(worker()) for _ in range(num_requests)]
    await asyncio.gather(*tasks)
    await asyncio.sleep(0.05)
    stop_event.set()
    heartbeat_delays = await heartbeat_task
    total_elapsed = time.perf_counter() - start_total

    sorted_lat = sorted(request_latencies)
    p95_idx = int(len(sorted_lat) * 0.95)

    return {
        "total_elapsed_sec": total_elapsed,
        "rps": num_requests / total_elapsed,
        "mean_latency_ms": sum(request_latencies) / len(request_latencies),
        "p95_latency_ms": sorted_lat[min(p95_idx, len(sorted_lat) - 1)],
        "max_latency_ms": max(request_latencies),
        "heartbeat_avg_lag_ms": sum(heartbeat_delays) / len(heartbeat_delays) if heartbeat_delays else 0.0,
        "heartbeat_max_lag_ms": max(heartbeat_delays) if heartbeat_delays else 0.0,
    }

# ---------------------------------------------------------------------
# 5. 실제 도커 Redis 기반 Safe TTL (15s) 분산 락 동시성 경합
# ---------------------------------------------------------------------
async def run_redis_distributed_lock_benchmark(concurrency: int = 20) -> Dict[str, Any]:
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    lock_key = "rpgsync:processing_reason:bench_uuid_9999"
    await redis.delete(lock_key)

    results = {"acquired": 0, "rejected": 0}
    lock_latencies = []

    async def staff_action(staff_id: int):
        t0 = time.perf_counter()
        # Redis SET key "1" EX 15 NX 원자적 커맨드 실행
        acquired = await redis.set(lock_key, str(staff_id), ex=15, nx=True)
        lat = (time.perf_counter() - t0) * 1000
        lock_latencies.append(lat)

        if not acquired:
            results["rejected"] += 1
            return False

        results["acquired"] += 1
        try:
            # 임계 구역: DB 조회 및 Pub/Sub 모의 실행
            await asyncio.sleep(0.05)
        finally:
            # 락 해제
            await redis.delete(lock_key)
        return True

    # 20개 동시 요청 폭주
    t_start = time.perf_counter()
    await asyncio.gather(*(staff_action(i) for i in range(concurrency)))
    total_time = time.perf_counter() - t_start

    # 정리
    await redis.delete(lock_key)
    await redis.aclose()

    sorted_lat = sorted(lock_latencies)
    p95_idx = int(len(sorted_lat) * 0.95)

    return {
        "concurrency": concurrency,
        "acquired_count": results["acquired"],
        "rejected_count": results["rejected"],
        "total_time_sec": total_time,
        "lock_mean_latency_ms": sum(lock_latencies) / len(lock_latencies),
        "lock_p95_latency_ms": sorted_lat[min(p95_idx, len(sorted_lat) - 1)],
        "lock_max_latency_ms": max(lock_latencies),
    }

# ---------------------------------------------------------------------
# 메인 벤치마크 실행 진입점
# ---------------------------------------------------------------------
async def main():
    print("=====================================================================")
    print("RPG Sync Project: 파트 2 도커 컴포즈 실증 벤치마크")
    print("환경: Docker Compose (rpg-db-dev, rpg-redis-dev)")
    print("=====================================================================")

    print("\n[테스트 1] Naive 방식: 이벤트 루프 내 직접 동기 DB 쿼리 (10회)...")
    naive = await run_naive_blocking_workload(num_requests=10)
    print(f"  - 총 소요 시간: {naive['total_elapsed_sec']:.3f} s")
    print(f"  - 처리량 (Throughput): {naive['rps']:.2f} RPS")
    print(f"  - 평균 지연시간: {naive['mean_latency_ms']:.2f} ms")
    print(f"  - p95 지연시간: {naive['p95_latency_ms']:.2f} ms")
    print(f"  - 하트비트 평균 Lag: {naive['heartbeat_avg_lag_ms']:.2f} ms")
    print(f"  - 하트비트 최대 Lag: {naive['heartbeat_max_lag_ms']:.2f} ms")

    print("\n[테스트 2] Hardened 방식: ThreadPoolExecutor 격리 병렬 처리 (10회)...")
    hardened = await run_hardened_isolated_workload(num_requests=10)
    print(f"  - 총 소요 시간: {hardened['total_elapsed_sec']:.3f} s")
    print(f"  - 처리량 (Throughput): {hardened['rps']:.2f} RPS")
    print(f"  - 평균 지연시간: {hardened['mean_latency_ms']:.2f} ms")
    print(f"  - p95 지연시간: {hardened['p95_latency_ms']:.2f} ms")
    print(f"  - 하트비트 평균 Lag: {hardened['heartbeat_avg_lag_ms']:.2f} ms")
    print(f"  - 하트비트 최대 Lag: {hardened['heartbeat_max_lag_ms']:.2f} ms")

    print("\n[테스트 3] Docker Redis Safe TTL (15s) 분산 락 동시성 경합 (20건 동시)...")
    lock_res = await run_redis_distributed_lock_benchmark(concurrency=20)
    print(f"  - 락 획득 성공 (정상 처리): {lock_res['acquired_count']} 건")
    print(f"  - 락 획득 차단 (중복 방지): {lock_res['rejected_count']} 건")
    print(f"  - SET NX 평균 응답시간: {lock_res['lock_mean_latency_ms']:.2f} ms")
    print(f"  - SET NX p95 응답시간: {lock_res['lock_p95_latency_ms']:.2f} ms")
    print(f"  - SET NX 최대 응답시간: {lock_res['lock_max_latency_ms']:.2f} ms")
    print("=====================================================================")

if __name__ == "__main__":
    asyncio.run(main())
