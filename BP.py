from datetime import datetime
from sklearn import preprocessing
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import matplotlib.pyplot as plt

try:
    from sklearn import svm
except:
    print('请安装scikit-learn库和带mkl的numpy')
    sys.exit(-1)

TRAINING_LEN = 300
TRAININGSET_LEN = 15
CONSECUTIVE = 5


def init(context):
    context.future = 'CU88'
    context.fired = False
    context.target_nums = 3
    subscribe(context.future)


# before_trading此函数会在每天策略交易开始前被调用，当天只会被调用一次
def before_trading(context):
    try:
        # 每天训练SVM模型
        # 　数据采用前 TRAINING_LEN+TRAININGSET_LEN 个分钟的收盘价
        data_traing = history_bars(context.future, TRAINING_LEN + TRAININGSET_LEN + CONSECUTIVE + 1, '1m', ['datetime', 'close'],
                                   include_now=False)['close']
        x_all = []
        y_all = []
        for i in range(TRAININGSET_LEN, TRAINING_LEN + TRAININGSET_LEN):
            features = [data_traing[j] for j in range(i - TRAININGSET_LEN, i)]
            x_all.append(features)
            # 判断是否连续增长
            temp_data = [data_traing[k] for k in range(i-1, i+CONSECUTIVE-1)]
            flag_increase = 1
            flag_decrease = 1
            for k in range(0, CONSECUTIVE-1):
                if temp_data[k+1]-temp_data[k] < 0:
                    flag_increase = 0
                elif temp_data[k+1]-temp_data[k] > 0:
                    flag_decrease = 0
            if flag_increase == 1:  # 连续涨
                label = 2
            elif flag_decrease == 1:  # 连续跌
                label = 1
            else:
                label = 0
            y_all.append(label)
        x_train = x_all[: -1]
        x_train = np.array(x_train)
        min_max_scaler = preprocessing.MinMaxScaler()
        x_train = min_max_scaler.fit_transform(x_train)

        y_train = y_all[: -1]
        # print(y_train)
        # context.model = svm.SVC(C=1.0, kernel='rbf', degree=3, gamma='auto', coef0=0.0, shrinking=True,
        #                         probability=False,
        #                         tol=0.001, cache_size=200, verbose=False, max_iter=-1,
        #                         decision_function_shape='ovr', random_state=None)
        # context.model.fit(x_train, y_train)
        context.model = MLPClassifier(hidden_layer_sizes=(100, 50), max_iter=500)
        context.model.fit(x_train, y_train)
        # print('训练完成!')
        context.fired = True
        subscribe(context.future)
    except ValueError as e:
        print("训练未完成！")
        print(e)
        print(context.now)


# 你选择的期货数据更新将会触发此段逻辑，例如日线或分钟线更新
def handle_bar(context, bar_dict):
    if context.fired == True:
        try:
            # logger.info(history_bars(context.future, 100, '1m', ['datetime','open'],include_now=True))
            data_test = history_bars(context.future, TRAININGSET_LEN, '1m', ['datetime', 'close'], include_now=False)[
                'close']
            x_test = [[data_test[j] for j in range(0, TRAININGSET_LEN)]]
            x_test = np.array(x_test)
            min_max_scaler = preprocessing.MinMaxScaler()
            x_test = min_max_scaler.fit_transform(x_test)
            y_test_pred = context.model.predict(x_test)

            position = get_position(context.future, context)

            if len(context.future_account.positions.keys()) > 0:
                # 记得try catch包裹
                try:
                    # 如果当前价格突破上轨，且当前仓位为负
                    if y_test_pred == 2 and position['side'] == 'SELL':
                        if position['quantity'] > 0:
                            logger.info("平空，买开")
                            # 平空、买开
                            buy_close(context.future, position['quantity'])
                            buy_open(context.future, position['quantity'])
                    # 如果当前价格突破下轨，且当前仓位为正
                    if y_test_pred == 1 and position['side'] == 'BUY':
                        if position['quantity'] > 0:
                            # 平多、卖开
                            logger.info("平多，卖开")
                            sell_close(context.future, position['quantity'])
                            sell_open(context.future, position['quantity'])
                except Exception as e:
                    logger.error('[信号出现]下单异常:' + str(e))
            # 否则，则根据初始化中设置的context.target_num数量进行买卖
            else:
                # 突破上轨，买开
                if y_test_pred == 2:
                    logger.info("买开")
                    buy_open(context.future, context.target_nums)
                # 突破下轨，卖开
                if y_test_pred == 1:
                    logger.info("卖开")
                    sell_open(context.future, context.target_nums)


        except ValueError as e:
            print(e)
            print(context.now)
    else:
        pass


# 单品种持仓状况
def get_position(future, context):
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

