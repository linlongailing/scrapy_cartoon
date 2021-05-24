import scrapy
import re
import mysql.connector
import requests
from w3lib.html import remove_tags
import json
import time
import math
from lxml import etree


class IqiyiSpider(scrapy.Spider):
    name = 'iqiyi'

    def __init__(self):
        self.conn = None

        res = self.connect_db()
        if not res:
            print('mysql init error,please check again')
            exit(0)

    # 连接数据库
    def connect_db(self):
        for i in range(3):
            try:
                self.conn = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    passwd="root",
                    database="cartoon"
                )
                return True
            except Exception as e:
                self.logger.info('The %d times mysql connect error,error is %s', i, e)
                continue
        return False

    def start_requests(self):
        page = 66

        # 创建分页链接抓取
        base_url = "https://pcw-api.iqiyi.com/search/recommend/list?channel_id=4&data_type=1&mode=24&ret_num=48" \
                   "&session=fa1d98b3e9dcc6e00a5cff2dd4f616bb "
        urls = []
        i = 1
        while i <= page:
            url_path = base_url + "&page_id=" + str(i)
            urls.append(url_path)
            i = i + 1

        for url in urls:
            yield scrapy.Request(url, callback=self.getCartoonList)

    def getCartoonList(self, response):
        print("now_page: " + response.request.url)
        volume_content = requests.get(response.request.url)
        jsons = json.loads(volume_content.text)
        if len(jsons['data']['list']) == 0:
            return None

        for cartoon in jsons['data']['list']:
            albumId = cartoon['albumId']
            title = cartoon['title']
            pic = cartoon['imageUrl']
            profile = cartoon['description']
            caption = cartoon['latestOrder']
            vip = 2 if cartoon['payMark'] == 7 else 1
            state = 2 if cartoon['videoCount'] == cartoon['latestOrder'] else 1
            play_url = cartoon.get('playUrl')

            data = {'title': title, 'pic': pic, 'desc': profile, 'caption': caption, 'vip': vip, 'state': state}

            cartoon_id = None
            cartoon_id = self.insertCartoon(data)
            if cartoon_id is None:
                continue

            # 获取第一集链接
            yield scrapy.Request(play_url, callback=self.getCartoonInfo,
                                 meta={'album': albumId, 'id': cartoon_id, 'caption': caption})

    def getCartoonInfo(self, response):
        cartoon_url = response.request.url
        print('cartoon_url：' + cartoon_url)

        album_id = response.meta['album']
        caption = response.meta['caption']
        cartoon_id = response.meta['id']

        album_json_data = re.findall(r":page-info=\'(.*?)\'", response.text)[0]
        album_json_detail_data = re.findall(r":video-info=\'(.*?)\'", response.text)[0]
        album_data = json.loads(album_json_data)
        album_detail_data = json.loads(album_json_detail_data)

        album_addr = album_detail_data.get('areas')
        album_year = album_detail_data.get('period')
        album_type = album_data.get('categories')
        issuer = album_data['user']['name'] if 'user' in album_data else ''
        album_addr_str = "".join(album_addr)

        # 更新动漫数据详情
        for i in range(5):
            try:
                db = self.conn.cursor()
                update_command = "update `cartoon`.`cartoon1` set `cartoon_type`=%s,`cartoon_addr`=%s," \
                                 "`cartoon_year`=%s,`cartoon_issuer`=%s where `cartoon_id`=%s "
                db.execute(update_command, (album_type, album_addr_str, album_year, issuer, cartoon_id))
                break
            except Exception as e:
                print("update mysql error------->", e)
                if 'MySQL Connection not available' in str(e):
                    self.connect_db()
        self.conn.commit()

        # 获取所有集数url
        base_url = "https://pcw-api.iqiyi.com/albums/album/avlistinfo?aid={aid}&page={page}&size=200&callback=jsonp_{" \
                   "time} "
        page = math.ceil(caption / 200)

        i = 1
        while i <= page:
            url_path = base_url.format(aid=album_id, page=i, time=int(time.time()))
            print(url_path)
            # 获取每集数据
            self.getVolume(cartoon_id=cartoon_id, json_url=url_path)
            i = i + 1

    def getVolume(self, cartoon_id, json_url):
        volume_list = requests.get(json_url)
        volume_list = volume_list.text[22:-13]
        volume_list = json.loads(volume_list)

        if len(volume_list['data']['epsodelist']) == 0:
            return None

        comment_total = 0
        for volume in volume_list['data']['epsodelist']:
            # 标题
            volume_title = volume['subtitle'] if volume['subtitle'] != "" else volume['name']
            # 本集链接
            volume_link = volume['playUrl']

            # 简介
            volume_desc = ''

            tvId = volume['tvId']
            # 评论量
            comment_url = "https://sns-comment.iqiyi.com/v3/comment/get_comments.action?agent_type=118&agent_version" \
                          "=9.11.5&authcookie=null&business_type=17&content_id={tvid}&hot_size=10&last_id=&page" \
                          "=&page_size=10&types=hot,time&callback=jsonp_{time}"
            comment_url = comment_url.format(tvid=tvId, time=int(time.time()))
            comment = requests.get(comment_url)
            comment = comment.text[22:-14]
            comment = json.loads(comment)
            comment_num = comment['data']['totalCount']
            comment_total += comment_num

            # # 插入每集信息
            for i in range(5):
                try:
                    db = self.conn.cursor()
                    insert_command = "insert into `cartoon`.`volume1` (`cartoon_id`,`volume_title`, `volume_link`," \
                                     "`volume_desc`,`volume_comment`,`volume_heat`,`volume_time`) values (%s,%s,%s," \
                                     "%s,%s,%s,%s) "
                    db.execute(insert_command,
                               (cartoon_id, volume_title, volume_link, volume_desc, comment_num, 0, int(time.time())))
                    break
                except Exception as e:
                    print("insert volume error----->", e)
                    if 'MySQL Connection not available' in str(e):
                        self.connect_db()
            self.conn.commit()

        # 动漫信息计 数
        for i in range(5):
            try:
                db = self.conn.cursor()
                update_command = 'update `cartoon`.`cartoon1` set `cartoon_comment`="%s" where `cartoon_id`="%s"'
                db.execute(update_command, (comment_total, cartoon_id))
                break
            except Exception as e:
                print("update mysql error------->", e)
                if 'MySQL Connection not available' in str(e):
                    self.connect_db()
        self.conn.commit()

    # 插入卡通数据
    def insertCartoon(self, data):
        if len(data) == 0:
            return None

        times = int(time.time())
        cartoon_id = None
        for i in range(5):
            try:
                db = self.conn.cursor()
                insert_command = "insert into `cartoon`.`cartoon1` (`cartoon_title`,`cartoon_source`,`cartoon_pic`," \
                                 "`cartoon_desc`,`cartoon_episode`,`cartoon_paid`,`cartoon_state`,`cartoon_time`) " \
                                 "values (%s, %s, %s, %s, %s, %s, %s, %s)"
                db.execute(insert_command, (
                    data['title'], 1, data['pic'], data['desc'], data['caption'], data['vip'], data['state'], times))
                cartoon_id = db.lastrowid
                break
            except Exception as e:
                print("insert mysql cartoon error----->", str(e))
                if 'MySQL Connection not available' in str(e):
                    self.connect_db()

        self.conn.commit()
        return cartoon_id

    # 去除标题多余字符
    def trim(self, title_arr):
        if len(title_arr) == 0:
            return None
        ss = ''
        for i in title_arr:
            ss = ss + i.strip()

        return ss

    # 集中获取元素
    def getElement(self, response, xpath_str, default=""):
        res = response.xpath(xpath_str).get()
        res = default if res == 'undefined' or res is None else res
        return res
