"""
ui.py — All step renderers for the BillSplit wizard.
"""
import streamlit as st

from logic import Item, Person, CURRENCY_SYMBOL, validate_items, calculate_split
from vlm import parse_receipt, VLMError, DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_API_KEY


# ═══════════════════════════════════════════════════════════════════════════════
#  Step 1 — Names
# ═══════════════════════════════════════════════════════════════════════════════

def render_names() -> None:
    st.subheader("Step 1 — Who's splitting the bill?")
    st.caption("Add every person who will be paying. You need at least 2 people to continue.")

    with st.form("names_form", clear_on_submit=True):
        new_name = st.text_input("Add a person", placeholder="e.g. Alice", max_chars=40)
        add_clicked = st.form_submit_button("➕ Add", use_container_width=True)

    if add_clicked and new_name.strip():
        name = new_name.strip()
        if name in st.session_state["people"]:
            st.warning(f'"{name}" is already on the list.')
        else:
            st.session_state["people"].append(name)
            st.rerun()

    people: list[str] = st.session_state["people"]

    if people:
        st.markdown("#### 👥 People")
        for i, name in enumerate(people):
            col_name, col_remove = st.columns([5, 1])
            col_name.markdown(
                f'<div style="padding:6px 0;font-weight:500;">{name}</div>',
                unsafe_allow_html=True,
            )
            if col_remove.button("✕", key=f"remove_{i}", help=f"Remove {name}"):
                st.session_state["people"].pop(i)
                st.rerun()
    else:
        st.info("No people added yet. Type a name above and click **Add**.")

    st.divider()

    # ── VLM Configuration ─────────────────────────────────────────────────────
    with st.expander("⚙️ VLM / AI Settings", expanded=False):
        st.caption("Configure the Vision Language Model used for receipt parsing.")

        # Initialise defaults on first run
        if "vlm_base_url" not in st.session_state:
            st.session_state["vlm_base_url"] = DEFAULT_BASE_URL
        if "vlm_model" not in st.session_state:
            st.session_state["vlm_model"] = DEFAULT_MODEL
        if "vlm_api_key" not in st.session_state:
            st.session_state["vlm_api_key"] = DEFAULT_API_KEY

        col_url, col_model = st.columns(2)
        with col_url:
            st.text_input(
                "Base URL",
                key="vlm_base_url",
                help="OpenAI-compatible API base URL (default: OpenRouter).",
            )
        with col_model:
            st.text_input(
                "Model",
                key="vlm_model",
                help="Model identifier (e.g. google/gemini-2.5-flash-image).",
            )

        st.text_input(
            "API Key",
            key="vlm_api_key",
            type="password",
            help="API key for the endpoint.",
        )

    col_left, col_right = st.columns([3, 1])
    with col_right:
        if st.button("Continue →", disabled=len(people) < 2, use_container_width=True, type="primary"):
            st.session_state["step"] = 2
            st.rerun()

    if len(people) == 1:
        st.caption("⚠ Add at least one more person before continuing.")


# ═══════════════════════════════════════════════════════════════════════════════
#  Step 2 — Upload / Manual Entry
# ═══════════════════════════════════════════════════════════════════════════════

def _empty_item() -> Item:
    return Item(name="", quantity=1, unit_price=0.0, tax=0.0, flagged=True)


def render_upload() -> None:
    st.subheader("Step 2 — Upload your receipt")
    if st.session_state.get("manual_mode", False):
        _render_manual_ui()
    else:
        _render_upload_ui()


def _render_upload_ui() -> None:
    st.caption("Take a clear photo of the bill and upload it below.")

    uploaded = st.file_uploader(
        "Receipt image", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed",
    )

    col_back, _, col_parse = st.columns([1, 3, 1])
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state["step"] = 1
            st.rerun()

    if uploaded is not None:
        st.image(uploaded, caption="Uploaded receipt", use_container_width=True)
        image_bytes = uploaded.getvalue()

        with col_parse:
            parse_clicked = st.button("Parse →", type="primary", use_container_width=True)

        if parse_clicked:
            with st.spinner("Sending to VLM — this may take a few seconds…"):
                try:
                    items, global_tax = parse_receipt(image_bytes)
                    validate_items(items)
                    st.session_state["items"] = items
                    st.session_state["global_tax"] = global_tax
                    st.session_state["manual_mode"] = False
                    st.session_state["step"] = 3
                    st.rerun()
                except VLMError as e:
                    st.error(f"**VLM parsing failed.** Switching to manual entry.\n\n_{e}_")
                    st.session_state["manual_mode"] = True
                    st.session_state["items"] = []
                    st.rerun()
    else:
        st.info("Upload an image to continue, or switch to manual entry below.")

    st.divider()
    if st.button("✏️ Enter items manually instead", use_container_width=True):
        st.session_state["manual_mode"] = True
        st.session_state["items"] = []
        st.rerun()


