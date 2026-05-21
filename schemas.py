from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

# ── Enums (as Literal types) ──────────────────────────────────────────────────

AccountCategory = Literal["retirement", "non_retirement", "trust", "liability", "bank"]
AccountOwner = Literal["client1", "client2", "joint"]
AccountType = Literal[
    "ira", "roth_ira", "401k", "pension",
    "brokerage", "joint", "checking", "savings",
    "trust", "mortgage", "auto_loan", "other"
]
Quarter = Literal["Q1", "Q2", "Q3", "Q4"]


# ── Account ───────────────────────────────────────────────────────────────────

class AccountBase(BaseModel):
    owner: AccountOwner
    category: AccountCategory
    accountType: AccountType
    accountName: str
    last4: Optional[str] = None
    interestRate: Optional[float] = None
    propertyAddress: Optional[str] = None


class AccountCreate(AccountBase):
    pass


class AccountResponse(AccountBase):
    id: int
    clientId: int

    class Config:
        from_attributes = True


# ── Client ────────────────────────────────────────────────────────────────────

class ClientBase(BaseModel):
    firstName: str
    lastName: str
    dob: Optional[str] = None
    ssnLast4: Optional[str] = None
    isMarried: bool = False
    spouseFirstName: Optional[str] = None
    spouseLastName: Optional[str] = None
    spouseDob: Optional[str] = None
    spouseSsnLast4: Optional[str] = None
    monthlySalary: float = 0
    monthlyExpenseBudget: float = 0
    privateReserveTarget: Optional[float] = None


class ClientCreate(ClientBase):
    accounts: List[AccountCreate] = []


class ClientUpdate(ClientBase):
    accounts: List[AccountCreate] = []


class ClientResponse(ClientBase):
    id: int
    accounts: List[AccountResponse] = []
    lastReportDate: Optional[str] = None

    class Config:
        from_attributes = True


class ClientSummary(BaseModel):
    """Lightweight client object for the list view."""
    id: int
    firstName: str
    lastName: str
    isMarried: bool
    spouseFirstName: Optional[str] = None
    spouseLastName: Optional[str] = None
    monthlySalary: float
    monthlyExpenseBudget: float
    accountCount: int
    lastReportDate: Optional[str] = None

    class Config:
        from_attributes = True


# ── Report ────────────────────────────────────────────────────────────────────

class ReportBalance(BaseModel):
    accountId: int
    balance: float
    cashBalance: Optional[float] = None


class ReportData(BaseModel):
    clientId: int
    quarter: Quarter
    year: int
    reportDate: str
    inflow: float
    outflow: float
    privateReserveBalance: float
    balances: List[ReportBalance] = []


class ReportCalculations(BaseModel):
    excess: float
    privateReserveTarget: float
    client1RetirementTotal: float
    client2RetirementTotal: float
    nonRetirementTotal: float
    trustTotal: float
    grandTotal: float
    liabilitiesTotal: float


class ReportResponse(ReportData):
    id: int
    calculations: ReportCalculations

    class Config:
        from_attributes = True


class ReportSummary(BaseModel):
    id: int
    quarter: str
    year: int
    reportDate: str

    class Config:
        from_attributes = True
