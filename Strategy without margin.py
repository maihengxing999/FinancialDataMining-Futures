from datetime import datetime
from sklearn import preprocessing
import numpy as np

# MULTIPLIER = 5  # 铜、铅、锌、铝的交易单位为5，银为15，金为1000


def init(context):
    context.future_list = ['CU']
    context.fired = False
    subscribe_all(context)


# before_trading此函数会在每天策略交易开始前被调用，当天只会被调用一次
def before_trading(context):
    context.fired = True
    context.flag = True
    subscribe_all(context)


# 你选择的期货数据更新将会触发此段逻辑，例如日线或分钟线更新
def handle_bar(context, bar_dict):
    try:
        if context.fired == True:
            context.fired = False
        # 主力换月
        if context.flag == True:
            change_dominate_future(context)
            context.flag = False
        # 换月完成之后、现持仓与目标持仓标的一致
        for future_M in context.target_list:
            # 设置交易单位 context.multiplier，方便计算交易量
            # 铜、铅、锌、铝的交易单位为5，银为15，金为1000
            if future_M[:-4] in ['CU', 'ZN', 'AL', 'PB']:
                context.multiplier = 5
            elif future_M[:-4] == 'AG':
                context.multiplier = 15
            elif future_M[:-4] == 'AU':
                context.multiplier = 1000
            # 判断前CONSECUTIVE分钟是否为连续上涨或连续下跌
            data = history_bars(future_M, 2, '1m', ['datetime', 'close'], include_now=False)['close']
            if data[0] < data[1]:
                flag = 1 # 增
            elif data[0] > data[1]:
                flag = 0 # 减
            else:
                flag = -1 # 涨停、跌停
            position = get_position(future_M, context)




            # 如果连续上涨则卖开
            # 如果连续下跌则买开
            if len(context.future_account.positions.keys()) > 0:
                # 记得try catch包裹
                try:
                    # 如果连续下跌，且当前仓位为负
                    if flag == 0 and position['side'] == 'SELL':
                        if position['quantity'] > 0:
                            # 平空、买开
                            buy_close(future_M, position['quantity'])
                            # 计算最大买开量
                            context.target_nums = int(context.future_account.cash / (context.multiplier * bar_dict[future_M].open))
                            buy_open(future_M, context.target_nums)
                            logger.info(future_M + " 平空 " + str(position['quantity']) + " 手 ，买开 " + str(context.target_nums) + " 手")

                    # 如果连续上涨，且当前仓位为正
                    elif flag == 1 and position['side'] == 'BUY':
                        if position['quantity'] > 0:
                            # 平多、卖开
                            sell_close(future_M, position['quantity'])
                            # 计算最大卖开量
                            context.target_nums = int(context.future_account.cash / (context.multiplier * bar_dict[future_M].open))
                            sell_open(future_M, context.target_nums)
                            logger.info(future_M + " 平多 " + str(position['quantity']) + " 手 ，卖开 " + str(context.target_nums) + " 手")
                except Exception as e:
                    logger.error('[信号出现]下单异常:' + str(e))
            # 否则，则根据初始化中设置的context.target_nums数量进行买卖
            else:
                # 连续下跌，买开
                if flag == 0:
                    # 计算最大买开量
                    context.target_nums = int(context.future_account.cash / (context.multiplier * bar_dict[future_M].open))
                    buy_open(future_M, context.target_nums)
                    logger.info(future_M + " 买开 " + str(context.target_nums) + " 手")

                # 连续上涨，卖开
                elif flag == 1:
                    # 计算最大卖开量
                    context.target_nums = int(context.future_account.cash / (context.multiplier * bar_dict[future_M].open))
                    sell_open(future_M, context.target_nums)
                    logger.info(future_M + " 卖开 " + str(context.target_nums) + " 手")
        else:
            pass
    except Exception as e:
        print(e)
        print(context.now)


# 主力换月
def change_dominate_future(context):
    try:
        # 遍历当前持仓的期货
        for future in list(context.future_account.positions.keys()):
            # 对于一个实际可交易的期货合约，形如'CU1503'，代表铜2015年3月的期货
            # future[:-4]就表示仅保留前两位，获得期货的品类
            future_sige = future[:-4]
            # ！！！使用平台提供的get_dominant_future方法，传入期货种类代码，如'CU'，
            # 返回当前时刻该品种期货的主力合约
            new_dominate_future = get_dominant_future(future_sige)
            # 如果主力合约没有发生更换，则不操作
            if future == new_dominate_future:
                pass
            # 否则
            else:
                logger.info('[移仓换月]开始')
                # 调用get_postion方法，获得仓位
                position = get_position(future, context)
                # 根据当前仓位信息，选择买卖的操作
                # 如果当前是正仓位，那么就把旧的期货合约平多(sell_close)，
                #                   然后买开 (buy_open)相同数量新的期货合约
                # 如果当前是负仓位，那么就把就旧的期货合约平空(buy_close),
                #                   然后卖开(sell_open)相同数量新的期货合约
                close_action = sell_close if position['side'] == 'BUY' else buy_close
                open_action = buy_open if position['side'] == 'BUY' else sell_open
                # ！具体进行交易的代码块一定要用try,catch进行包裹，防止意外出错导致代码终止运行
                try:
                    close_order = close_action(future, position['quantity'])
                    open_order = open_action(new_dominate_future, position['quantity'])

                except Exception as e:
                    logger.error('[移仓换月]平仓失败:' + str(e))
                logger.info('[移仓换月]结束')
    except Exception as e:
        print(str(e))

# 单品种持仓状况
def get_position(future, context):
    try:
        # contxtx.future_account为context的内置属性，可以获取期货资金账户信息
        # 根据期货代码获取对该期货的持仓情况position
        position = context.future_account.positions[future]

        # 若当前有持仓
        if len(context.future_account.positions.keys()) > 0:
            # 如果当前卖出的数量>0，则为负仓位，设置变量position_side为'SELL'，否则为'BUY'
            position_side = 'SELL' if position.sell_quantity > 0 else 'BUY'
            # 获取仓位的数量
            position_quantity = position.sell_quantity if position_side == 'SELL' else position.buy_quantity

            # 返回结果字典，'side'对应仓位的正负，'quantity'对应仓位的数量
            return {'side': position_side, 'quantity': position_quantity}

        # 否则返回空
        else:
            return {}
    except Exception as e:
        print(str(e))


# 订阅行情
def subscribe_all(context):
    try:
        context.target_list = [get_dominant_future(i) for i in context.future_list]
        # print(context.target_list)
        for future in context.target_list:
            # print(future)
            subscribe(future)
    except Exception as e:
        print(str(e))