def _render_manual_ui() -> None:
    st.info("**Manual entry mode** — type in all bill items by hand.")

    if "manual_items" not in st.session_state:
        st.session_state["manual_items"] = [_empty_item()]

    manual_items: list[Item] = st.session_state["manual_items"]

    h1, h2, h3, h4, h5 = st.columns([4, 1, 2, 2, 1])
    h1.caption("Item name")
    h2.caption("Qty")
    h3.caption("Unit price")
    h4.caption("Item tax")
    h5.caption("")

    to_remove: int | None = None
    for i, item in enumerate(manual_items):
        c1, c2, c3, c4, c_del = st.columns([4, 1, 2, 2, 1])
        name = c1.text_input("Name", value=item.name, key=f"man_{i}_name", label_visibility="collapsed", placeholder="Item name")
        qty = c2.number_input("Qty", value=item.quantity, min_value=1, step=1, key=f"man_{i}_qty", label_visibility="collapsed")
        price = c3.number_input("Unit price", value=item.unit_price, min_value=0.0, step=0.01, format="%.2f", key=f"man_{i}_price", label_visibility="collapsed")
        tax = c4.number_input("Item tax", value=item.tax, min_value=0.0, step=0.01, format="%.2f", key=f"man_{i}_tax", label_visibility="collapsed")
        manual_items[i] = Item(name=name.strip(), quantity=int(qty), unit_price=float(price), tax=float(tax))
        if c_del.button("✕", key=f"del_manual_{i}", help="Remove row"):
            to_remove = i

    if to_remove is not None:
        manual_items.pop(to_remove)
        st.session_state["manual_items"] = manual_items
        st.rerun()

    if st.button("➕ Add row", use_container_width=True):
        manual_items.append(_empty_item())
        st.rerun()

    st.divider()
    global_tax = st.number_input(
        "Global tax (total tax at bottom of bill)",
        value=st.session_state.get("global_tax", 0.0),
        min_value=0.0, step=0.01, format="%.2f",
    )
    st.session_state["global_tax"] = global_tax

    col_back, col_switch, _, col_next = st.columns([1, 2, 2, 1])
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state["manual_mode"] = False
            st.session_state["step"] = 1
            st.rerun()
    with col_switch:
        if st.button("📷 Try uploading instead", use_container_width=True):
            st.session_state["manual_mode"] = False
            st.rerun()
    with col_next:
        valid = any(it.name.strip() and it.unit_price > 0 for it in manual_items)
        if st.button("Continue →", type="primary", disabled=not valid, use_container_width=True):
            validate_items(manual_items)
            st.session_state["items"] = manual_items
            st.session_state["manual_items"] = []
            st.session_state["manual_mode"] = False
            st.session_state["step"] = 3
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  Step 3 — Review & Edit Items
# ═══════════════════════════════════════════════════════════════════════════════

