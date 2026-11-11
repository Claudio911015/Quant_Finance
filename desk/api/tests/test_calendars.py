"""Calendarios de México y EE. UU. (corte 3, T5): reglas 2020–2040 y su uso en fijaciones, FIX y coberturas (R8, D3)."""
from datetime import date, timedelta

import pytest

from desk.api import calendars, valuation
from desk.api.tests.conftest import empty_portfolio
from desk.api.tests.hedge_fixture import DOC, designate, market_forward, par_irs, roll
from desk.api.tests.hedge_fixture import frozen_clock  # noqa: F401  (autouse: reloj fijo)


def _d(*isos):
    return [date.fromisoformat(i) for i in isos]


# ------------------------------------------------------------------------------ reglas

MX_HOLIDAYS = _d(
    "2025-02-03", "2025-03-17", "2025-04-17", "2025-04-18", "2025-09-16", "2025-11-17", "2025-12-12",
    "2026-02-02", "2026-03-16", "2026-04-02", "2026-04-03", "2026-11-02", "2026-11-16",
    "2027-03-25", "2027-03-26", "2027-09-16", "2027-11-15",
)
MX_BUSINESS = _d("2026-04-06", "2026-07-03")
US_HOLIDAYS = _d(
    "2025-04-18", "2025-11-27", "2026-01-19", "2026-07-03", "2026-11-26", "2027-07-05", "2027-12-24",
)
US_BUSINESS = _d("2026-09-16", "2026-11-02")


@pytest.mark.parametrize("day", MX_HOLIDAYS)
def test_mexican_bank_holidays_are_not_business_days(day):
    assert calendars.is_holiday("MX", day)
    assert not calendars.is_business_day("MX", day)


@pytest.mark.parametrize("day", MX_BUSINESS)
def test_mexican_ordinary_days_are_business_days(day):
    assert not calendars.is_holiday("MX", day)
    assert calendars.is_business_day("MX", day)


@pytest.mark.parametrize("day", US_HOLIDAYS)
def test_us_sifma_holidays_are_not_business_days(day):
    assert calendars.is_holiday("US", day)
    assert not calendars.is_business_day("US", day)


@pytest.mark.parametrize("day", US_BUSINESS)
def test_us_ordinary_days_are_business_days(day):
    assert not calendars.is_holiday("US", day)
    assert calendars.is_business_day("US", day)


def test_the_two_calendars_differ_where_they_should():
    assert calendars.is_holiday("MX", date(2026, 11, 2)) and not calendars.is_holiday("US", date(2026, 11, 2))
    assert calendars.is_holiday("US", date(2026, 11, 26)) and not calendars.is_holiday("MX", date(2026, 11, 26))
    assert calendars.is_holiday("MX", date(2026, 4, 3)) and calendars.is_holiday("US", date(2026, 4, 3))  # Viernes Santo


def test_executive_handover_is_a_holiday_only_in_the_sexennial_years():
    for year in (2024, 2030, 2036):
        assert calendars.is_holiday("MX", date(year, 10, 1))
        assert calendars.holidays("MX", year)[date(year, 10, 1)] == "Transmisión del Poder Ejecutivo"
    assert not calendars.is_holiday("MX", date(2025, 10, 1)) and not calendars.is_holiday("MX", date(2027, 10, 1))


@pytest.mark.parametrize("year, easter", [(2025, date(2025, 4, 20)), (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28))])
def test_holy_week_follows_easter(year, easter):
    mx = calendars.holidays("MX", year)
    assert mx[easter - timedelta(days=3)] == "Jueves Santo"
    assert mx[easter - timedelta(days=2)] == "Viernes Santo"
    assert calendars.holidays("US", year)[easter - timedelta(days=2)] == "Good Friday"
    assert easter not in mx  # el domingo de Pascua no es feriado propio


@pytest.mark.parametrize("year, easter", [(2020, date(2020, 4, 12)), (2024, date(2024, 3, 31)),
                                          (2035, date(2035, 3, 25)), (2038, date(2038, 4, 25)),
                                          (2040, date(2040, 4, 1))])
def test_easter_algorithm_on_known_years(year, easter):
    assert calendars._easter(year) == easter


