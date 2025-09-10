# app.py
# =============================================================================
# Food Cost Calculator — UX pulita + grafico a torta per batch
# =============================================================================

import os
import hashlib
import re
import streamlit as st
from math import ceil, floor
import matplotlib.pyplot as plt  # per il grafico a torta

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Food Cost Calculator", layout="wide")

# -----------------------------------------------------------------------------
# LICENSE (demo)
# -----------------------------------------------------------------------------
def _hash_key(key: str) -> str:
    """Return SHA-256 hex digest of the given key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

# Environment variable can contain multiple keys separated by commas or spaces
VALID_KEYS = {
    _hash_key(k.strip().upper())
    for k in re.split(r"[\s,]+", os.environ.get("APP_PASS", ""))
    if k.strip()
}

if "unlocked" not in st.session_state:
    st.session_state.unlocked = False

def check_key(k: str) -> bool:
    k = (k or "").strip()
    if not k:
        return False
    return _hash_key(k.upper()) in VALID_KEYS

if not st.session_state.unlocked:
    st.title("Enter License Key")
    key = st.text_input("License key", type="password", key="license_input")
    if st.button("Unlock", key="license_btn"):
        if check_key(key):
            st.session_state.unlocked = True
            st.success("Unlocked")
            st.rerun()
        else:
            st.error("Invalid key")
    st.stop()

# -----------------------------------------------------------------------------
# DATI DI BASE
# -----------------------------------------------------------------------------
if "ingredients" not in st.session_state:
    st.session_state.ingredients = {
        "Flour 00":   {"unit": "kg", "package_qty": 25.0, "package_price": 29.90},
        "Water":      {"unit": "L",  "package_qty": 10.0, "package_price": 1.50},
        "Salt":       {"unit": "kg", "package_qty": 1.0,  "package_price": 0.50},
        "Yeast":      {"unit": "kg", "package_qty": 1.0,  "package_price": 8.00},
        "Mozzarella": {"unit": "kg", "package_qty": 1.0,  "package_price": 6.50},
        "Tomato":     {"unit": "kg", "package_qty": 1.0,  "package_price": 1.40},
        "Oil EVO":    {"unit": "L",  "package_qty": 1.0,  "package_price": 7.00},
    }

# densità (kg/L) per convertire volumi in peso batch
if "densities" not in st.session_state:
    st.session_state.densities = {
        "Water": 1.0,
        "Oil EVO": 0.91,
    }

if "batch_id_counter" not in st.session_state:
    st.session_state.batch_id_counter = 1
if "batches" not in st.session_state:
    st.session_state.batches = {}
if "recipes" not in st.session_state:
    st.session_state.recipes = {}
if "new_batch_buffer" not in st.session_state:
    st.session_state.new_batch_buffer = {"name": "", "category": "", "portion_weight_g": 280.0, "items": []}

# -----------------------------------------------------------------------------
# FUNZIONI DI SUPPORTO
# -----------------------------------------------------------------------------
def _new_batch_id() -> str:
    bid = f"b{st.session_state.batch_id_counter}"
    st.session_state.batch_id_counter += 1
    return bid

def unit_cost(name: str) -> float:
    d = st.session_state.ingredients[name]
    return float(d["package_price"]) / max(float(d["package_qty"]), 1e-9)

def to_base(qty: float, unit: str) -> float:
    if unit == "g":  return qty / 1000.0
    if unit == "ml": return qty / 1000.0
    return qty

def to_weight_kg(name: str, qty: float, unit: str) -> float:
    if unit == "kg": return qty
    if unit == "g":  return qty / 1000.0
    if unit in ("L", "ml"):
        dens = st.session_state.densities.get(name)
        if not dens:
            return 0.0
        return dens * qty if unit == "L" else dens * qty / 1000.0
    return 0.0

def batch_total_cost(batch: dict) -> float:
    total = 0.0
    for it in batch.get("items", []):
        if it["name"] not in st.session_state.ingredients:
            continue
        total += unit_cost(it["name"]) * to_base(float(it["qty"]), it["unit"])
    return total

def batch_total_weight_kg(batch: dict) -> tuple[float, int]:
    w, unknown = 0.0, 0
    for it in batch.get("items", []):
        wk = to_weight_kg(it["name"], float(it["qty"]), it["unit"])
        if it["unit"] in ("L", "ml") and wk == 0.0:
            unknown += 1
        w += wk
    return w, unknown

def batch_portions_yield(batch: dict) -> int:
    pw = float(batch.get("portion_weight_g") or 0.0)
    if pw <= 0:
        return 0
    tot_w, _ = batch_total_weight_kg(batch)
    return max(floor((tot_w * 1000.0) / pw), 0)

def batch_cost_per_portion(batch: dict) -> float | None:
    total = batch_total_cost(batch)
    portions = batch_portions_yield(batch)
    if portions <= 0:
        return None
    return total / portions

def toppings_cost_per_portion(recipe: dict) -> float:
    total = 0.0
    for it in recipe.get("items", []):
        if it["name"] not in st.session_state.ingredients:
            continue
        total += unit_cost(it["name"]) * to_base(float(it["qty"]), it["unit"])
    return total / max(recipe.get("portions", 1), 1)

def recipe_cost_per_pizza(recipe_name: str) -> float:
    r = st.session_state.recipes[recipe_name]
    bcost = 0.0
    for bu in r.get("batch_uses", []):
        b = st.session_state.batches.get(bu["batch_id"])
        if not b:
            continue
        cpp = batch_cost_per_portion(b)
        if cpp is not None:
            bcost += cpp * float(bu.get("portions", 0) or 0)
    return bcost + toppings_cost_per_portion(r)

def format_money(x, cur):
    if x is None:
        return "—"
    symbol = "€" if cur == "EUR" else "$"
    return f"{symbol}{x:,.2f}"

def batch_label(bid: str) -> str:
    b = st.session_state.batches[bid]
    cat = f" ({b.get('category','').strip()})" if b.get("category","").strip() else ""
    return f"{b.get('name','?')}{cat} [{bid}]"

# Nome libero + creazione inline ingrediente nel catalogo
def ingredient_inline_creator(name_key: str, prefix: str = "") -> str | None:
    name = st.text_input("🧾 Ingredient name", key=f"{prefix}{name_key}").strip()
    if not name:
        return None
    if name in st.session_state.ingredients:
        st.caption("Using catalog price for this ingredient.")
        return name
    st.warning("This ingredient is not in the catalog yet. Add it now to compute costs.")
    with st.expander("➕ Add to catalog now", expanded=True):
        base_unit = st.selectbox("Base unit for pricing", ["kg", "L"], key=f"{prefix}new_ing_unit_{name}")
        pack_qty  = st.number_input("Package size (in base unit)", min_value=0.0001, value=1.0, step=0.1,
                                    key=f"{prefix}new_ing_qty_{name}")
        pack_price= st.number_input("Package price", min_value=0.0, value=1.0, step=0.10,
                                    key=f"{prefix}new_ing_price_{name}")
        if st.button("Save to catalog", key=f"{prefix}save_ing_{name}"):
            st.session_state.ingredients[name] = {
                "unit": base_unit,
                "package_qty": float(pack_qty),
                "package_price": float(pack_price)
            }
            st.success(f"Added '{name}' to catalog.")
            st.rerun()
    return None

# -----------------------------------------------------------------------------
# UI — TABS
# -----------------------------------------------------------------------------
tabs = st.tabs(["Food Cost (Home)", "Menu (soon)", "Recipes", "Batches", "Ingredients", "Settings"])

# -----------------------------------------------------------------------------
# HOME
# -----------------------------------------------------------------------------
with tabs[0]:
    st.header("Food Cost — Caveman Mode")
    if not st.session_state.recipes:
        st.info("No recipes yet. Create one in the 'Recipes' tab.")
    else:
        rsel = st.selectbox("Recipe", list(st.session_state.recipes.keys()), key="home_recipe")
        currency = st.selectbox("Currency", ["EUR", "USD"], key="home_currency")
        tax_pct = st.number_input("Tax % (VAT/Sales Tax)", 0.0, 50.0, 9.0, 0.5, key="home_taxpct")
        target_fc = st.slider("Target Food-Cost %", 20, 40, 30, key="home_targetfc") / 100.0
        step = st.selectbox("Rounding step", [0.10, 0.50, 1.00], index=1, key="home_roundstep")
        sell_gross = st.number_input("Selling price (GROSS)", 0.0, value=9.90, step=0.10, key="home_sellgross")

        cpp = recipe_cost_per_pizza(rsel)
        sell_net = sell_gross / (1.0 + tax_pct/100.0) if sell_gross > 0 else 0.0
        current_fc = (cpp / sell_net) if sell_net > 0 else 0.0
        rec_net = cpp / max(target_fc, 1e-9)
        rec_gross = ceil((rec_net * (1.0 + tax_pct/100.0)) / step) * step
        margin_now = sell_net - cpp

        st.metric("Cost per portion", format_money(cpp, currency))
        st.metric("Current Food-Cost", f"{current_fc*100:,.1f}%")
        st.metric("Recommended Price (GROSS)", format_money(rec_gross, currency))
        st.metric("Margin now (net)", format_money(margin_now, currency))

# -----------------------------------------------------------------------------
# MENU (placeholder)
# -----------------------------------------------------------------------------
with tabs[1]:
    st.header("Menu (Dynamic) — coming next")
    st.info("Tabella con tutte le ricette, prezzi e margini live (prossima iterazione).")

# -----------------------------------------------------------------------------
# RECIPES
# -----------------------------------------------------------------------------
with tabs[2]:
    st.header("Recipes")

    st.subheader("Create new recipe")
    new_name = st.text_input("Recipe name", key="recipes_new_name")
    new_portions = st.number_input("Recipe portions (usually 1)", 1, value=1, step=1, key="recipes_new_portions")
    if st.button("Create recipe", key="recipes_create_btn"):
        if not new_name:
            st.error("Please enter a recipe name")
        elif new_name in st.session_state.recipes:
            st.error("A recipe with this name already exists.")
        else:
            st.session_state.recipes[new_name] = {"portions": int(new_portions), "batch_uses": [], "items": []}
            st.success("Recipe created")
            st.rerun()

    st.divider()

    if st.session_state.recipes:
        rsel = st.selectbox("Select recipe", list(st.session_state.recipes.keys()), key="recipes_view_recipe")
        r = st.session_state.recipes[rsel]

        colA, colB = st.columns([1, 1])
        with colA:
            st.subheader("🧱 Batches in this recipe")
            if r.get("batch_uses"):
                for bu in r["batch_uses"]:
                    bid = bu["batch_id"]
                    label = batch_label(bid) if bid in st.session_state.batches else f"[missing {bid}]"
                    st.write(f"- {label} × {bu.get('portions', 0)}")
            else:
                st.info("No batches attached yet.")

            st.subheader("🧀 Extra ingredients (per portion)")
            if r.get("items"):
                for it in r["items"]:
                    st.write(f"- {it['name']}: {it['qty']} {it['unit']}")
            else:
                st.info("No extra ingredients.")

            st.success(f"Cost per portion: {format_money(recipe_cost_per_pizza(rsel), 'EUR')}")

        with colB:
            st.subheader("➕ Attach a batch")
            if st.session_state.batches:
                bid_to_add = st.selectbox("Choose batch",
                                          options=list(st.session_state.batches.keys()),
                                          format_func=batch_label,
                                          key="recipes_pick_batch")
                pp = st.number_input("Portions of this batch used in recipe",
                                     min_value=0.0, value=1.0, step=0.5, key="recipes_batch_pp")
                if st.button("Add batch to recipe", key="recipes_add_batch_btn"):
                    r.setdefault("batch_uses", [])
                    r["batch_uses"].append({"batch_id": bid_to_add, "portions": float(pp)})
                    st.success("Batch attached")
                    st.rerun()
            else:
                st.info("No batches yet. Create them in 'Batches' tab.")

            st.markdown("---")
            st.subheader("➕ Add extra ingredient (per portion)")
            ingr = st.selectbox("Ingredient (from catalog)", list(st.session_state.ingredients.keys()),
                                key="recipes_ingr_select")
            qty = st.number_input("Qty", 0.0, value=0.10, step=0.01, key="recipes_qty")
            unit = st.selectbox("Unit", ["kg", "g", "L", "ml"], key="recipes_unit")
            c1, c2, c3 = st.columns([1, 1, 1])
            if c1.button("Add item", key="recipes_add_item"):
                r.setdefault("items", [])
                r["items"].append({"name": ingr, "qty": qty, "unit": unit})
                st.success("Ingredient added")
                st.rerun()
            if c2.button("Remove last item", key="recipes_remove_last"):
                if r.get("items"):
                    r["items"].pop()
                    st.warning("Removed last")
                    st.rerun()
            if c3.button("Delete recipe", key="recipes_delete_recipe"):
                st.session_state.recipes.pop(rsel, None)
                st.warning("Recipe deleted")
                st.rerun()

# -----------------------------------------------------------------------------
# BATCHES — pannello EDIT (sinistra) + pannello NEW (destra) ben distinti
# -----------------------------------------------------------------------------
with tabs[3]:
    st.header("Batches")

    colL, colR = st.columns([1, 1])

    # -------------------- EDIT SELECTED --------------------
    with colL:
        st.subheader("🛠️ Edit selected batch")
        if not st.session_state.batches:
            st.info("No batches yet. Create one on the right.")
        else:
            bid_sel = st.selectbox("Select batch",
                                   options=list(st.session_state.batches.keys()),
                                   format_func= batch_label,
                                   key="b_sel")
            b = st.session_state.batches[bid_sel]

            # Sezione base
            st.markdown("#### 📄 Basic")
            b["name"] = st.text_input("Batch name (free text)", value=b.get("name",""), key=f"b_name_{bid_sel}")
            b["category"] = st.text_input("Category (free text)", value=b.get("category",""), key=f"b_cat_{bid_sel}")
            b["portion_weight_g"] = st.number_input("Portion weight (g)", 1.0,
                                                    value=float(b.get("portion_weight_g") or 280.0),
                                                    step=10.0, key=f"b_pw_{bid_sel}")

            st.divider()

            # Ingredienti + form di aggiunta nello stesso pannello
            st.markdown("#### 🧾 Ingredients in this batch (TOTAL quantities)")
            if b.get("items"):
                for it in b["items"]:
                    st.write(f"- {it['name']}: {it['qty']} {it['unit']}")
            else:
                st.info("No items yet.")

            st.markdown("##### ➕ Add ingredient to this batch")
            name_ok_e = ingredient_inline_creator(name_key=f"edit_ing_name_{bid_sel}", prefix=f"b_{bid_sel}_")
            qty_e = st.number_input("Qty (total in batch)", 0.0, value=0.5, step=0.1, key=f"b_add_qty_{bid_sel}")
            unit_e = st.selectbox("Unit", ["kg", "g", "L", "ml"], key=f"b_add_unit_{bid_sel}")
            ec1, ec2 = st.columns([1, 1])
            if ec1.button("Add item", key=f"b_add_btn_{bid_sel}"):
                if name_ok_e is None:
                    st.error("Please add the ingredient to catalog first (see above).")
                else:
                    b.setdefault("items", [])
                    b["items"].append({"name": name_ok_e, "qty": qty_e, "unit": unit_e})
                    st.success("Item added")
                    st.rerun()
            if ec2.button("Remove last item", key=f"b_rem_btn_{bid_sel}"):
                if b.get("items"):
                    b["items"].pop()
                    st.warning("Removed last")
                    st.rerun()

            st.divider()

            # Riepilogo + grafico a torta
            st.markdown("#### 📊 Batch Summary")
            total_cost = batch_total_cost(b)
            total_w, unknown = batch_total_weight_kg(b)
            portions = batch_portions_yield(b)
            cpp = batch_cost_per_portion(b)
            cpkg = (total_cost / total_w) if total_w > 0 else None

            m1, m2, m3 = st.columns(3)
            m1.metric("Total cost", format_money(total_cost, "EUR"))
            m2.metric("Total weight", f"{total_w:.3f} kg")
            m3.metric("Est. portions", f"{portions:d}" if portions else "—")
            m1, m2 = st.columns(2)
            m1.metric("Cost / portion", format_money(cpp, "EUR"))
            m2.metric("Cost / kg", format_money(cpkg, "EUR"))
            if unknown > 0:
                st.warning(f"{unknown} volume ingredient(s) missing density → excluded from weight.")

            # 🥧 pie chart: costo per ingrediente
            cost_labels, cost_vals = [], []
            for it in b.get("items", []):
                if it["name"] in st.session_state.ingredients:
                    cost_labels.append(it["name"])
                    cost_vals.append(unit_cost(it["name"]) * to_base(float(it["qty"]), it["unit"]))
            if sum(cost_vals) > 0:
                fig, ax = plt.subplots()
                ax.pie(cost_vals, labels=cost_labels, autopct='%1.1f%%', startangle=90)
                ax.axis('equal')
                st.pyplot(fig)
            else:
                st.info("Add priced ingredients to see the cost breakdown pie chart.")

            st.divider()
            if st.button("🗑️ Delete this batch", key=f"b_del_{bid_sel}"):
                for rn, rdict in st.session_state.recipes.items():
                    if rdict.get("batch_uses"):
                        rdict["batch_uses"] = [bu for bu in rdict["batch_uses"] if bu.get("batch_id") != bid_sel]
                st.session_state.batches.pop(bid_sel, None)
                st.warning("Batch deleted (also removed from recipes)")
                st.rerun()

    # -------------------- NEW BATCH --------------------
    with colR:
        st.subheader("🧪 Create new batch")
        nb = st.session_state.new_batch_buffer

        st.markdown("#### 📄 Basic")
        nb["name"] = st.text_input("Batch name (free text)", value=nb.get("name",""), key="nb_name")
        nb["category"] = st.text_input("Category (free text)", value=nb.get("category",""), key="nb_cat")
        nb["portion_weight_g"] = st.number_input("Portion weight (g)", 1.0,
                                                 value=float(nb.get("portion_weight_g", 280.0)),
                                                 step=10.0, key="nb_pw")

        st.divider()

        st.markdown("#### 🧾 Ingredients in NEW batch (TOTAL quantities)")
        if nb.get("items"):
            for it in nb["items"]:
                st.write(f"- {it['name']}: {it['qty']} {it['unit']}")
        else:
            st.info("No items yet.")

        st.markdown("##### ➕ Add ingredient to NEW batch")
        name_ok = ingredient_inline_creator(name_key="new_ing_name", prefix="nb_")
        qty_val = st.number_input("Qty (total in batch)", 0.0, value=0.5, step=0.1, key="nb_add_qty")
        unit_val = st.selectbox("Unit", ["kg", "g", "L", "ml"], key="nb_add_unit")
        c1, c2 = st.columns([1, 1])
        if c1.button("Add item to NEW batch", key="nb_add_btn"):
            if name_ok is None:
                st.error("Please add the ingredient to catalog first (see above).")
            else:
                nb.setdefault("items", [])
                nb["items"].append({"name": name_ok, "qty": qty_val, "unit": unit_val})
                st.success("Item added")
                st.rerun()
        if c2.button("Remove last item (NEW)", key="nb_rem_btn"):
            if nb.get("items"):
                nb["items"].pop()
                st.warning("Removed last")
                st.rerun()

        st.divider()

        tmp_cost = batch_total_cost(nb)
        tmp_w, tmp_unknown = batch_total_weight_kg(nb)
        tmp_portions = batch_portions_yield(nb)
        tmp_cpp = batch_cost_per_portion(nb)
        tmp_cpkg = (tmp_cost / tmp_w) if tmp_w > 0 else None

        m1, m2, m3 = st.columns(3)
        m1.metric("Total cost", format_money(tmp_cost, "EUR"))
        m2.metric("Total weight", f"{tmp_w:.3f} kg")
        m3.metric("Est. portions", f"{tmp_portions:d}" if tmp_portions else "—")
        m1, m2 = st.columns(2)
        m1.metric("Cost / portion", format_money(tmp_cpp, "EUR"))
        m2.metric("Cost / kg", format_money(tmp_cpkg, "EUR"))
        if tmp_unknown > 0:
            st.warning(f"{tmp_unknown} volume ingredient(s) missing density → excluded from weight.")

        if st.button("✅ Create batch", key="nb_create"):
            if not nb["name"]:
                st.error("Please enter a batch name")
            elif float(nb.get("portion_weight_g") or 0) <= 0:
                st.error("Please set a valid portion weight (g)")
            else:
                bid = _new_batch_id()
                st.session_state.batches[bid] = {
                    "name": nb["name"].strip(),
                    "category": nb["category"].strip(),
                    "portion_weight_g": float(nb["portion_weight_g"]),
                    "items": list(nb.get("items", []))
                }
                st.session_state.new_batch_buffer = {"name": "", "category": "", "portion_weight_g": 280.0, "items": []}
                st.success(f"Batch created: {st.session_state.batches[bid]['name']} [{bid}]")
                st.rerun()

# -----------------------------------------------------------------------------
# INGREDIENTS
# -----------------------------------------------------------------------------
with tabs[4]:
    st.header("Ingredients (package-based pricing)")
    st.caption("Enter package size + package price; the app computes unit cost automatically.")

    for name, d in list(st.session_state.ingredients.items()):
        with st.expander(name, expanded=False):
            d["unit"] = st.selectbox(f"{name} unit", ["kg", "L"],
                                     index=0 if d["unit"] == "kg" else 1, key=f"ing_unit_{name}")
            d["package_qty"] = st.number_input(f"{name} package size ({d['unit']})",
                                               min_value=0.0001, value=float(d["package_qty"]),
                                               step=0.1, key=f"ing_qty_{name}")
            d["package_price"] = st.number_input(f"{name} package price",
                                                 min_value=0.0, value=float(d["package_price"]),
                                                 step=0.10, key=f"ing_price_{name}")
            unit_cost_val = d["package_price"] / max(d["package_qty"], 1e-9)
            st.info(f"Computed unit cost: {format_money(unit_cost_val, 'EUR')}/{d['unit']}")

    st.divider()
    new_in = st.text_input("Add new ingredient (name)", key="ing_new_name")
    if st.button("Add ingredient", key="ing_add_btn"):
        if new_in:
            if new_in in st.session_state.ingredients:
                st.error("Ingredient already exists.")
            else:
                st.session_state.ingredients[new_in] = {"unit": "kg", "package_qty": 1.0, "package_price": 1.0}
                st.success("Ingredient added")
                st.rerun()
        else:
            st.error("Please enter an ingredient name")

# -----------------------------------------------------------------------------
# SETTINGS
# -----------------------------------------------------------------------------
with tabs[5]:
    st.header("Settings")
    st.caption("Future: export CSV/PDF, backend licenze, densità editabili in UI, tema.")
    if st.button("Reset all data (ingredients, recipes, batches)", key="settings_reset"):
        for k in ("ingredients", "recipes", "batches", "new_batch_buffer"):
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()
