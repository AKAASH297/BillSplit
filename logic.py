"""
logic.py — Data models, validation, and bill-splitting logic.

Splitting rules:
  - Tax + Service Charge: combined and split equally among all people.
  - Discount: split equally and deducted from everyone's share.
  - Tip: split equally among all people.
"""
from dataclasses import dataclass, field

CURRENCY_SYMBOL = "$"


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class Item:
    name: str
    quantity: int
    unit_price: float
    tax: float = 0.0          # per-item tax (0 if not on bill)
    flagged: bool = False      # True if VLM returned incomplete data


@dataclass
class Person:
    name: str
    items: list[tuple['Item', float]] = field(default_factory=list)  # (Item, share_amount)

    @property
    def total(self) -> float:
        return sum(share for _, share in self.items)


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_items(items: list[Item]) -> list[Item]:
    """
    Flag items with missing or invalid fields.
    Items are mutated in place and also returned for convenience.
    """
    for item in items:
        if not item.name or not item.name.strip():
            item.flagged = True
        elif item.unit_price <= 0:
            item.flagged = True
        elif item.quantity <= 0:
            item.flagged = True
    return items


# ── Bill splitting ─────────────────────────────────────────────────────────────

def calculate_split(
    items: list[Item],
    assignments: dict[tuple[int, int], list[str]],
    people_names: list[str],
    global_tax: float,
    service_charge: float,
    discount: float,
    tip: float,
) -> list[Person]:
    """
    Calculate each person's total based on item assignments, taxes, and tip.

    Args:
        items: List of all bill items
        assignments: Maps (item_idx, unit_idx) -> list of person names sharing that unit
        people_names: All people splitting the bill
        global_tax: Lump-sum tax from bottom of bill
        service_charge: Service charge from the bill (split equally, combined with tax)
        discount: Discount on the bill (split equally, deducted from everyone)
        tip: Optional tip amount

    Returns:
        List of Person objects with itemized shares and computed totals
    """
    people = {name: Person(name=name) for name in people_names}
    n = len(people_names)

    for (item_idx, unit_idx), assigned_names in assignments.items():
        if not assigned_names:
            continue

        item = items[item_idx]
        # Cost per unit = unit_price + per-item tax
        cost_per_unit = item.unit_price + item.tax
        share = round(cost_per_unit / len(assigned_names), 2)

        for name in assigned_names:
            if name in people:
                people[name].items.append((item, share))

    # Combine global tax + service charge and split evenly across all people
    tax_and_service = global_tax + service_charge
    if tax_and_service > 0 and n > 0:
        combined_share = round(tax_and_service / n, 2)
        label = "Tax & Service Charge" if (global_tax > 0 and service_charge > 0) \
            else ("Tax" if global_tax > 0 else "Service Charge")
        combined_item = Item(name=label, quantity=1, unit_price=tax_and_service, tax=0.0)
        for person in people.values():
            person.items.append((combined_item, combined_share))

    # Split discount equally and deduct from everyone
    if discount > 0 and n > 0:
        discount_share = round(discount / n, 2)
        discount_item = Item(name="Discount", quantity=1, unit_price=-discount, tax=0.0)
        for person in people.values():
            person.items.append((discount_item, -discount_share))

    # Split tip evenly across all people
    if tip > 0 and n > 0:
        tip_share = round(tip / n, 2)
        tip_item = Item(name="Tip", quantity=1, unit_price=tip, tax=0.0)
        for person in people.values():
            person.items.append((tip_item, tip_share))

    return list(people.values())
