# database.py
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# =====================================================================
# 🌐 資料庫連線配置 (Production-Ready)
# =====================================================================
# 在生產環境中，絕對不要把密碼寫死在程式碼中。
# 這裡使用 os.getenv 讀取系統環境變數，若讀不到則預設連線到本機 PostgreSQL。
# 注意：驅動程式必須指定為 postgresql+asyncpg，這是萬人併發效能最高的異步驅動。
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://frank@127.0.0.1:5432/wealth_db")

# =====================================================================
# ⚡ 異步連線池調校 (高併發核心設定)
# =====================================================================
# 這套配置是專門為了承受極高併發流量而調校的生產等級設定。
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,               # 生產環境下設為 False，避免瘋狂列印 SQL 紀錄導致 CPU 損耗
    pool_size=50,             # 連線池常駐的核心連線數。萬人規模預設給 50
    max_overflow=100,         # 當核心連線不敷使用時，允許臨時額外開闢的最大連線上限
    pool_recycle=1800,        # 每 30 分鐘自動強制回收舊連線，防止 PostgreSQL 端因閒置超時斷線
    pool_pre_ping=True,       # 每次拿連線前自動發送測試訊號 (Ping)，確保該連線依然活著，防止跳出斷線錯誤
    future=True               # 強制啟用 SQLAlchemy 2.0 的現代化全新語法標準
)

# =====================================================================
# 🏭 異步連線工廠與 ORM 基類
# =====================================================================
# 建立一個專門生產異步 Session 的大工廠
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False   # 萬人高併發環境下必設！防止提交後物件資料失效、重複向資料庫發送查詢。
)

# 所有資料庫實體模型 (Models) 必須繼承的基類
Base = declarative_base()

# =====================================================================
# 🔌 FastAPI 專用：異步資料庫連線注入器 (Dependency)
# =====================================================================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 專用的資料庫連線相依注入函式。
    當理專或客戶發送請求時，自動開闢一個獨立的異步 Session，
    任務執行完畢（不論成功或失敗）都會自動關閉並將連線還給連線池。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # 任務成功，這裡會自動 commit（若在 Controller 層有呼叫的話）
        except Exception:
            await session.rollback() # 發生任何錯誤，自動啟動防護網：全量回滾，絕不污染資料庫
            raise
        finally:
            await session.close()    # 確保不管怎樣，連線一定會關閉並回歸連池