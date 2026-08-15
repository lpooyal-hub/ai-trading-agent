import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.strategy.intraday_signal_selector import IntradaySignalSelector

KST = ZoneInfo("Asia/Seoul")
TRADING_DAY_OPEN = datetime(2026, 8, 12, 9, 0, 0, tzinfo=KST)
PREVIOUS_DAY_LATE_SESSION_START = datetime(2026, 8, 11, 15, 16, 0, tzinfo=KST)


def _candle_at(moment: datetime, close, volume: float = 1000.0) -> dict:
    return {
        "timestamp": moment.isoformat(),
        "openPrice": str(close),
        "highPrice": str(close),
        "lowPrice": str(close),
        "closePrice": str(close),
        "volume": str(volume),
    }


def _same_day_candles(
    count: int = 20,
    close: float = 10000.0,
    volume: float = 1000.0,
    start: datetime = TRADING_DAY_OPEN,
) -> list[dict]:
    return [_candle_at(start + timedelta(minutes=i), close, volume) for i in range(count)]


def _orderbook(bid, ask) -> dict:
    return {"bids": [{"price": str(bid)}], "asks": [{"price": str(ask)}]}


def _payload(
    candles: list[dict],
    price,
    *,
    bid=None,
    ask=None,
    observed_at: str | None = None,
    price_timestamp: str | None = None,
    orderbook_timestamp: str | None = None,
) -> dict:
    # All three timestamps default to the latest candle's own timestamp, so a
    # payload built with no overrides is fully self-consistent and fresh --
    # individual tests override one field at a time to isolate a failure mode.
    # Found via max(), not candles[-1]: some tests deliberately pass candles
    # in reverse order, and the anchor must track the true latest moment
    # regardless of list order, same as the selector's own sort does.
    anchor = max(candles, key=lambda candle: datetime.fromisoformat(candle["timestamp"]))["timestamp"]
    payload: dict = {"price": price, "candles": candles}
    if bid is not None and ask is not None:
        payload.update(_orderbook(bid, ask))
    payload["observed_at"] = observed_at or anchor
    payload["price_timestamp"] = price_timestamp or anchor
    payload["orderbook_timestamp"] = orderbook_timestamp or anchor
    return payload


