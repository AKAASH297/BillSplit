"""
vlm.py — VLM client setup and receipt image parsing.
"""
import json
import base64
import re

# pyrefly: ignore [missing-import]
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


def _detect_mime_type(image_bytes: bytes) -> str:
    """Sniff image magic bytes to return the correct MIME type."""
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if image_bytes[:4] in (b'RIFF',) and image_bytes[8:12] == b'WEBP':
        return "image/webp"
    if image_bytes[:3] == b'GIF':
        return "image/gif"
    # Default to JPEG (covers \xff\xd8\xff and other JPEG variants)
    return "image/jpeg"


_RECEIPT_PROMPT = (
    "Analyze this restaurant receipt/bill image and extract all items and tax information.\n\n"
    "Return ONLY a raw JSON object (no markdown, no code fences, no explanation) in this exact format:\n\n"
    '{\n  "items": [\n    {"name": "Item Name", "quantity": 1, "unit_price": 10.00, "tax": null}\n  ],\n  "tax": 0.00,\n  "service_charge": 0.00,\n  "discount": 0.00\n}\n\n'
    "Rules:\n"
    '- "name": the item name exactly as shown on the bill\n'
    '- "quantity": number of that item ordered (integer). Default to 1 if unclear.\n'
    '- "unit_price": price per single unit (float). If the bill shows a total line price for quantity > 1, divide by quantity.\n'
    '- "tax": per-item tax if printed next to the item on the bill, otherwise null\n'
    '- Top-level "tax": total/global tax amount if printed at the bottom of the bill, otherwise 0\n'
    '- Top-level "service_charge": any service charge, gratuity, or auto-tip printed at the bottom of the bill, otherwise 0\n'
    '- Top-level "discount": any discount or promotion amount printed at the bottom of the bill (as a positive number), otherwise 0\n'
    "- If you cannot determine a field confidently, use null for that field\n"
    "- Do NOT include subtotals, totals, or payment method lines as items\n"
    "- Do NOT include service charge or discount as items in the items list\n"
    "- Return ONLY the JSON object, nothing else"
)


def parse_receipt(image_bytes: bytes) -> tuple[list[Item], float, float, float]:
    """Send receipt image to VLM and parse into Items + global tax + service charge + discount."""
    client = _get_client()
    cfg = _get_active_config()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    mime_type = _detect_mime_type(image_bytes)

    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _RECEIPT_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}}
                ]
            }],
            max_tokens=4096,
            temperature=0.1,
        )
        msg = response.choices[0].message
        content = msg.content
        raw = content.strip() if content else ""
    except VLMError:
        raise
    except Exception as e:
        raise VLMError(f"VLM API call failed: {e}")

    if not raw:
        # Build a detailed diagnostic to help debug empty-response situations.
        # Some thinking/reasoning models (e.g. gemini-2.5-flash) return their
        # reply in non-standard fields when the standard content field is empty.
        msg = response.choices[0].message
        msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else vars(msg)

        # Try common alternative fields used by reasoning models
        for alt_field in ("reasoning", "reasoning_content", "thinking"):
            alt = msg_dict.get(alt_field) or getattr(msg, alt_field, None)
            if alt and str(alt).strip():
                raw = str(alt).strip()
                break

        # Check for content blocks (Anthropic-style thinking)
        if not raw:
            for block in msg_dict.get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    raw = block.get("text", "").strip()
                    if raw:
                        break

        if not raw:
            refusal = msg_dict.get("refusal") or getattr(msg, "refusal", None)
            finish_reason = response.choices[0].finish_reason
            diag = (
                f"finish_reason={finish_reason!r}\n"
                f"model={cfg['model']!r}\n"
                f"message fields: {list(msg_dict.keys())}\n"
                f"full message dump: {json.dumps(msg_dict, default=str)[:800]}"
            )
            if refusal:
                raise VLMError(f"Model refused to process the image: {refusal}\n\nDiagnostics:\n{diag}")
            raise VLMError(
                f"VLM returned an empty response.\n\n"
                f"**Likely causes:**\n"
                f"- The model `{cfg['model']}` may not support vision/image inputs\n"
                f"- The API key may lack permissions for this model\n"
                f"- Try switching to `google/gemini-2.0-flash` or `google/gemini-2.5-flash-preview-05-20`\n\n"
                f"**Diagnostics:**\n{diag}"
            )

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

    service_charge = data.get("service_charge", 0.0)
    if service_charge is None:
        service_charge = 0.0

    discount = data.get("discount", 0.0)
    if discount is None:
        discount = 0.0

    return items, global_tax, service_charge, discount