def test_mexican_names_are_in_spanish_and_complete_for_2026():
    assert calendars.holidays("MX", 2026) == {
        date(2026, 1, 1): "Año Nuevo",
        date(2026, 2, 2): "Día de la Constitución",
        date(2026, 3, 16): "Natalicio de Benito Juárez",
        date(2026, 4, 2): "Jueves Santo",
        date(2026, 4, 3): "Viernes Santo",
        date(2026, 5, 1): "Día del Trabajo",
        date(2026, 9, 16): "Día de la Independencia",
        date(2026, 11, 2): "Día de Muertos",
        date(2026, 11, 16): "Día de la Revolución",
        date(2026, 12, 12): "Día de la Virgen de Guadalupe",
        date(2026, 12, 25): "Navidad",
    }


def test_us_holidays_for_2026_are_complete_with_observed_dates():
    assert calendars.holidays("US", 2026) == {
        date(2026, 1, 1): "New Year's Day",
        date(2026, 1, 19): "Martin Luther King Jr.",
        date(2026, 2, 16): "Presidents Day",
        date(2026, 4, 3): "Good Friday",
        date(2026, 5, 25): "Memorial Day",
        date(2026, 6, 19): "Juneteenth",
        date(2026, 7, 3): "Independence Day",  # 4 de julio en sábado -> viernes
        date(2026, 9, 7): "Labor Day",
        date(2026, 10, 12): "Columbus Day",
        date(2026, 11, 11): "Veterans Day",
        date(2026, 11, 26): "Thanksgiving",
        date(2026, 12, 25): "Christmas",
    }


def test_mexican_fixed_holidays_on_a_weekend_are_not_moved():
    assert calendars.holidays("MX", 2027)[date(2027, 5, 1)] == "Día del Trabajo"  # sábado
    assert calendars.is_business_day("MX", date(2027, 4, 30)) and calendars.is_business_day("MX", date(2027, 5, 3))


def test_us_new_year_on_a_saturday_is_not_moved_to_the_previous_year():
    assert date(2022, 1, 1).weekday() == 5
    assert calendars.is_holiday("US", date(2022, 1, 1))
    assert not calendars.is_holiday("US", date(2021, 12, 31))
    assert calendars.is_business_day("US", date(2021, 12, 31))
    assert date(2023, 1, 1).weekday() == 6  # domingo -> lunes siguiente
    assert calendars.is_holiday("US", date(2023, 1, 2)) and not calendars.is_holiday("US", date(2023, 1, 1))


def test_us_juneteenth_exists_from_2022_only():
    assert not calendars.is_holiday("US", date(2021, 6, 18)) and not calendars.is_holiday("US", date(2021, 6, 19))
    assert calendars.is_holiday("US", date(2022, 6, 20))  # 19 de junio en domingo -> lunes


def test_the_range_of_the_calendars_is_2020_to_2040():
    assert (calendars.FIRST_YEAR, calendars.LAST_YEAR) == (2020, 2040)
    assert calendars.holidays("MX", 2020) and calendars.holidays("US", 2040)
    for cal in ("MX", "US"):
        for year in (2019, 2041):
            with pytest.raises(ValueError):
                calendars.holidays(cal, year)
    with pytest.raises(ValueError):
        calendars.holidays("EU", 2026)


def test_outside_the_range_nothing_is_a_holiday_but_weekends_are_still_closed():
    assert calendars.is_holiday("MX", date(2019, 12, 25)) is False
    assert calendars.is_holiday("US", date(2041, 12, 25)) is False
    assert calendars.is_business_day("MX", date(2041, 12, 25)) is True  # jueves
    assert calendars.is_business_day("MX", date(2041, 12, 28)) is False  # sábado


def test_unknown_calendar_is_an_error_everywhere():
    for call in (lambda: calendars.is_holiday("EU", date(2026, 1, 1)),
                 lambda: calendars.is_business_day("EU", date(2026, 1, 1)),
                 lambda: calendars.holidays_between("EU", date(2026, 1, 1), date(2026, 1, 2))):
        with pytest.raises(ValueError):
            call()


def test_holidays_returns_a_copy_so_callers_cannot_corrupt_the_tables():
    table = calendars.holidays("MX", 2026)
    table.clear()
    assert calendars.is_holiday("MX", date(2026, 11, 16))


def test_holidays_between_is_inclusive_sorted_and_named():
    got = calendars.holidays_between("MX", date(2026, 11, 2), date(2026, 12, 12))
    assert got == [
        {"date": "2026-11-02", "name": "Día de Muertos"},
        {"date": "2026-11-16", "name": "Día de la Revolución"},
        {"date": "2026-12-12", "name": "Día de la Virgen de Guadalupe"},
    ]
    assert calendars.holidays_between("US", date(2026, 11, 27), date(2027, 1, 17)) == [
        {"date": "2026-12-25", "name": "Christmas"},
        {"date": "2027-01-01", "name": "New Year's Day"},
    ]


