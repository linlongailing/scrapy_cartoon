import scrapy
import re
import mysql.connector
import requests
from w3lib.html import remove_tags
from test.items import CartoonItem
import time


class TencentSpider(scrapy.Spider):
    name = 'tencent'

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
        page = 76

        # 创建分页链接抓取
        base_url = "https://v.qq.com/x/bu/pagesheet/list?_all=1&anime_status=-1&append=1&channel=cartoon&ipay=-1&item" \
                   "=1&itype=-1&listpage=2&pagesize=30&sort=18 "
        urls = []
        i = 1
        while i <= page:
            offset = (i - 1) * 30
            url_path = base_url + "&offset=" + str(offset)
            urls.append(url_path)
            i = i + 1

        for url in urls:
            yield scrapy.Request(url, callback=self.getCartoonList)

    def getCartoonList(self, response):
        print("now page: " + response.request.url)
        cartoon_box = response.xpath("//div[@class='list_item']")
        if len(cartoon_box) == 0:
            return None

        for cartoon in cartoon_box:
            item = CartoonItem()
            # 图片
            pic = self.getElement(cartoon, ".//img[@class='figure_pic']/@src")

            # 标题，可能为空
            title = self.getElement(cartoon, ".//a[contains(@class,'figure_title figure_title_two_row')]/@title")

            # 描述，可能为空
            desc = self.getElement(cartoon, ".//div[@class='figure_desc']/text()")

            # 更新集数，为预告片是为空
            caption = self.getElement(cartoon, ".//div[@class='figure_caption']/text()")

            # 链接
            url = self.getElement(cartoon, ".//a[contains(@class,'figure_title')]/@href")

            # 获取专辑id
            menu = self.getElement(cartoon, ".//a[@class='figure']/@data-float")

            # 该位置可能为预告，独播，超前点播，自制，vip
            vip_tag = self.getElement(cartoon, ".//img[contains(@class,'mark_v')]/@alt")

            # 判断是否完结
            state = 0
            paid = 1
            if vip_tag == 'VIP' or vip_tag == '超前点播':
                paid = 2

            if caption.find("更新至"):
                state = 1
            if caption.find("全"):
                state = 2

            item['title'] = title
            item['desc'] = desc
            item['caption'] = caption
            item['pic'] = pic
            item['vip'] = paid
            item['state'] = state
            item['menu'] = menu

            if url != "":
                yield scrapy.Request(url, callback=self.getCartoonInfo, meta={'item': item})

    def getCartoonInfo(self, response):
        print('now_url：' + response.request.url)
        items = response.meta['item']

        # 简介
        profile = items['desc']
        if profile == "":
            profile = self.getElement(response, "//p[@class='summary']/text()")

        # 年份
        year = self.getElement(response, "//a[contains(@href,'year')]/text()")
        # 地区
        addr = self.getElement(response, "//a[contains(@href,'area')]/text()")
        # 类型
        item = self.getElement(response, "//a[contains(@href,'stag')]/text()")

        # 没有这些类型时，则从专辑页面获取
        print(year + '-' + addr + '-' + item)

        # 专辑播放量
        playnum = self.getElement(response, "//em[@class='num']/text()")

        # 发行方
        user = self.getElement(response, "//div[@class='user_aside']/span[1]/text()", "腾讯出品")

        # 获取每集信息
        volume_str = response.xpath("//script").re('LIST_INFO = {\"vid\":\[(.*)?\]')
        volume_arr = volume_str[0].replace('"', "").split(",")

        # 获取周边视频数
        figure = self.getElement(response, "//div[@_wind='columnname=精彩周边']/preceding-sibling::div[1]/text()")
        if figure != "":
            figure = re.findall(r"（(\d+)）", figure)
        else:
            figure = ['0']

        figure = int(figure[0])

        # 获取集数
        caption = items['caption']
        if items['caption'] == "" or ":" in items['caption']:
            caption = len(volume_arr) - figure

        times = int(time.time())
        # 插入数据
        cartoon_id = None
        for i in range(5):
            try:
                db = self.conn.cursor()
                insert_command = "insert into `cartoon`.`cartoon` (`cartoon_title`,`cartoon_pic`,`cartoon_desc`," \
                                 "`cartoon_episode`,`cartoon_type`,`cartoon_paid`,`cartoon_addr`,`cartoon_year`," \
                                 "`cartoon_issuer`,`cartoon_volume`,`cartoon_state`,`cartoon_time`) values ('" + \
                                 items['title'] + "','" + items['pic'] + "','" + profile + "','" + str(
                    caption) + "','" + str(
                    item) + "','" + str(items['vip']) + "','" + str(
                    addr) + "','" + str(year) + "','" + user + "','" + str(playnum) + "','" + str(
                    items['state']) + "','" + str(times) + "');"
                db.execute(insert_command)
                cartoon_id = db.lastrowid
                break
            except Exception as e:
                print("insert mysql cartoon error----->", str(e))
                if 'MySQL Connection not available' in str(e):
                    self.connect_db()

        self.conn.commit()
        if cartoon_id is None:
            return None

        for i in range(0, len(volume_arr) - figure):
            # 获取每集url
            volume_url = "https://v.qq.com/x/cover/" + items['menu'] + "/" + volume_arr[i] + ".html"
            yield scrapy.Request(volume_url, callback=self.getVolume,
                                 meta={'id': cartoon_id, 'item': items, 'volume': volume_arr[i]})

    def getVolume(self, response):
        volume_url = response.request.url
        print('volume_url：' + volume_url)
        items = response.meta['item']
        volume = response.meta['volume']
        cartoon_id = response.meta['id']

        # 是否是预告
        trailer = self.getElement(response, "//span[@id='" + volume + "']//img/@src")
        if "trailerlite" in trailer:
            return None

        # 每集标题
        title = response.xpath("//h1[@class='video_title _video_title']").xpath("string(.)").get()
        title = remove_tags(title)
        title = re.sub(r'[\t\r\n\s]', '', title)

        # 获取评论id
        comment_id_url = "https://access.video.qq.com/fcgi-bin/video_comment_id?otype=json&callback" \
                         "=jQuery19105534040520914412_1617256774219&op=3&vappid=30645497&vsecret" \
                         "=d38052bb634963e03eca5ce3aaf93525324d970f110f585f&vid=" + volume + "&_=1617256774254 "
        volume_content = requests.get(comment_id_url)
        comment_id = volume_content.text
        comment_id = re.findall(r"comment_id\":\"(\d+)\"", comment_id)[0]

        # 获取评论数
        comment_num_url = "https://video.coral.qq.com/article/" + comment_id + "/commentnum?callback=_article" + comment_id + "commentnum&_=1617257028913"
        volume_comment = requests.get(comment_num_url)
        comment_num = volume_comment.text
        comment_num = re.findall(r"commentnum\":\"(\d+)\"", comment_num)[0]

        # 插入每集信息
        for i in range(5):
            try:
                db = self.conn.cursor()
                insert_command = "insert into `cartoon`.`volume` (`cartoon_id`,`volume_title`, `volume_link`, `volume_desc`," \
                                 "`volume_comment`,`volume_time`) values ('" + str(
                    cartoon_id) + "','" + title + "','" + str(volume_url) + "','','" + str(comment_num) + "','" + str(
                    int(time.time())) + "');"
                db.execute(insert_command)
                break
            except Exception as e:
                print("insert volume error----->", e)
                if 'MySQL Connection not available' in str(e):
                    self.connect_db()
        self.conn.commit()

        # 评论计数
        for i in range(5):
            try:
                db = self.conn.cursor()
                select_command = "select `cartoon_id`,`cartoon_comment` from `cartoon`.`cartoon` where `cartoon_id`='" + str(
                    cartoon_id) + "';"
                db.execute(select_command)
                result = db.fetchall()
                cartoon_info = result[0]
                cartoon_nums = int(cartoon_info[1]) + int(comment_num)
                update_command = "update `cartoon`.`cartoon` set `cartoon_comment`='" + str(
                    cartoon_nums) + "' where `cartoon_id`='" + str(cartoon_id) + "' and `cartoon_comment`='" + str(
                    cartoon_info[1]) + "';"

                db.execute(update_command)
                break
            except Exception as e:
                print("update mysql error------->", e)
                if 'MySQL Connection not available' in str(e):
                    self.connect_db()
        self.conn.commit()
        yield items

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
