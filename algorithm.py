from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import jsonpickle
import numpy as np

class Trader:

    def get_mid_price(self, state, product):
        # returns mid price only if both sides exist, otherwise None
        order_depths = state.order_depths[product]
        buy_orders = order_depths.buy_orders
        sell_orders = order_depths.sell_orders

        if not buy_orders or not sell_orders:
            return None

        return (max(buy_orders) + min(sell_orders)) / 2

    def update_stats(self, mid_price, stats):
        # welford's online algorithm - updates running slope stats in O(1) without storing history
        stats['n'] += 1
        n = stats['n']
        dx = (n - 1) - stats['mean_x']
        dy = mid_price - stats['mean_y']
        stats['mean_x'] += dx / n
        stats['mean_y'] += dy / n
        stats['M2_x'] += dx * ((n - 1) - stats['mean_x'])
        stats['C_xy'] += dx * (mid_price - stats['mean_y'])

    def get_slope(self, stats):
        # slope = covariance(x,y) / variance(x), returns 0 if not enough data
        if stats['M2_x'] == 0:
            return 0
        return stats['C_xy'] / stats['M2_x']

    def take_book(self, state, action, product, max_position, max_half_edge, fair_price, orders):
        # sweeps the book up to a clearing price derived from fair price +/- half edge
        order_depth = state.order_depths[product]
        buy_orders = order_depth.buy_orders
        sell_orders = order_depth.sell_orders
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

    # ===== ASH_COATED_OSMIUM Mean Reversion Strategy =====

    def osmium_update_data(self, state: TradingState, historical_data: list):
        """Track mid-price history for ASH_COATED_OSMIUM"""
        mid_price = self.get_mid_price(state, 'ASH_COATED_OSMIUM')

        if mid_price is None and len(historical_data) >= 1:
            historical_data.append(historical_data[-1])
        elif mid_price is not None:
            historical_data.append(mid_price)

    def osmium_mean_reversion_signals(self, historical_data: list, lookback: int = 15, num_std: float = 1.5) -> tuple:
        """
        Calculate Bollinger Bands for mean reversion strategy.
        Returns (mean, upper_band, lower_band, z_score)
        """
        if len(historical_data) < lookback:
            if len(historical_data) == 0:
                return 0, 0, 0, 0
            mean = np.mean(historical_data)
            std = np.std(historical_data) if len(historical_data) > 1 else 0
        else:
            recent_data = historical_data[-lookback:]
            mean = np.mean(recent_data)
            std = np.std(recent_data)

        upper_band = mean + (num_std * std)
        lower_band = mean - (num_std * std)

        current_price = historical_data[-1] if historical_data else 0
        z_score = (current_price - mean) / std if std > 0 else 0

        return mean, upper_band, lower_band, z_score

    def osmium_mean_reversion_take(self, state: TradingState, historical_data: list, orders: list, max_position: int = 50):
        """
        Aggressive mean reversion strategy for high volatility ASH_COATED_OSMIUM.
        """
        order_depth = state.order_depths['ASH_COATED_OSMIUM']
        buy_orders = order_depth.buy_orders
        sell_orders = order_depth.sell_orders
        position = state.position.get('ASH_COATED_OSMIUM', 0)

        mean, upper_band, lower_band, z_score = self.osmium_mean_reversion_signals(historical_data)

        if mean == 0:
            return

        fair = int(round(mean))

        # Strong buy signal: price significantly below mean
        if z_score < -1.0:
            # Take ALL asks below mean (they're cheap)
            for price in sorted(sell_orders.keys()):
                if price < mean and position < max_position:
                    qty = min(-sell_orders[price], max_position - position)
                    if qty > 0:
                        orders.append(Order("ASH_COATED_OSMIUM", price, qty))
                        position += qty
            # Place aggressive bid at fair value
            if position < max_position:
                orders.append(Order("ASH_COATED_OSMIUM", fair, max_position - position))

        # Strong sell signal: price significantly above mean
        elif z_score > 1.0:
            # Take ALL bids above mean (they're expensive)
            for price in sorted(buy_orders.keys(), reverse=True):
                if price > mean and position > -max_position:
                    qty = max(-buy_orders[price], -max_position - position)
                    if qty < 0:
                        orders.append(Order("ASH_COATED_OSMIUM", price, qty))
                        position += qty
            # Place aggressive ask at fair value
            if position > -max_position:
                orders.append(Order("ASH_COATED_OSMIUM", fair, -max_position - position))

        # Neutral zone: unwind positions
        else:
            if position > 0:
                # We're long, sell above mean
                for price in sorted(buy_orders.keys(), reverse=True):
                    if price >= fair and position > 0:
                        qty = max(-buy_orders[price], -position)
                        if qty < 0:
                            orders.append(Order("ASH_COATED_OSMIUM", price, qty))
                            position += qty
                # Place ask above fair to exit
                if position > 0:
                    orders.append(Order("ASH_COATED_OSMIUM", fair + 1, -position))

            elif position < 0:
                # We're short, buy below mean
                for price in sorted(sell_orders.keys()):
                    if price <= fair and position < 0:
                        qty = min(-sell_orders[price], -position)
                        if qty > 0:
                            orders.append(Order("ASH_COATED_OSMIUM", price, qty))
                            position += qty
                # Place bid below fair to exit
                if position < 0:
                    orders.append(Order("ASH_COATED_OSMIUM", fair - 1, -position))

    def run(self, state: TradingState) -> dict:
        # initialize stats and state, overwritten by traderData if it exists
        empty_stats = lambda: {'n': 0, 'mean_x': 0, 'mean_y': 0, 'M2_x': 0, 'C_xy': 0}
        root_stats = empty_stats()
        fair_price = {"INTARIAN_PEPPER_ROOT": 0, "ASH_COATED_OSMIUM": 0}
        hold_indicator = 1
        osmium_history = []

        # decode data
        if state.traderData:
            root_stats, fair_price, hold_indicator, osmium_history = jsonpickle.decode(state.traderData)

        time = state.timestamp
        positions = state.position
        root_orders = []
        osmium_orders = []
        root_max_hold = 80

        # ===== INTARIAN_PEPPER_ROOT Strategy (Trend Following) =====
        if 'INTARIAN_PEPPER_ROOT' in state.order_depths:
            mid_price = self.get_mid_price(state, 'INTARIAN_PEPPER_ROOT')

            # update stats and fair price every tick, no matter what
            if mid_price is not None:
                self.update_stats(mid_price, root_stats)
                slope = self.get_slope(root_stats)
                fair_price['INTARIAN_PEPPER_ROOT'] = mid_price + slope

            # data phase - no trading for first 5000 ticks
            if time < 5000:
                pass
            elif hold_indicator != -1:
                # trading phase - sweep book in direction of slope
                slope = self.get_slope(root_stats)
                if slope > 0:
                    self.take_book(state, 1, 'INTARIAN_PEPPER_ROOT', root_max_hold, 5, fair_price['INTARIAN_PEPPER_ROOT'], root_orders)
                else:
                    self.take_book(state, -1, 'INTARIAN_PEPPER_ROOT', -root_max_hold, 5, fair_price['INTARIAN_PEPPER_ROOT'], root_orders)

                if abs(positions.get('INTARIAN_PEPPER_ROOT', 0)) == root_max_hold:
                    hold_indicator = -1

        # ===== ASH_COATED_OSMIUM Strategy (Mean Reversion) =====
        if 'ASH_COATED_OSMIUM' in state.order_depths:
            self.osmium_update_data(state, osmium_history)
            osmium_pos = positions.get('ASH_COATED_OSMIUM', 0)
            mid = self.get_mid_price(state, 'ASH_COATED_OSMIUM')

            # Start trading after collecting enough data points for Bollinger Bands
            if len(osmium_history) >= 10:
                mean, upper, lower, z = self.osmium_mean_reversion_signals(osmium_history)

                # Determine signal status
                if z < -1.0:
                    signal = "BUY SIGNAL"
                elif z > 1.0:
                    signal = "SELL SIGNAL"
                elif abs(z) < 0.5 and osmium_pos != 0:
                    signal = "UNWIND"
                else:
                    signal = "NO SIGNAL"

                if mid is not None:
                    print(f"[OSMIUM] t={time} | z={z:.3f} | {signal} | pos={osmium_pos} | mid={mid:.1f} | mean={mean:.1f} | bands=[{lower:.1f}, {upper:.1f}]")

                self.osmium_mean_reversion_take(state, osmium_history, osmium_orders)

                if osmium_orders:
                    print(f"[OSMIUM] ORDERS: {osmium_orders}")

        result = {"INTARIAN_PEPPER_ROOT": root_orders, "ASH_COATED_OSMIUM": osmium_orders}
        traderData = jsonpickle.encode([root_stats, fair_price, hold_indicator, osmium_history])
        conversions = 0
        return result, conversions, traderData
