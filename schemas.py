# schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

# --- 1. 基礎時間軸參數 ---
class TimelineConfig(BaseModel):
    current_age: int = Field(..., description="當前年紀", ge=0, le=100)
    life_expectancy: int = Field(..., description="模擬至年紀", ge=0, le=120)
    retire_age: int = Field(..., description="預計退休年紀", ge=0, le=100)

# --- 2. 一般性資產結構 ---
class AssetItem(BaseModel):
    id: str
    name: str = Field(..., description="子帳戶自訂名稱")
    type: str = Field(..., description="資產主分類：現金、基金、股票、不動產、其他")
    value: float = Field(..., description="起始投入金額 (萬元)")
    rate: float = Field(..., description="預期年化報酬率")
    monthly_add: float = Field(0.0, description="每月定期定額金額 (萬元)")
    add_years: int = Field(0, description="每月定期定額持續年期")
    tax_type: str = Field(..., description="稅務屬性標籤")

# --- 3. 專業保單配置結構 ---
class InsuranceItem(BaseModel):
    id: str
    name: str
    type: str = Field(..., description="險種類別")
    appraiser: str = Field(..., description="要保人")
    insured: str = Field(..., description="被保險人")
    beneficiaries: List[str] = Field(..., description="身故受益人清單")
    custom_beneficiary: Optional[str] = None
    allocation_method: str = Field(..., description="均分比例 或 順位")
    premium: float = Field(..., description="年化保費總額 (萬元)")
    remaining_years: int = Field(..., description="剩餘繳費年期")
    current_cv: float = Field(..., description="目前保價金/解約金 (萬元)")
    expected_irr: float = Field(..., description="預期年化 IRR")
    death_benefit: float = Field(..., description="目前身故保額 (萬元)")
    survival_annuity: float = Field(0.0, description="年領生存還本金 (萬元)")
    survival_start_age: int = Field(65, description="生存金起領年紀")

# --- 4. 負債與房貸結構 ---
class LiabilityItem(BaseModel):
    id: str
    name: str = Field(..., description="債務名稱，如：自住房貸")
    start_age: int = Field(..., description="開始借款年紀")
    loan_amount: float = Field(..., description="貸款金額 (萬元)")
    years: int = Field(..., description="貸款年期")
    rate: float = Field(..., description="貸款利率")
    grace_period: int = Field(0, description="寬限期 (年)")
    method: str = Field(..., description="本利平均 或 本金平均")
    claim_tax: bool = Field(True, description="是否列報房貸利息抵稅")

# --- 5. 現金流與收支結構 (新補齊) ---
class ExtraIncome(BaseModel):
    name: str
    type: str = Field(..., description="所得類別，如 9A, 9B, 租賃所得等")
    monthly_amt: float = Field(..., description="每月收入 (元)")

class CashFlowConfig(BaseModel):
    main_salary_monthly: float = Field(0.0, description="主業薪資/月 (元)")
    salary_growth_rate: float = Field(0.012, description="預期薪資成長率")
    extra_incomes: List[ExtraIncome] = Field(default_factory=list, description="其他各類所得")
    living_expense_monthly: float = Field(0.0, description="生活雜費/餐費 (元)")
    rent_expense_monthly: float = Field(0.0, description="房租/水電 (元)")
    inflation_rate: float = Field(0.02, description="預估通貨膨脹率")

# --- 6. 家庭成員與扶養結構 (新補齊) ---
class DependentMember(BaseModel):
    id: str
    relation: str = Field(..., description="父親, 母親, 子女, 兄弟姊妹, 祖父母")
    age: int
    life_expectancy: int
    is_disabled: bool = Field(False, description="是否領有身心障礙手冊")
    is_ltc: bool = Field(False, description="是否符合長照資格")
    claim_tax_dependent: bool = Field(True, description="是否申報所得稅扶養")

class SpouseConfig(BaseModel):
    has_spouse: bool = False
    age: int = 30
    life_expectancy: int = 88
    is_disabled: bool = False
    is_ltc: bool = False
    salary_yearly: float = Field(0.0, description="配偶目前年薪 (萬元)")
    wealth_net: float = Field(0.0, description="配偶現有淨資產 (萬元，計算剩餘財產差額分配用)")

class FamilyConfig(BaseModel):
    spouse: SpouseConfig = SpouseConfig()
    dependents: List[DependentMember] = Field(default_factory=list)

# --- 7. 全局請求主體 (最終大裝配) ---
class FinancialAnalysisRequest(BaseModel):
    timeline: TimelineConfig
    assets: List[AssetItem]
    insurances: List[InsuranceItem]
    liabilities: List[LiabilityItem] = Field(default_factory=list)
    cashflow: CashFlowConfig = CashFlowConfig()
    family: FamilyConfig = FamilyConfig()