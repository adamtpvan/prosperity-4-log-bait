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
    
    def z_score(self, state, product, historical_data : List):
        # where historical_stats is in the form of [mu, sd]
        mu = np.mean(historical_data)
        sd = np.std(historical_data)

        mid_price = self.get_mid_price(state, product)

        z_score = (mid_price - mu)/sd

        return z_score

    def update_historical_stats(self, state, product, window_length : int, historical_data: List[float, float, List]) -> List:
        order_depths = state.order_depths[product]
        mid_price = self.get_mid_price(state, product)

        if len(historical_data) <= window_length:
            historical_data.append(mid_price)
        else:
            pass



    def mean_revert(self, state, product):
        pass 

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
        root_intercept = 0

        if state.traderData:
            decoded_data = jsonpickle.decode(state.traderData)
            if isinstance(decoded_data, (list, tuple)) and len(decoded_data) == 2:
                hold_indicator, root_intercept = decoded_data

        if root_intercept==0:
            root_intercept = round(self.get_mid_price(state, 'INTARIAN_PEPPER_ROOT')/1000)*1000

        time = state.timestamp
        positions = state.position
        root_orders = []
        osmium_orders = []


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
        traderData = jsonpickle.encode([hold_indicator,root_intercept])
        conversions = 0
        return result, conversions, traderData
