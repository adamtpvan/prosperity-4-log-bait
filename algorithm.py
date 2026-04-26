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

    def market_make(self, state, product, history, window_size=50, k=1.0, position_limit=100):
        mid = self.get_mid_price(state, product)
        if mid is None:
            return []
        
        # Update history
        if product not in history:
            history[product] = []
        history[product].append(mid)
        if len(history[product]) > window_size:
            history[product] = history[product][-window_size:]
        
        if len(history[product]) < 2:
            # Not enough data, use fixed spread
            spread = 5  # arbitrary
        else:
            prices = np.array(history[product])
            mean = np.mean(prices)
            std = np.std(prices)
            spread = k * std
        
        buy_price = int(mid - spread)
        sell_price = int(mid + spread)
        
        position = state.position.get(product, 0)
        
        orders = []
        # Place buy order if not at position limit
        if position < position_limit:
            # Buy at buy_price, quantity to reach limit or some amount
            qty = min(10, position_limit - position)  # arbitrary quantity
            orders.append(Order(product, buy_price, qty))
        
        # Place sell order if not at negative position limit
        if position > -position_limit:
            qty = min(10, position + position_limit)  # since position is negative, this is positive qty to sell
            orders.append(Order(product, sell_price, -qty))
        
        return orders

    def mean_reversion_strategy(self, state, product, history, alpha=0.1, sd_multiplier=1.5, window_size=50, position_limit=100):
        mid = self.get_mid_price(state, product)
        if mid is None:
            return []
        
        # Update EMA
        if product not in history:
            history[product] = {'ema': mid, 'prices': []}
        else:
            history[product]['ema'] = alpha * mid + (1 - alpha) * history[product]['ema']
        
        ema = history[product]['ema']
        
        # Update prices for SD calculation
        history[product]['prices'].append(mid)
        if len(history[product]['prices']) > window_size:
            history[product]['prices'] = history[product]['prices'][-window_size:]
        
        # Calculate SD-based threshold
        if len(history[product]['prices']) < 2:
            threshold = 5  # fallback
        else:
            prices = np.array(history[product]['prices'])
            sd = np.std(prices)
            threshold = sd_multiplier * sd
        
        # Get best bid and ask
        order_depth = state.order_depths[product]
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        
        if best_bid is None or best_ask is None:
            return []  # No orders if no bid/ask
        
        position = state.position.get(product, 0)
        
        orders = []
        
        deviation = mid - ema
        
        # If price significantly above EMA, expect reversion down: place sell order at best bid
        if deviation > threshold and position > -position_limit:
            qty = min(10, position + position_limit)
            orders.append(Order(product, best_bid, -qty))
        
        # If price significantly below EMA, expect reversion up: place buy order at best ask
        elif deviation < -threshold and position < position_limit:
            qty = min(10, position_limit - position)
            orders.append(Order(product, best_ask, qty))
        
        return orders

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

        history = {}
        if state.traderData:
            history = jsonpickle.decode(state.traderData)

        time = state.timestamp
        positions = state.position
        hydrogel_orders = []
        velvetfruit_orders = []
        velvet_voucher_orders = {4000 : [], 4500 : [], 5000 : [], 5100 : [], 5200 : [], 5300 : [], 5400 : [], 5500 : [], 6000 : [], 6500 : []}

        # Market making for main products
        hydrogel_orders = self.mean_reversion_strategy(state, "HYDROGEL_PACK", history, position_limit = 200)
        # velvetfruit_orders = self.mean_reversion_strategy(state, "VELVETFRUIT_EXTRACT", history)

        # For vouchers, perhaps similar, but let's skip for now or implement simply
        # For simplicity, not implementing for vouchers yet

        result = {"HYDROGEL_PACK": hydrogel_orders, "VELVETFRUIT_EXTRACT": velvetfruit_orders, 
                  "VEV_4000" : velvet_voucher_orders[4000], "VEV_4500" : velvet_voucher_orders[4500], "VEV_5000" : velvet_voucher_orders[5000], 
                  "VEV_5100" : velvet_voucher_orders[5100], "VEV_5200" : velvet_voucher_orders[5200], "VEV_5300" : velvet_voucher_orders[5300], 
                  "VEV_5400" : velvet_voucher_orders[5400], "VEV_5500" : velvet_voucher_orders[5500], "VEV_6000" : velvet_voucher_orders[6000],
                    "VEV_6500" : velvet_voucher_orders[6500]}
        traderData = jsonpickle.encode(history)
        conversions = 0
        return result, conversions, traderData