import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calc import unit_cost, batch_total_cost, batch_total_weight_kg


def test_unit_cost():
    ingredients = {"Flour": {"package_price": 25.0, "package_qty": 25}}
    assert unit_cost("Flour", ingredients) == pytest.approx(1.0)


def test_batch_total_cost():
    ingredients = {
        "Flour": {"package_price": 2.0, "package_qty": 1},
        "Water": {"package_price": 1.0, "package_qty": 1},
    }
    batch = {
        "items": [
            {"name": "Flour", "qty": 1, "unit": "kg"},
            {"name": "Water", "qty": 500, "unit": "g"},
        ]
    }
    assert batch_total_cost(batch, ingredients) == pytest.approx(2.5)


def test_batch_total_weight_kg():
    densities = {"Water": 1.0}
    batch = {
        "items": [
            {"name": "Flour", "qty": 1, "unit": "kg"},
            {"name": "Water", "qty": 500, "unit": "ml"},
            {"name": "Oil", "qty": 100, "unit": "ml"},
        ]
    }
    total, unknown = batch_total_weight_kg(batch, densities)
    assert total == pytest.approx(1.5)
    assert unknown == 1


def test_batch_total_cost_unknown():
    ingredients = {"Flour": {"package_price": 2.0, "package_qty": 1}}
    batch = {"items": [{"name": "Flour", "qty": 1, "unit": "kg"}, {"name": "Salt", "qty": 1, "unit": "kg"}]}
    with pytest.raises(ValueError):
        batch_total_cost(batch, ingredients)
