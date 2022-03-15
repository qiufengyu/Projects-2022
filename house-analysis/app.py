import copy

import jieba
import sqlite3
import numpy as np
import pandas as pd
from tqdm import tqdm
import pickle
from flask import Flask, render_template, jsonify, request
import xgboost as xgb
from model import load_meta

app = Flask(__name__)
app.config.from_object('config')

# 加载特征数据字典
features = load_meta('meta/features.pkl')
# 需要转化为 categories，即标签值的列
categorized_features = [
    '产权年限', '产权性质', '唯一住房', '房屋朝向', '房本年限', '所在楼层', '所属区域', '所属小区', '物业类型', '装修程度', '配套电梯'
]
m_chanquan_xingzhi = load_meta('meta/产权性质.pkl')
m_wuye_leixing = load_meta('meta/物业类型.pkl')
m_chanquan_nianxian = load_meta('meta/产权年限.pkl')
m_fangben_nianxian = load_meta('meta/房本年限.pkl')
m_weiyi_zhufang = load_meta('meta/唯一住房.pkl')
m_suozai_louceng = load_meta('meta/所在楼层.pkl')
m_zhuangxiu_chengdu = load_meta('meta/装修程度.pkl')
m_fangwu_chaoxiang = load_meta('meta/房屋朝向.pkl')
m_peitao_dianti = load_meta('meta/配套电梯.pkl')
m_suoshu_xiaoqu = load_meta('meta/所属小区.pkl')
m_suoshu_quyu = load_meta('meta/所属区域.pkl')

login_name = None

# --------------------- html render ---------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/house_overview')
def house_overview():
    return render_template('house_overview.html')

@app.route('/basic_analysis')
def basic_analysis():
    return render_template('basic_analysis.html')

@app.route('/influence_analysis')
def influence_analysis():
    return render_template('influence_analysis.html')

@app.route('/house_predict')
def house_predict():
    return render_template('house_predict.html')


# ------------------ ajax restful api -------------------
@app.route('/check_login')
def check_login():
    """判断用户是否登录"""
    return jsonify({'username': login_name, 'login': login_name is not None})


@app.route('/register/<name>/<password>')
def register(name, password):
    conn = sqlite3.connect('user_info.db')
    cursor = conn.cursor()

    check_sql = "SELECT * FROM sqlite_master where type='table' and name='user'"
    cursor.execute(check_sql)
    results = cursor.fetchall()
    # 数据库表不存在
    if len(results) == 0:
        # 创建数据库表
        sql = """
                CREATE TABLE user(
                    name CHAR(256), 
                    password CHAR(256)
                );
                """
        cursor.execute(sql)
        conn.commit()
        print('创建数据库表成功！')

    sql = "INSERT INTO user (name, password) VALUES (?,?);"
    cursor.executemany(sql, [(name, password)])
    conn.commit()
    return jsonify({'info': '用户注册成功！', 'status': 'ok'})


@app.route('/login/<name>/<password>')
def login(name, password):
    global login_name
    conn = sqlite3.connect('user_info.db')
    cursor = conn.cursor()

    check_sql = "SELECT * FROM sqlite_master where type='table' and name='user'"
    cursor.execute(check_sql)
    results = cursor.fetchall()
    # 数据库表不存在
    if len(results) == 0:
        # 创建数据库表
        sql = """
                CREATE TABLE user(
                    name CHAR(256), 
                    password CHAR(256)
                );
                """
        cursor.execute(sql)
        conn.commit()
        print('创建数据库表成功！')

    sql = "select * from user where name='{}' and password='{}'".format(name, password)
    cursor.execute(sql)
    results = cursor.fetchall()

    login_name = name
    if len(results) > 0:
        print(results)
        return jsonify({'info': name + '用户登录成功！', 'status': 'ok'})
    else:
        return jsonify({'info': '当前用户不存在！', 'status': 'error'})


