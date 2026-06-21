from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from schemas import SimulationRequest
from wealth_engine import run_wealth_simulation

app = FastAPI(title="資產配置戰情室 Pro API")

# 開放跨網域連線 (CORS)，允許前端連線
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Your service is live 🚀"}

@app.post("/api/v1/wealth/simulate")
def simulate_wealth(payload: SimulationRequest):
    """
    接收前端財務參數，進行終身資產與傳承稅負精算
    """
    result = run_wealth_simulation(payload)
    return result