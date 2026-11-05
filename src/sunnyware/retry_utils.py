"""
Async retry utilities with exponential backoff + jitter.
Use this for any network call that might transiently fail.
"""
import asyncio
import random
import logging

logger = logging.getLogger(__name__)


async def retry_async(
    coro_fn,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 15.0,
    jitter: float = 0.3,
    backoff_factor: float = 2.0,
    **kwargs,
):
    """Retry an async function with exponential backoff and jitter.

    Example:
        result = await retry_async(
            some_llm_call,
            prompt="hello",
            max_attempts=3,
            base_delay=1.0,
        )
    """
    attempt = 0
    last_exc = None
    while attempt < max_attempts:
        attempt += 1
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt >= max_attempts:
                logger.warning(f"[retry] giving up after {attempt} attempts: {e}")
                break
            # exponential backoff: base * 2^(attempt-1), capped at max_delay
            delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
            # add jitter to avoid thundering herd
            delay += random.uniform(-jitter, jitter) * delay
            delay = max(0.1, delay)
            logger.info(f"[retry] attempt {attempt} failed ({type(e).__name__}: {e}). Retrying in {delay:.2f}s...")
            await asyncio.sleep(delay)
    if last_exc:
        raise last_exc
