from __future__ import annotations
from typing import List, Optional, Literal
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator, model_validator, computed_field
import re

# ── Enums ─────────────────────────────────────────────────────────────────────

AccountCategory = Literal["retirement", "non_retirement", "trust", "liability", "bank"]
AccountOwner    = Literal["client1", "client2", "joint"]
AccountType     = Literal[
    "ira", "roth_ira", "401k", "pension",
    "brokerage", "joint", "checking", "savings",
    "trust", "mortgage", "auto_loan", "other"
]
Quarter = Literal["Q1", "Q2", "Q3", "Q4"]

CATEGORY_TYPE_MAP = {
    "retirement":     {"ira", "roth_ira", "401k", "pension", "other"},
    "non_retirement": {"brokerage", "joint", "checking", "savings", "other"},
    "trust":          {"trust", "other"},
    "liability":      {"mortgage", "auto_loan", "other"},
    "bank":           {"checking", "savings", "other"},
}


# ── Age helper ────────────────────────────────────────────────────────────────

def _calculate_age(dob_str: str) -> int:
    """Return age in whole years from a YYYY-MM-DD string."""
    dob    = datetime.strptime(dob_str, "%Y-%m-%d").date()
    today  = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ── Account ───────────────────────────────────────────────────────────────────

class AccountBase(BaseModel):
    owner:           AccountOwner
    category:        AccountCategory
    accountType:     AccountType
    accountName:     str             = Field(..., min_length=1, max_length=100)
    last4:           Optional[str]   = None
    interestRate:    Optional[float] = None
    propertyAddress: Optional[str]   = None

    @field_validator("accountName")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("accountName must not be blank")
        return v.strip()

    @field_validator("last4")
    @classmethod
    def last4_digits(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"\d{4}", v):
            raise ValueError("last4 must be exactly 4 digits (e.g. '1234')")
        return v

    @field_validator("interestRate")
    @classmethod
    def interest_rate_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if v < 0:
                raise ValueError("interestRate must be 0 or greater")
            if v > 100:
                raise ValueError("interestRate must be a percentage value (0–100)")
        return v

    @model_validator(mode="after")
    def category_type_match(self) -> "AccountBase":
        allowed = CATEGORY_TYPE_MAP.get(self.category, set())
        if self.accountType not in allowed:
            raise ValueError(
                f"accountType '{self.accountType}' is not valid for category "
                f"'{self.category}'. Allowed types: {sorted(allowed)}"
            )
        return self

    @model_validator(mode="after")
    def liability_needs_rate(self) -> "AccountBase":
        if self.category == "liability" and self.interestRate is None:
            raise ValueError("interestRate is required for liability accounts")
        return self

    @model_validator(mode="after")
    def trust_needs_address(self) -> "AccountBase":
        if self.category == "trust" and not self.propertyAddress:
            raise ValueError("propertyAddress is required for trust/property accounts")
        return self


class AccountCreate(AccountBase):
    pass


class AccountResponse(AccountBase):
    id:       int
    clientId: int

    class Config:
        from_attributes = True


# ── Client ────────────────────────────────────────────────────────────────────