@app.route('/xiaoqu_name_wordcloud')
def xiaoqu_name_wordcloud():
    """小区名称的词云分析"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()
    sql = 'select 所属小区 from HouseInfo where 爬虫 = 1'
    cursor.execute(sql)
    datas = cursor.fetchall()

    word_count = {}
    for name in tqdm(datas):
        words = jieba.cut(name[0])
        for word in words:
            if word in {'(', ')', '（', '）', '组团'}:
                continue
            if len(word) < 2:
                continue
            if word in word_count:
                word_count[word] += 1
            else:
                word_count[word] = 1

    wordclout_dict = sorted(word_count.items(), key=lambda d: d[1], reverse=True)
    wordclout_dict = [{"name": k[0], "value": k[1]} for k in wordclout_dict if k[1] > 1]
    return jsonify({'词云数据': wordclout_dict})


@app.route('/query_key_count/<key>')
def query_key_count(key):
    """获取房屋属性的个数分布情况"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()
    sql = 'select {} from HouseInfo where 爬虫 = 1'.format(key)
    cursor.execute(sql)
    datas = cursor.fetchall()

    key_counts = {}
    for data in datas:
        if data not in key_counts:
            key_counts[data] = 0
        key_counts[data] += 1

    keys = list(key_counts.keys())
    counts = [key_counts[c] for c in keys]
    return jsonify({'keys': keys, 'counts': counts})


@app.route('/area_house_count_mean_house_price')
def area_house_count_mean_house_price():
    """不同地区的平均房价情况"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()
    sql = 'select 所属区域, 总价 from HouseInfo where 爬虫 = 1'
    cursor.execute(sql)
    datas = cursor.fetchall()

    loc_price = {}
    for data in datas:
        loc, price = data
        loc = loc.split('－')[0]

        if loc not in loc_price:
            loc_price[loc] = []

        loc_price[loc].append(price)

    loc_counts = {}
    loc_mean_price = {}
    for loc in loc_price:
        loc_counts[loc] = len(loc_price[loc])
        loc_mean_price[loc] = np.mean(loc_price[loc])

    locations = list(loc_price.keys())
    results = {
        '地区': locations,
        '地区房子数量': [loc_counts[loc] for loc in locations],
        '地区平均房价': [loc_mean_price[loc] for loc in locations],
        '地区房价数据': [loc_price[loc] for loc in locations]
    }
    return jsonify(results)



@app.route('/fetch_house_area_and_price')
def fetch_house_area_and_price():
    """获取房屋面积和价格数据"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()

    sql = 'select 总价, 建筑面积, 房屋户型_室, 房屋户型_厅, 房屋户型_卫 from HouseInfo where 爬虫 = 1'
    cursor.execute(sql)
    datas = cursor.fetchall()

    results = {'面积': [], '每间房间的面积': [], '总价': []}
    for data in datas:
        zongjia, mianji, huxin_s, huxin_t, huxin_w = data
        # 房间数
        fangjian_count = huxin_s + huxin_t + huxin_w
        # 每间房间的面积
        per_fanjian = mianji / fangjian_count
        results['面积'].append(mianji)
        results['每间房间的面积'].append(per_fanjian)
        results['总价'].append(zongjia)

    return jsonify(results)


@app.route('/fetch_influence_analysis_datas/<column_key>')
def fetch_influence_analysis_datas(column_key):
    """获取影响房价因素分析的数据"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()

    sql = 'select {}, 总价 from HouseInfo where 爬虫 = 1'.format(column_key)
    cursor.execute(sql)
    datas = cursor.fetchall()

    results = {}
    for data in datas:
        key, value = data
        if key == '':
            continue

        if '房屋户型' in column_key:
            key = str(key) + column_key.split('_')[1]
        if key not in results:
            results[key] = [value]
        else:
            results[key].append(value)

    counts = []
    for key in results:
        counts.append(len(results[key]))
        results[key] = np.mean(results[key])

    results = list(zip(list(results.keys()), counts, list(results.values())))
    results = sorted(results, key=lambda k: k[2], reverse=False)
    zhibiao = [r[0] for r in results]
    counts = [r[1] for r in results]
    junjia = [r[2] for r in results]

    return jsonify({'指标': zhibiao, '个数': counts, '均价': junjia})


@app.route('/get_all_unique_values/<key>')
def get_all_unique_values(key):
    """获取当前指标所有的唯一值"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()
    sql = 'select distinct {} from HouseInfo where 爬虫 = 1'.format(key)
    cursor.execute(sql)
    datas = cursor.fetchall()

    key_count = {}
    for data in datas:
        sql = "select count(*) from HouseInfo where {}='{}' and 爬虫 = 1".format(key, data[0])
        cursor.execute(sql)
        count = cursor.fetchall()[0][0]
        key_count[data[0]] = count

    key_count = sorted(key_count.items(), key=lambda d: d[0])

    return jsonify(key_count)


