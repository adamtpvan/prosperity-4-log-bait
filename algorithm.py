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

    def run(self, state: TradingState) -> dict:
        #slope for intarian pepper root 0.001

        # initialize stats and state, overwritten by traderData if it exists
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
            if hold_indicator != -1:
                # trading phase - sweep book in direction of slope
                slope = self.get_slope(root_stats)
                if slope > 0:
                    self.take_book(state, 1, 'INTARIAN_PEPPER_ROOT', root_max_hold, 5, fair_price['INTARIAN_PEPPER_ROOT'], root_orders)

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
