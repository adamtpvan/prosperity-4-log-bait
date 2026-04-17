from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import jsonpickle

class Trader:

    def get_mid_price(self, state, product):
        # returns mid price from best bid and ask, or whichever side exists
        order_depths = state.order_depths[product]
        buy_orders = order_depths.buy_orders
        sell_orders = order_depths.sell_orders

        best_bid = max(buy_orders) if buy_orders else 0
        best_ask = min(sell_orders) if sell_orders else 0

        if best_bid != 0 and best_ask != 0:
            return (best_bid + best_ask) / 2
        return max(best_bid, best_ask)

    def update_stats(self, mid_price, stats):
        # welford's online algorithm - updates running slope stats in O(1) without storing history
        stats['n'] += 1
        n = stats['n']
        dx = (n - 1) - stats['mean_x']       # deviation of new x from old mean_x
        dy = mid_price - stats['mean_y']       # deviation of new y from old mean_y
        stats['mean_x'] += dx / n             # update mean_x
        stats['mean_y'] += dy / n             # update mean_y
        stats['M2_x'] += dx * ((n - 1) - stats['mean_x'])   # accumulate variance of x
        stats['C_xy'] += dx * (mid_price - stats['mean_y'])  # accumulate covariance of x and y

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
            # buying - take all asks at or below fair_price + half_edge
            clearing_price = fair_price + max_half_edge
            for value in sell_orders:
                if value <= clearing_price:
                    orders.append(Order(product, value, min(-sell_orders[value], max_position - position)))
        else:
            # selling - take all bids at or above fair_price - half_edge
            clearing_price = fair_price - max_half_edge
            for value in buy_orders:
                if value >= clearing_price:
                    orders.append(Order(product, value, max(-buy_orders[value], max_position - position)))

    def intarian_root_take(self, state, fair_price, orders):
        # takes any order strictly better than fair price (free edge)
        order_depth = state.order_depths['INTARIAN_PEPPER_ROOT']
        buy_orders = order_depth.buy_orders
        sell_orders = order_depth.sell_orders
        position = state.position.get('INTARIAN_PEPPER_ROOT', 0)

        for value in sell_orders:
            if value < fair_price:
                # ask is below fair value, buy it
                orders.append(Order("INTARIAN_PEPPER_ROOT", value, min(-sell_orders[value], 80 - position)))
        for value in buy_orders:
            if value > fair_price:
                # bid is above fair value, sell into it
                orders.append(Order("INTARIAN_PEPPER_ROOT", value, max(-buy_orders[value], 80 - position)))

    def run(self, state: TradingState) -> dict:
        # initialize stats and state, overwritten by traderData if it exists
        empty_stats = lambda: {'n': 0, 'mean_x': 0, 'mean_y': 0, 'M2_x': 0, 'C_xy': 0}
        root_stats = empty_stats()
        fair_price = {"INTARIAN_PEPPER_ROOT": 0, "ASH_COATED_OSMIUM": 0}
        hold_indicator = 1  # 1 = actively trading, -1 = position full, stop trading

        if state.traderData:
            root_stats, fair_price, hold_indicator = jsonpickle.decode(state.traderData)

        time = state.timestamp
        positions = state.position
        root_orders = []
        osmium_orders = []

        mid_price = self.get_mid_price(state, 'INTARIAN_PEPPER_ROOT')

        # update slope stats every tick regardless of phase so slope is ready at t=5000
        if mid_price != 0:
            self.update_stats(mid_price, root_stats)

        if time < 5000:
            # warmup phase - just accumulate stats, seed fair price on first valid tick
            if fair_price['INTARIAN_PEPPER_ROOT'] == 0:
                fair_price['INTARIAN_PEPPER_ROOT'] = mid_price
        elif hold_indicator != -1:
            # trading phase - advance fair price by slope each tick then sweep the book for holding
            slope = self.get_slope(root_stats)
            fair_price['INTARIAN_PEPPER_ROOT'] += slope

            if slope > 0:
                # price trending up, buy
                self.take_book(state, 1, 'INTARIAN_PEPPER_ROOT', 77, 5, fair_price['INTARIAN_PEPPER_ROOT'], root_orders)
            else:
                # price trending down, sell
                self.take_book(state, -1, 'INTARIAN_PEPPER_ROOT', -77, 5, fair_price['INTARIAN_PEPPER_ROOT'], root_orders)

            # lock out further trading once position hits 75
            if abs(positions.get('INTARIAN_PEPPER_ROOT', 0)) == 75:
                print("LOCKED")
                hold_indicator = -1
        else:
            print('LOOKING')
            # take favorable trades and sell at fair price instantly
            self.intarian_root_take(state, fair_price['INTARIAN_PEPPER_ROOT'], root_orders)
            
            # exit 
            if (positions.get('INTARIAN_PEPPER_ROOT', 0) > 75) or (positions.get('INTARIAN_PEPPER_ROOT', 0) < 0 and positions.get('INTARIAN_PEPPER_ROOT', 0) > -75):
                #we are long and want to sell
                self.take_book(state, -1, 'INTARIAN_PEPPER_ROOT', -80, 0, fair_price['INTARIAN_PEPPER_ROOT'], root_orders)
            elif (positions.get('INTARIAN_PEPPER_ROOT', 0) > 0 and positions.get('INTARIAN_PEPPER_ROOT', 0) < 75) or (positions.get('INTARIAN_PEPPER_ROOT', 0) < -75):
                #we are short and want to buy
                self.take_book(state, 1, 'INTARIAN_PEPPER_ROOT', 80, 0, fair_price['INTARIAN_PEPPER_ROOT'], root_orders)

        result = {"INTARIAN_PEPPER_ROOT": root_orders, "ASH_COATED_OSMIUM": osmium_orders}
        traderData = jsonpickle.encode([root_stats, fair_price, hold_indicator])
        conversions = 0
        return result, conversions, traderData