def render_review() -> None:
    st.subheader("Step 3 — Review & edit items")
    st.caption(
        "Check the items extracted from your receipt. "
        "Items marked **FLAGGED** have missing or suspicious data — please correct them before continuing."
    )

    items: list[Item] = st.session_state.get("items", [])
    if not items:
        st.warning("No items found. Please go back and re-upload or add items manually.")
        if st.button("← Back"):
            st.session_state["step"] = 2
            st.rerun()
        return

    h_name, h_qty, h_price, h_tax, h_status, h_del = st.columns([4, 1, 2, 2, 1, 1])
    h_name.markdown("**Item**")
    h_qty.markdown("**Qty**")
    h_price.markdown(f"**Unit price ({CURRENCY_SYMBOL})**")
    h_tax.markdown(f"**Item tax ({CURRENCY_SYMBOL})**")
    h_status.markdown("**Status**")
    h_del.markdown("")

    st.divider()

    to_remove: int | None = None
    for i, item in enumerate(items):
        c_name, c_qty, c_price, c_tax, c_status, c_del = st.columns([4, 1, 2, 2, 1, 1])
        new_name = c_name.text_input("Name", value=item.name, key=f"rev_name_{i}", label_visibility="collapsed", placeholder="Item name")
        new_qty = c_qty.number_input("Qty", value=item.quantity, min_value=1, step=1, key=f"rev_qty_{i}", label_visibility="collapsed")
        new_price = c_price.number_input("Price", value=item.unit_price, min_value=0.0, step=0.01, format="%.2f", key=f"rev_price_{i}", label_visibility="collapsed")
        new_tax = c_tax.number_input("Tax", value=item.tax, min_value=0.0, step=0.01, format="%.2f", key=f"rev_tax_{i}", label_visibility="collapsed")

        updated = Item(name=new_name.strip(), quantity=int(new_qty), unit_price=float(new_price), tax=float(new_tax), flagged=False)
        updated.flagged = not updated.name or updated.unit_price <= 0 or updated.quantity <= 0
        items[i] = updated

        if updated.flagged:
            c_status.markdown('<span class="flagged-badge">⚠ Fix</span>', unsafe_allow_html=True)
        else:
            c_status.markdown("✅")

        if c_del.button("✕", key=f"del_rev_{i}", help="Remove item"):
            to_remove = i

    if to_remove is not None:
        items.pop(to_remove)
        st.rerun()

    if st.button("➕ Add item", use_container_width=False):
        items.append(Item(name="", quantity=1, unit_price=0.0, flagged=True))
        st.rerun()

    st.divider()

    global_tax = st.number_input(
        f"Global tax ({CURRENCY_SYMBOL}) — from bottom of bill",
        value=float(st.session_state.get("global_tax", 0.0)),
        min_value=0.0, step=0.01, format="%.2f",
        help="This will be split evenly across all people.",
    )
    st.session_state["global_tax"] = global_tax

    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state["items"] = items
            st.session_state["step"] = 2
            st.rerun()
    with col_next:
        any_flagged = any(it.flagged for it in items)
        has_items = len(items) > 0
        if any_flagged:
            st.caption("⚠ Fix flagged items before continuing.")
        if st.button("Continue →", type="primary", disabled=any_flagged or not has_items, use_container_width=True):
            st.session_state["items"] = items
            st.session_state["assignments"] = {}
            st.session_state["step"] = 4
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  Step 4 — Assign Items to People
# ═══════════════════════════════════════════════════════════════════════════════

def _build_units(items: list[Item]) -> list[tuple[int, int, Item]]:
    units = []
    for i, item in enumerate(items):
        for u in range(item.quantity):
            units.append((i, u, item))
    return units


