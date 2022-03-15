from __future__ import annotations

import copy
import datetime
import pickle
import sqlite3
import numpy as np
import pandas as pd
from pandas import DataFrame
from typing import (Iterator)

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

import xgboost as xgb

def load_meta(file):
    with open(file, 'rb') as f:
        return pickle.load(f)

def rmse(y_true, y_pred):
    return np.sqrt(mean_squared_error(y_true, y_pred))

class DataModel():
    def __init__(self):
        # 从数据库加载数据
        conn = sqlite3.connect('all_house_infos.db')
        sql = "select * from HouseInfo where 爬虫 = 1"
        df = pd.read_sql(sql=sql, con=conn)
        # 去掉一些列
        del df['爬虫']
        del df['标识']
        df.sample(frac=1).reset_index(drop=True)
        self.df = df
        # 构建标签类的字典映射
        self.chanquan_xingzhi = self.make_category('产权性质')
        self.wuye_leixing = self.make_category('物业类型')
        self.chanquan_nianxian = self.make_category('产权年限')
        self.fangben_nianxian = self.make_category('房本年限')
        self.weiyi_zhufang = self.make_category('唯一住房')
        self.suozai_louceng = self.make_category('所在楼层')
        self.zhuangxiu_chengdu = self.make_category('装修程度')
        self.fangwu_chaoxiang = self.make_category('房屋朝向')
        self.peitao_dianti = self.make_category('配套电梯')
        self.suoshu_xiaoqu = self.make_category('所属小区')
        self.suoshu_quyu = self.make_category('所属区域')
        self.df['发布时间'] = self.df['发布时间'].map(lambda s: (datetime.datetime.now() - datetime.datetime.strptime(s, '%Y-%m-%d')).days)

    def get_df(self) -> DataFrame | Iterator[DataFrame]:
        return self.df

    def make_category(self, col: str):
        s = set(self.df[col])
        index = 0
        m = {}
        for i in s:
            m[i] = str(index)
            index += 1
        print(col, '映射关系：', m)
        self.__save_map(m, f'meta/{col}.pkl')
        self.df[col] = self.df[col].map(m).astype('category')
        return m

    def __save_map(self, obj, file_name):
        with open(file_name, 'wb') as f:
            pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

    def train_and_test(self):
        # 拷贝一份源数据
        all_x = copy.deepcopy(self.df)
        # 预测值
        all_y = all_x['总价'].map(np.log1p).values
        # 把要预测的数据删除
        del all_x['总价']
        # 总价可以根据单价和面积直接计算，所以单价也从训练特征中删除
        del all_x['单价']
        del all_x['链接']
        del all_x['参考首付']
        df_columns = all_x.columns.values.tolist()
        self.__save_map(df_columns, 'meta/features.pkl')
        # 划分训练集和测试集
        train_X, valid_X, train_Y, valid_Y = train_test_split(all_x, all_y, test_size=0.1, random_state=42)
        # 训练模型
        print(all_x.info())
        # 首先使用 cross validation方式选择最佳的 boost 轮次
        print('---> 使用 cross validation 方式选择 best_num_boost_round')
        dtrain = xgb.DMatrix(train_X, label=train_Y, feature_names=df_columns, enable_categorical=True)
        xgb_params = {
            'learning_rate': 0.005,
            'max_depth': 7,
            'min_child_weight': 0.5,
            'eval_metric': 'rmse',
            'objective': 'reg:squarederror',
            'nthread': -1,
            'verbosity': 1,
            'booster': 'gbtree'
        }
        cv_result = xgb.cv(dict(xgb_params),
                           dtrain,
                           num_boost_round=10000,
                           early_stopping_rounds=100,
                           verbose_eval=100,
                           show_stdv=False,
                           )
        best_num_boost_rounds = len(cv_result)
        mean_train_logloss = cv_result.loc[best_num_boost_rounds - 11: best_num_boost_rounds - 1,
                             'train-rmse-mean'].mean()
        mean_test_logloss = cv_result.loc[best_num_boost_rounds - 11: best_num_boost_rounds - 1,
                            'test-rmse-mean'].mean()
        print('best_num_boost_rounds = {}'.format(best_num_boost_rounds))
        print('mean_train_rmse = {:.7f} , mean_valid_rmse = {:.7f}\n'.format(mean_train_logloss, mean_test_logloss))
        # 在整个训练集上训练
        print('---> 根据选择的最佳 best_num_boost_rounds 在整个训练集上训练...')
        model = xgb.train(dict(xgb_params), dtrain, num_boost_round=best_num_boost_rounds)
        # 显示每个特征的权重
        feature_importance = model.get_fscore()
        feature_importance = sorted(feature_importance.items(), key=lambda d: d[1], reverse=True)
        print(feature_importance)
        # 在测试集上测试
        dvalid = xgb.DMatrix(valid_X, feature_names=df_columns, enable_categorical=True)
        predict_valid = model.predict(dvalid)
        print('决策树模型在验证集上的均方误差 RMSE 为：', rmse(valid_Y, predict_valid))
        # 保存模型
        model.save_model('house_price.model')



if __name__ == '__main__':
    model = DataModel()
    model.train_and_test()
