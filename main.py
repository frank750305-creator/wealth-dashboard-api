from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import math

app = FastAPI(title="高資產傳承與所得稅擇優核算大腦", version="3.6")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    ben: List[str]
    custom_ben: Optional[str] = ""
    ben_allocation: str
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
    disabled: bool
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
    daily_tool_val: float
    job_tool_val: float

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
    tax_params: Dict[str, float]
    main_salary: float
    base_m_exp: float

def calc_tw_tax(net_inc: float) -> float:
    if net_inc <= 56: return net_inc * 0.05
    elif net_inc <= 126: return net_inc * 0.12 - 3.92
    elif net_inc <= 252: return net_inc * 0.20 - 14.0
    elif net_inc <= 498: return net_inc * 0.30 - 39.2
    else: return net_inc * 0.40 - 89.0

@app.post("/api/v1/wealth/simulate")
async def simulate_wealth_trajectory(payload: SimulationPayload):
    try:
        t = payload.timeline
        f = payload.family
        tp = payload.tax_params
        
        LIQUIDATION_ORDER = ["現金", "保單", "基金", "債券", "股票", "其他", "不動產"]
        trajectory = []
        
        cur_bal = {a.name: a.value * 10000 for a in payload.assets}
        sub_to_cat = {a.name: a.type for a in payload.assets}
        rate_dict = {a.name: a.rate for a in payload.assets}
        tax_dict = {a.name: a.tax_type for a in payload.assets}
        
        if "日常活存" not in cur_bal:
            cur_bal["日常活存"] = 0.0
            sub_to_cat["日常活存"] = "現金"
            rate_dict["日常活存"] = 0.01
            tax_dict["日常活存"] = "國內利息(計入27萬)"

        sim_ins = [ins.model_copy() for ins in payload.insurances]
        accumulated_deficit = 0.0

        for age in range(t.current_age, t.life_expectancy + 1):
            yrs = age - t.current_age
            row_data = {"年紀": age}
            cur_house = 0.0
            item_mortgage_interest = 0.0
            
            for h in payload.mortgages:
                if h.start <= age < h.start + h.years:
                    p_yrs = age - h.start
                    loan_yuan = h.loan_amount * 10000
                    m_rate = (h.rate / 100) / 12
                    
                    if p_yrs < h.grace:
                        interest = loan_yuan * (h.rate / 100)
                        cur_house += interest
                        if h.claim_tax: item_mortgage_interest += interest / 10000
                    else:
                        amort_p_yrs = p_yrs - h.grace
                        a_yrs = h.years - h.grace
                        
                        if h.method == "本金平均":
                            p_ann = loan_yuan / a_yrs if a_yrs > 0 else 0
                            current_rem_loan = max(0.0, loan_yuan - (p_ann * amort_p_yrs))
                            year_interest = max(0.0, current_rem_loan * (h.rate / 100))
                            cur_house += (p_ann + year_interest)
                            if h.claim_tax: item_mortgage_interest += year_interest / 10000
                        else:
                            amort_months = a_yrs * 12
                            pmt = (loan_yuan * m_rate * (1+m_rate)**amort_months) / ((1+m_rate)**amort_months - 1) if m_rate > 0 else loan_yuan / amort_months
                            cur_house += pmt * 12
                            
                            months_passed = amort_p_yrs * 12
                            if amort_months > months_passed:
                                current_rem_loan = loan_yuan * (((1+m_rate)**amort_months - (1+m_rate)**months_passed) / ((1+m_rate)**amort_months - 1)) if m_rate > 0 else loan_yuan - (pmt * months_passed)
                                year_interest = current_rem_loan * (h.rate / 100)
                                if h.claim_tax: item_mortgage_interest += year_interest / 10000

            cur_debt = sum(d.monthly_pay * 12 for d in payload.debts if d.start <= age < d.start + d.years)

            cur_extra_inc_gross = 0.0
            cur_extra_inc_net_taxable = 0.0
            total_9b_annual = 0.0
            for inc in payload.extra_incomes:
                annual_gross = inc.monthly_amt * 12
                cur_extra_inc_gross += annual_gross
                if "9B" in inc.type: total_9b_annual += annual_gross
                elif "9A" in inc.type: cur_extra_inc_net_taxable += annual_gross * 0.7
                elif "租賃" in inc.type: cur_extra_inc_net_taxable += annual_gross * 0.57
                else: cur_extra_inc_net_taxable += annual_gross
            if total_9b_annual > 180000: cur_extra_inc_net_taxable += (total_9b_annual - 180000)

            ins_premium_total = 0.0
            ins_survival_total = 0.0
            total_cv_wan = 0.0
            trigger_amt_base = 0.0
            estate_cv_addition_wan = 0.0
            insurance_payouts = {}

            for p in sim_ins:
                p_prem_yuan = p.premium * 10000
                p_surv_yuan = p.survival * 10000
                if age < (t.current_age + p.years):
                    ins_premium_total += p_prem_yuan
                    p.cv = (p.cv + p.premium) * (1 + p.irr)
                else:
                    p.cv = p.cv * (1 + p.irr)
                p.db = max(p.db, p.cv)
                total_cv_wan += p.cv

                if age >= p.survival_age and p.survival > 0:
                    ins_survival_total += p_surv_yuan

                if p.app == '本人' and p.ins == '本人':
                    trigger_amt_base += max(0.0, p.db - 3740.0)
                    for b in p.ben:
                        b_name = p.custom_ben if b == "其他(自行輸入)" else b
                        if p.ben_allocation == "均分比例":
                            insurance_payouts[b_name] = insurance_payouts.get(b_name, 0.0) + (p.db * 10000 / len(p.ben))
                        else:
                            insurance_payouts[p.ben[0]] = p.db * 10000
                elif p.app == '本人':
                    estate_cv_addition_wan += p.cv

            if age < t.retire_age:
                temp_salary = payload.main_salary * 12 * ((1 + t.salary_growth)**yrs)
                temp_pension = 0.0
                display_living_exp = payload.base_m_exp * 12 * ((1 + t.inflation_rate)**yrs)
            else:
                temp_salary = 0.0
                calc_salary = payload.main_salary if payload.main_salary < 45800 else 45800
                temp_pension = calc_salary * payload.pension.lb_current_years * 0.0155 * 12
                display_living_exp = payload.base_m_exp * t.replacement_rate * 12 * ((1 + t.inflation_rate)**(age - t.retire_age))

            cur_inc = temp_salary + cur_extra_inc_gross + temp_pension + ins_survival_total
            current_year_net_inflow = cur_inc - display_living_exp - cur_house - cur_debt - ins_premium_total

            is_spouse_alive = f.has_spouse and (f.sp_age + yrs < f.sp_life)
            tax_people = 1 + (1 if is_spouse_alive else 0) + len(f.kids) + (1 if f.has_father else 0) + (1 if f.has_mother else 0)
            total_exemption = (tp["exemption"] * 1.5) if age >= 70 else tp["exemption"]
            inc_tax_disabled_count = 1 if f.sp_disabled else 0
            ltc_count = 1 if f.sp_ltc else 0
            preschool_ded = 0.0
            
            if is_spouse_alive:
                total_exemption += (tp["exemption"] * 1.5) if (f.sp_age + yrs) >= 70 else tp["exemption"]

            for k in f.kids:
                if k.age + yrs <= k.dep_age:
                    tax_people += 1
                    total_exemption += tp["exemption"]
                    if k.age + yrs <= 6: preschool_ded += tp["preschool_1st"]
                    if k.disabled: inc_tax_disabled_count += 1
                    if k.ltc: ltc_count += 1

            user_salary_wan = temp_salary / 10000
            biz_other_wan = cur_extra_inc_net_taxable / 10000
            if age >= t.retire_age: biz_other_wan += max(0.0, (temp_pension / 10000) - tp["retire_exempt"])

            interest_inc, dividend_inc, overseas_inc, amt_ins_inc = 0.0, 0.0, 0.0, 0.0
            for nm, val in cur_bal.items():
                lbl = tax_dict.get(nm, "")
                yield_wan = (val / 10000) * rate_dict.get(nm, 0.01)
                if "利息" in lbl: interest_inc += yield_wan
                elif "股利" in lbl: dividend_inc += yield_wan
                elif "海外" in lbl: overseas_inc += yield_wan
                elif "保單" in lbl: amt_ins_inc += yield_wan

            savings_deduction = min(interest_inc, tp["savings_limit"])
            taxable_interest = interest_inc - savings_deduction
            std_deduction = tp["std_deduction"] * (2 if is_spouse_alive else 1)
            item_ins = min(2.4 * tax_people, tp["ins_limit"] * tax_people) 
            item_mortgage_final = min(max(0.0, item_mortgage_interest - savings_deduction), tp["mortgage_limit"])
            final_deduction = max(std_deduction, item_ins + item_mortgage_final)
            
            total_special_ded = savings_deduction + (inc_tax_disabled_count * tp["inc_disabled_ded"]) + (ltc_count * tp["ltc_deduction"]) + preschool_ded
            basic_living_diff = max(0.0, (tax_people * tp["basic_living"]) - (total_exemption + final_deduction + total_special_ded))
            user_sal_ded = min(user_salary_wan, tp["salary_deduction"])

            # 🛠️ 修復：定義綜合所得總額變數
            gross_income_total = user_salary_wan + biz_other_wan + taxable_interest + dividend_inc

            def check_tax(add_div):
                gross = user_salary_wan + biz_other_wan + taxable_interest + (dividend_inc if add_div else 0.0)
                net = max(0.0, gross - total_exemption - final_deduction - total_special_ded - basic_living_diff - user_sal_ded)
                return calc_tw_tax(net), net

            # 🛠️ 修復：統一變數名稱為 tax_scenario_1 與 tax_scenario_2
            tax_joint, joint_net = check_tax(add_div=True)
            tax_scenario_1 = max(0.0, tax_joint - min(dividend_inc * 0.085, 8.0))
            tax_no_div, _ = check_tax(add_div=False)
            tax_scenario_2 = tax_no_div + (dividend_inc * 0.28)
            general_tax = min(tax_scenario_1, tax_scenario_2)

            basic_income = joint_net + overseas_inc + amt_ins_inc
            amt_tax = max(0.0, basic_income - tp["amt_threshold"]) * 0.2
            final_income_tax_wan = max(general_tax, amt_tax)
            
            current_year_net_inflow -= (final_income_tax_wan * 10000)

            if current_year_net_inflow > 0:
                if accumulated_deficit > 0:
                    payoff = min(current_year_net_inflow, accumulated_deficit)
                    accumulated_deficit -= payoff
                    current_year_net_inflow -= payoff
                cur_bal["日常活存"] += current_year_net_inflow
            else:
                deficit = abs(current_year_net_inflow)
                for cat in LIQUIDATION_ORDER:
                    if deficit <= 0: break
                    for k, v in sub_to_cat.items():
                        if v == cat and cur_bal.get(k, 0) > 0:
                            take = min(cur_bal[k], deficit)
                            cur_bal[k] -= take
                            deficit -= take
                if deficit > 0: accumulated_deficit += deficit

            total_a = sum(cur_bal.values())
            total_a_wan = (total_a / 10000) + total_cv_wan
            total_liab_wan = (cur_debt + accumulated_deficit) / 10000

            total_a_wan_estate = total_a_wan + estate_cv_addition_wan
            ded_total = 1333.0 + 138.0
            ded_details = {"免稅額": 1333.0, "喪葬費": 138.0}
            alive_dict = {"配偶": [], "子女": [], "父母": [], "兄弟姊妹": [], "祖父母": []}
            if is_spouse_alive:
                alive_dict["配偶"].append({"name": "配偶"})
                ded_total += 553.0; ded_details["配偶扣除額"] = 553.0
            for k in f.kids:
                if k.age + yrs <= k.life:
                    alive_dict["子女"].append({"name": k.id})
                    ded_total += 56.0 + max(0.0, (18 - (k.age + yrs)) * 56.0)
            
            sp_claim_wan = max(0.0, (total_a_wan_estate - f.sp_wealth) / 2) if is_spouse_alive else 0.0
            taxable_net_wan = max(0.0, total_a_wan_estate - total_liab_wan - min(f.daily_tool_val, 100.0) - min(f.job_tool_val, 56.0) - sp_claim_wan - ded_total)
            
            if taxable_net_wan <= 5621: tax_wan = taxable_net_wan * 0.1
            elif taxable_net_wan <= 11242: tax_wan = 562.1 + (taxable_net_wan - 5621) * 0.15
            else: tax_wan = 562.1 + 843.15 + (taxable_net_wan - 11242) * 0.2

            trajectory.append({
                "年紀": age, "總資產_萬": round(total_a_wan, 0), "預估遺產稅_萬": round(tax_wan, 0),
                "差額分配請求權": round(sp_claim_wan, 0), "扣除額總計": ded_total, "收_年金收入": round(temp_pension, 0),
                "支_所得稅金": round(final_income_tax_wan * 10000, 0), "收_主業薪資": round(temp_salary, 0),
                "收_其他所得": round(cur_extra_inc_gross, 0), "收_保險還本": round(ins_survival_total, 0),
                "支_生活開銷": round(display_living_exp, 0), "支_保險費": round(ins_premium_total, 0),
                "保單總價值": total_cv_wan, "保單理賠分配": insurance_payouts, "身故觸發受益人AMT_預估": trigger_amt_base,
                "民法繼承基數": max(0.0, total_a_wan_estate - total_liab_wan - sp_claim_wan),
                "可分配餘額": max(0.0, total_a_wan_estate - total_liab_wan - tax_wan - sp_claim_wan),
                "扣除額明細": ded_details, "存活字典": alive_dict, "股利計稅": "合併計稅" if tax_scenario_1 <= tax_scenario_2 else "分開計稅",
                "觸發AMT": "是" if amt_tax > general_tax else "否", "稅_綜合所得總額": gross_income_total,
                "稅_綜合所得淨額": joint_net, "稅_一般應納稅額": general_tax, "稅_AMT基本所得額": basic_income, "稅_AMT稅額": amt_tax,
                "稅_免稅額": total_exemption, "稅_扣除額": final_deduction, "稅_特扣總計": total_special_ded, "稅_基本差額": basic_living_diff,
                "稅_申報人數": tax_people, "扣除額類型": "列舉" if item_ins + item_mortgage_final > std_deduction else "標準"
            })

        return {"trajectory": trajectory}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"核心引擎精算異常: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)