# init_db.py
import asyncio
from database import async_engine, Base, AsyncSessionLocal
from models import Tenant, User, Client

async def init_models():
    # 1. 進入資料庫，依照 models.py 自動打造實體資料表
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. 寫入第一筆合法的測試組織與首席理專，打通權限
    async with AsyncSessionLocal() as session:
        # 建立組織架構
        hq_tenant = Tenant(company_name="富邦財管團隊")
        session.add(hq_tenant)
        await session.flush() # 取得組織專屬 ID
        
        # 建立首席顧問帳號
        chief_advisor = User(tenant_id=hq_tenant.id, full_name="鍾國正 (首席顧問)")
        session.add(chief_advisor)
        await session.flush() # 取得顧問專屬 ID
        
        await session.commit()
        
        print("✅ PostgreSQL 實體資料庫裝潢完畢！所有關聯表已建置。")
        print("==================================================")
        print("🎉 請複製以下兩組「真實系統 ID」，貼入 Swagger 網頁的 Header 中進行最終測試：")
        print(f"X-Tenant-ID  ->  {hq_tenant.id}")
        print(f"X-Advisor-ID ->  {chief_advisor.id}")
        print("==================================================")

if __name__ == "__main__":
    asyncio.run(init_models())