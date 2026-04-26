from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import jsonpickle
import numpy as np

class Trader:

    def bid(self):
        return 500

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

        if state.traderData:
            _____ = jsonpickle.decode(state.traderData) 

        time = state.timestamp
        positions = state.position
        hydrogel_orders = []
        velvetfruit_orders = []
        velvet_voucher_orders = {4000 : [], 4500 : [], 5000 : [], 5100 : [], 5200 : [], 5300 : [], 5400 : [], 5500 : [], 6000 : [], 6500 : []}


        result = {"HYDROGEL_PACK ": hydrogel_orders, "VELVETFRUIT_EXTRACT": velvetfruit_orders, 
                  "VEV_4000" : velvet_voucher_orders[4000], "VEV_4500" : velvet_voucher_orders[4500], "VEV_5000" : velvet_voucher_orders[5000], 
                  "VEV_5100" : velvet_voucher_orders[5100], "VEV_5200" : velvet_voucher_orders[5200], "VEV_5300" : velvet_voucher_orders[5300], 
                  "VEV_5400" : velvet_voucher_orders[5400], "VEV_5500" : velvet_voucher_orders[5500], "VEV_6000" : velvet_voucher_orders[6000],
                    "VEV_6500" : velvet_voucher_orders[6500]}
        traderData = jsonpickle.encode()
        conversions = 0
        return result, conversions, traderData