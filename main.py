"""
AW Client Report Portal — FastAPI Backend
Railway-deployable, SQLite-backed.
"""
import os
from io import BytesIO
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import models
import schemas
from database import engine, get_db
from calculations import calculate_report
from pdf_sacs import generate_sacs_pdf
from pdf_tcc import generate_tcc_pdf

# ── Bootstrap ─────────────────────────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AW Client Report Portal",
    description="Financial planning portal for Windbrook Solutions — generates SACS and TCC reports.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client_or_404(client_id: int, db: Session) -> models.Client:
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
    return client


def _get_report_or_404(report_id: int, db: Session) -> models.Report:
    report = (
        db.query(models.Report)
        .filter(models.Report.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return report


def _orm_account_to_schema(acc: models.Account) -> schemas.AccountResponse:
    return schemas.AccountResponse(
        id=acc.id,
        clientId=acc.client_id,
        owner=acc.owner,
        category=acc.category,
        accountType=acc.account_type,
        accountName=acc.account_name,
        last4=acc.last4,
        interestRate=acc.interest_rate,
        propertyAddress=acc.property_address,
    )


def _orm_client_to_response(client: models.Client) -> schemas.ClientResponse:
    last_report_date = None
    if client.reports:
        last_report_date = client.reports[0].report_date
    return schemas.ClientResponse(
        id=client.id,
        firstName=client.first_name,
        lastName=client.last_name,
        dob=client.dob,
        ssnLast4=client.ssn_last4,
        isMarried=client.is_married,
        spouseFirstName=client.spouse_first_name,
        spouseLastName=client.spouse_last_name,
        spouseDob=client.spouse_dob,
        spouseSsnLast4=client.spouse_ssn_last4,
        monthlySalary=client.monthly_salary,
        monthlyExpenseBudget=client.monthly_expense_budget,
        privateReserveTarget=client.private_reserve_target,
        accounts=[_orm_account_to_schema(a) for a in client.accounts],
        lastReportDate=last_report_date,
    )


def _orm_report_to_response(report: models.Report) -> schemas.ReportResponse:
    return schemas.ReportResponse(
        id=report.id,
        clientId=report.client_id,
        quarter=report.quarter,
        year=report.year,
        reportDate=report.report_date,
        inflow=report.inflow,
        outflow=report.outflow,
        privateReserveBalance=report.private_reserve_balance,
        balances=[
            schemas.ReportBalance(
                accountId=rb.account_id,
                balance=rb.balance,
                cashBalance=rb.cash_balance,
            )
            for rb in report.balances
        ],
        calculations=schemas.ReportCalculations(
            excess=report.excess,
            privateReserveTarget=report.private_reserve_target_calc,
            client1RetirementTotal=report.client1_retirement_total,
            client2RetirementTotal=report.client2_retirement_total,
            nonRetirementTotal=report.non_retirement_total,
            trustTotal=report.trust_total,
            grandTotal=report.grand_total,
            liabilitiesTotal=report.liabilities_total,
        ),
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "service": "AW Client Report Portal", "version": "1.0.0"}


# ── Clients ───────────────────────────────────────────────────────────────────

@app.get("/clients", response_model=List[schemas.ClientSummary], tags=["Clients"])
def list_clients(db: Session = Depends(get_db)):
    """Return lightweight summary of all clients for the dashboard."""
    clients = db.query(models.Client).all()
    result = []
    for cl in clients:
        last_report_date = cl.reports[0].report_date if cl.reports else None
        result.append(schemas.ClientSummary(
            id=cl.id,
            firstName=cl.first_name,
            lastName=cl.last_name,
            isMarried=cl.is_married,
            spouseFirstName=cl.spouse_first_name,
            spouseLastName=cl.spouse_last_name,
            monthlySalary=cl.monthly_salary,
            monthlyExpenseBudget=cl.monthly_expense_budget,
            accountCount=len(cl.accounts),
            lastReportDate=last_report_date,
        ))
    return result


@app.post("/clients", response_model=schemas.ClientResponse, status_code=status.HTTP_201_CREATED, tags=["Clients"])
def create_client(payload: schemas.ClientCreate, db: Session = Depends(get_db)):
    """Create a new client with accounts (3-step wizard submission)."""
    client = models.Client(
        first_name=payload.firstName,
        last_name=payload.lastName,
        dob=payload.dob,
        ssn_last4=payload.ssnLast4,
        is_married=payload.isMarried,
        spouse_first_name=payload.spouseFirstName,
        spouse_last_name=payload.spouseLastName,
        spouse_dob=payload.spouseDob,
        spouse_ssn_last4=payload.spouseSsnLast4,
        monthly_salary=payload.monthlySalary,
        monthly_expense_budget=payload.monthlyExpenseBudget,
        private_reserve_target=payload.privateReserveTarget,
    )
    db.add(client)
    db.flush()  # get client.id before inserting accounts

    for acc in payload.accounts:
        db.add(models.Account(
            client_id=client.id,
            owner=acc.owner,
            category=acc.category,
            account_type=acc.accountType,
            account_name=acc.accountName,
            last4=acc.last4,
            interest_rate=acc.interestRate,
            property_address=acc.propertyAddress,
        ))

    db.commit()
    db.refresh(client)
    return _orm_client_to_response(client)


@app.get("/clients/{client_id}", response_model=schemas.ClientResponse, tags=["Clients"])
def get_client(client_id: int, db: Session = Depends(get_db)):
    """Return full client record with all accounts."""
    return _orm_client_to_response(_get_client_or_404(client_id, db))


@app.put("/clients/{client_id}", response_model=schemas.ClientResponse, tags=["Clients"])
def update_client(client_id: int, payload: schemas.ClientUpdate, db: Session = Depends(get_db)):
    """Update client profile and replace their account list."""
    client = _get_client_or_404(client_id, db)

    client.first_name = payload.firstName
    client.last_name = payload.lastName
    client.dob = payload.dob
    client.ssn_last4 = payload.ssnLast4
    client.is_married = payload.isMarried
    client.spouse_first_name = payload.spouseFirstName
    client.spouse_last_name = payload.spouseLastName
    client.spouse_dob = payload.spouseDob
    client.spouse_ssn_last4 = payload.spouseSsnLast4
    client.monthly_salary = payload.monthlySalary
    client.monthly_expense_budget = payload.monthlyExpenseBudget
    client.private_reserve_target = payload.privateReserveTarget

    # Replace accounts (delete old, insert new)
    for acc in list(client.accounts):
        db.delete(acc)
    db.flush()

    for acc in payload.accounts:
        db.add(models.Account(
            client_id=client.id,
            owner=acc.owner,
            category=acc.category,
            account_type=acc.accountType,
            account_name=acc.accountName,
            last4=acc.last4,
            interest_rate=acc.interestRate,
            property_address=acc.propertyAddress,
        ))

    db.commit()
    db.refresh(client)
    return _orm_client_to_response(client)


@app.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Clients"])
def delete_client(client_id: int, db: Session = Depends(get_db)):
    client = _get_client_or_404(client_id, db)
    db.delete(client)
    db.commit()


# ── Reports ───────────────────────────────────────────────────────────────────

@app.get("/clients/{client_id}/reports", response_model=List[schemas.ReportSummary], tags=["Reports"])
def list_client_reports(client_id: int, db: Session = Depends(get_db)):
    """Return report history for a client (summary only)."""
    _get_client_or_404(client_id, db)
    reports = (
        db.query(models.Report)
        .filter(models.Report.client_id == client_id)
        .order_by(models.Report.year.desc(), models.Report.quarter.desc())
        .all()
    )
    return [
        schemas.ReportSummary(
            id=r.id,
            quarter=r.quarter,
            year=r.year,
            reportDate=r.report_date,
        )
        for r in reports
    ]


@app.post("/reports", response_model=schemas.ReportResponse, status_code=status.HTTP_201_CREATED, tags=["Reports"])
def create_report(payload: schemas.ReportData, db: Session = Depends(get_db)):
    """
    Save balance data, run all calculations, persist the report.
    Returns full ReportResponse including calculations.
    """
    client = _get_client_or_404(payload.clientId, db)

    # Build a lookup for entered balances
    balances_map = {rb.accountId: rb.balance for rb in payload.balances}

    # Run calculations
    calcs = calculate_report(client, payload.inflow, payload.outflow, balances_map)

    # Persist report
    report = models.Report(
        client_id=payload.clientId,
        quarter=payload.quarter,
        year=payload.year,
        report_date=payload.reportDate,
        inflow=payload.inflow,
        outflow=payload.outflow,
        private_reserve_balance=payload.privateReserveBalance,
        excess=calcs["excess"],
        private_reserve_target_calc=calcs["private_reserve_target"],
        client1_retirement_total=calcs["client1_retirement_total"],
        client2_retirement_total=calcs["client2_retirement_total"],
        non_retirement_total=calcs["non_retirement_total"],
        trust_total=calcs["trust_total"],
        grand_total=calcs["grand_total"],
        liabilities_total=calcs["liabilities_total"],
    )
    db.add(report)
    db.flush()

    for rb in payload.balances:
        # Validate account belongs to this client
        acc = db.query(models.Account).filter(
            models.Account.id == rb.accountId,
            models.Account.client_id == payload.clientId,
        ).first()
        if not acc:
            raise HTTPException(
                status_code=400,
                detail=f"Account {rb.accountId} does not belong to client {payload.clientId}",
            )
        db.add(models.ReportBalance(
            report_id=report.id,
            account_id=rb.accountId,
            balance=rb.balance,
            cash_balance=rb.cashBalance,
        ))

    db.commit()
    db.refresh(report)
    return _orm_report_to_response(report)


@app.get("/reports/{report_id}", response_model=schemas.ReportResponse, tags=["Reports"])
def get_report(report_id: int, db: Session = Depends(get_db)):
    """Get a single report with full calculations and balances."""
    return _orm_report_to_response(_get_report_or_404(report_id, db))


@app.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Reports"])
def delete_report(report_id: int, db: Session = Depends(get_db)):
    report = _get_report_or_404(report_id, db)
    db.delete(report)
    db.commit()


# ── PDF Export ────────────────────────────────────────────────────────────────

@app.get("/reports/{report_id}/pdf/sacs", tags=["PDF"])
def download_sacs_pdf(report_id: int, db: Session = Depends(get_db)):
    """
    Stream a SACS (Simple Automated Cash Flow System) PDF.
    Content-Type: application/pdf
    """
    report = _get_report_or_404(report_id, db)
    client = report.client
    calcs = {
        "excess":                    report.excess,
        "private_reserve_target":    report.private_reserve_target_calc,
        "client1_retirement_total":  report.client1_retirement_total,
        "client2_retirement_total":  report.client2_retirement_total,
        "non_retirement_total":      report.non_retirement_total,
        "trust_total":               report.trust_total,
        "grand_total":               report.grand_total,
        "liabilities_total":         report.liabilities_total,
    }
    pdf_bytes = generate_sacs_pdf(client, report, calcs)
    filename  = f"SACS_{client.last_name}_{report.quarter}{report.year}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/reports/{report_id}/pdf/tcc", tags=["PDF"])
def download_tcc_pdf(report_id: int, db: Session = Depends(get_db)):
    """
    Stream a TCC (Total Client Chart) PDF.
    Content-Type: application/pdf
    """
    report = _get_report_or_404(report_id, db)
    client = report.client
    balances_map = {rb.account_id: rb.balance for rb in report.balances}
    calcs = {
        "excess":                    report.excess,
        "private_reserve_target":    report.private_reserve_target_calc,
        "client1_retirement_total":  report.client1_retirement_total,
        "client2_retirement_total":  report.client2_retirement_total,
        "non_retirement_total":      report.non_retirement_total,
        "trust_total":               report.trust_total,
        "grand_total":               report.grand_total,
        "liabilities_total":         report.liabilities_total,
    }
    pdf_bytes = generate_tcc_pdf(client, report, balances_map, calcs)
    filename  = f"TCC_{client.last_name}_{report.quarter}{report.year}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