def test_holidays_between_crosses_years_and_clamps_to_the_supported_range():
    got = calendars.holidays_between("MX", date(2026, 12, 20), date(2027, 1, 5))
    assert [h["date"] for h in got] == ["2026-12-25", "2027-01-01"]
    assert calendars.holidays_between("MX", date(2019, 12, 1), date(2019, 12, 31)) == []
    assert calendars.holidays_between("MX", date(2026, 12, 1), date(2026, 1, 1)) == []
    edge = calendars.holidays_between("US", date(2040, 12, 1), date(2041, 12, 31))
    assert [h["date"] for h in edge] == ["2040-12-25"]


def test_every_year_has_the_expected_number_of_holidays():
    for year in range(2020, 2041):
        assert len(calendars.holidays("MX", year)) in (11, 12)  # 12 con la transmisión del Ejecutivo
        assert len(calendars.holidays("US", year)) == (11 if year < 2022 else 12)


# ------------------------------------------------------------------------------ ruta

def test_holidays_route_returns_both_calendars(client):
    r = client.get("/api/calendars/holidays?from=2026-01-01&to=2026-12-31")
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert (body["from"], body["to"]) == ("2026-01-01", "2026-12-31")
    mx, us = body["holidays"]["MX"], body["holidays"]["US"]
    assert {"date": "2026-04-03", "name": "Viernes Santo"} in mx
    assert {"date": "2026-04-03", "name": "Good Friday"} in us
    assert "2026-11-26" in [h["date"] for h in us] and "2026-11-26" not in [h["date"] for h in mx]
    assert [h["date"] for h in mx] == sorted(h["date"] for h in mx)
    assert len(mx) == 11 and len(us) == 12


def test_holidays_route_respects_the_range(client):
    r = client.get("/api/calendars/holidays?from=2026-11-16&to=2026-11-16")
    assert r.get_json()["holidays"] == {
        "MX": [{"date": "2026-11-16", "name": "Día de la Revolución"}], "US": [],
    }


# ------------------------------------------------------------------------------ (a) fijaciones

def _load(client, index, days, value=0.07):
    lines = ["index,date,value"] + ["%s,%s,%r" % (index, d.isoformat(), value) for d in days]
    r = client.post("/api/fixings/csv", json={"csv": "\n".join(lines)})
    assert r.status_code == 200, r.get_json()


def _days(start, end):
    """Lunes a viernes de `[start, end)`."""
    out, day = [], start
    while day < end:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def _row(client, snapshot, trade_id):
    r = client.get("/api/portfolio/valuation?snapshot=%s" % snapshot)
    assert r.status_code == 200, r.get_json()
    return {row["id"]: row for row in r.get_json()["rows"]}[trade_id]


D0 = date(2026, 11, 10)
D20 = date(2026, 11, 20)


def _tiie_swap_at_nov_20(client, skipped):
    """`irs` TIIE-F pactado el 2026-11-10, rodado al 2026-11-20, con fijaciones hábiles de MX salvo `skipped`."""
    empty_portfolio(client)
    trade = par_irs(client, "TIIE-F", 500e6, D0, D0 + timedelta(days=28))
    roll(client, "MX-DEMO", "D10", 10)
    _load(client, "TIIE-F", [d for d in _days(D0, D20) if d not in skipped])
    return trade["id"]


def test_r8_a_mexican_holiday_without_fixing_is_not_missing(client):
    tid = _tiie_swap_at_nov_20(client, skipped=_d("2026-11-16"))
    row = _row(client, "D10", tid)
    assert row["error"] is None and row["status"] == "viva"
    assert [w for w in row["warnings"] if w["code"] == "missing_fixing"] == []


def test_r8_a_business_day_without_fixing_is_still_missing(client):
    tid = _tiie_swap_at_nov_20(client, skipped=_d("2026-11-16", "2026-11-17"))
    row = _row(client, "D10", tid)
    missing = [w for w in row["warnings"] if w["code"] == "missing_fixing"]
    assert len(missing) == 1 and missing[0]["index"] == "TIIE-F" and missing[0]["dates"] == ["2026-11-17"]


def _context(app, snapshot_id):
    from desk.api import market
    from desk.api.db import connect

    conn = connect(app.config["DESK_DB"])
    try:
        return market.load_context(conn, snapshot_id)
    finally:
        conn.close()


