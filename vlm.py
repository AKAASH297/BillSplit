"""
vlm.py — VLM client setup and receipt image parsing.
"""
import json
import base64
import re

import streamlit as st
from openai import OpenAI
from logic import Item


# Default VLM settings (OpenRouter)
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-2.5-flash"
DEFAULT_API_KEY = ""


class VLMError(Exception):
    pass


def _get_active_config() -> dict:
    """Return the active VLM config dict from session state."""
    return {
        "base_url": st.session_state.get("vlm_base_url", DEFAULT_BASE_URL),
        "model": st.session_state.get("vlm_model", DEFAULT_MODEL),
        "api_key": st.session_state.get("vlm_api_key", DEFAULT_API_KEY),
    }


def _get_client() -> OpenAI:
    cfg = _get_active_config()
    if not cfg["api_key"].strip():
        raise VLMError("API key is not set. Please enter your API key in ⚙️ VLM Settings on Step 1.")
    return OpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        default_headers={
            "HTTP-Referer": "https://github.com/BillSplit",
            "X-Title": "BillSplit",
        },
    )


_RECEIPT_PROMPT = (
    "Analyze this restaurant receipt/bill image and extract all items and tax information.\n\n"
    "Return ONLY a raw JSON object (no markdown, no code fences, no explanation) in this exact format:\n\n"
    '{\n  "items": [\n    {"name": "Item Name", "quantity": 1, "unit_price": 10.00, "tax": null}\n  ],\n  "tax": 0.00\n}\n\n'
    "Rules:\n"
    '- "name": the item name exactly as shown on the bill\n'
    '- "quantity": number of that item ordered (integer). Default to 1 if unclear.\n'
    '- "unit_price": price per single unit (float). If the bill shows a total line price for quantity > 1, divide by quantity.\n'
    '- "tax": per-item tax if printed next to the item on the bill, otherwise null\n'
    '- Top-level "tax": total/global tax amount if printed at the bottom of the bill, otherwise 0\n'
    "- If you cannot determine a field confidently, use null for that field\n"
    "- Do NOT include subtotals, totals, or payment method lines as items\n"
    "- Return ONLY the JSON object, nothing else"
)


def parse_receipt(image_bytes: bytes) -> tuple[list[Item], float]:
    """Send receipt image to VLM and parse into Items + global tax."""
    client = _get_client()
    cfg = _get_active_config()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _RECEIPT_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                ]
            }],
            max_tokens=2048,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
    except VLMError:
        raise
    except Exception as e:
        raise VLMError(f"VLM API call failed: {e}")

    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise VLMError(f"VLM returned invalid JSON: {e}\n\nRaw response:\n{raw[:500]}")

    if not isinstance(data, dict) or "items" not in data:
        raise VLMError(f"VLM response missing 'items' key.\n\nRaw response:\n{raw[:500]}")

    items = []
    for d in data.get("items", []):
        name = d.get("name")
        quantity = d.get("quantity")
        unit_price = d.get("unit_price")
        tax = d.get("tax")
        flagged = name is None or quantity is None or unit_price is None
        items.append(Item(
            name=name or "",
            quantity=quantity if quantity is not None else 1,
            unit_price=unit_price if unit_price is not None else 0.0,
            tax=tax if tax is not None else 0.0,
            flagged=flagged
        ))

    global_tax = data.get("tax", 0.0)
    if global_tax is None:
        global_tax = 0.0

    return items, global_tax
