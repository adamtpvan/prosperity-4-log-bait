from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import numpy as np

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
    
    def take_book(self, state : TradingState, action : int, product : string, max_position : int, max_half_edge : float, historical_fair_price : list, orders : dict):
        # buy/sell the entire side of a book 
        
        # initialize variables
        order_depth = state.order_depths[product]
        buy_orders = order_depth.buy_orders 
        sell_orders = order_depth.sell_orders 


        # take orders  (we want to buy, so take the sell book at a slight premium so +)
        # want to buy, so take the sell book
        if action == 1:
            clearing_price = historical_fair_price[-1] + max_half_edge
            for value in sell_orders:
                if value <= clearing_price:
                    
        # want to sell, so take the buy book
        else:


        pass

    def intarian_root_take(self, state: TradingState) -> int:
        #check around calculated fair price for favorable trades
        pass

    def market_make(self, state : TradingState, mid_value : int, half_edge : int, orders : int):
        #market make
        pass
    
    def run(self, state: TradingState) -> dict: #dict should be product with value list of orders
        """Only method required. It takes all buy and sell orders for all
        symbols as an input, and outputs a list of orders to be sent."""

        # Orders to be placed on exchange matching engine
        result = {"INTARIAN_PEPPER_ROOT" : [], "ASH_COATED_OSMIUM" : []}


        traderData = ""  # No state needed - we check position directly
        conversions = 0
        return result, conversions, traderData