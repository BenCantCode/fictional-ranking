from __future__ import annotations
from typing import Awaitable
from litellm import ModelResponse, token_counter, get_max_tokens, acompletion
from config import (
    MAX_OUTPUT_TOKENS_ESTIMATE,
    INTERVAL_SECS,
    TOKENS_PER_INTERVAL,
    REQUESTS_PER_INTERVAL,
    EXECUTE_DELAY,
)
import asyncio
import traceback
import sys
from aiolimiter import AsyncLimiter


# class _Waiter:
#     def __init__(self, tokens: int):
#         self.tokens = tokens
#         self.future = asyncio.get_running_loop().create_future()

#     def start(self, executor: _Executor):
#         self.future.set_result(executor)


# class _Executor:
#     def __init__(self, tokens: int, interval: float):
#         self.tokens = tokens
#         self.interval = interval
#         self.future = asyncio.get_running_loop().create_future()

#     @property
#     def done(self):
#         return self.future.done()

#     async def _end(self):
#         await asyncio.sleep(self.interval)
#         self.future.set_result(self)

#     def end(self):
#         self._end_task = asyncio.get_running_loop().create_task(self._end())


class RateLimit:
    # async def _manage_executing(self):
    #     try:
    #         total_tokens_executing = 0
    #         while True:
    #             if len(self._executing) == 0:
    #                 if len(self._waiting) == 0:
    #                     await self._new_waiting
    #             if len(self._executing) != 0:
    #                 done: set[Awaitable[_Executor]]
    #                 done, pending = await asyncio.wait(
    #                     [executor.future for executor in self._executing],
    #                     return_when="FIRST_COMPLETED",
    #                 )
    #                 for finished_executor in done:
    #                     executor = await finished_executor
    #                     total_tokens_executing -= executor.tokens
    #                     self._executing.remove(executor)
    #             for waiting in self._waiting.copy():
    #                 if (
    #                     self.requests_per_interval is not None
    #                     and len(self._executing) >= self.requests_per_interval
    #                 ):
    #                     break
    #                 if self.tokens_per_interval is None or (
    #                     total_tokens_executing + waiting.tokens
    #                     <= self.tokens_per_interval
    #                 ):
    #                     total_tokens_executing += waiting.tokens
    #                     finished_executor = _Executor(waiting.tokens, self.interval)
    #                     self._executing.append(finished_executor)
    #                     waiting.start(finished_executor)
    #                     self._waiting.remove(waiting)
    #                     if self.execute_delay:
    #                         await asyncio.sleep(self.execute_delay)
    #     except Exception as e:
    #         traceback.print_exception(e)
    #         sys.exit(1)

    def __init__(
        self,
        interval: float = INTERVAL_SECS,
        requests_per_interval: int = REQUESTS_PER_INTERVAL,
        tokens_per_interval: int = TOKENS_PER_INTERVAL,
        execute_delay: float | None = EXECUTE_DELAY,
    ):
        # self.interval = 1
        # self.requests_per_interval = requests_per_interval
        # self.tokens_per_interval = tokens_per_interval
        # self.execute_delay = execute_delay
        # self._waiting = []
        # self._executing = []
        # self._new_waiting = asyncio.get_running_loop().create_future()
        # self._task = (
        #     asyncio.get_running_loop()
        #     .create_task(self._manage_executing())
        #     .add_done_callback
        # )

        # TODO: Add requests per minute check
        self.limiter = AsyncLimiter(tokens_per_interval, interval)

    # async def _start_waiting(self, waiter: _Waiter):
    #     self._waiting.append(waiter)
    #     self._new_waiting.set_result(True)
    #     self._new_waiting = asyncio.get_running_loop().create_future()
    #     return await waiter.future

    async def rate_limit_completion(self, **completion_args):
        max_tokens_estimate = (
            get_max_tokens(completion_args["model"]) or MAX_OUTPUT_TOKENS_ESTIMATE
        )
        input_tokens = token_counter(
            completion_args["model"], messages=completion_args["messages"]
        )
        total_tokens = input_tokens + max_tokens_estimate

        # waiter = _Waiter(total_tokens)
        # executor = await self._start_waiting(waiter)
        await self.limiter.acquire(total_tokens)
        try:
            res: ModelResponse = await acompletion(**completion_args)  # type: ignore
            # executor.tokens = res.usage.total_tokens  # type: ignore
            return res
        finally:
            # executor.end()
            pass

    # def __del__(self):
    #     self._task.cancel()
