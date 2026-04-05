from inventra_collector.infrastructure.rate_limit import RateLimiter


def test_rate_limiter_waits_when_requests_are_too_close():
    import asyncio

    current = 0.0
    sleep_calls = []

    def clock():
        return current

    async def sleep(seconds: float):
        nonlocal current
        sleep_calls.append(seconds)
        current += seconds

    limiter = RateLimiter(10, clock=clock, sleep=sleep)

    asyncio.run(limiter.acquire())
    asyncio.run(limiter.acquire())

    assert sleep_calls == [0.1]