def _factor(app, index, published, first_day, on):
    warnings = []
    factor = valuation.accrued_factor(index, first_day, on, {index: published}, _context(app, "MX-DEMO"), warnings)
    return factor, warnings


def test_r8_the_holiday_accrues_with_the_previous_business_day_rate(app):
    published = {d: 0.07 + 0.001 * i for i, d in enumerate(_days(date(2026, 11, 9), date(2026, 11, 14)))}
    published[date(2026, 11, 13)] = 0.0705
    factor, warnings = _factor(app, "TIIE-F", published, date(2026, 11, 13), date(2026, 11, 17))  # vie, sáb, dom, lun feriado
    assert warnings == []
    assert factor == pytest.approx(1.0 + 0.0705 * 4 / 360.0, rel=1e-15)  # 4 días con la tasa del viernes


def test_a_holiday_fixing_that_was_loaded_is_used_as_one_more_day(app):
    published = {date(2026, 11, 13): 0.0705, date(2026, 11, 16): 0.0710}
    factor, warnings = _factor(app, "TIIE-F", published, date(2026, 11, 13), date(2026, 11, 17))
    assert warnings == []
    assert factor == pytest.approx((1.0 + 0.0705 * 3 / 360.0) * (1.0 + 0.0710 / 360.0), rel=1e-15)


def test_a_tiie_fixing_missing_on_us_thanksgiving_is_still_missing(app):
    # El 2026-11-26 es hábil en México aunque sea feriado en EE. UU.: para TIIE-F el aviso sigue
    published = {d: 0.07 for d in _days(date(2026, 11, 23), date(2026, 11, 30)) if d != date(2026, 11, 26)}
    _, warnings = _factor(app, "TIIE-F", published, date(2026, 11, 23), date(2026, 11, 30))
    assert [(w["code"], w["dates"]) for w in warnings] == [("missing_fixing", ["2026-11-26"])]


def test_a_sofr_fixing_missing_on_the_mexican_holiday_is_still_missing(app):
    # El 2026-11-16 es feriado en México pero SOFR sí se publica: para SOFR el aviso sigue
    published = {d: 0.043 for d in _days(date(2026, 11, 9), date(2026, 11, 20)) if d != date(2026, 11, 16)}
    _, warnings = _factor(app, "SOFR", published, date(2026, 11, 9), date(2026, 11, 20))
    assert [(w["code"], w["dates"]) for w in warnings] == [("missing_fixing", ["2026-11-16"])]


def _sofr_swap_at_dec_1(client, skipped):
    """`irs` SOFR pactado el 2026-11-10, rodado al 2026-12-01, con fijaciones hábiles de EE. UU. salvo `skipped`."""
    empty_portfolio(client)
    trade = par_irs(client, "SOFR", 100e6, D0, D0 + timedelta(days=365))
    roll(client, "MX-DEMO", "D21", 21)
    _load(client, "SOFR", [d for d in _days(D0, date(2026, 12, 1)) if d not in skipped], 0.043)
    return trade["id"]


def test_r8_sofr_us_holidays_without_fixing_are_not_missing(client):
    # Veterans Day (11-11) y Thanksgiving (11-26) no se publican; el 11-16 (feriado en MX) sí se publica
    tid = _sofr_swap_at_dec_1(client, skipped=_d("2026-11-11", "2026-11-26"))
    row = _row(client, "D21", tid)
    assert row["error"] is None and [w for w in row["warnings"] if w["code"] == "missing_fixing"] == []


def test_r8_sofr_business_day_without_fixing_is_still_missing(client):
    tid = _sofr_swap_at_dec_1(client, skipped=_d("2026-11-11", "2026-11-16", "2026-11-26"))
    missing = [w for w in _row(client, "D21", tid)["warnings"] if w["code"] == "missing_fixing"]
    assert len(missing) == 1 and missing[0]["index"] == "SOFR" and missing[0]["dates"] == ["2026-11-16"]


# ------------------------------------------------------------------------------ (b) FIX USDMXN

def _forward_settled_on(client, maturity, fix_days, snapshot_days):
    empty_portfolio(client)
    trade = market_forward(client, "buy", 10e6, maturity)
    for day, value in fix_days.items():
        r = client.post("/api/fixings", json={"index": "USDMXN", "date": day, "value": value})
        assert r.status_code == 201, r.get_json()
    snap = roll(client, "MX-DEMO", "DFWD", snapshot_days)
    r = client.get("/api/trades/%d/flows?snapshot=DFWD" % trade["id"])
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    settled = [f for f in body["flows"] if f["status"] == "settled"]
    return trade, settled, body["warnings"], snap


