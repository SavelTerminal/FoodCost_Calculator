"""Pure calculation utilities for food cost logic."""

from typing import Dict, Tuple, Any


def unit_cost(name: str, ingredients: Dict[str, Dict[str, Any]]) -> float:
    """Compute unit cost for an ingredient from catalog data."""
    d = ingredients[name]
    return float(d["package_price"]) / max(float(d["package_qty"]), 1e-9)


def to_base(qty: float, unit: str) -> float:
    """Convert quantity to base unit (kg or L)."""
    if unit == "g":
        return qty / 1000.0
    if unit == "ml":
        return qty / 1000.0
    return qty


def to_weight_kg(name: str, qty: float, unit: str, densities: Dict[str, float]) -> float:
    """Convert various units to kilograms using densities when needed."""
    if unit == "kg":
        return qty
    if unit == "g":
        return qty / 1000.0
    if unit in ("L", "ml"):
        dens = densities.get(name)
        if not dens:
            return 0.0
        return dens * qty if unit == "L" else dens * qty / 1000.0
    return 0.0


def batch_total_cost(batch: Dict[str, Any], ingredients: Dict[str, Dict[str, Any]]) -> float:
    """Compute total batch cost given ingredient catalog."""
    total = 0.0
    for it in batch.get("items", []):
        if it["name"] not in ingredients:
            continue
        total += unit_cost(it["name"], ingredients) * to_base(float(it["qty"]), it["unit"])
    return total


def batch_total_weight_kg(batch: Dict[str, Any], densities: Dict[str, float]) -> Tuple[float, int]:
    """Return total weight in kg and number of items lacking density info."""
    w, unknown = 0.0, 0
    for it in batch.get("items", []):
        wk = to_weight_kg(it["name"], float(it["qty"]), it["unit"], densities)
        if it["unit"] in ("L", "ml") and wk == 0.0:
            unknown += 1
        w += wk
    return w, unknown