model = xgb.Booster(model_file='house_price.model')


@app.route('/history_and_predict_price')
def history_and_predict_price():
    """当前小区的历史价格，以及针对当前配置预测的价格"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()
    quyu = request.args.get('所属区域')
    xiaoqu = request.args.get('所属小区')
    sql = "select 总价, 建筑面积 from HouseInfo where 所属小区='{}' and 爬虫 = 1".format(xiaoqu)

    cursor.execute(sql)
    datas = cursor.fetchall()

    results = {'面积': [], '总价': []}
    for data in datas:
        zongjia, mianji = data
        results['面积'].append(mianji)
        results['总价'].append(zongjia)
    niandai = request.args.get('建造年代')
    chaoxiang = request.args.get('房屋朝向')
    fangwuleix = request.args.get('物业类型')
    suozailouceng = request.args.get('所在楼层')
    zhuangxiuchengdu = request.args.get('装修程度')
    changquannianxian = request.args.get('产权年限')
    dianti = request.args.get('配套电梯')
    fangbennianxian = request.args.get('房本年限')
    changquanxingzhi = request.args.get('产权性质')
    weiyizhufang = request.args.get('唯一住房')
    shishu = request.args.get('房屋户型_室')
    tingshu = request.args.get('房屋户型_厅')
    weishu = request.args.get('房屋户型_卫')
    zonglouceng = request.args.get('总楼层')

    m_chanquan_xingzhi = load_meta('meta/产权性质.pkl')
    m_wuye_leixing = load_meta('meta/物业类型.pkl')
    m_chanquan_nianxian = load_meta('meta/产权年限.pkl')
    m_fangben_nianxian = load_meta('meta/房本年限.pkl')
    m_weiyi_zhufang = load_meta('meta/唯一住房.pkl')
    m_suozai_louceng = load_meta('meta/所在楼层.pkl')
    m_zhuangxiu_chengdu = load_meta('meta/装修程度.pkl')
    m_fangwu_chaoxiang = load_meta('meta/房屋朝向.pkl')
    m_peitao_dianti = load_meta('meta/配套电梯.pkl')
    m_suoshu_xiaoqu = load_meta('meta/所属小区.pkl')
    m_suoshu_quyu = load_meta('meta/所属区域.pkl')

    feature = {
        '建筑面积': float(request.args.get('建筑面积')),
        '房屋朝向': m_fangwu_chaoxiang[chaoxiang],
        '物业类型': m_wuye_leixing[fangwuleix],
        '所在楼层': m_suozai_louceng[suozailouceng],
        '装修程度': m_zhuangxiu_chengdu[zhuangxiuchengdu],
        '产权年限': m_chanquan_nianxian[changquannianxian],
        '配套电梯': m_peitao_dianti[dianti],
        '房本年限': m_fangben_nianxian[fangbennianxian],
        '产权性质': m_chanquan_xingzhi[changquanxingzhi],
        '唯一住房': m_weiyi_zhufang[weiyizhufang],
        '所属小区': m_suoshu_xiaoqu[xiaoqu],
        '所属区域': m_suoshu_quyu[quyu],
        '房屋户型_室': int(shishu),
        '房屋户型_厅': int(tingshu),
        '房屋户型_卫': int(weishu),
        '总楼层': int(zonglouceng),
        '发布时间': 0, # 认为今天发布
        '建造年代': int(niandai)
    }
    df_columns = copy.deepcopy(features)
    test_x = pd.DataFrame([[feature[f] for f in df_columns]], columns=df_columns)
    for cf in categorized_features:
        test_x[cf] = test_x[cf].astype('category')
    dtest = xgb.DMatrix(test_x, feature_names=df_columns, enable_categorical=True)
    predict_price = model.predict(dtest)[0]
    predict_price = np.expm1(predict_price)
    results['predict_price'] = str(predict_price)
    return jsonify(results)


if __name__ == "__main__":
    app.run(host='127.0.0.1')
