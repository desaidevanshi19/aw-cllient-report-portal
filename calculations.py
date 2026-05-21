"""
Pure calculation functions — no DB, no I/O.
All rules sourced directly from the PRD and client meeting transcript.
"""
from typing import Dict, List
from models import Client, Account


def calculate_report(
    client: Client,
    inflow: float,
    outflow: float,
    balances_by_account_id: Dict[int, float],
) -> dict:
    """
    Perform all SACS and TCC calculations.

    Rules from transcript:
    - excess = inflow - outflow
    - private_reserve_target = 6 × monthly_expense_budget  (or stored override)
    - client1_retirement_total = sum of client1 retirement balances
    - client2_retirement_total = sum of client2 retirement balances
    - non_retirement_total = sum of non_retirement balances  ← does NOT include trust
    - grand_total = c1_retirement + c2_retirement + non_retirement + trust
    - liabilities_total = sum of liability balances  ← NOT subtracted from net worth
    """
    excess = inflow - outflow

    # Use stored target override if set; otherwise default to 6× expense budget
    private_reserve_target = (
        client.private_reserve_target
        if client.private_reserve_target is not None
        else 6.0 * client.monthly_expense_budget
    )

    c1_retirement: float = 0.0
    c2_retirement: float = 0.0
    non_retirement: float = 0.0
    trust: float = 0.0
    liabilities: float = 0.0

    for account in client.accounts:
        balance = balances_by_account_id.get(account.id, 0.0)

        if account.category == "retirement":
            if account.owner == "client1":
                c1_retirement += balance
            elif account.owner == "client2":
                c2_retirement += balance
            # joint retirement → split or ignore; PRD does not mention joint retirement,
            # so we leave it out of both totals (safe default)

        elif account.category == "non_retirement":
            non_retirement += balance          # trust explicitly excluded per Rebecca

        elif account.category == "trust":
            trust += balance

        elif account.category == "liability":
            liabilities += balance             # displayed separately, never subtracted

        # "bank" category (private reserve / checking floor) → not in net worth

    grand_total = c1_retirement + c2_retirement + non_retirement + trust

    return {
        "excess": excess,
        "private_reserve_target": private_reserve_target,
        "client1_retirement_total": c1_retirement,
        "client2_retirement_total": c2_retirement,
        "non_retirement_total": non_retirement,
        "trust_total": trust,
        "grand_total": grand_total,
        "liabilities_total": liabilities,
    }
