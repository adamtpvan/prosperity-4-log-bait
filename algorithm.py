from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import jsonpickle
import numpy as np

class Trader:

    def bid(self):
        #seeing about a ~4000 xirec profit from osmium, so perhaps around ~1000 with added liquidity?
        return 700

    def get_mid_price(self, state, product):
        # returns mid price only if both sides exist, otherwise None
        order_depths = state.order_depths[product]
        buy_orders = order_depths.buy_orders
        sell_orders = order_depths.sell_orders

        if not buy_orders or not sell_orders:
            return None

        return (max(buy_orders) + min(sell_orders)) / 2
    
    def z_score(self, state, product, historical_data : List):
        #its 3 am, im hard coding the mean 
        mu = 9995
        sd = np.std(historical_data)
        order_depth = state.order_depths[product]
        #buy_orders so we sell, want higher values first 
        buy_orders = dict(sorted(order_depth.buy_orders.items(), reverse = True))
        #sell_orders so we buy, want lower values first
        sell_orders = dict(sorted(order_depth.sell_orders.items()))
        
        if len(buy_orders) != 0:
            best_bid = max(buy_orders, key=buy_orders.get)
            buy_z_score = (best_bid - mu)/sd
        else:
            buy_z_score = -999
        if len(sell_orders) != 0:
            best_ask = min(sell_orders, key=sell_orders.get)
            sell_z_score = (best_ask - mu)/sd
        else:
            sell_z_score = 999

        return buy_z_score, sell_z_score

    def update_historical_stats(self, state, product, window_length : int, historical_data: List) -> List:
        mid_price = self.get_mid_price(state, product)
        if mid_price:
            if len(historical_data) <= window_length:
                historical_data.append(mid_price)
            else:
                historical_data[:-1] = historical_data[1:]
                historical_data[-1] = mid_price

    def mean_revert(self, state, product, historical_data, z_threshold, exit_threshold, max_position, orders):
        order_depth = state.order_depths[product]
        buy_orders = dict(sorted(order_depth.buy_orders.items(), reverse=True))
        sell_orders = dict(sorted(order_depth.sell_orders.items()))
        position = state.position.get(product, 0)

        buy_z_score, sell_z_score = self.z_score(state, product, historical_data)

        # enter
        if buy_z_score >= z_threshold:
            delta = max(buy_orders) - np.mean(historical_data)
            self.take_book(state, -1, product, -max_position, delta, np.mean(historical_data), orders)
        elif sell_z_score <= -z_threshold:
            delta = np.mean(historical_data) - min(sell_orders)
            self.take_book(state, 1, product, max_position, delta, np.mean(historical_data), orders)

        # exit
        if (buy_z_score <= exit_threshold) and (position > 0):
            self.take_book(state, -1, product, 0, 0, np.mean(historical_data), orders)
        elif (sell_z_score >= -exit_threshold) and (position < 0):
            self.take_book(state, 1, product, 0, 0, np.mean(historical_data), orders)

    def take_book(self, state, action, product, max_position, max_half_edge, fair_price, orders):
        # sweeps the book up to a clearing price derived from fair price +/- half edge
        order_depth = state.order_depths[product]
        #buy_orders so we sell, want higher values first 
        buy_orders = dict(sorted(order_depth.buy_orders.items(), reverse = True))
        #sell_orders so we buy, want lower values first
        sell_orders = dict(sorted(order_depth.sell_orders.items()))
        position = state.position.get(product, 0)

        if action == 1:
            #buy
            clearing_price = fair_price + max_half_edge
            for value in sell_orders:
                if value <= clearing_price:
                    orders.append(Order(product, value, min(-sell_orders[value], max_position - position)))
        else:
            #sell
            clearing_price = fair_price - max_half_edge
            for value in buy_orders:
                if value >= clearing_price:
                    orders.append(Order(product, value, max(-buy_orders[value], max_position - position)))

    def run(self, state: TradingState) -> dict:
        # initialize stats and state, overwritten by traderData if it exists
        hold_indicator = 1
        root_intercept = self.get_mid_price(state, 'INTARIAN_PEPPER_ROOT')
        osmium_data = []
        
        if state.traderData:
            hold_indicator, root_intercept, osmium_data = jsonpickle.decode(state.traderData)

        if root_intercept==0:
            root_intercept = round(self.get_mid_price(state, 'INTARIAN_PEPPER_ROOT')/1000)*1000

        time = state.timestamp
        positions = state.position
        root_orders = []
        osmium_orders = []

        #osmium
        enter_z_score = 0.5
        exit_z_score = 0.5
        osmium_average = 9995

        if time >= 5000:
            self.mean_revert(state, "ASH_COATED_OSMIUM", osmium_data, enter_z_score, exit_z_score, 80, osmium_orders)
        self.update_historical_stats(state, "ASH_COATED_OSMIUM", 50, osmium_data)

        #roots
        root_max_hold = 80
        root_slope = 0.001

        if 'INTARIAN_PEPPER_ROOT' in state.order_depths:
            root_mid_price = self.get_mid_price(state, 'INTARIAN_PEPPER_ROOT')

            if root_intercept is None and root_mid_price is not None:
                root_intercept = root_mid_price

            root_fair_price = None
            if root_intercept is not None:
                root_fair_price = root_intercept + root_slope * time

            if time < 1000000-25:
                if hold_indicator != -1 and root_fair_price is not None:
                    self.take_book(state, 1, 'INTARIAN_PEPPER_ROOT', root_max_hold, 5, root_fair_price, root_orders)

                    if abs(positions.get('INTARIAN_PEPPER_ROOT', 0)) == root_max_hold:
                        hold_indicator = -1
                
                else:
                    if root_mid_price is not None and root_mid_price > root_fair_price:
                        self.take_book(state, 2, 'INTARIAN_PEPPER_ROOT', root_max_hold, 5, root_fair_price, root_orders)

                    hold_indicator=1

            else: 
                self.take_book(state, 2, 'INTARIAN_PEPPER_ROOT', root_max_hold, 5, 0, root_orders)


        result = {"INTARIAN_PEPPER_ROOT": root_orders, "ASH_COATED_OSMIUM": osmium_orders}
        traderData = jsonpickle.encode([hold_indicator,root_intercept, osmium_data])
        conversions = 0
        return result, conversions, traderData
