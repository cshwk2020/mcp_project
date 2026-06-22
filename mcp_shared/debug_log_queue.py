import asyncio

DEBUG_LOG_QUEUE = asyncio.Queue()

def push_log(msg: str):
    print('push_log...msg == ', msg)
    DEBUG_LOG_QUEUE.put_nowait(msg)




