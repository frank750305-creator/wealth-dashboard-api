# main.py
from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from schemas import FinancialAnalysisRequest
from repository import ClientRepository
from engine import run_core_financial_engine
from fastapi.middleware.cors import CORSMiddleware

# =====================================================================
# 1. 建立唯一總部大樓 (全域只能有一個 app)
# =====================================================================
app = FastAPI(
    title="台版 Bloomberg 財富精算與量化核心平台",
    description="採用非阻塞式異步架構 (Async/Await)，支援多租戶隔離、精算綜合所得稅、AMT 最低稅負、民法繼承順位與房貸本息攤還。"
)

# =====================================================================
# 2. 部署跨域防護網 (CORS 警衛必須在路由前面設定)
# =====================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # 嚴格指定只允許 Next.js 前端通行
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

# =====================================================================
# 3. 註冊精算部門路由
# =====================================================================
@app.post(
    "/api/v1/wealth/simulate", 
    summary="執行生命週期財務與傳承模擬",
    status_code=status.HTTP_200_OK
)
async def simulate_wealth_trajectory(
    payload: FinancialAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    x_tenant_id: UUID = Header(default=None, alias="X-Tenant-ID"),
    x_advisor_id: UUID = Header(default=None, alias="X-Advisor-ID")
):
    if not x_tenant_id or not x_advisor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="安全防禦攔截：請求未攜帶合法的租戶別代碼 (X-Tenant-ID) 或理顧問代碼 (X-Advisor-ID)"
        )

    try:
        db_client = await ClientRepository.create_client(
            session=db,
            tenant_id=x_tenant_id,
            advisor_id=x_advisor_id,
            name="客戶_" + str(payload.timeline.current_age) + "歲案例",
            current_age=payload.timeline.current_age,
            life_expectancy=payload.timeline.life_expectancy,
            retire_age=payload.timeline.retire_age
        )

        result_df, warning_logs = run_core_financial_engine(payload)
        await db.commit()

        return {
            "status": "success",
            "metadata": {
                "saved_client_id": db_client.id,
                "tenant_id": x_tenant_id,
                "advisor_id": x_advisor_id,
                "database_record_created": True
            },
            "trajectory": result_df.to_dict(orient="records"),
            "warnings": warning_logs
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"精算大腦或持久層發生未預期潰散，已啟動防護網安全回滾。錯誤資訊: {str(e)}"
        )

# =====================================================================
# 4. 啟動伺服器 (必須放在整個檔案的最最最下方)
# =====================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)