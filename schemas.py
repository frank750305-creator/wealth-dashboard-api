# wealth_engine.py
import math
from typing import Dict, Any, List
import numpy as np
from schemas import FullSimulationRequest

# --- 法規硬常數 ---
TAX_EXEMPT_VAL = 1333.0     # 免稅額 (萬)
SPOUSE_DED = 553.0          # 配偶扣除額 (萬)
PARENT_DED = 138.0          # 父母扣除額 (萬)
KID_DED = 56.0              # 直系血親卑親屬扣除額 (萬)
KID_YEAR_ADD = 56.0         # 未成年加扣 (萬)
ESTATE_DISABLED_DED = 693.0 # 身心障礙特別扣除額 (萬)
FUNERAL_FEE = 138.0         # 喪葬費 (萬)
HOUSEHOLD_LIMIT = 100.0     # 日常生活用品限額 (萬)
TOOL_LIMIT = 56.0           # 職業工具限額 (萬)
AMT_INS_EXEMPT = 3740.0     # 特定保險身故給付 AMT 免稅額 (萬)

LIQUIDATION_ORDER = ["現金", "保單", "基金", "債券", "股票", "其他", "不動產"]

def calc_tw_tax(net_inc: float) -> float:
    """綜合所得稅累進稅率 (單位：萬)"""
    if net_inc <= 56: return net_inc * 0.05
    elif net_inc <= 126: return net_inc * 0.12 - 3.92
    elif net_inc <= 252: return net_inc * 0.20 - 14.0
    elif net_inc <= 498: return net_inc * 0.30 - 39.2
    else: return net_inc * 0.40 - 89.0

class PensionCalculator:
    def __init__(self, age: int, labor_years: float, national_years: float, 
                 avg_salary_60: int, avg_salary_36: int, has_old_system: bool, 
                 offset_years: int = 0):
        self.age = age
        self.labor_years = labor_years
        self.national_years = national_years
        self.avg_salary_60 = avg_salary_60
        self.avg_salary_36 = avg_salary_36
        self.has_old_system = has_old_system
        self.offset_years = max(-5, min(5, offset_years))
        self.national_insured_amount = 19761
        self.national_basic_guarantee = 3772

    def _calc_labor_annuity(self, years, offset) -> int:
        if self.avg_salary_60 <= 0 or years <= 0: return 0
        adjustment_ratio = 1.0 + (offset * 0.04)
        formula_A = (self.avg_salary_60 * years * 0.00775) + 3000
        formula_B = self.avg_salary_60 * years * 0.0155
        return int(max(formula_A, formula_B) * adjustment_ratio)

    def evaluate_best_strategy(self) -> dict:
        """回傳最優退休策略金流 (單位: 萬/年 或 萬一次)"""
        # 預設簡易精算邏輯，對齊原型代碼中擇優策略
        if self.labor_years >= 15:
            m_amt = self._calc_labor_annuity(self.labor_years, self.offset_years)
            return {"type": "monthly", "val": (m_amt * 12) / 10000}
        else:
            lump = self.avg_salary_60 * min(self.labor_years, 60)
            return {"type": "lump", "val": lump / 10000}

