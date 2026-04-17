from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import jsonpickle

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

    def run(self, state: TradingState) -> dict:
        # initialize stats and state, overwritten by traderData if it exists
        empty_stats = lambda: {'n': 0, 'mean_x': 0, 'mean_y': 0, 'M2_x': 0, 'C_xy': 0}
        root_stats = empty_stats()
        fair_price = {"INTARIAN_PEPPER_ROOT": 0, "ASH_COATED_OSMIUM": 0}
        hold_indicator = 1

        # decode data
        if state.traderData:
            root_stats, fair_price, hold_indicator = jsonpickle.decode(state.traderData)

        time = state.timestamp
        positions = state.position
        root_orders = []
        osmium_orders = []
        root_max_hold = 75

        mid_price = self.get_mid_price(state, 'INTARIAN_PEPPER_ROOT')

        # update stats and fair price every tick, no matter what
        if mid_price is not None:
            self.update_stats(mid_price, root_stats)
            slope = self.get_slope(root_stats)
            fair_price['INTARIAN_PEPPER_ROOT'] = mid_price + slope
            #print(f"t={time} mid={mid_price} slope={slope} fair={fair_price['INTARIAN_PEPPER_ROOT']}")

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

        result = {"INTARIAN_PEPPER_ROOT": root_orders, "ASH_COATED_OSMIUM": osmium_orders}
        traderData = jsonpickle.encode([root_stats, fair_price, hold_indicator])
        conversions = 0
        return result, conversions, traderData