def test_a_forward_settled_on_a_mexican_holiday_uses_the_last_published_fix_without_warning(client):
    trade, settled, warnings, _ = _forward_settled_on(
        client, date(2026, 11, 16), {"2026-11-13": 19.5}, 7
    )
    assert warnings == [] and len(settled) == 1
    assert settled[0]["date"] == "2026-11-16"
    assert settled[0]["amount"] == pytest.approx(10e6 * (19.5 - trade["params"]["strike"]))


def test_a_forward_settled_on_a_weekend_uses_the_friday_fix_without_warning(client):
    trade, settled, warnings, _ = _forward_settled_on(
        client, date(2026, 11, 14), {"2026-11-13": 19.5, "2026-11-12": 19.4}, 7
    )
    assert warnings == [] and settled[0]["amount"] == pytest.approx(10e6 * (19.5 - trade["params"]["strike"]))


def test_a_forward_on_a_holiday_still_warns_when_the_previous_business_day_has_no_fix(client):
    trade, settled, warnings, _ = _forward_settled_on(
        client, date(2026, 11, 16), {"2026-11-12": 19.4}, 7  # falta el viernes 11-13 (hábil): hueco real de datos
    )
    assert [(w["code"], w["index"], w["dates"]) for w in warnings] == [("fx_fallback", "USDMXN", ["2026-11-16"])]


def test_a_forward_on_a_holiday_without_any_earlier_fix_falls_back_to_the_spot(client):
    _, settled, warnings, _ = _forward_settled_on(client, date(2026, 11, 16), {}, 7)
    assert [(w["code"], w["dates"]) for w in warnings] == [("fx_fallback", ["2026-11-16"])]


def test_a_forward_on_a_business_day_without_fix_still_warns_even_with_earlier_fixes(client):
    _, settled, warnings, _ = _forward_settled_on(client, date(2026, 11, 17), {"2026-11-13": 19.5}, 8)
    assert [(w["code"], w["dates"]) for w in warnings] == [("fx_fallback", ["2026-11-17"])]


def test_a_published_fix_on_a_holiday_is_used_as_is(client):
    trade, settled, warnings, _ = _forward_settled_on(
        client, date(2026, 11, 16), {"2026-11-13": 19.5, "2026-11-16": 19.7}, 7
    )
    assert warnings == [] and settled[0]["amount"] == pytest.approx(10e6 * (19.7 - trade["params"]["strike"]))


# ------------------------------------------------------------------------------ (c) coberturas

def _fx_item(day, **over):
    return {"amount_usd": 10e6, "date": day, "side": "buy_usd", **over}


def _codes(body):
    return [w["code"] for w in body["warnings"]]


def test_a_forecast_flow_on_a_mexican_holiday_warns_with_its_name(client):
    trade = market_forward(client, "buy", 10e6, date(2027, 3, 25))
    r = designate(client, trade["id"], "forecast_fx", _fx_item("2027-03-25"))
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert _codes(body) == ["forecast_date_holiday"]
    assert body["warnings"][0]["message"] == (
        "La fecha del flujo pronosticado (2027-03-25) es inhábil en México (Jueves Santo): "
        "se liquidará con el último FIX publicado"
    )


def test_a_forecast_flow_on_a_weekend_holiday_only_gets_the_weekend_warning(client):
    saturday = date(2027, 5, 1)  # Día del Trabajo en sábado
    trade = market_forward(client, "buy", 10e6, saturday)
    r = designate(client, trade["id"], "forecast_fx", _fx_item(saturday.isoformat()))
    assert r.status_code == 201, r.get_json()
    assert _codes(r.get_json()) == ["forecast_date_weekend"]


def test_a_forecast_flow_on_a_us_only_holiday_gets_no_holiday_warning(client):
    day = date(2026, 11, 26)  # Thanksgiving: hábil en México
    trade = market_forward(client, "buy", 10e6, day)
    r = designate(client, trade["id"], "forecast_fx", _fx_item(day.isoformat()))
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["warnings"] == []


def test_holiday_warning_comes_after_the_economic_relationship_one(client):
    trade = market_forward(client, "sell", 10e6, date(2027, 3, 25))  # vende USD y se cubre una compra
    r = designate(client, trade["id"], "forecast_fx", _fx_item("2027-03-25"))
    assert r.status_code == 201, r.get_json()
    assert _codes(r.get_json()) == ["no_economic_relationship", "forecast_date_holiday"]
    assert DOC  # la documentación es la de siempre
