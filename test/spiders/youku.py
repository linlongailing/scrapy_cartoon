from abc import ABC

import scrapy
import math
import os
import re
import mysql.connector
import requests
from test.items import CartoonItem
import time


class IqiyiSpider(scrapy.Spider, ABC):
    name = 'youku'

    def __init__(self):
        # 连接数据库
        self.mydb = mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="root",
            database="cartoon"
        )

    def start_requests(self):
        """
        total_url="https://v.qq.com/channel/cartoon?_all=1&anime_status=-1&channel=cartoon&ipay=-1&item=1&itype=-1&listpage=1&sort=18"
        session=HTMLSession()
        r=session.get(total_url)
        total=r.html.xpath("//div[@class='filter_result']/span/text()")
        total=total[0]
        """
        # 固定值，没有总部数
        total = 70000

        page = math.ceil(int(total) / 30)

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
            # print(url)
            yield scrapy.Request(url=url, callback=self.getInfo)
            # 休眠1分钟
            time.sleep(60)

    def getInfo(self, response):
        # 获取每部动漫信息
        cartoon_box = response.xpath("//div[@class='list_item']")
        if len(cartoon_box) == 0:
            os._exit(0);

        for cartoon in cartoon_box:
            item = CartoonItem()
            # 图片
            pic = cartoon.xpath(".//img[@class='figure_pic']/@src").extract()[0]
            # 标题，可能为空
            title = cartoon.xpath(".//a[@class='figure_title figure_title_two_row bold']/@title").extract()
            title = "" if len(title) == 0 else title[0]
            # 描述，可能为空
            desc = cartoon.xpath(".//div[@class='figure_desc']/text()").extract()
            desc = "" if len(desc) == 0 else desc[0]
            # 更新集数，为预告片是为空
            caption = cartoon.xpath(".//div[@class='figure_caption']/text()").extract()
            caption = "" if len(caption) == 0 else caption[0]
            # 链接
            url = cartoon.xpath(".//a[contains(@class,'figure_title')]/@href").extract()
            url = "" if len(url) == 0 else url[0]
            # 获取专辑id
            menu = cartoon.xpath(".//a[@class='figure']/@data-float").extract()[0]
            # 该位置可能为预告，独播，超前点播，自制，vip
            vip_tag = cartoon.xpath(".//img[contains(@class,'mark_v')]/@alt").extract()
            vip_tag = "" if len(vip_tag) == 0 else vip_tag[0]
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
                yield scrapy.Request(url, callback=self.url_parse, meta={'item': item})

    def url_parse(self, response):
        self.logger.info("解析url:%s", response.url)
        items = response.meta['item']

        # 简介
        profile = response.xpath("//p[@class='summary']/text()").extract()[0]

        tag_num = response.xpath("count(//div[@class='video_tags _video_tags']/a)").extract()[0]

        year = ''
        if tag_num == 3:
            # 发行地区，可能没有
            addr = response.xpath("//div[@class='video_tags _video_tags']/a[1]/text()").extract()[0]

            # 发行年份，可能没有
            year = response.xpath("//div[@class='video_tags _video_tags']/a[2]/text()").extract()[0]

            # 动漫类型，可能没有
            item = response.xpath("//div[@class='video_tags _video_tags']/a[3]/text()").extract()[0]
        else:
            # 发行地区，可能没有
            addr = response.xpath("//div[@class='video_tags _video_tags']/a[1]/text()").extract()[0]

            # 动漫类型，可能没有
            item = response.xpath("//div[@class='video_tags _video_tags']/a[2]/text()").extract()[0]

            # 专辑播放量
        playnum = response.xpath("//em[@class='num']/text()").extract()[0]

        # 发行方
        user = response.xpath("//div[@class='user_aside']/span[1]/text()").extract()[0]
        user = "腾讯出品" if user == 'undefined' else user

        times = int(time.time())
        # 插入数据
        cartoon_id = None
        try:
            db = self.mydb.cursor()
            insert_command = "insert into `cartoon`.`cartoon` (`cartoon_title`,`cartoon_pic`,`cartoon_desc`," \
                             "`cartoon_episode`,`cartoon_type`,`cartoon_paid`,`cartoon_addr`,`cartoon_year`," \
                             "`cartoon_issuer`,`cartoon_volume`,`cartoon_state`,`cartoon_time`) values ('" + \
                             items['title'] + "','" + profile + "','" + items['desc'] + "','" + items[
                                 'caption'] + "','" + str(item) + "','" + str(items['vip']) + "','" + str(
                addr) + "','" + str(year) + "','" + user + "','" + str(playnum) + "','" + str(
                items['state']) + "','" + str(times) + "');"
            db.execute(insert_command)
            cartoon_id = db.lastrowid
        except Exception as e:
            print("insert mysql error----->", e)
        self.mydb.commit()
        if cartoon_id is None:
            return None

        # 获取更新到的集数，取整
        volume_count = items['caption']
        volume_num = re.findall(r"\d+", volume_count)
        volume_num = int(volume_num[0])

        # 获取每集信息
        volume_str = response.xpath("//script").re('LIST_INFO = {\"vid\":\[(.*)?\]')
        volume_arr = volume_str[0].replace('"', "").split(",")

        # 获取周边视频数
        figure = response.xpath("//div[@_wind='columnname=精彩周边']/preceding-sibling::div[1]/text()").extract()
        figure = re.findall(r"\d+", figure[0])
        figure = int(figure[0])

        for i in range(0, len(volume_arr) - figure):
            # 获取每集url
            volume_url = "https://v.qq.com/x/cover/" + items['menu'] + "/" + volume_arr[i] + ".html"
            yield scrapy.Request(volume_url, callback=self.volume_parse,
                                 meta={'id': cartoon_id, 'item': items, 'volume': volume_arr[i]})

    def volume_parse(self, response):
        items = response.meta['item']
        volume = response.meta['volume']
        cartoon_id = response.meta['id']

        # 是否是预告
        trailer = response.xpath("//span[@id='" + volume + "']//img/@src").extract()
        trailer = "" if len(trailer) == 0 else trailer[0]
        if "trailerlite" in trailer:
            return None

            # 每集标题
        title = response.xpath("//h1[@class='video_title _video_title']/text()").extract()
        title = self.trim(title)
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
        try:
            db = self.mydb.cursor()
            insert_command = "insert into `cartoon`.`volume` (`cartoon_id`,`volume_title`,`volume_desc`," \
                             "`volume_comment`,`volume_time`) values ('" + str(
                cartoon_id) + "','" + title + "','','" + str(comment_num) + "','" + str(int(time.time())) + "');"
            db.execute(insert_command)
        except Exception as e:
            print("insert volume error----->", e)
        self.mydb.commit()

        try:
            for i in range(3):
                # 评论计数
                db = self.mydb.cursor()
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
                self.mydb.commit()
                if db.rowcount > 0:
                    break;
        except Exception as e:
            print("error", e)

        yield items

    # 去除标题多余字符
    def trim(self, title_arr):
        if len(title_arr) == 0:
            return None
        ss = ''
        for i in title_arr:
            ss = ss + i.strip()
        return ss
