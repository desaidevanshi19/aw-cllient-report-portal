from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    dob = Column(String, nullable=True)
    ssn_last4 = Column(String, nullable=True)
    is_married = Column(Boolean, default=False)
    spouse_first_name = Column(String, nullable=True)
    spouse_last_name = Column(String, nullable=True)
    spouse_dob = Column(String, nullable=True)
    spouse_ssn_last4 = Column(String, nullable=True)
    monthly_salary = Column(Float, nullable=False, default=0)
    monthly_expense_budget = Column(Float, nullable=False, default=0)
    private_reserve_target = Column(Float, nullable=True)

    accounts = relationship("Account", back_populates="client", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="client", cascade="all, delete-orphan", order_by="Report.id.desc()")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    owner = Column(String, nullable=False)           # client1 | client2 | joint
    category = Column(String, nullable=False)         # retirement | non_retirement | trust | liability | bank
    account_type = Column(String, nullable=False)     # ira | roth_ira | 401k | pension | ...
    account_name = Column(String, nullable=False)
    last4 = Column(String, nullable=True)
    interest_rate = Column(Float, nullable=True)
    property_address = Column(String, nullable=True)

    client = relationship("Client", back_populates="accounts")
    report_balances = relationship("ReportBalance", back_populates="account", cascade="all, delete-orphan")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    quarter = Column(String, nullable=False)          # Q1 | Q2 | Q3 | Q4
    year = Column(Integer, nullable=False)
    report_date = Column(String, nullable=False)      # ISO date string
    inflow = Column(Float, nullable=False, default=0)
    outflow = Column(Float, nullable=False, default=0)
    private_reserve_balance = Column(Float, nullable=False, default=0)

    # Stored calculations
    excess = Column(Float, nullable=False, default=0)
    private_reserve_target_calc = Column(Float, nullable=False, default=0)
    client1_retirement_total = Column(Float, nullable=False, default=0)
    client2_retirement_total = Column(Float, nullable=False, default=0)
    non_retirement_total = Column(Float, nullable=False, default=0)
    trust_total = Column(Float, nullable=False, default=0)
    grand_total = Column(Float, nullable=False, default=0)
    liabilities_total = Column(Float, nullable=False, default=0)

    client = relationship("Client", back_populates="reports")
    balances = relationship("ReportBalance", back_populates="report", cascade="all, delete-orphan")


class ReportBalance(Base):
    __tablename__ = "report_balances"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    balance = Column(Float, nullable=False, default=0)
    cash_balance = Column(Float, nullable=True)

    report = relationship("Report", back_populates="balances")
    account = relationship("Account", back_populates="report_balances")
