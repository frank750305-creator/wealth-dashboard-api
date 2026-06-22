from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import math

app = FastAPI(title="高資產客戶傳承與稅務精算後端大腦", version="3.1")

# 啟動跨來源資源共用 (CORS)，確保前端 Next.js 能順利連線
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. 定義與前端 Next.js 完全對接的 Pydantic 資料模型 ---
class TimelineSchema(BaseModel):
    current_age: int
    life_expectancy: int
    retire_age: int
    salary_growth: float
    inflation_rate: float
    replacement_rate: float
    roi_after_retire: float

class AssetSchema(BaseModel):
    id: str
    name: str
    type: str
    value: float
    rate: float
    monthly_add: float
    add_years: int
    tax_type: str

class InsuranceSchema(BaseModel):
    id: str
    name: str
    type: str
    app: str
    ins: str
    ben: str
    premium: float
    years: int
    cv: float
    irr: float
    db: float
    survival: float
    survival_age: int

class MortgageSchema(BaseModel):
    id: str
    name: str
    start: int
    total_price: float
    loan_amount: float
    years: int
    grace: int
    rate: float
    method: str
    replace_rent: bool
    claim_tax: bool

class DebtSchema(BaseModel):
    id: str
    name: str
    start: int
    loan_amount: float
    years: int
    rate: float
    monthly_pay: float

class ExtraIncomeSchema(BaseModel):
    id: str
    name: str
    type: str
    monthly_amt: float

class EventSchema(BaseModel):
    id: str
    label: str
    age: int
    amount: float
    target: str
    duration: int

class KidSchema(BaseModel):
    id: str
    age: int
    dep_age: int
    life: int
    ltc: bool

class SiblingSchema(BaseModel):
    id: str
    age: int
    life: int
    claim_tax: bool
    tax_inc: float
    dependent: bool
    disabled: bool
    ltc: bool

class FamilySchema(BaseModel):
    has_spouse: bool
    has_father: bool
    has_mother: bool
    has_grand: bool
    sp_age: int
    sp_life: int
    sp_wealth: float
    sp_disabled: bool
    sp_ltc: bool
    kids: List[KidSchema]
    siblings: List[SiblingSchema]

class PensionSchema(BaseModel):
    mode: str
    lb_salary: float
    lb_current_years: float

class SimulationPayload(BaseModel):
    timeline: TimelineSchema
    assets: List[AssetSchema]
    insurances: List[InsuranceSchema]
    mortgages: List[MortgageSchema]
    debts: List[DebtSchema]
    extra_incomes: List[ExtraIncomeSchema]
    events: List[EventSchema]
    family: FamilySchema
    pension: PensionSchema
    main_salary: float
    base_m_exp: float

# --- 2. 台灣綜合所得稅法定級距計算 (2024最新修正) ---
def calc_tw_income_tax(taxable_net_income_yuan: float) -> float:
    net_inc_wan = taxable_net_income_yuan / 10000
    if net_inc_wan <= 56:
        return (net_inc_wan * 0.05) * 10000
    elif net_inc_wan <= 126:
        return (net_inc_wan * 0.12 - 3.92) * 10000
    elif net_inc_wan <= 252:
        return (net_inc_wan * 0.20 - 14.0) * 10000
    elif net_inc_wan <= 498:
        return (net_inc_wan * 0.30 - 39.2) * 10000
    else:
        return (net_inc_wan * 0.40 - 89.0) * 10000

