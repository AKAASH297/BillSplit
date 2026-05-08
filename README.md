# 🧾 BillSplit

A single-session Streamlit app that turns a photo of a restaurant receipt into a clean, per-person cost breakdown — powered by a local or cloud Vision Language Model.

---

## Features

- **VLM receipt parsing** — upload a photo and extract items, quantities, prices, and tax via a multimodal model
- **Manual entry fallback** — if the VLM is unreachable or returns bad JSON, type items in by hand
- **Flagged-item review** — items with missing or suspicious fields are highlighted for correction
- **Unit-by-unit assignment** — each individual unit of a multi-quantity item is assigned separately; a *Split equally* shortcut handles shared items
- **Tax & tip handling** — per-item tax is folded into the item cost before splitting; global tax and optional tip are split evenly across all people
- **Itemized results** — each person sees exactly what they're paying for and their share of tax/tip
- **No persistence** — single-session only; data lives entirely in `st.session_state`

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI + server | Python 3.11+ · Streamlit ≥ 1.30 |
| VLM (default) | OpenRouter (`google/gemini-2.5-flash`) |
| Image handling | Pillow |

---

## Quickstart

### 1. Clone and enter the project

```bash
git clone <repo-url>
cd BillSplit
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501**. You can configure your VLM settings (API key, model, endpoint) directly in Step 1 of the app.

---

## Configuration

VLM settings are fully configurable through the UI in **Step 1 — Names**. 
Expand the **⚙️ VLM / AI Settings** section to input your Base URL, Model, and API Key.

| Setting | Default |
|---|---|
| Base URL | `https://openrouter.ai/api/v1` (OpenRouter) |
| Model | `google/gemini-2.5-flash` |
| API Key | (Empty, user must provide) |

To change the currency symbol, edit `CURRENCY_SYMBOL` in `logic.py`.

---

## User Flow

```
Step 1  Enter names        → who is splitting the bill?
Step 2  Upload receipt     → photo sent to VLM (or manual entry)
Step 3  Review & edit      → correct any flagged items
Step 4  Assign items       → who ordered what (unit by unit)
Step 5  Tip                → optional, split evenly
Step 6  Results            → per-person summary + itemized breakdown
```

---

## Project Structure

```
BillSplit/
├── app.py              # Entry point — page config, CSS, session state, step routing
├── ui.py               # All 6 step renderers (names, upload, review, assign, tip, results)
├── logic.py            # Data models (Item, Person), validation, bill-splitting math
├── vlm.py              # VLM client config + receipt image → structured JSON parser
├── requirements.txt
├── README.md
└── .streamlit/
    └── config.toml     # Dark theme (Slate + Emerald)
```

---

## Data Models

Defined in `logic.py`:

```python
@dataclass
class Item:
    name: str
    quantity: int
    unit_price: float
    tax: float = 0.0        # per-item tax; 0 if not on bill
    flagged: bool = False   # True if VLM returned incomplete data

@dataclass
class Person:
    name: str
    items: list[tuple[Item, float]]  # (item, share_amount)

    @property
    def total(self) -> float: ...
```

---

## Math & Splitting Logic

| Type | Where it appears on the bill | How it's split |
|---|---|---|
| Per-item tax (`item.tax`) | Printed next to the line item | Added to that item's cost before dividing among assignees |
| Global tax | Lump sum at the bottom | Combined with service charge and divided equally across **all** people |
| Service Charge | Lump sum at the bottom | Combined with global tax and divided equally across **all** people |
| Discount | Lump sum at the bottom | Divided equally across **all** people and deducted from their shares |
| Tip | User-entered | Divided equally across **all** people |

Both per-item and global tax can coexist on the same bill.

---

## VLM Prompt

The parser instructs the model to return **only raw JSON** (no markdown, no preamble):

```json
{
  "items": [
    {"name": "Margherita Pizza", "quantity": 2, "unit_price": 12.50, "tax": null},
    {"name": "Coke",             "quantity": 1, "unit_price":  3.00, "tax": 0.45}
  ],
  "tax": 4.20,
  "service_charge": 5.00,
  "discount": 0.00
}
```

- Any field the model can't determine confidently is returned as `null` → that item is flagged for user correction.
- Accidental code fences in the response are stripped before `json.loads()`.
- Any exception (network error, malformed JSON, missing `items` key) raises `VLMError`, which triggers a switch to manual entry mode.

---

## Development Notes

- **No database, no auth, no history** — all state is `st.session_state` and disappears on page refresh.
- The `.venv/` directory is gitignored. Always activate it before running the app.
- To add a new currency, change `CURRENCY_SYMBOL` in `logic.py` — it propagates everywhere via the import.
- VLM defaults can be altered by editing `DEFAULT_BASE_URL` and `DEFAULT_MODEL` in `vlm.py`.