class IntradaySignalSelectorTest(unittest.TestCase):
    def setUp(self):
        self.selector = IntradaySignalSelector(max_candidates=3)

    def test_constructor_rejects_non_positive_max_candidates(self):
        with self.assertRaises(ValueError):
            IntradaySignalSelector(max_candidates=0)

    def test_no_qualifying_move_returns_no_candidates(self):
        payload = _payload(_same_day_candles(), 10000.0, bid=9995, ask=10005)
        result = self.selector.select({"005930": payload}, ["005930"])
        self.assertEqual(result, [])

    def test_diagnostics_explain_a_valid_payload_without_an_event(self):
        payload = _payload(_same_day_candles(), 10000.0, bid=9995, ask=10005)

        result = self.selector.select_with_diagnostics({"005930": payload}, ["005930"])

        self.assertEqual(result.signals, [])
        self.assertEqual(result.diagnostics[0].symbol, "005930")
        self.assertEqual(result.diagnostics[0].outcome, "NO_EVENT")

    def test_diagnostics_explain_a_stale_price_quote(self):
        candles = _same_day_candles(count=20, close=10000.0)
        anchor = candles[-1]["timestamp"]
        stale_price_timestamp = (TRADING_DAY_OPEN + timedelta(minutes=10)).isoformat()
        payload = _payload(
            candles,
            10300.0,
            bid=10295,
            ask=10305,
            observed_at=anchor,
            price_timestamp=stale_price_timestamp,
        )

        result = self.selector.select_with_diagnostics({"005930": payload}, ["005930"])

        self.assertEqual(result.signals, [])
        self.assertEqual(result.diagnostics[0].outcome, "STALE_OR_FUTURE_PRICE")

    def test_diagnostics_report_missing_context_for_each_shortlisted_symbol(self):
        result = self.selector.select_with_diagnostics({}, ["005930", "000660"])

        self.assertEqual(
            [item.outcome for item in result.diagnostics],
            ["MISSING_CONTEXT", "MISSING_CONTEXT"],
        )

    def test_same_day_continuous_candles_compute_returns_normally(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10200.0)
        payload = _payload(candles, 10200.0, bid=10195, ask=10205)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(len(result), 1)
        signal = result[0]
        self.assertTrue(signal.event_triggered)
        self.assertAlmostEqual(signal.return_5m_percent, 2.0, places=2)
        self.assertAlmostEqual(signal.return_15m_percent, 2.0, places=2)

    def test_candle_order_does_not_affect_the_result(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10200.0)
        payload_forward = _payload(candles, 10200.0, bid=10195, ask=10205)
        payload_reversed = _payload(list(reversed(candles)), 10200.0, bid=10195, ask=10205)

        forward = self.selector.select({"005930": payload_forward}, ["005930"])[0]
        reversed_result = self.selector.select({"005930": payload_reversed}, ["005930"])[0]

        self.assertEqual(forward.return_5m_percent, reversed_result.return_5m_percent)
        self.assertEqual(forward.return_15m_percent, reversed_result.return_15m_percent)
        self.assertEqual(forward.event_triggered, reversed_result.event_triggered)

    def test_volume_expansion_triggers_an_event_without_a_price_move(self):
        candles = _same_day_candles(count=20, close=10000.0, volume=1000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10000.0, volume=5000.0)
        payload = _payload(candles, 10000.0, bid=9995, ask=10005)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(len(result), 1)
        signal = result[0]
        self.assertTrue(signal.event_triggered)
        self.assertGreaterEqual(signal.volume_ratio, 2.0)

    def test_vwap_deviation_reflects_price_above_the_volume_weighted_average(self):
        candles = _same_day_candles(count=20, close=10000.0, volume=1000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10500.0, volume=5000.0)
        payload = _payload(candles, 10500.0, bid=10495, ask=10505)

        signal = self.selector._build_signal("005930", payload)

        self.assertIsNotNone(signal)
        self.assertGreater(signal.vwap_deviation_percent, 0)

    # -- Requirement 1: orderbook fail-closed -------------------------------

    def test_missing_orderbook_produces_no_event(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        payload = _payload(candles, 10300.0)  # no bid/ask at all

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_empty_orderbook_sides_produce_no_event(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        payload = _payload(candles, 10300.0)
        payload["bids"] = []
        payload["asks"] = []

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_crossed_orderbook_produces_no_event(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        # best bid above best ask -- an invalid/crossed book.
        payload = _payload(candles, 10300.0, bid=10500, ask=10000)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_malformed_orderbook_prices_produce_no_event(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        payload = _payload(candles, 10300.0)
        payload["bids"] = [{"price": "not-a-number"}]
        payload["asks"] = [{"price": "10305"}]

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_excessive_spread_blocks_the_event_even_with_a_qualifying_move(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        payload = _payload(candles, 10300.0, bid=10000, ask=10500)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_valid_move_and_orderbook_triggers_an_event(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].event_triggered)

    # -- Requirement 2: overnight gap / same trading day ---------------------

    def test_previous_day_candles_mixed_with_first_candle_of_new_day_produce_no_event(self):
        previous_day_tail = [
            _candle_at(PREVIOUS_DAY_LATE_SESSION_START + timedelta(minutes=i), 10000.0)
            for i in range(15)
        ]
        first_candle_of_new_day = [_candle_at(TRADING_DAY_OPEN, 10300.0)]
        candles = previous_day_tail + first_candle_of_new_day
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_large_gap_within_the_trading_day_blocks_the_event(self):
        first_block = _same_day_candles(count=10, close=10000.0, start=TRADING_DAY_OPEN)
        second_block = _same_day_candles(
            count=10,
            close=10300.0,
            start=TRADING_DAY_OPEN + timedelta(minutes=20),  # 11-minute gap after the 10th candle
        )
        candles = first_block + second_block
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_insufficient_same_day_history_fails_closed(self):
        candles = _same_day_candles(count=5, close=10000.0)
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    # -- Requirement 3: non-finite numbers ------------------------------------

    def test_non_finite_price_produces_no_event(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        for bad_value in ("nan", "inf", "-inf"):
            with self.subTest(bad_value=bad_value):
                payload = _payload(candles, bad_value, bid=10295, ask=10305)
                result = self.selector.select({"005930": payload}, ["005930"])
                self.assertEqual(result, [])

    def test_non_finite_orderbook_prices_produce_no_event(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        for bad_value in ("nan", "inf"):
            with self.subTest(bad_value=bad_value):
                payload = _payload(candles, 10300.0, bid=bad_value, ask=10305)
                result = self.selector.select({"005930": payload}, ["005930"])
                self.assertEqual(result, [])

    def test_non_finite_candle_volume_fails_the_whole_symbol_not_zeroed(self):
        # A single corrupted volume field invalidates the whole candle series
        # (see "Requirement: strict per-candle OHLCV validation" below),
        # rather than silently treating "Infinity" as "0" and continuing.
        candles = _same_day_candles(count=20, close=10000.0)
        candles[5]["volume"] = "inf"
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_negative_volume_candle_fails_the_whole_symbol(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[5]["volume"] = "-500"
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_non_positive_price_fails_closed(self):
        candles = _same_day_candles(count=20, close=10000.0)
        for bad_price in (0, -100):
            with self.subTest(bad_price=bad_price):
                payload = _payload(candles, bad_price, bid=9995, ask=10005)
                result = self.selector.select({"005930": payload}, ["005930"])
                self.assertEqual(result, [])

    # -- General malformed/missing data ---------------------------------------

    def test_malformed_candles_fail_closed_without_raising(self):
        candles = _same_day_candles(count=16, close=10000.0)
        candles[0]["closePrice"] = "not-a-number"
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_missing_price_fails_closed(self):
        payload = {"candles": _same_day_candles(), **_orderbook(9995, 10005)}
        result = self.selector.select({"005930": payload}, ["005930"])
        self.assertEqual(result, [])

    def test_missing_symbol_in_signals_map_is_skipped_without_raising(self):
        result = self.selector.select({}, ["005930"])
        self.assertEqual(result, [])

    def test_non_dict_payload_fails_closed(self):
        result = self.selector.select({"005930": "not-a-dict"}, ["005930"])
        self.assertEqual(result, [])

    # -- Requirement: observed_at-anchored freshness -------------------------

    def test_stale_latest_candle_fails_closed(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        # observed_at (and the price/orderbook quotes) are fresh, but the
        # candle feed itself lags behind by more than the allowed window.
        observed_at = (TRADING_DAY_OPEN + timedelta(minutes=23)).isoformat()
        payload = _payload(
            candles,
            10300.0,
            bid=10295,
            ask=10305,
            observed_at=observed_at,
            price_timestamp=observed_at,
            orderbook_timestamp=observed_at,
        )

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_future_candle_timestamp_fails_closed(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        observed_at = (TRADING_DAY_OPEN + timedelta(minutes=10)).isoformat()
        payload = _payload(
            candles,
            10300.0,
            bid=10295,
            ask=10305,
            observed_at=observed_at,
            price_timestamp=observed_at,
            orderbook_timestamp=observed_at,
        )

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_future_price_timestamp_fails_closed(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        observed_at = candles[-1]["timestamp"]
        future_price_timestamp = (TRADING_DAY_OPEN + timedelta(minutes=25)).isoformat()
        payload = _payload(
            candles,
            10300.0,
            bid=10295,
            ask=10305,
            observed_at=observed_at,
            price_timestamp=future_price_timestamp,
        )

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_future_orderbook_timestamp_fails_closed(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        observed_at = candles[-1]["timestamp"]
        future_orderbook_timestamp = (TRADING_DAY_OPEN + timedelta(minutes=25)).isoformat()
        payload = _payload(
            candles,
            10300.0,
            bid=10295,
            ask=10305,
            observed_at=observed_at,
            orderbook_timestamp=future_orderbook_timestamp,
        )

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_missing_observed_at_fails_closed(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)
        del payload["observed_at"]

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_missing_price_timestamp_fails_closed(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)
        del payload["price_timestamp"]

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_missing_orderbook_timestamp_fails_closed(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)
        del payload["orderbook_timestamp"]

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    def test_all_timestamps_consistent_but_thirty_minutes_stale_fails_closed(self):
        # price_timestamp, orderbook_timestamp, and the latest candle all
        # agree with each other -- but observed_at (the real fetch time) is
        # 30 minutes later, so the whole snapshot is stale relative to now.
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        quote_time = candles[-1]["timestamp"]
        stale_observed_at = (TRADING_DAY_OPEN + timedelta(minutes=49)).isoformat()
        payload = _payload(
            candles,
            10300.0,
            bid=10295,
            ask=10305,
            observed_at=stale_observed_at,
            price_timestamp=quote_time,
            orderbook_timestamp=quote_time,
        )

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    # -- Requirement: strict per-candle OHLCV validation ----------------------

    def test_missing_ohlcv_field_fails_the_whole_symbol(self):
        for field in ("openPrice", "highPrice", "lowPrice", "closePrice", "volume"):
            with self.subTest(field=field):
                candles = _same_day_candles(count=20, close=10000.0)
                del candles[5][field]
                payload = _payload(candles, 10300.0, bid=10295, ask=10305)

                result = self.selector.select({"005930": payload}, ["005930"])

                self.assertEqual(result, [])

    def test_infinite_ohlc_value_fails_the_whole_symbol(self):
        for field in ("openPrice", "highPrice", "lowPrice", "closePrice"):
            with self.subTest(field=field):
                candles = _same_day_candles(count=20, close=10000.0)
                candles[5][field] = "inf"
                payload = _payload(candles, 10300.0, bid=10295, ask=10305)

                result = self.selector.select({"005930": payload}, ["005930"])

                self.assertEqual(result, [])

    def test_zero_or_negative_ohlc_price_fails_the_whole_symbol(self):
        for field in ("openPrice", "highPrice", "lowPrice", "closePrice"):
            for bad_value in ("0", "-100"):
                with self.subTest(field=field, bad_value=bad_value):
                    candles = _same_day_candles(count=20, close=10000.0)
                    candles[5][field] = bad_value
                    payload = _payload(candles, 10300.0, bid=10295, ask=10305)

                    result = self.selector.select({"005930": payload}, ["005930"])

                    self.assertEqual(result, [])

    def test_inconsistent_high_low_relationship_fails_the_whole_symbol(self):
        # high must be >= max(open, close) and low must be <= min(open, close).
        # (high < low is implied by those two and so can't be triggered in
        # isolation -- the code still checks it explicitly as a second layer.)
        scenarios = {
            "high_below_open_and_close": {
                "openPrice": "10000",
                "closePrice": "10000",
                "highPrice": "9900",
                "lowPrice": "9900",
            },
            "low_above_open_and_close": {
                "openPrice": "10000",
                "closePrice": "10000",
                "highPrice": "10100",
                "lowPrice": "10050",
            },
        }
        for name, overrides in scenarios.items():
            with self.subTest(scenario=name):
                candles = _same_day_candles(count=20, close=10000.0)
                candles[5].update(overrides)
                payload = _payload(candles, 10300.0, bid=10295, ask=10305)

                result = self.selector.select({"005930": payload}, ["005930"])

                self.assertEqual(result, [])

    def test_source_timestamps_skew_beyond_the_explicit_limit_fails_closed(self):
        # Each source is individually "recent enough" relative to observed_at
        # (candle within 180s, quotes within 120s) but the candle and the
        # quotes disagree with each other by more than the explicit
        # cross-source skew limit -- observed_at alone can't catch this.
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        candle_latest_dt = TRADING_DAY_OPEN + timedelta(minutes=19)
        observed_at_dt = candle_latest_dt + timedelta(seconds=170)
        quote_dt = observed_at_dt - timedelta(seconds=5)
        payload = _payload(
            candles,
            10300.0,
            bid=10295,
            ask=10305,
            observed_at=observed_at_dt.isoformat(),
            price_timestamp=quote_dt.isoformat(),
            orderbook_timestamp=quote_dt.isoformat(),
        )

        result = self.selector.select({"005930": payload}, ["005930"])

        self.assertEqual(result, [])

    # -- Ranking / truncation ---------------------------------------------------

    def test_select_never_returns_more_than_max_candidates(self):
        selector = IntradaySignalSelector(max_candidates=1)
        signals_by_symbol = {}
        candidates = []
        for index, symbol in enumerate(["005930", "000660", "035420"]):
            last_price = 10000.0 * (1 + 0.01 * (index + 1))
            candles = _same_day_candles(count=20, close=10000.0)
            candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), last_price)
            signals_by_symbol[symbol] = _payload(
                candles, last_price, bid=last_price - 5, ask=last_price + 5
            )
            candidates.append(symbol)

        result = selector.select(signals_by_symbol, candidates)

        self.assertLessEqual(len(result), 1)

    def test_higher_score_symbol_is_ranked_first(self):
        weak_candles = _same_day_candles(count=20, close=10000.0)
        weak_candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10060.0)
        strong_candles = _same_day_candles(count=20, close=10000.0)
        strong_candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10500.0)

        signals_by_symbol = {
            "WEAK": _payload(weak_candles, 10060.0, bid=10055, ask=10065),
            "STRONG": _payload(strong_candles, 10500.0, bid=10495, ask=10505),
        }

        result = self.selector.select(signals_by_symbol, ["WEAK", "STRONG"])

        self.assertEqual([signal.symbol for signal in result], ["STRONG", "WEAK"])

    def test_selector_never_emits_a_buy_or_sell_action(self):
        candles = _same_day_candles(count=20, close=10000.0)
        candles[-1] = _candle_at(TRADING_DAY_OPEN + timedelta(minutes=19), 10300.0)
        payload = _payload(candles, 10300.0, bid=10295, ask=10305)

        signal = self.selector._build_signal("005930", payload)

        self.assertIsNotNone(signal)
        self.assertFalse(hasattr(signal, "action"))


if __name__ == "__main__":
    unittest.main()