# --- 3. 核心精算模擬路由端點 ---
@app.post("/api/v1/wealth/simulate")
async def simulate_wealth_trajectory(payload: SimulationPayload):
    try:
        t = payload.timeline
        f = payload.family
        
        trajectory = []
        
        # 初始化動態資產水庫 (元)
        cur_bal = {a.name: a.value * 10000 for a in payload.assets}
        rate_dict = {a.name: a.rate for a in payload.assets}
        tax_dict = {a.name: a.tax_type for a in payload.assets}
        
        # 確保有系統預設活存總水庫
        if "日常活存" not in cur_bal:
            cur_bal["日常活存"] = 0.0
            rate_dict["日常活存"] = 0.01
            tax_dict["日常活存"] = "國內利息(計入27萬)"

        # 複製保單動態陣列，用於計算複利保價金
        sim_ins = [ins.model_copy() for ins in payload.insurances]

        # 終身時間軸精算迴圈 (逐年推演)
        for age in range(t.current_age, t.life_expectancy + 1):
            yrs = age - t.current_age
            row_data = {"年紀": age}
            
            # 房貸與信貸當年度支出核算
            year_mortgage_pay = 0.0
            year_mortgage_interest_wan = 0.0
            for h in payload.mortgages:
                if h.start <= age < h.start + h.years:
                    # 寬限期本息攤還精密計算
                    p_yrs = age - h.start
                    loan_yuan = h.loan_amount * 10000
                    if p_yrs < h.grace:
                        interest = loan_yuan * h.rate
                        year_mortgage_pay += interest
                        year_mortgage_interest_wan += interest / 10000
                    else:
                        # 寬限期後本利平均攤還
                        amort_years = h.years - h.grace
                        m_rate = h.rate / 12
                        m_pmt = (loan_yuan * m_rate * ((1+m_rate)**(amort_years*12))) / (((1+m_rate)**(amort_years*12)) - 1)
                        year_mortgage_pay += m_pmt * 12
                        year_mortgage_interest_wan += (loan_yuan * h.rate) / 10000
            
            year_debt_pay = sum(d.monthly_pay * 12 for d in payload.debts if d.start <= age < d.start + d.years)
            
            # 處理多元額外所得
            cur_extra_inc_gross = 0.0
            cur_extra_inc_taxable = 0.0
            for inc in payload.extra_incomes:
                annual_gross = inc.monthly_amt * 12
                cur_extra_inc_gross += annual_gross
                if "9A" in inc.type:
                    cur_extra_inc_taxable += annual_gross * 0.7
                elif "51" in inc.type:
                    cur_extra_inc_taxable += annual_gross * 0.57
                else:
                    cur_extra_inc_taxable += annual_gross

            # 處理保單現金流、保價金與身故保額複合成長
            ins_premium_total = 0.0
            ins_survival_total = 0.0
            total_cv_wan = 0.0
            
            for p in sim_ins:
                if age < (t.current_age + p.years):
                    ins_premium_total += p.premium * 10000
                    p.cv = (p.cv + p.premium) * (1 + p.irr)
                else:
                    p.cv = p.cv * (1 + p.irr)
                
                p.db = max(p.db, p.cv)
                total_cv_wan += p.cv

            # ✅ 修復點：主業收入與退休金自動對接判斷 (使用 payload.main_salary)
            if age < t.retire_age:
                year_salary = payload.main_salary * 12 * ((1 + t.salary_growth) ** yrs)
                year_pension = 0.0
                year_living_exp = payload.base_m_exp * 12 * ((1 + t.inflation_rate) ** yrs)
            else:
                year_salary = 0.0
                calc_salary = payload.main_salary if payload.main_salary < 45800 else 45800
                year_pension = calc_salary * payload.pension.lb_current_years * 0.0155 * 12
                year_living_exp = (payload.base_m_exp * t.replacement_rate) * 12 * ((1 + t.inflation_rate) ** (age - t.retire_age))

            # 當年總流入與總流出核算
            total_inflow = year_salary + year_pension + cur_extra_inc_gross + ins_survival_total
            total_outflow = year_living_exp + year_mortgage_pay + year_debt_pay + ins_premium_total
            
            # --- 4. 年度綜合所得稅與最低稅負制 (AMT) 合流最優化試算 ---
            is_spouse_alive = f.has_spouse and (f.sp_age + yrs < f.sp_life)
            tax_people = 1 + (1 if is_spouse_alive else 0) + len(f.kids) + (1 if f.has_father else 0) + (1 if f.has_mother else 0)
            
            exemption_pool = 97000 * tax_people
            std_deduction = 131000 * (2 if is_spouse_alive else 1)
            salary_deduction = 218000 if age < t.retire_age else 0
            
            itemized_mortgage = min(year_mortgage_interest_wan * 10000, 300000)
            chosen_deduction = max(std_deduction, itemized_mortgage)
            
            gross_income_total = year_salary + cur_extra_inc_taxable
            net_income_taxable = max(0, gross_income_total - exemption_pool - chosen_deduction - salary_deduction)
            
            general_income_tax = calc_tw_income_tax(net_income_taxable)
            amt_basic_income = net_income_taxable + 0.0
            amt_tax = max(0, amt_basic_income - 7500000) * 0.2
            
            final_year_tax = max(general_income_tax, amt_tax)
            total_outflow += final_year_tax

            # 結餘注入活存總水庫
            net_year_cashflow = total_inflow - total_outflow
            cur_bal["日常活存"] += net_year_cashflow

            for name in cur_bal.keys():
                cur_bal[name] = cur_bal[name] * (1 + rate_dict.get(name, 0.01))

            year_total_assets_wan = (sum(cur_bal.values()) / 10000) + total_cv_wan
            
            # --- 5. 當年度模擬身故民法與傳承遺產稅預估 ---
            estate_tax_exempt = 1333.0
            estate_deductions = 138.0
            if is_spouse_alive:
                estate_tax_exempt += 553.0
            estate_tax_exempt += (56.0 * len(f.kids))
            
            sp_claim_wan = max(0, (year_total_assets_wan - f.sp_wealth) / 2) if is_spouse_alive else 0.0
            taxable_estate_net = max(0, year_total_assets_wan - estate_tax_exempt - sp_claim_wan)
            
            if taxable_estate_net <= 5621:
                estate_tax_wan = taxable_estate_net * 0.1
            elif taxable_estate_net <= 11242:
                estate_tax_wan = 562.1 + (taxable_estate_net - 5621) * 0.15
            else:
                estate_tax_wan = 562.1 + 843.15 + (taxable_estate_net - 11242) * 0.2

            # 寫入年度軌跡封包
            row_data.update({
                "總資產_萬": round(year_total_assets_wan, 1),
                "預估遺產稅_萬": round(estate_tax_wan, 1),
                "差額分配請求權": round(sp_claim_wan, 1),
                "扣除額總計": estate_tax_exempt,
                "收_年金收入": year_pension,
                "支_所得稅金": final_year_tax
            })
            trajectory.append(row_data)

        return {"trajectory": trajectory}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"核心精算引擎崩潰: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)