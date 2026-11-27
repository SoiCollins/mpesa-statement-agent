from mpesa_agent.models import Transaction

RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("suppliers", ("supplier", "wholesale", "stock purchase", "inventory", "bulk goods")),
    ("utilities", ("electricity", "water bill", "internet", "utility", "kplc")),
    ("fees", ("transaction fee", "service charge", "mpesa fee", "withdrawal fee")),
    ("payroll", ("salary", "payroll", "staff wages", "employee pay")),
    ("transport", ("fuel", "fare", "transport", "matatu", "delivery")),
    ("sales", ("customer payment", "sale", "payment received", "cash deposit")),
)


def categorize(transaction: Transaction) -> Transaction:
    searchable = f"{transaction.details} {transaction.transaction_type}".casefold()
    for category, keywords in RULES:
        if any(keyword in searchable for keyword in keywords):
            return transaction.model_copy(update={"category": category})
    return transaction.model_copy(update={"category": "other"})
