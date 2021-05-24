# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class TestItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class CartoonItem(scrapy.Item):
    title=scrapy.Field() #标题
    desc=scrapy.Field() #描述
    caption=scrapy.Field() #集数
    pic=scrapy.Field() #图片
    profile=scrapy.Field() #内容简介
    item=scrapy.Field() #动漫类型
    addr=scrapy.Field() #发行地区
    year=scrapy.Field() #发行年份
    playnum=scrapy.Field() #专辑播放量
    user=scrapy.Field() #发行方
    vip=scrapy.Field() #vip
    state=scrapy.Field() #是否连载
    menu=scrapy.Field() #主目录
    comment=scrapy.Field() #评论数
