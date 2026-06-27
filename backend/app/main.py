from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import resolve_cors_allowed_origins
from app.routers import decision_journal, portfolio, stats, stocks, system, trades, watchlists


def create_app(cors_origins: list[str] | None = None) -> FastAPI:
    application = FastAPI(title="台灣股票分析與投資紀錄 API", version="0.2.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=(
            cors_origins
            if cors_origins is not None
            else resolve_cors_allowed_origins()
        ),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(stocks.router, prefix="/api")
    application.include_router(trades.router, prefix="/api")
    application.include_router(portfolio.router, prefix="/api")
    application.include_router(stats.router, prefix="/api")
    application.include_router(system.router, prefix="/api")
    application.include_router(watchlists.router, prefix="/api")
    application.include_router(decision_journal.router, prefix="/api")
    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=9000, reload=True)
