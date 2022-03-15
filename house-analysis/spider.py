import time
from sqlite3 import IntegrityError


import copy
import random
import sqlite3
import requests
from bs4 import BeautifulSoup


class AnjukeSpider():
    def __init__(self):
        self.BASE_COMMUNITY_URL = 'https://hf.anjuke.com/community/p{}'
        self.BASE_HOUSE_URL = 'https://hf.anjuke.com/community/props/sale/{}/p{}/#filtersort'
        self.HEADERS = {
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'max-age=0',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'cookie': 'aQQ_ajkguid=6695A670-192B-C8ED-DC08-6CE6074BC354; wmda_new_uuid=1; wmda_uuid=be447124ff9de93693b3d339a16ce8d6; wmda_visited_projects=;6289197098934; id58=CrIIEGIQ6TcRz/1TPnK7Ag==; ctid=33; sessid=6C83C7AC-16FE-4141-A394-7419392205BB; fzq_h=c66e4b9268feae7576c15d40ca74751c_1645551906749_4c8f66f0e4ae4c87a8c281cfb61cc619_1700319457; obtain_by=2; twe=2; fzq_js_anjuke_ershoufang_pc=03e04b07ec2355160802aab5ad4c118d_1645586297664_23; xxzl_cid=bab48784c3fe4bdda782a47a6bd19ea8; xzuid=442877c5-b026-47ff-8563-4f6b7c573368; ajk-appVersion=',
            'referer': 'https://hf.anjuke.com/sale/',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.55 Safari/537.36'
        }
        self.db_conn = sqlite3.connect('all_house_infos.db')
        self.house_info = {
            '产权性质': '未知',
            '物业类型': '未知',
            '产权年限': '未知',
            '房本年限': '未知',
            '唯一住房': '未知',
            '参考首付': '未知',
            '发布时间': '未知',
            '总价': 0,
            '单价': 0,
            '房屋户型_室': 0,
            '房屋户型_厅': 0,
            '房屋户型_卫': 0,
            '所在楼层': '未知',
            '总楼层': 0,
            '建筑面积': 0,
            '装修程度': '未知',
            '房屋朝向': '未知',
            '建造年代': '未知',
            '配套电梯': '无',
            '所属小区': '未知',
            '所属区域': '未知'
        }

    def get_house_by_community(self):
        cursor = self.db_conn.cursor()
        GET_COMMUNITIES = '''select 社区链接, 社区名称, 社区标记 from Community where 爬虫 = 0'''
        UPDATE_COMMUNITY = '''update Community set 爬虫 = 1 where 社区标记 = ?'''
        INSERT_HOUSE = '''INSERT INTO HouseInfo(链接, 爬虫, 标识) VALUES (?, 0, ?)'''
        headers = copy.deepcopy(self.HEADERS)
        communities = cursor.execute(GET_COMMUNITIES).fetchall()
        for community in communities:
            link, name, cid = community[0], community[1], community[2]
            referer = 'https://hf.anjuke.com/community/view/{}'.format(cid)
            headers['referer'] = referer
            for page in range(1, 10):
                url = self.BASE_HOUSE_URL.format(cid, page)
                print('获取', name, '的房价信息：', url)
                response = requests.get(url, headers=headers)
                response.encoding = 'utf8'
                soup = BeautifulSoup(response.text, 'lxml')
                houses = soup.find_all('li', 'm-rent-house')
                if not houses:
                    break
                for house in houses:
                    detail = house.find('div', 'details')
                    info = detail.find('span', 'title-info')
                    house_link = info['href']
                    url_suffix = house_link.split('/')[-1]
                    hid = url_suffix.split('?')[0]
                    print('获取房源：', house_link)
                    try:
                        cursor.execute(INSERT_HOUSE, (house_link, hid))
                    except IntegrityError as e:
                        print('重复的 id， 跳过：', hid, e)
                self.db_conn.commit()
                time.sleep(random.random() * 10)
                headers['referer'] = url
            cursor.execute(UPDATE_COMMUNITY, (cid,))
            self.db_conn.commit()
            time.sleep(random.random() * 10 + 25)


    def get_house_detail(self):
        cursor = self.db_conn.cursor()
        GET_HOUSE = '''select 链接, 标识 from HouseInfo where 爬虫 = 0'''
        INSERT_HOUSE_DETAIL = '''
                               UPDATE HouseInfo set 产权性质=?, 物业类型=?, 产权年限=?, 房本年限=?, 唯一住房=?, 参考首付=?, 发布时间=?, 总价=?, 单价=?, 
                                                    所在楼层=?, 建筑面积=?, 装修程度=?, 房屋朝向=?, 建造年代=?, 配套电梯=?, 所属小区=?,
                                                    所属区域=?, 房屋户型_室=?, 房屋户型_厅=?, 房屋户型_卫=?, 总楼层=?, 爬虫=1 where 标识=?
        '''
        all_houses = cursor.execute(GET_HOUSE).fetchall()
        random.shuffle(all_houses)
        headers = copy.deepcopy(self.HEADERS)
        failed_count = 0
        for house in all_houses:
            house_link, hid = house[0], house[1]
            print(hid, house_link)
            house_info = copy.deepcopy(self.house_info)
            headers['referer'] = house_link
            response = requests.get(house_link, headers=headers)
            response.encoding = 'utf8'
            soup = BeautifulSoup(response.text, 'lxml')
            house_info_main = soup.find('tbody', 'houseInfo-main')
            if not house_info_main:
                failed_count += 1
                if failed_count == 5:
                    print('请在浏览器中访问安居客网站，以通过人机验证')
                    exit(1)
                continue
            tds = house_info_main.find_all('td')
            if not tds:
                print('当前房源已失效，跳过')
                cursor.execute('DELETE FROM HouseInfo where 标识 = ?', (hid))
                failed_count += 1
                if failed_count == 5:
                    print('请在浏览器中访问安居客网站，以通过人机验证')
                    exit(1)
                continue
            failed_count = 0
            for td in tds:
                td_text = td.text.split(' ')
                if '产权性质' in td_text[0]:
                    house_info['产权性质'] = td_text[0].replace('产权性质', '')
                if '产权年限' in td_text[0]:
                    house_info['产权年限'] = td_text[0].replace('产权年限', '')
                if '发布时间' in td_text[0]:
                    house_info['发布时间'] = td_text[0].replace('发布时间', '')
                if '唯一住房' in td_text[0]:
                    house_info['唯一住房'] = td_text[0].replace('唯一住房', '')
                if '物业类型' in td_text[0]:
                    house_info['物业类型'] = td_text[0].replace('物业类型', '')
                if '房本年限' in td_text[0]:
                    house_info['房本年限'] = td_text[0].replace('房本年限', '')
                if '参考预算' in td_text[0]:
                    yusuan = td_text[0].replace('参考预算', '')
                    house_info['参考首付'] = yusuan[2:].split('，')[0][:-1]
            price_num = soup.find('span', 'maininfo-price-num')
            house_info['总价'] = float(price_num.text.strip())
            avgprice_price = soup.find('div','maininfo-avgprice-price')
            house_info['单价'] = float(avgprice_price.text.strip().split('元')[0])
            huxing_louceng = soup.select('div.maininfo-model-item.maininfo-model-item-1')[0]
            huxing = huxing_louceng.find('div', 'maininfo-model-strong')
            shi = huxing.find('span', string='室')
            house_info['房屋户型_室'] = int(shi.previous_element.text.strip())
            ting = huxing.find('span', string='厅')
            house_info['房屋户型_厅'] = int(ting.previous_element.text.strip())
            wei = huxing.find('span', string='卫')
            house_info['房屋户型_卫'] = int(wei.previous_element.text.strip())
            louceng = huxing_louceng.find('div', 'maininfo-model-weak').text.strip()
            if '(' in louceng:
                house_info['所在楼层'] = louceng.split('(')[0]
                house_info['总楼层'] = int(louceng.split('(')[1][1:-2])
            else:
                house_info['所在楼层'] = '低层'
                house_info['总楼层'] = int(louceng[1:-1])
            daxiao = soup.select('div.maininfo-model-item.maininfo-model-item-2')[0]
            house_info['建筑面积'] = float(daxiao.find('i', 'maininfo-model-strong-num').text)
            house_info['装修程度'] = daxiao.find('div', 'maininfo-model-weak').text
            chaoxiang = soup.select('div.maininfo-model-item.maininfo-model-item-3')[0]
            house_info['房屋朝向'] = chaoxiang.find('i', 'maininfo-model-strong-text').text
            house_info['建造年代'] = int(chaoxiang.find('div', 'maininfo-model-weak').text.split('/')[0][:-3])
            xiaoqu_quyu = soup.find_all('div', 'maininfo-community-item')
            xiaoqu, quyu = xiaoqu_quyu[0], xiaoqu_quyu[1]
            house_info['所属小区'] = xiaoqu.find('span', string='所属小区').find_next('a').text.strip()
            house_info['所属区域'] = quyu.find('span', 'maininfo-community-item-name').text.strip().split('\xa0')[0]
            tags = soup.find_all('span', 'maininfo-tags-item')
            for tag in tags:
                if '电梯' in tag.text:
                    house_info['配套电梯'] = '有'
            print(house_info)
            cursor.execute(INSERT_HOUSE_DETAIL, (house_info['产权性质'], house_info['物业类型'], house_info['产权年限'], house_info['房本年限'],
                                                 house_info['唯一住房'], house_info['参考首付'], house_info['发布时间'], house_info['总价'],
                                                 house_info['单价'], house_info['所在楼层'], house_info['建筑面积'], house_info['装修程度'],
                                                 house_info['房屋朝向'], house_info['建造年代'], house_info['配套电梯'], house_info['所属小区'],
                                                 house_info['所属区域'], house_info['房屋户型_室'], house_info['房屋户型_厅'], house_info['房屋户型_卫'],
                                                 house_info['总楼层'], hid))
            self.db_conn.commit()
            time.sleep((random.random() * 5) + 10)

    def get_all_communities(self, start: int = 1, end: int = 10):
        cursor = self.db_conn.cursor()
        INSERT_COMMUNITY = '''INSERT INTO Community (社区链接, 社区名称, 社区标记) VALUES (?, ?, ?)'''
        refer = self.BASE_COMMUNITY_URL
        for page in range(start, end + 1):
            url = self.BASE_COMMUNITY_URL.format(page)
            response = requests.get(url, headers=self.HEADERS)
            refer = url
            self.HEADERS['referer'] = refer
            response.encoding = 'utf8'
            soup = BeautifulSoup(response.text, 'lxml')
            communities = soup.find_all('a', 'li-row')
            print('第', page, '页共有数据：', len(communities))
            for community in communities:
                link = community['href']
                name = community.find('div', 'li-community-title').string.strip()
                cid = int(link.split('/')[-1])
                try:
                    cursor.execute(INSERT_COMMUNITY, (link, name, cid))
                except IntegrityError as e:
                    print(e)
                    print('当前社区在数据库中已存在，跳过')
                time.sleep(random.random() * 5)
            self.db_conn.commit()
            print('第', page, '页处理完成')
            time.sleep((random.random() * 10) + 10)


# 如果爬虫中间出现异常而停止，则需要手动打开安居客合肥的页面，在浏览器中验证为人类使用
if __name__ == '__main__':
    spider = AnjukeSpider()
    # 依次执行下面的代码
    # 1. 获取小区数据，默认 1 - 10 页一共 250 个热门小区
    # spider.get_all_communities()
    # 2. 依次获取小区内的房屋链接，目前只爬取了大约前 100 个小区
    # spider.get_house_by_community()
    # 3. 获取每一套房屋的具体信息
    spider.get_house_detail()

