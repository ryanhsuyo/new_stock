from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import decision_journal, portfolio, stats, stocks, system, trades, watchlists

app = FastAPI(title="台灣股票分析與投資紀錄 API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(watchlists.router, prefix="/api")
app.include_router(decision_journal.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=9000, reload=True)
