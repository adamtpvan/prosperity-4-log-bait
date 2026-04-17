from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import numpy as np
import jsonpickle

#note t = 0 to t = 1,000,000, ticks are 100 a piece

class Trader:

    def bid(self):
        return 15
    
    def root_update_data(self, state : TradingState, historical_data : list):
        # calculates mid price and updates historical data list 

        # initialize variables
        order_depths = state.order_depths['INTARIAN_PEPPER_ROOT']
        buy_orders = order_depths.buy_orders
        sell_orders = order_depths.sell_orders

        # define best_bid and best_ask if not empty, else use last mid price
        if buy_orders:
            best_bid = max(buy_orders)
        else:
            best_bid = 0
        if sell_orders:    
            best_ask = min(sell_orders)
        else:
            best_ask = 0

        # calculate mid price and append to list 
        if best_bid != 0 and best_ask != 0:
            mid_price = (best_bid + best_ask) / 2
        else:
            mid_price = max(best_bid, best_ask)

        if mid_price == 0 and len(historical_data) >= 1:
            historical_data.append(historical_data[-1])
        else:
            historical_data.append(mid_price)
        

    def root_fair_price(self, state : TradingState, historical_data : list, historical_fair_price : list) -> float:
        # calculates fair_price and updates historical fair_price

        # calculate slope given historical data
        x = np.arrange(len(historical_data))
        slope, intercept = np.polyfit(x, historical_data, 1)

        # calculate historical_fair_price and append
        if len(historical_fair_price) == 0:
            historical_fair_price.append(historical_data[-1])
        else:
            historical_fair_price.append(historical_fair_price[-1] + slope)
        
        return slope
    
    def take_book(self, state : TradingState, action : int, product : string, max_position : int, max_half_edge : float, historical_fair_price : list, orders : list[Order]):
        # buy/sell the entire side of a book 
        
        # initialize variables
        order_depth = state.order_depths[product]
        buy_orders = order_depth.buy_orders 
        sell_orders = order_depth.sell_orders 
        position = state.position[product]


        # take orders
        # want to buy, so take the sell book
        if action == 1:
            # we want to buy, so take the sell book at a slight premium so +
            clearing_price = historical_fair_price[-1] + max_half_edge
            for value in sell_orders:
                if value <= clearing_price:
                    orders.append(Order(product, value, min(-sell_orders[value], max_position - position)))
        # want to sell, so take the buy book
        else:
            # we want to sell, so take the buy book at a slight premium so -
            clearing_price = historical_fair_price[-1] - max_half_edge
            for value in buy_orders:
                if value >= sell_orders:
                    orders.append(Order(product, value, max(-buy_orders[value] , max_position - position)))

    def intarian_root_take(self, state: TradingState, historical_fair_price : list, orders : list[Order]) -> int:
        #check around calculated fair price for favorable trades

        #initialize variables
        order_depth = state.order_depths['INTARIAN_PEPPER_ROOT']
        buy_orders = order_depth.buy_orders 
        sell_orders = order_depth.sell_orders 
        position = state.position['INTARIAN_PEPPER_ROOT']

        #fair price
        fair_price = historical_fair_price[-1]

        for value in sell_orders:
            if value < fair_price:
                orders.append(Order("INTARIAN_PEPPER_ROOT", value, min(-sell_orders[value], 80 - position)))
        for value in buy_orders:
            if value > fair_price:
                    orders.append(Order("INTARIAN_PEPPER_ROOT", value, max(-buy_orders[value] , 80 - position)))
    
    def run(self, state: TradingState) -> dict: #dict should be product with value list of orders
        # initialize variables
        # traderData is a list of historical_data, historical_fair_price
        historical_data = {"INTARIAN_PEPPER_ROOT" : [], "ASH_COATED_OSMIUM" : []}
        historical_fair_price = {"INTARIAN_PEPPER_ROOT" : [], "ASH_COATED_OSMIUM" : []}
        hold_indicator = 1
        if state.traderData:
            historical_data, historical_fair_price, hold_indicator = jsonpickle.decode(state.traderData)
        time = state.timestamp
        positions = state.position
        root_orders = []
        osmium_orders = []

        #allow time for slope
        if time < 5000:
            self.root_update_data(state, historical_data['INTARIAN_PEPPER_ROOT'])
        #if we havent bought yet, buy now
        elif hold_indicator != -1:
            #slope going up, buy
            if self.root_fair_price(state, historical_data['INTARIAN_PEPPER_ROOT'], historical_fair_price['INTARIAN_PEPPER_ROOT']) > 0:
                self.take_book(state, 1, 'INTARIAN_PEPPER_ROOT', 75, 999999999, historical_fair_price['INTARIAN_PEPPER_ROOT'], root_orders)
            #slope going down, sell
            else:
                self.take_book(state, -1, 'INTARIAN_PEPPER_ROOT', 75, 999999999, historical_fair_price['INTARIAN_PEPPER_ROOT'], root_orders)
            #this wil change the indicator on the tick after we get a full position but should be okay
            if abs(positions['INTARIAN_PEPPER_ROOT']) == 75:
               hold_indicator = -1

        # Orders to be placed on exchange matching engine
        result = {"INTARIAN_PEPPER_ROOT" : root_orders, "ASH_COATED_OSMIUM" : osmium_orders}

        traderData = jsonpickle.encode([historical_data, historical_fair_price, hold_indicator])
        conversions = 0
        return result, conversions, traderData