def render_assign() -> None:
    st.subheader("Step 4 — Assign items to people")

    items: list[Item] = st.session_state.get("items", [])
    people: list[str] = st.session_state.get("people", [])
    assignments: dict = st.session_state.get("assignments", {})

    if not items:
        st.warning("No items found. Go back to the upload step.")
        if st.button("← Back"):
            st.session_state["step"] = 3
            st.rerun()
        return

    units = _build_units(items)
    total_units = len(units)

    if "assign_cursor" not in st.session_state:
        st.session_state["assign_cursor"] = 0
    cursor: int = st.session_state["assign_cursor"]

    # All done
    if cursor >= total_units:
        st.success("All items assigned! 🎉")
        col_back, _, col_next = st.columns([1, 4, 1])
        with col_back:
            if st.button("← Edit assignments", use_container_width=True):
                st.session_state["assign_cursor"] = 0
                st.session_state["step"] = 4
                st.rerun()
        with col_next:
            if st.button("Continue →", type="primary", use_container_width=True):
                st.session_state["assignments"] = assignments
                st.session_state["step"] = 5
                st.rerun()
        return

    item_idx, unit_idx, item = units[cursor]
    st.progress(cursor / total_units, text=f"Item {cursor + 1} of {total_units}")

    unit_label = f" (unit {unit_idx + 1}/{item.quantity})" if item.quantity > 1 else ""
    item_cost = item.unit_price + item.tax

    tax_part = f"&nbsp;+&nbsp;{CURRENCY_SYMBOL}{item.tax:.2f} tax" if item.tax > 0 else ""
    card_html = (
        f'<div class="card">'
        f'<div style="font-size:1.15rem;font-weight:700;margin-bottom:6px;">{item.name}{unit_label}</div>'
        f'<div style="color:#94a3b8;font-size:0.9rem;">'
        f'{CURRENCY_SYMBOL}{item.unit_price:.2f} per unit{tax_part}'
        f'&nbsp;·&nbsp;<strong style="color:#818cf8;">{CURRENCY_SYMBOL}{item_cost:.2f} total for this unit</strong>'
        f'</div></div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)

    key = (item_idx, unit_idx)
    current_assignment: list[str] = assignments.get(key, [])

    col_shortcut, _ = st.columns([2, 3])
    with col_shortcut:
        if st.button("👥 Split equally among everyone", use_container_width=True):
            assignments[key] = list(people)
            st.session_state["assignments"] = assignments
            st.session_state["assign_cursor"] = cursor + 1
            st.rerun()

    selected = st.multiselect(
        "Who ordered this?", options=people,
        default=current_assignment if current_assignment else [],
        key=f"assign_{item_idx}_{unit_idx}", placeholder="Select people…",
    )

    assignments[key] = selected
    st.session_state["assignments"] = assignments

    if selected:
        per_person = item_cost / len(selected)
        st.caption(f"Each person pays: **{CURRENCY_SYMBOL}{per_person:.2f}**")

    st.divider()
    col_back, col_skip, _, col_next = st.columns([1, 1, 3, 1])
    with col_back:
        if st.button("← Prev", disabled=cursor == 0, use_container_width=True):
            st.session_state["assign_cursor"] = cursor - 1
            st.rerun()
    with col_skip:
        if st.button("Skip →", use_container_width=True, help="Skip this item (unassigned)"):
            assignments[key] = []
            st.session_state["assignments"] = assignments
            st.session_state["assign_cursor"] = cursor + 1
            st.rerun()
    with col_next:
        if st.button("Next →", type="primary", disabled=not selected, use_container_width=True):
            assignments[key] = selected
            st.session_state["assignments"] = assignments
            st.session_state["assign_cursor"] = cursor + 1
            st.rerun()

    if not selected:
        st.caption("Select at least one person or use **Skip** to leave this item unassigned.")

    if assignments:
        with st.expander("📋 Assignment summary so far", expanded=False):
            for (ii, ui_), names in assignments.items():
                it = items[ii]
                ulabel = f" #{ui_+1}" if it.quantity > 1 else ""
                assignees = ", ".join(names) if names else "_unassigned_"
                st.markdown(f"- **{it.name}{ulabel}** → {assignees}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Step 5 — Tip
# ═══════════════════════════════════════════════════════════════════════════════

def render_tip() -> None:
    st.subheader("Step 5 — Add a tip?")
    st.caption("Optional. If entered, the tip is split evenly among everyone.")

    people: list[str] = st.session_state.get("people", [])
    n = len(people)

    tip = st.number_input(
        f"Tip amount ({CURRENCY_SYMBOL})",
        value=float(st.session_state.get("tip", 0.0)),
        min_value=0.0, step=0.50, format="%.2f",
    )

    if tip > 0 and n > 0:
        per_person = tip / n
        st.info(f"**{CURRENCY_SYMBOL}{tip:.2f}** tip ÷ {n} people = **{CURRENCY_SYMBOL}{per_person:.2f}** per person")

    st.divider()
    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state["tip"] = tip
            st.session_state["step"] = 4
            st.session_state["assign_cursor"] = len([
                (i, u)
                for i, item in enumerate(st.session_state.get("items", []))
                for u in range(item.quantity)
            ])
            st.rerun()
    with col_next:
        if st.button("Calculate →", type="primary", use_container_width=True):
            st.session_state["tip"] = tip
            items = st.session_state.get("items", [])
            assignments = st.session_state.get("assignments", {})
            people_names = st.session_state.get("people", [])
            global_tax = st.session_state.get("global_tax", 0.0)
            st.session_state["result_people"] = calculate_split(items, assignments, people_names, global_tax, tip)
            st.session_state["step"] = 6
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  Step 6 — Results
# ═══════════════════════════════════════════════════════════════════════════════

def render_results() -> None:
    st.subheader("Step 6 — Results")

    result_people: list[Person] = st.session_state.get("result_people", [])
    global_tax: float = st.session_state.get("global_tax", 0.0)
    tip: float = st.session_state.get("tip", 0.0)

    if not result_people:
        st.warning("No results yet. Please complete the assignment and tip steps.")
        if st.button("← Back"):
            st.session_state["step"] = 5
            st.rerun()
        return

    grand_total = sum(p.total for p in result_people)

    # Grand total banner
    tax_tip_line = ""
    if global_tax > 0 or tip > 0:
        parts = []
        if global_tax > 0:
            parts.append(f"{CURRENCY_SYMBOL}{global_tax:.2f} global tax")
        if tip > 0:
            parts.append(f"{CURRENCY_SYMBOL}{tip:.2f} tip")
        tax_tip_line = f'<div style="font-size:0.8rem;color:#64748b;margin-top:4px;">Includes {" &amp; ".join(parts)}</div>'

    grand_total_html = (
        f'<div class="card" style="text-align:center;border-color:rgba(99,102,241,0.4);">'
        f'<div style="font-size:0.85rem;color:#94a3b8;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Grand Total</div>'
        f'<div style="font-size:2.5rem;font-weight:800;background:linear-gradient(135deg,#818cf8,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">{CURRENCY_SYMBOL}{grand_total:.2f}</div>'
        f'{tax_tip_line}</div>'
    )
    st.markdown(grand_total_html, unsafe_allow_html=True)

    st.markdown("---")

    # Per-person summary cards
    st.markdown("### 💳 Summary")
    cols = st.columns(min(len(result_people), 3))
    for idx, person in enumerate(result_people):
        with cols[idx % 3]:
            percentage = (person.total / grand_total * 100) if grand_total > 0 else 0
            person_card = (
                f'<div class="card" style="text-align:center;">'
                f'<div style="font-size:1.05rem;font-weight:700;margin-bottom:4px;">{person.name}</div>'
                f'<div style="font-size:1.8rem;font-weight:800;color:#818cf8;">{CURRENCY_SYMBOL}{person.total:.2f}</div>'
                f'<div style="font-size:0.75rem;color:#64748b;margin-top:4px;">{percentage:.1f}% of bill</div>'
                f'</div>'
            )
            st.markdown(person_card, unsafe_allow_html=True)

    # Itemized breakdown
    st.markdown("### 📋 Breakdown")
    for person in result_people:
        with st.expander(f"**{person.name}** — {CURRENCY_SYMBOL}{person.total:.2f}", expanded=True):
            if not person.items:
                st.caption("No items assigned.")
                continue
            for item, share in person.items:
                col_label, col_amount = st.columns([5, 1])
                is_special = item.name in ("Tax (global)", "Tip")
                display = (
                    f'<span style="color:#94a3b8;font-style:italic;">{item.name}</span>'
                    if is_special else f"<span>{item.name}</span>"
                )
                col_label.markdown(display, unsafe_allow_html=True)
                col_amount.markdown(
                    f'<div style="text-align:right;font-weight:600;">{CURRENCY_SYMBOL}{share:.2f}</div>',
                    unsafe_allow_html=True,
                )
            st.divider()
            total_col1, total_col2 = st.columns([5, 1])
            total_col1.markdown("**Total**")
            total_col2.markdown(
                f'<div style="text-align:right;font-weight:800;color:#818cf8;">{CURRENCY_SYMBOL}{person.total:.2f}</div>',
                unsafe_allow_html=True,
            )

    # Start over
    st.divider()
    _, _, col_reset = st.columns([2, 4, 1])
    with col_reset:
        if st.button("🔄 Start Over", use_container_width=True, type="secondary"):
            for key in ["step", "people", "items", "global_tax", "assignments",
                        "tip", "result_people", "manual_mode", "manual_items", "assign_cursor"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
