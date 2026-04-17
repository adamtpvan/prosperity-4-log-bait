from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import numpy as np
import jsonpickle

class Trader:

    def bid(self):
        return 15
    
    def root_update_data(self, state : TradingState, historical_data : list):
        order_depths = state.order_depths['INTARIAN_PEPPER_ROOT']
        buy_orders = order_depths.buy_orders
        sell_orders = order_depths.sell_orders

        if buy_orders:
            best_bid = max(buy_orders)
        else:
            best_bid = 0
        if sell_orders:    
            best_ask = min(sell_orders)
        else:
            best_ask = 0

        if best_bid != 0 and best_ask != 0:
            mid_price = (best_bid + best_ask) / 2
        else:
            mid_price = max(best_bid, best_ask)

        if mid_price == 0 and len(historical_data) >= 1:
            historical_data.append(historical_data[-1])
        else:
            historical_data.append(mid_price)
        

    def root_fair_price(self, state : TradingState, historical_data : list, historical_fair_price : float) -> tuple:
        x = np.arange(len(historical_data))
        slope, intercept = np.polyfit(x, historical_data, 1)

        if historical_fair_price == 0:
            historical_fair_price = historical_data[-1]
        else:
            historical_fair_price = historical_fair_price + slope
        
        return slope, historical_fair_price
    
    def take_book(self, state : TradingState, action : int, product : string, max_position : int, max_half_edge : float, historical_fair_price : float, orders : list[Order]):
        order_depth = state.order_depths[product]
        buy_orders = order_depth.buy_orders 
        sell_orders = order_depth.sell_orders 
        position = state.position.get(product, 0)

        if action == 1:
            clearing_price = historical_fair_price + max_half_edge
            for value in sell_orders:
                if value <= clearing_price:
                    orders.append(Order(product, value, min(-sell_orders[value], max_position - position)))
        else:
            clearing_price = historical_fair_price - max_half_edge
            for value in buy_orders:
                if value >= clearing_price:
                    orders.append(Order(product, value, max(-buy_orders[value], max_position - position)))

    def intarian_root_take(self, state: TradingState, historical_fair_price : float, orders : list[Order]) -> int:
        #take favorable trades around fair price
        order_depth = state.order_depths['INTARIAN_PEPPER_ROOT']
        buy_orders = order_depth.buy_orders 
        sell_orders = order_depth.sell_orders 
        position = state.position.get('INTARIAN_PEPPER_ROOT', 0)

        fair_price = historical_fair_price

        for value in sell_orders:
            if value < fair_price:
                orders.append(Order("INTARIAN_PEPPER_ROOT", value, min(-sell_orders[value], 80 - position)))
        for value in buy_orders:
            if value > fair_price:
                    orders.append(Order("INTARIAN_PEPPER_ROOT", value, max(-buy_orders[value], 80 - position)))
    
    def run(self, state: TradingState) -> dict:
        historical_data = {"INTARIAN_PEPPER_ROOT" : [], "ASH_COATED_OSMIUM" : []}
        historical_fair_price = {"INTARIAN_PEPPER_ROOT" : 0, "ASH_COATED_OSMIUM" : 0}
        hold_indicator = 1
        if state.traderData:
            historical_data, historical_fair_price, hold_indicator = jsonpickle.decode(state.traderData)
        time = state.timestamp
        positions = state.position
        root_orders = []
        osmium_orders = []

        #wait for slope
        if time < 5000:
            self.root_update_data(state, historical_data['INTARIAN_PEPPER_ROOT'])
        #hold
        elif hold_indicator != -1:
            slope, historical_fair_price['INTARIAN_PEPPER_ROOT'] = self.root_fair_price(
                state,
                historical_data['INTARIAN_PEPPER_ROOT'],
                historical_fair_price['INTARIAN_PEPPER_ROOT']
            )
            if slope > 0:
                self.take_book(state, 1, 'INTARIAN_PEPPER_ROOT', 80, 5, historical_fair_price['INTARIAN_PEPPER_ROOT'], root_orders)
            else:
                self.take_book(state, -1, 'INTARIAN_PEPPER_ROOT', 80, 5, historical_fair_price['INTARIAN_PEPPER_ROOT'], root_orders)
            if abs(positions.get('INTARIAN_PEPPER_ROOT', 0)) == 75:
               hold_indicator = -1

        result = {"INTARIAN_PEPPER_ROOT" : root_orders, "ASH_COATED_OSMIUM" : osmium_orders}

        traderData = jsonpickle.encode([historical_data, historical_fair_price, hold_indicator])
        conversions = 0
        return result, conversions, traderData