class ClientBase(BaseModel):
    firstName:            str           = Field(..., min_length=1, max_length=50)
    lastName:             str           = Field(..., min_length=1, max_length=50)
    # DOB and SSN are required per PRD: "Add a new client with: name(s), DOB,
    # age (auto-calculated), last four of SSN"
    dob:                  str           = Field(..., description="Required. Format: YYYY-MM-DD")
    ssnLast4:             str           = Field(..., description="Required. Exactly 4 digits.")
    isMarried:            bool          = False
    spouseFirstName:      Optional[str] = Field(None, max_length=50)
    spouseLastName:       Optional[str] = Field(None, max_length=50)
    spouseDob:            Optional[str] = None
    spouseSsnLast4:       Optional[str] = None
    monthlySalary:        float         = Field(..., ge=0)
    monthlyExpenseBudget: float         = Field(..., ge=0)
    privateReserveTarget: Optional[float] = Field(None, ge=0)

    @field_validator("firstName", "lastName", "spouseFirstName", "spouseLastName")
    @classmethod
    def name_alpha(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Name fields must not be blank")
        if not re.fullmatch(r"[A-Za-z\s\-'\.]+", v):
            raise ValueError("Name must contain only letters, spaces, hyphens, or apostrophes")
        return v

    @field_validator("ssnLast4", "spouseSsnLast4")
    @classmethod
    def ssn_four_digits(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"\d{4}", v):
            raise ValueError("SSN last 4 must be exactly 4 digits")
        return v

    @field_validator("dob", "spouseDob")
    @classmethod
    def valid_dob(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                parsed = datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format (e.g. '1975-06-15')")
            if parsed.year < 1900:
                raise ValueError("Date of birth year must be 1900 or later")
            if parsed > datetime.now():
                raise ValueError("Date of birth cannot be in the future")
        return v

    @model_validator(mode="before")
    @classmethod
    def clear_spouse_if_single(cls, data):
        """
        Runs BEFORE field-level validators.
        When isMarried=false, wipe all spouse fields so their validators
        never fire — even if the caller accidentally sent values for them.
        """
        if isinstance(data, dict) and not data.get("isMarried", False):
            for field in ("spouseFirstName", "spouseLastName",
                          "spouseDob", "spouseSsnLast4"):
                data[field] = None
        return data

    @model_validator(mode="after")
    def budget_lte_salary(self) -> "ClientBase":
        if self.monthlyExpenseBudget > self.monthlySalary:
            raise ValueError(
                f"monthlyExpenseBudget ({self.monthlyExpenseBudget}) cannot exceed "
                f"monthlySalary ({self.monthlySalary})"
            )
        return self

    @model_validator(mode="after")
    def spouse_fields_required(self) -> "ClientBase":
        if self.isMarried:
            missing = []
            if not self.spouseFirstName:
                missing.append("spouseFirstName")
            if not self.spouseLastName:
                missing.append("spouseLastName")
            if not self.spouseDob:
                missing.append("spouseDob")
            if not self.spouseSsnLast4:
                missing.append("spouseSsnLast4")
            if missing:
                raise ValueError(
                    f"When isMarried is true, these fields are required: {missing}"
                )
        if not self.isMarried:
            self.spouseFirstName  = None
            self.spouseLastName   = None
            self.spouseDob        = None
            self.spouseSsnLast4   = None
        return self


class ClientCreate(ClientBase):
    accounts: List[AccountCreate] = []

    @field_validator("accounts")
    @classmethod
    def at_least_one_account(cls, v: list) -> list:
        if len(v) == 0:
            raise ValueError("At least one account is required")
        if len(v) > 50:
            raise ValueError("A client cannot have more than 50 accounts")
        return v


class ClientUpdate(ClientBase):
    accounts: List[AccountCreate] = []

    @field_validator("accounts")
    @classmethod
    def at_least_one_account(cls, v: list) -> list:
        if len(v) == 0:
            raise ValueError("At least one account is required")
        return v


class ClientResponse(ClientBase):
    id:             int
    accounts:       List[AccountResponse] = []
    lastReportDate: Optional[str]         = None

    # Age is auto-calculated from dob — never stored, always derived
    @computed_field
    @property
    def age(self) -> int:
        return _calculate_age(self.dob)

    # Spouse age auto-calculated from spouseDob if present
    @computed_field
    @property
    def spouseAge(self) -> Optional[int]:
        if self.spouseDob:
            return _calculate_age(self.spouseDob)
        return None

    class Config:
        from_attributes = True


class ClientSummary(BaseModel):
    id:                   int
    firstName:            str
    lastName:             str
    isMarried:            bool
    spouseFirstName:      Optional[str] = None
    spouseLastName:       Optional[str] = None
    monthlySalary:        float
    monthlyExpenseBudget: float
    accountCount:         int
    lastReportDate:       Optional[str] = None

    class Config:
        from_attributes = True


# ── Report ────────────────────────────────────────────────────────────────────

class ReportBalance(BaseModel):
    accountId:   int   = Field(..., ge=1)
    balance:     float = Field(..., ge=0)
    cashBalance: Optional[float] = Field(None, ge=0)


class ReportData(BaseModel):
    clientId:              int   = Field(..., ge=1)
    quarter:               Quarter
    year:                  int   = Field(..., ge=2000, le=2100)
    reportDate:            str
    inflow:                float = Field(..., ge=0)
    outflow:               float = Field(..., ge=0)
    privateReserveBalance: float = Field(..., ge=0)
    balances:              List[ReportBalance] = []

    @field_validator("reportDate")
    @classmethod
    def valid_report_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("reportDate must be in YYYY-MM-DD format (e.g. '2026-05-21')")
        return v

    @field_validator("balances")
    @classmethod
    def no_duplicate_accounts(cls, v: List[ReportBalance]) -> List[ReportBalance]:
        ids = [b.accountId for b in v]
        if len(ids) != len(set(ids)):
            raise ValueError("balances contains duplicate accountId entries")
        return v

    @model_validator(mode="after")
    def outflow_lte_inflow(self) -> "ReportData":
        if self.outflow > self.inflow:
            raise ValueError(
                f"outflow ({self.outflow}) cannot exceed inflow ({self.inflow})"
            )
        return self


class ReportCalculations(BaseModel):
    excess:                  float
    privateReserveTarget:    float
    client1RetirementTotal:  float
    client2RetirementTotal:  float
    nonRetirementTotal:      float
    trustTotal:              float
    grandTotal:              float
    liabilitiesTotal:        float


class ReportResponse(ReportData):
    id:           int
    calculations: ReportCalculations

    class Config:
        from_attributes = True


class ReportSummary(BaseModel):
    id:         int
    quarter:    str
    year:       int
    reportDate: str

    class Config:
        from_attributes = True
