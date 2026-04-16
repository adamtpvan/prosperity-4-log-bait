from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string

class Trader:

    def bid(self):
        return 15
    
    def update_data(self):
        #update mid price data
        pass

    def root_fair_price(self):
        #add calculated slope to last data point
        pass
    
    def take_book(self):
        #buy/sell the entire side of a book 
        pass

    def intarian_root_take(self):
        #check around calculated fair price for favorable trades
        pass

    def market_make(self, state, mid_value, half_edge, orders):
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