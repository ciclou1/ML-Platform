import asyncio
import sys

if __name__ == "__main__":
    # Windows 下 psycopg 异步驱动需要 Selector 事件循环；
    # uvicorn 仅在 --reload 子进程模式自动切换，直接运行时需手动设置。
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
