"""Transaction model — fund buy/sell/convert/DCA records."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TxType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    CONVERT = "convert"
    DIVIDEND_INVEST = "dividend_invest"


class TxStatus(str, Enum):
    PENDING = "pending"      # 已下单，等待净值确认 (T+1)
    CONFIRMED = "confirmed"  # 已用真实净值确认份额
    FAILED = "failed"        # 多次拉取净值失败


class DCAFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class Transaction(BaseModel):
    tx_id: str = Field(..., description="Unique transaction ID")
    user_id: str
    fund_code: str = Field(..., pattern=r"^\d{6}$")
    fund_name: str = ""
    tx_type: TxType
    date: datetime = Field(..., description="用户提交的下单时间 (UTC)")
    submitted_at: datetime | None = Field(None, description="实际提交时间")
    confirm_date: datetime | None = Field(None, description="预计净值确认日期")
    status: TxStatus = TxStatus.PENDING
    nav_source: Literal["estimated", "confirmed"] = "estimated"
    amount: float = Field(..., description="申购金额或赎回金额（元）")
    shares: float = Field(..., description="份额变动（买为正、卖为负）")
    nav: float = Field(..., description="净值（待确认时为估算值）")
    fee: float = Field(default=0.0, description="手续费")
    source_fund_code: str | None = Field(None, description="转换源基金（仅 convert 类型）")
    notes: str = ""
    created_at: datetime
    confirmed_at: datetime | None = None
    is_dca: bool = Field(default=False, description="是否定投自动生成")
    dca_plan_id: str | None = None


class DCAPlan(BaseModel):
    plan_id: str
    user_id: str
    fund_code: str = Field(..., pattern=r"^\d{6}$")
    fund_name: str = ""
    frequency: DCAFrequency
    amount: float = Field(..., gt=0)
    day_of_month: int | None = Field(None, ge=1, le=28, description="每月第几天 (monthly)")
    day_of_week: int | None = Field(None, ge=1, le=7, description="周几 (weekly/biweekly), 1=Mon")
    anchor_date: datetime | None = Field(None, description="biweekly 起始日，用于14天计算")
    status: Literal["active", "paused"] = "active"
    last_executed: datetime | None = None
    created_at: datetime



class DCAPlan(BaseModel):
    plan_id: str
    user_id: str
    fund_code: str = Field(..., pattern=r"^\d{6}$")
    fund_name: str = ""
    frequency: DCAFrequency
    amount: float = Field(..., gt=0)
    # frequency-specific fields:
    day_of_month: int | None = Field(None, ge=1, le=28, description="每月第几天 (monthly)")
    day_of_week: int | None = Field(None, ge=1, le=7, description="周几 (weekly/biweekly), 1=Mon")
    anchor_date: datetime | None = Field(None, description="biweekly 起始日，用于14天计算")
    status: Literal["active", "paused"] = "active"
    last_executed: datetime | None = None
    created_at: datetime
