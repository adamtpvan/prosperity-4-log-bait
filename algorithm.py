from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import jsonpickle
import numpy as np
import math


class Trader:
    OPTION_STRIKES = [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500]
    OPTION_POSITION_LIMIT = 300
    UNDERLYING_POSITION_LIMIT = 300
    IV_LOOKBACK = 60
    EDGE_ENTRY_THRESHOLD = 0.6
    MAX_OPTION_TRADE_PER_TICK = 40
    MAX_UNDERLYING_TRADE_PER_TICK = 80

    def bid(self):
        return 500

    def normal_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def black_scholes_call(self, spot: float, strike: float, ttm: float, rate: float, sigma: float) -> float:
        if spot is None or spot <= 0 or strike <= 0:
            return float("nan")
        if ttm <= 0:
            return max(spot - strike, 0.0)
        if sigma <= 0:
            return max(spot - strike * math.exp(-rate * ttm), 0.0)

        sqrt_t = math.sqrt(ttm)
        d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * ttm) / (sigma * sqrt_t)
        d2 = d1 - sigma * sqrt_t
        return spot * self.normal_cdf(d1) - strike * math.exp(-rate * ttm) * self.normal_cdf(d2)

    def black_scholes_call_delta(self, spot: float, strike: float, ttm: float, rate: float, sigma: float) -> float:
        if spot is None or spot <= 0 or strike <= 0 or ttm <= 0:
            return 0.0
        sigma = max(sigma, 1e-6)
        sqrt_t = math.sqrt(ttm)
        d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * ttm) / (sigma * sqrt_t)
        return self.normal_cdf(d1)

    def implied_volatility_call(self, market_price: float, spot: float, strike: float, ttm: float, rate: float) -> float:
        if market_price is None or spot is None:
            return float("nan")
        if market_price <= 0 or spot <= 0 or strike <= 0:
            return float("nan")

        intrinsic = max(spot - strike * math.exp(-rate * ttm), 0.0)
        if market_price < intrinsic or market_price > spot:
            return float("nan")

        low, high = 1e-6, 5.0
        for _ in range(100):
            mid = 0.5 * (low + high)
            model_price = self.black_scholes_call(spot, strike, ttm, rate, mid)
            if model_price > market_price:
                high = mid
            else:
                low = mid

        return 0.5 * (low + high)

    def get_mid_price(self, state, product):
        # returns mid price only if both sides exist, otherwise None
        order_depths = state.order_depths[product]
        buy_orders = order_depths.buy_orders
        sell_orders = order_depths.sell_orders

        if not buy_orders or not sell_orders:
            return None

        return (max(buy_orders) + min(sell_orders)) / 2

    def get_spread(self, state: TradingState, product: str):
        if product not in state.order_depths:
            return None
        order_depth = state.order_depths[product]
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None
        return float(min(order_depth.sell_orders) - max(order_depth.buy_orders))

    def market_make(self, state, product, history, window_size=50, k=1.0, position_limit=100):
        mid = self.get_mid_price(state, product)
        if mid is None:
            return []

        if product not in history:
            history[product] = []
        history[product].append(mid)
        if len(history[product]) > window_size:
            history[product] = history[product][-window_size:]

        if len(history[product]) < 2:
            spread = 5
        else:
            prices = np.array(history[product])
            std = np.std(prices)
            spread = k * std

        buy_price = int(mid - spread)
        sell_price = int(mid + spread)

        position = state.position.get(product, 0)

        orders = []
        if position < position_limit:
            qty = min(10, position_limit - position)
            orders.append(Order(product, buy_price, qty))

        if position > -position_limit:
            qty = min(10, position + position_limit)
            orders.append(Order(product, sell_price, -qty))

        return orders

    def mean_reversion_strategy(self, state, product, history, alpha=0.1, sd_multiplier=1.5, window_size=50, position_limit=100):
        mid = self.get_mid_price(state, product)
        if mid is None:
            return []

        if product not in history:
            history[product] = {'ema': mid, 'prices': []}
        else:
            history[product]['ema'] = alpha * mid + (1 - alpha) * history[product]['ema']

        ema = history[product]['ema']

        history[product]['prices'].append(mid)
        if len(history[product]['prices']) > window_size:
            history[product]['prices'] = history[product]['prices'][-window_size:]

        if len(history[product]['prices']) < 2:
            threshold = 5
        else:
            prices = np.array(history[product]['prices'])
            sd = np.std(prices)
            threshold = sd_multiplier * sd

        order_depth = state.order_depths[product]
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None

        if best_bid is None or best_ask is None:
            return []

        position = state.position.get(product, 0)

        orders = []
        deviation = mid - ema

        if deviation > threshold and position > -position_limit:
            qty = min(10, position + position_limit)
            orders.append(Order(product, best_bid, -qty))
        elif deviation < -threshold and position < position_limit:
            qty = min(10, position_limit - position)
            orders.append(Order(product, best_ask, qty))

        return orders

    def rolling_fair_vol(self, iv_history: list, strike_index: int, fallback_iv: float) -> float:
        vals = []
        for snapshot in reversed(iv_history):
            snap_ivs = snapshot.get("implied_volatilities", [])
            if strike_index < len(snap_ivs):
                iv = snap_ivs[strike_index]
                if iv is not None and not np.isnan(iv) and iv > 0:
                    vals.append(iv)
                    if len(vals) >= self.IV_LOOKBACK:
                        break

        if len(vals) >= 8:
            return float(np.median(vals))
        if fallback_iv is not None and not np.isnan(fallback_iv) and fallback_iv > 0:
            return float(fallback_iv)
        return 0.5

    def move_to_target_position(self, state: TradingState, product: str, orders: list, target_position: int, position_limit: int, max_trade_per_tick: int):
        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]
        current_position = state.position.get(product, 0)
        target_position = int(np.clip(target_position, -position_limit, position_limit))
        delta = target_position - current_position

        if delta == 0:
            return

        if delta > 0:
            asks = dict(sorted(order_depth.sell_orders.items()))
            remaining = min(delta, max_trade_per_tick)
            for price, qty in asks.items():
                if remaining <= 0:
                    break
                available = max(0, -qty)
                if available <= 0:
                    continue
                trade_qty = min(remaining, available)
                if trade_qty > 0:
                    orders.append(Order(product, int(price), int(trade_qty)))
                    remaining -= trade_qty
        else:
            bids = dict(sorted(order_depth.buy_orders.items(), reverse=True))
            remaining = min(-delta, max_trade_per_tick)
            for price, qty in bids.items():
                if remaining <= 0:
                    break
                available = max(0, qty)
                if available <= 0:
                    continue
                trade_qty = min(remaining, available)
                if trade_qty > 0:
                    orders.append(Order(product, int(price), int(-trade_qty)))
                    remaining -= trade_qty

    def take_book(self, state, action, product, max_position, max_half_edge, fair_price, orders):
        # sweeps the book up to a clearing price derived from fair price +/- half edge
        order_depth = state.order_depths[product]
        # buy_orders so we sell, want higher values first
        buy_orders = dict(sorted(order_depth.buy_orders.items(), reverse=True))
        # sell_orders so we buy, want lower values first
        sell_orders = dict(sorted(order_depth.sell_orders.items()))
        position = state.position.get(product, 0)

        if action == 1:
            clearing_price = fair_price + max_half_edge
            for value in sell_orders:
                if value <= clearing_price:
                    orders.append(Order(product, value, min(-sell_orders[value], max_position - position)))
        else:
            clearing_price = fair_price - max_half_edge
            for value in buy_orders:
                if value >= clearing_price:
                    orders.append(Order(product, value, max(-buy_orders[value], max_position - position)))

    def run(self, state: TradingState) -> dict:
        memory = {}
        if state.traderData:
            decoded = jsonpickle.decode(state.traderData)
            if isinstance(decoded, dict):
                memory = decoded

        history = memory.get("history", {})
        iv_history = memory.get("implied_volatility_history", [])

        time = state.timestamp
        positions = state.position
        hydrogel_orders = []
        velvetfruit_orders = []
        velvet_voucher_orders = {4000: [], 4500: [], 5000: [], 5100: [], 5200: [], 5300: [], 5400: [], 5500: [], 6000: [], 6500: []}

        if "HYDROGEL_PACK" in state.order_depths:
            hydrogel_orders = self.mean_reversion_strategy(state, "HYDROGEL_PACK", history, position_limit=200)

        underlying_symbol = "VELVETFRUIT_EXTRACT"
        risk_free_rate = 0.0
        time_to_maturity = max((1_000_000 - float(time)) / 1_000_000, 1e-6)
        underlying_mid = self.get_mid_price(state, underlying_symbol) if underlying_symbol in state.order_depths else None

        implied_volatilities = []
        option_mids = []
        for strike in self.OPTION_STRIKES:
            option_symbol = f"VEV_{strike}"
            option_mid = self.get_mid_price(state, option_symbol) if option_symbol in state.order_depths else None
            option_mids.append(option_mid)
            iv = self.implied_volatility_call(option_mid, underlying_mid, strike, time_to_maturity, risk_free_rate)
            implied_volatilities.append(iv)

        iv_history.append({"timestamp": time, "implied_volatilities": implied_volatilities})
        if len(iv_history) > 600:
            iv_history = iv_history[-600:]

        net_option_delta = 0.0
        for idx, strike in enumerate(self.OPTION_STRIKES):
            option_symbol = f"VEV_{strike}"
            if option_symbol not in state.order_depths:
                continue

            option_mid = option_mids[idx]
            current_iv = implied_volatilities[idx]
            spread = self.get_spread(state, option_symbol)
            current_pos = positions.get(option_symbol, 0)

            fair_vol = self.rolling_fair_vol(iv_history[:-1], idx, current_iv)
            fair_price = self.black_scholes_call(underlying_mid, strike, time_to_maturity, risk_free_rate, fair_vol)

            target_pos = current_pos
            if option_mid is not None and spread is not None and not np.isnan(fair_price):
                score = (option_mid - fair_price) / max(spread, 1.0)
                if abs(score) < self.EDGE_ENTRY_THRESHOLD:
                    target_pos = 0
                else:
                    scaled = int(np.clip(-score / 2.0, -1.0, 1.0) * self.OPTION_POSITION_LIMIT)
                    target_pos = int(np.clip(scaled, -self.OPTION_POSITION_LIMIT, self.OPTION_POSITION_LIMIT))

            self.move_to_target_position(
                state=state,
                product=option_symbol,
                orders=velvet_voucher_orders[strike],
                target_position=target_pos,
                position_limit=self.OPTION_POSITION_LIMIT,
                max_trade_per_tick=self.MAX_OPTION_TRADE_PER_TICK,
            )

            delta_sigma = fair_vol if np.isnan(current_iv) else current_iv
            option_delta = self.black_scholes_call_delta(underlying_mid, strike, time_to_maturity, risk_free_rate, delta_sigma)
            net_option_delta += current_pos * option_delta

        hedge_target = int(np.clip(-net_option_delta, -self.UNDERLYING_POSITION_LIMIT, self.UNDERLYING_POSITION_LIMIT))
        self.move_to_target_position(
            state=state,
            product=underlying_symbol,
            orders=velvetfruit_orders,
            target_position=hedge_target,
            position_limit=self.UNDERLYING_POSITION_LIMIT,
            max_trade_per_tick=self.MAX_UNDERLYING_TRADE_PER_TICK,
        )

        memory["history"] = history
        memory["implied_volatility_history"] = iv_history
        memory["implied_volatilities"] = implied_volatilities

        result = {
            "HYDROGEL_PACK": hydrogel_orders,
            "VELVETFRUIT_EXTRACT": velvetfruit_orders,
            "VEV_4000": velvet_voucher_orders[4000],
            "VEV_4500": velvet_voucher_orders[4500],
            "VEV_5000": velvet_voucher_orders[5000],
            "VEV_5100": velvet_voucher_orders[5100],
            "VEV_5200": velvet_voucher_orders[5200],
            "VEV_5300": velvet_voucher_orders[5300],
            "VEV_5400": velvet_voucher_orders[5400],
            "VEV_5500": velvet_voucher_orders[5500],
            "VEV_6000": velvet_voucher_orders[6000],
            "VEV_6500": velvet_voucher_orders[6500],
        }
        traderData = jsonpickle.encode(memory)
        conversions = 0
        return result, conversions, traderData
