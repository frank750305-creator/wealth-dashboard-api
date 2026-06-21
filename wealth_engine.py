# wealth_engine.py
from typing import List, Dict, Any
from schemas import SimulationRequest

def calculate_estate_tax(net_estate_wan: float) -> float:
    """台灣遺產稅三級距計算 (單位：萬)"""
    if net_estate_wan <= 0:
        return 0.0
    elif net_estate_wan <= 5000:
        return net_estate_wan * 0.1
    elif net_estate_wan <= 10000:
        return 500 + (net_estate_wan - 5000) * 0.15
    else:
        return 500 + 750 + (net_estate_wan - 10000) * 0.2

def run_wealth_simulation(req: SimulationRequest) -> Dict[str, Any]:
    """執行終身資產與遺產稅傳承模擬"""
    timeline = req.timeline
    assets = req.assets
    
    trajectory = []
    
    # 建立動態資產池
    current_balances = {a.id: a.value for a in assets}
    
    # 台灣稅法基本免稅額與喪葬扣除額 (單位: 萬)
    BASE_EXEMPTION = 1333.0
    FUNERAL_FEE = 138.0
    
    for age in range(timeline.current_age, timeline.life_expectancy + 1):
        total_assets_wan = 0.0
        yrs_passed = age - timeline.current_age
        
        # 1. 結算當年資產成長與投入
        for a in assets:
            # 每年複利滾存
            current_balances[a.id] *= (1 + a.rate)
            # 若還在定期定額期間，加入當年度投入
            if yrs_passed < a.add_years:
                current_balances[a.id] += (a.monthly_add * 12)
            total_assets_wan += current_balances[a.id]
            
        # 2. 精算當年度若發生繼承的遺產稅缺口
        taxable_estate = max(0, total_assets_wan - BASE_EXEMPTION - FUNERAL_FEE)
        estate_tax_wan = calculate_estate_tax(taxable_estate)
        
        # 3. 紀錄軌跡
        trajectory.append({
            "年紀": age,
            "總資產_萬": round(total_assets_wan, 2),
            "預估遺產稅_萬": round(estate_tax_wan, 2),
            "可分配遺產_萬": round(total_assets_wan - estate_tax_wan, 2)
        })
        
    return {
        "status": "success",
        "trajectory": trajectory
    }