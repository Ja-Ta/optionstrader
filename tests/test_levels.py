from optionstrader.indicators import detect_levels, nearest_resistance, nearest_support


def test_range_produces_levels_at_extremes(range_bound):
    levels = detect_levels(range_bound)
    assert levels, "oscillating series must produce clustered levels"
    prices = [lv.price for lv in levels]
    # Repeated ~11 tops and ~9 bottoms should each cluster into a level.
    assert any(abs(p - 11.0) / 11.0 < 0.05 for p in prices), f"no top level in {prices}"
    assert any(abs(p - 9.0) / 9.0 < 0.06 for p in prices), f"no bottom level in {prices}"


def test_nearest_queries_and_roles(range_bound):
    levels = detect_levels(range_bound)
    price = 10.0
    res = nearest_resistance(levels, price)
    sup = nearest_support(levels, price)
    assert res is not None and res.price > price
    assert sup is not None and sup.price < price
    assert res.role(price) == "resistance"
    assert sup.role(price) == "support"


def test_level_touch_counts(range_bound):
    levels = detect_levels(range_bound)
    top = nearest_resistance(levels, 10.0)
    # Six cycles hit the top — expect several clustered touches.
    assert top.touches >= 3
