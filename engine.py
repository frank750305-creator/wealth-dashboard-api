# (保留您原本檔案最上方的 import，例如 import pandas as pd 等)

# 💥 1. 新增：獨立的台灣遺產稅精算模組
def calculate_taiwan_estate_tax(total_assets_10k: float) -> float:
    """
    ▍ 台灣遺產稅精算模組 (單位：萬)
    計算邏輯：總資產 - (免稅額 1333 + 喪葬扣除額 138) = 課稅遺產淨額
    """
    base_exemption = 1471 # 基礎免稅額 + 喪葬扣除額
    
    net_estate = max(0, total_assets_10k - base_exemption)
    
    if net_estate == 0:
        return 0
    elif net_estate <= 5000:
        return net_estate * 0.10
    elif net_estate <= 10000:
        return net_estate * 0.15 - 250
    else:
        return net_estate * 0.20 - 750


# 💥 2. 升級：保留原有擴充性，掛載稅務模組的主引擎
def run_core_financial_engine(payload):
    current_age = payload.timeline.current_age
    life_expectancy = payload.timeline.life_expectancy
    assets = payload.assets

    trajectory = []
    warning_logs = []

    # 這裡保留了未來處理多種資產 (如不動產、股票) 的彈性
    total_initial_assets = sum(asset.value for asset in assets)
    # 若前端有傳入特定報酬率則使用，否則預設 2%
    growth_rate = assets[0].rate if assets and hasattr(assets[0], 'rate') else 0.02 

    current_assets = total_initial_assets

    for age in range(current_age, life_expectancy + 1):
        # 呼叫剛剛新增的精算模組
        estate_tax = calculate_taiwan_estate_tax(current_assets)
        
        trajectory.append({
            "年紀": age,
            "總資產_萬": round(current_assets, 0),
            "保單總價值_萬": 0, # 您原本規劃保留給保單的欄位，完美保留！
            "累積財務缺口_萬": 0,
            "預估遺產稅_萬": round(estate_tax, 0),
        })
        
        current_assets = current_assets * (1 + growth_rate)

    import pandas as pd # 確保有載入 pandas
    result_df = pd.DataFrame(trajectory)
    
    # 智能警示系統
    if result_df["預估遺產稅_萬"].max() > 1000:
        warning_logs.append("⚠️ 系統偵測到潛在遺產稅現金缺口超過 1,000 萬，建議立刻啟動高額壽險規劃或家族信託防禦。")

    return result_df, warning_logs

# (保留您檔案最下方的任何其他程式碼)