def run_wealth_simulation(req: FullSimulationRequest) -> Dict[str, Any]:
    # 基礎參數讀取
    tl = req.timeline
    fam = req.family
    pen = req.pension
    
    current_age = tl.current_age
    life_expectancy = tl.life_expectancy
    retire_age = tl.retire_age
    
    # 1. 退休金前置精算
    annuity_m_amt_wan = 0.0
    pension_lump_sum_wan = 0.0
    pension_lump_sum_age = retire_age
    pension_acct_bal_wan = 0.0
    pension_acct_add_wan = 0.0
    pension_acct_roi = 0.0
    pension_vol_deduct_wan = 0.0
    annuity_start_age = retire_age

    if pen.mode and "清空" not in pen.mode:
        if "勞工" in pen.mode:
            future_years = max(0, retire_age - current_age)
            total_lb_years = pen.lb_current_years + future_years
            offset = pen.lb_age - 65
            calc = PensionCalculator(
                age=pen.lb_age, labor_years=total_lb_years, national_years=pen.national_years,
                avg_salary_60=pen.lb_salary, avg_salary_36=pen.lb_salary, has_old_system=pen.has_old_sys, offset_years=offset
            )
            strat = calc.evaluate_best_strategy()
            if strat["type"] == "monthly":
                annuity_start_age = pen.lb_age
                annuity_m_amt_wan = strat["val"] / 12
            else:
                pension_lump_sum_age = pen.lb_age
                pension_lump_sum_wan = strat["val"]
            
            lt_base_salary = min(req.main_salary, 150000)
            pension_acct_bal_wan = pen.lt_bal
            pension_acct_add_wan = (lt_base_salary * 0.06 + lt_base_salary * (pen.lt_vol / 100)) / 10000
            pension_acct_roi = pen.lt_roi
            pension_vol_deduct_wan = (lt_base_salary * (pen.lt_vol / 100)) / 10000
            
        elif "公教" in pen.mode:
            if "按月" in pen.pb_type:
                annuity_m_amt_wan += ((pen.pb_salary * min(pen.pb_years, 35) * 0.013) / 10000)
            else:
                pension_lump_sum_wan += ((pen.pb_salary * min(pen.pb_years * 1.2, 42)) / 10000)
            
            if "舊制" in pen.tf_sys:
                max_ratio = min(0.75, max(0.0, 0.375 + (pen.tf_years - 15) * 0.015))
                annuity_m_amt_wan += (((pen.tf_salary * 2) * max_ratio) / 10000)
            else:
                pension_acct_bal_wan = pen.tf_bal
                pension_acct_add_wan = ((pen.tf_sal * 2) * (0.0975 + 0.0525) + (pen.tf_sal * 2) * (pen.tf_vol / 100)) / 10000
                pension_vol_deduct_wan = ((pen.tf_sal * 2) * 0.0525 + (pen.tf_sal * 2) * (pen.tf_vol / 100)) / 10000
                pension_acct_roi = pen.tf_roi

    # 資產水庫與名稱對照表初始化
    cur_bal = {a.name: a.value * 10000 for a in req.assets}
    sub_to_cat = {a.name: a.type for a in req.assets}
    rate_dict = {a.name: a.rate for a in req.assets}
    tax_type_dict = {a.name: a.tax_type for a in req.assets}

    if "日常活存" not in cur_bal:
        cur_bal["日常活存"] = 0.0
        sub_to_cat["日常活存"] = "現金"
        rate_dict["日常活存"] = 0.0
        tax_type_dict["日常活存"] = "國內利息(計入27萬)"

    cur_bal["退休金專戶"] = pension_acct_bal_wan * 10000
    sub_to_cat["退休金專戶"] = "其他"
    rate_dict["退休金專戶"] = pension_acct_roi / 100
    tax_type_dict["退休金專戶"] = "資本利得/不計稅"

    # 複製動態保單物件明細
    sim_ins = [ins.dict() for ins in req.insurances]
    history = []
    accumulated_deficit = 0.0

    # 所得稅輔助常數
    tp = {
        "exemption": 9.7, "std_deduction": 13.1, "salary_deduction": 21.8, "inc_disabled_ded": 21.8,
        "savings_limit": 27.0, "amt_threshold": 750.0, "rent_limit": 18.0, "mortgage_limit": 30.0,
        "ins_limit": 2.4, "retire_exempt": 81.4, "basic_living": 21.8, "ltc_deduction": 12.0,
        "preschool_1st": 12.0, "preschool_2nd": 15.0
    }

    # ⚙️ 終身 90 年大迴圈正式運轉
    for age in range(int(current_age), int(life_expectancy) + 1):
        yrs = age - current_age
        row_data = {"年紀": age}
        
        cur_house_pay = 0.0
        cur_debt_pay = 0.0
        item_mortgage_interest = 0.0
        current_mortgage_principal = 0.0
        current_debt_principal = 0.0
        
        # A. 房貸與不動產本利計算
        for h in req.mortgages:
            if h.start <= age < h.start + h.years:
                p_yrs = age - h.start
                loan_amt_calc = h.loan_amount * 10000
                m_rate = (h.rate / 100) / 12
                g_yrs = h.grace
                a_yrs = h.years - g_yrs
                
                current_rem_loan = 0.0
                if p_yrs < g_yrs:
                    year_interest = loan_amt_calc * (h.rate / 100)
                    cur_house_pay += year_interest
                    current_rem_loan = loan_amt_calc
                    if h.claim_tax: item_mortgage_interest += year_interest / 10000
                else:
                    amort_p_yrs = p_yrs - g_yrs
                    if h.method == "本金平均":
                        p_ann = loan_amt_calc / a_yrs if a_yrs > 0 else 0
                        current_rem_loan = max(0.0, loan_amt_calc - (p_ann * amort_p_yrs))
                        year_interest = max(0.0, current_rem_loan * (h.rate / 100))
                        cur_house_pay += (p_ann + year_interest)
                        if h.claim_tax: item_mortgage_interest += year_interest / 10000
                    else: # 本利平均
                        months_total = a_yrs * 12
                        months_passed = amort_p_yrs * 12
                        pmt = (loan_amt_calc * m_rate * (1+m_rate)**months_total) / ((1+m_rate)**months_total - 1) if m_rate > 0 else loan_amt_calc / months_total
                        cur_house_pay += pmt * 12
                        if months_total > months_passed:
                            current_rem_loan = loan_amt_calc * (((1+m_rate)**months_total - (1+m_rate)**months_passed) / ((1+m_rate)**months_total - 1)) if m_rate > 0 else loan_amt_calc - (pmt * months_passed)
                            year_interest = current_rem_loan * (h.rate / 100)
                            if h.claim_tax: item_mortgage_interest += year_interest / 10000
                            
                current_mortgage_principal += current_rem_loan
                row_data[f"房貸_{h.name}"] = current_rem_loan / 10000
            else:
                row_data[f"房貸_{h.name}"] = 0.0

        # B. 信貸計算
        for d in req.debts:
            if d.start <= age < d.start + d.years:
                cur_debt_pay += d.monthly_pay * 12
                loan_amt_d = d.loan_amount * 10000
                m_rate_d = (d.rate / 100) / 12
                months_d = d.years * 12
                months_passed = (age - d.start) * 12
                current_rem_debt = 0.0
                if months_d > months_passed:
                    if m_rate_d > 0:
                        current_rem_debt = loan_amt_d * (((1+m_rate_d)**months_d - (1+m_rate_d)**months_passed) / ((1+m_rate_d)**months_d - 1))
                    else:
                        current_rem_debt = loan_amt_d - ((loan_amt_d/months_d) * months_passed)
                current_debt_principal += max(0.0, current_rem_debt)
                row_data[f"信貸_{d.name}"] = max(0.0, current_rem_debt) / 10000
            else:
                row_data[f"信貸_{d.name}"] = 0.0

        # C. 兼職/其他外部多元所得優化判讀
        cur_extra_inc_gross = 0.0
        cur_extra_inc_net_taxable = 0.0
        total_9b_annual = 0.0
        for inc in req.extra_incomes:
            annual_gross = inc.monthly_amt * 12
            cur_extra_inc_gross += annual_gross
            if "9B" in inc.type: total_9b_annual += annual_gross
            elif "9A" in inc.type: cur_extra_inc_net_taxable += annual_gross * 0.7
            elif "租賃" in inc.type: cur_extra_inc_net_taxable += annual_gross * 0.57
            else: cur_extra_inc_net_taxable += annual_gross
        if total_9b_annual > 180000: cur_extra_inc_net_taxable += (total_9b_annual - 180000)

        # D. 🛡️ 保單現金流自動扣抵、IRR 增值與雙軌理賠判定
        ins_premium_total = 0.0
        ins_survival_total = 0.0
        total_cv_wan = 0.0
        trigger_amt_base = 0.0
        estate_cv_addition_wan = 0.0
        insurance_payouts = {}

        for p in sim_ins:
            p_prem_yuan = p['premium'] * 10000
            p_surv_yuan = p['survival'] * 10000
            
            if age < (current_age + p['years']): ins_premium_total += p_prem_yuan
            if age >= p['survival_age'] and p['survival'] > 0: ins_survival_total += p_surv_yuan
            
            # 保價金 IRR 複利增長
            if age < (current_age + p['years']):
                p['cv'] = (p['cv'] + p['premium']) * (1 + p['irr'])
            else:
                p['cv'] = p['cv'] * (1 + p['irr'])
            p['db'] = max(p['db'], p['cv'])
            total_cv_wan += p['cv']

            # 身故與生存傳承屬性判定 (若模擬當前身故)
            if p['app'] == '本人':
                if p['ins'] == '本人':
                    ben_list = p['ben']
                    is_same = (len(ben_list) == 1 and ben_list[0] == p['app'])
                    if p['type'] in ["人壽保險", "年金保險"] and not is_same:
                        trigger_amt_base += max(0.0, p['db'] - AMT_INS_EXEMPT)
                    
                    # 雙軌制派發名單建立
                    actual_bens = [b if b != "其他(自行輸入)" else p.get('custom_ben', '其他') for b in ben_list]
                    if actual_bens:
                        if p.get('ben_allocation') == "均分比例":
                            split_amt = (p['db'] * 10000) / len(actual_bens)
                            for b in actual_bens: insurance_payouts[b] = insurance_payouts.get(b, 0.0) + split_amt
                        else:
                            insurance_payouts[actual_bens[0]] = insurance_payouts.get(actual_bens[0], 0.0) + (p['db'] * 10000)
                else:
                    estate_cv_addition_wan += p['cv']

        # E. 主業與退休金收入交叉比對
        temp_salary = 0.0
        temp_pension = 0.0
        if age < retire_age:
            temp_salary = req.main_salary * 12 * ((1 + tl.salary_growth)**yrs)
            if age >= annuity_start_age:
                temp_pension = (annuity_m_amt_wan * 10000 * 12) * ((1 + tl.inflation_rate)**(age - annuity_start_age))
            cur_inc = temp_salary + cur_extra_inc_gross + temp_pension + ins_survival_total
            temp_living_exp = (req.base_m_exp * 12) * ((1 + tl.inflation_rate)**yrs)
            
            rent_saved = 0.0
            if any(h.replace_rent and age >= h.start for h in req.mortgages):
                rent_saved = 0.0 # 簡化對齊省租邏輯
            temp_pension_vol = (pension_vol_deduct_wan * 10000 * 12) * ((1 + tl.salary_growth)**yrs)
            cur_invest = sum(a.monthly_add * 10000 * 12 for a in req.assets if yrs < a.add_years)
            
            current_year_net_inflow = cur_inc - temp_living_exp + rent_saved - cur_house_pay - cur_debt_pay - cur_invest - temp_pension_vol - ins_premium_total
            display_living_exp = temp_living_exp - rent_saved
        else:
            if age >= annuity_start_age:
                temp_pension = (annuity_m_amt_wan * 10000 * 12) * ((1 + tl.inflation_rate)**(age - annuity_start_age))
            cur_inc = cur_extra_inc_gross + temp_pension + ins_survival_total
            temp_living_exp = (tl.replacement_rate * req.main_salary * 12) * ((1 + tl.inflation_rate)**(age - retire_age))
            display_living_exp = temp_living_exp
            current_year_net_inflow = cur_inc - temp_living_exp - cur_house_pay - cur_debt_pay - ins_premium_total

        if age == pension_lump_sum_age and pension_lump_sum_wan > 0:
            cur_bal["退休金專戶"] += (pension_lump_sum_wan * 10000)

        # F. 🏛️ 所得稅與 最低稅負制（AMT）動態優化計算
        is_spouse_alive = fam.has_spouse and (fam.sp_age + yrs < fam.sp_life)
        tax_people = 1 + (1 if is_spouse_alive else 0)
        total_exemption = tp["exemption"] * (1.5 if age >= 70 else 1.0)
        if is_spouse_alive: total_exemption += tp["exemption"] * (1.5 if (fam.sp_age + yrs) >= 70 else 1.0)
        
        # 子女免稅與學前特扣累加
        preschool_ded = 0.0
        first_kid_done = False
        for k in fam.kids:
            k_age_now = k.get('age', 0) + yrs
            if k_age_now <= k.get('dep_age', 22) and k_age_now < k.get('life', 85):
                tax_people += 1
                total_exemption += tp["exemption"]
                if k_age_now <= 6:
                    preschool_ded += tp["preschool_1st"] if not first_kid_done else tp["preschool_2nd"]
                    first_kid_done = True

        user_salary_wan = temp_salary / 10000
        biz_other_wan = cur_extra_inc_net_taxable / 10000
        
        # 利息/股利/海外所得水庫結算
        interest_inc = 0.0; dividend_inc = 0.0; overseas_inc = 0.0; amt_ins_inc = 0.0
        for nm, val in cur_bal.items():
            if val <= 0: continue
            a_yield = (val / 10000) * rate_dict.get(nm, 0.0)
            ttype = tax_type_dict.get(nm, "資本利得/不計稅")
            if "利息" in ttype: interest_inc += a_yield
            elif "股利" in ttype: dividend_inc += a_yield
            elif "海外" in ttype: overseas_inc += a_yield
            elif "保單" in ttype: amt_ins_inc += a_yield

        savings_deduction = min(interest_inc, tp["savings_limit"])
        std_deduction = tp["std_deduction"] * (2 if is_spouse_alive else 1)
        final_deduction = max(std_deduction, savings_deduction + preschool_ded)
        
        joint_net_inc = max(0.0, user_salary_wan + biz_other_wan + (interest_inc - savings_deduction) - total_exemption - final_deduction)
        general_tax = calc_tw_tax(joint_net_inc)
        
        # 股利擇優合併/分開計稅
        tax_scenario_1 = max(0.0, calc_tw_tax(joint_net_inc + dividend_inc) - min(dividend_inc * 0.085, 8.0))
        tax_scenario_2 = general_tax + (dividend_inc * 0.28)
        final_general_tax = min(tax_scenario_1, tax_scenario_2)

        # AMT 最低稅負判定
        basic_income = joint_net_inc + overseas_inc + amt_ins_inc
        amt_tax = max(0.0, basic_income - tp["amt_threshold"]) * 0.2
        final_income_tax_wan = max(final_general_tax, amt_tax)
        
        current_year_net_inflow -= (final_income_tax_wan * 10000)

        # G. 購屋頭期款一次性扣除
        for h in req.mortgages:
            if age == h.start:
                prop_name = f"房產_{h.name}"
                cur_bal[prop_name] = (h.total_price * 10000)
                sub_to_cat[prop_name] = "不動產"
                rate_dict[prop_name] = 0.0
                tax_type_dict[prop_name] = "資本利得/不計稅"
                current_year_net_inflow -= (h.total_price - h.loan_amount) * 10000

        # H. 💰 結餘灌入日常活存 / 觸發「變現救火隊」
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
                avail_subs = [k for k, v in sub_to_cat.items() if v == cat and cur_bal.get(k, 0.0) > 0]
                for sub in avail_subs:
                    take = min(cur_bal[sub], deficit)
                    cur_bal[sub] -= take
                    deficit -= take
            if deficit > 0: accumulated_deficit += deficit

        # I. 複利滾存更新明細
        total_a = 0.0
        for nm, val in cur_bal.items():
            val *= (1 + rate_dict.get(nm, 0.0))
            cur_bal[nm] = val
            total_a += val
            
        total_a_wan = (total_a / 10000) + total_cv_wan
        total_liab_wan = (current_mortgage_principal + current_debt_principal + accumulated_deficit) / 10000

        # J. 民法遺產稅與特留分試算
        total_a_wan_estate = total_a_wan + estate_cv_addition_wan
        ded_total = TAX_EXEMPT_VAL + FUNERAL_FEE
        ded_details = {"免稅額": TAX_EXEMPT_VAL, "喪葬費": FUNERAL_FEE}
        
        if is_spouse_alive:
            ded_total += SPOUSE_DED; ded_details["配偶扣除額"] = SPOUSE_DED
            if fam.sp_disabled: ded_total += ESTATE_DISABLED_DED
            
        taxable_net_wan = max(0.0, total_a_wan_estate - total_liab_wan - ded_total)
        estate_tax_result = calculate_estate_tax(taxable_net_wan)

        # 封裝結果列
        row_data.update({
            "總資產": round(total_a_wan, 2),
            "總資產_萬": round(total_a_wan, 2),
            "總負債": round(total_liab_wan, 2),
            "淨資產": round(total_a_wan - total_liab_wan, 2),
            "預估遺產稅": round(estate_tax_result, 2),
            "預估遺產稅_萬": round(estate_tax_result, 2),
            "差額分配請求權": 0.0,
            "扣除額總計": ded_total,
            "扣除額明細": ded_details,
            "民法繼承基數": round(max(0.0, total_a_wan_estate - total_liab_wan), 2),
            "可分配餘額": round(max(0.0, total_a_wan_estate - total_liab_wan - estate_tax_result), 2),
            "身故觸發受益人AMT_預估": round(trigger_amt_base, 2),
            "保單總價值": round(total_cv_wan, 2),
            "保單理賠分配": insurance_payouts,
            "累積財務缺口": round(accumulated_deficit / 10000, 2),
            "收_主業薪資": round(temp_salary, 0),
            "收_其他所得": round(cur_extra_inc_gross, 0),
            "收_年金收入": round(temp_pension, 0),
            "收_保險還本": round(ins_survival_total, 0),
            "支_生活開銷": round(display_living_exp, 0),
            "支_保險費": round(ins_premium_total, 0),
            "支_房貸繳款": round(cur_house_pay, 0),
            "支_信貸繳款": round(cur_debt_pay, 0),
            "支_自提勞退": round(temp_pension_vol, 0),
            "支_所得稅金": round(final_income_tax_wan * 10000, 0),
            "稅_應納稅金": round(final_income_tax_wan, 2),
            "稅_基本差額": round(0.0, 2),
            "稅_申報人數": tax_people,
            "扣除額類型": "標準" if std_deduction > (savings_deduction + preschool_ded) else "列舉",
            "股利計稅": "合併計稅" if tax_scenario_1 <= tax_scenario_2 else "分開計稅",
            "觸發AMT": "是" if amt_tax > final_general_tax else "否",
            "稅_綜合所得總額": round(user_salary_wan + biz_other_wan + interest_inc + dividend_inc, 2),
            "稅_特扣總計": round(savings_deduction + preschool_ded, 2),
            "稅_綜合所得淨額": round(joint_net_inc, 2),
            "稅_一般應納稅額": round(final_general_tax, 2),
            "稅_AMT基本所得額": round(basic_income, 2),
            "稅_AMT稅額": round(amt_tax, 2),
            "存活字典": {
                "配偶": [{"name": "配偶"}] if is_spouse_alive else [],
                "子女": [{"name": f"子女 {i+1}"} for i, _ in enumerate(fam.kids)],
                "父母": [{"name": "父親"} if fam.has_father else []],
                "兄弟姊妹": [],
                "祖父母": []
            }
        })
        
        # 補齊個別資產水庫明細供歷史列表回填
        for nm, val in cur_bal.items():
            row_data[nm] = round(val, 0)
            
        history.append(row_data)

    return {
        "status": "success",
        "trajectory": history
    }