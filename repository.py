# repository.py
from uuid import UUID
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import Client

class ClientRepository:
    """
    客戶資料表 (clients) 的異步資料庫操作倉儲層 (Production-Grade)
    全面採用 SQLAlchemy 2.0 異步執行標準，嚴格防範記憶體阻塞與阻塞
    """
    
    @staticmethod
    async def create_client(
        session: AsyncSession, 
        tenant_id: UUID, 
        advisor_id: UUID, 
        name: str, 
        current_age: int, 
        life_expectancy: int, 
        retire_age: int
    ) -> Client:
        """
        異步新增客戶基本資料
        """
        # 建立 ORM 實體物件
        new_client = Client(
            tenant_id=tenant_id,
            advisor_id=advisor_id,
            name=name,
            current_age=current_age,
            life_expectancy=life_expectancy,
            retire_age=retire_age
        )
        
        # 1. 將物件加入異步 Session 的追蹤範圍
        session.add(new_client)
        
        # 2. 執行 flush 讓資料庫先生成 UUID 主鍵與預設時間戳記，但不鎖死事務
        await session.flush()
        
        # 3. 重新整理實體，確保 Python 記憶體能即時拿到資料庫生成的欄位
        await session.refresh(new_client)
        
        return new_client

    @staticmethod
    async def get_client_by_id(
        session: AsyncSession, 
        tenant_id: UUID, 
        client_id: UUID
    ) -> Optional[Client]:
        """
        異步精準查詢單一客戶資料
        💥 安全控管：查詢條件必須同時鎖死 tenant_id，實施雙重應用層隔離防護
        """
        # SQLAlchemy 2.0 標準：先使用 select() 建構抽象 AST 查詢語法樹
        stmt = (
            select(Client)
            .where(Client.id == client_id)
            .where(Client.tenant_id == tenant_id) # 應用層的安全印章雙重覆蓋
        )
        
        # 執行異步查詢，此時執行緒會釋放控制權，不卡死 CPU
        result = await session.execute(stmt)
        
        # 傳回第一筆符合的資料，若無則傳回 None
        return result.scalar_one_or_none()

    @staticmethod
    async def get_clients_by_advisor(
        session: AsyncSession, 
        tenant_id: UUID, 
        advisor_id: UUID, 
        limit: int = 20, 
        offset: int = 0
    ) -> List[Client]:
        """
        異步分頁查詢該理專名下的所有客戶列表
        💥 萬人併發設計：必須強制實作 limit 與 offset 分頁機制，絕不允許全表一次撈取撈乾記憶體
        """
        stmt = (
            select(Client)
            .where(Client.tenant_id == tenant_id)
            .where(Client.advisor_id == advisor_id)
            .order_by(Client.created_at.desc()) # 預設依建立時間由新到舊排序
            .limit(limit)                       # 限制本次最高撈取幾筆
            .offset(offset)                     # 跳過前幾筆（用於下一頁）
        )
        
        result = await session.execute(stmt)
        
        # scalars().all() 將結果集自動打包成乾淨的 Python 陣列
        return list(result.scalars().all())