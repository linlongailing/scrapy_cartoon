create database cartoon;

CREATE TABLE IF NOT EXISTS `cartoon`(
   `cartoon_id` bigint(20) UNSIGNED AUTO_INCREMENT comment 'id',
   `cartoon_source` tinyint(4) UNSIGNED not null default 0 comment '来源，0腾讯1爱奇艺',
   `cartoon_title` varchar(200) NOT NULL comment '标题',
   `cartoon_pic` varchar(1000) NOT NULL default '' comment '图片',
   `cartoon_desc` varchar(1000) NOT NULL default '' comment '简介',
   `cartoon_episode` varchar(100) NOT NULL default '' comment '更新集数',
   `cartoon_format` tinyint(4) not null default 0 comment '影片格式，0无 1 2D  2 3D',
   `cartoon_type` varchar(200) NOT NULL default '' comment '动漫类型',
   `cartoon_paid` tinyint(4) NOT NULL default 1 comment '付费类型，1不收费2收费vip',
   `cartoon_addr` varchar(30) NOT NULL default '' comment '发行地区',
   `cartoon_year` varchar(10) NOT NULL default '' comment '发行年份',
   `cartoon_issuer` varchar(30) NOT NULL default '' comment '发行方',
   `cartoon_volume` varchar(100) NOT NULL default '' comment '播放量',
   `cartoon_comment` int(11) NOT NULL default 0 comment '评论量',
   `cartoon_state` tinyint(4) NOT NULL default 0 comment '0预告片1连载2完结',
   `cartoon_time` char(10) not null comment '时间',
   PRIMARY KEY (`cartoon_id`)
)ENGINE=InnoDB DEFAULT CHARSET=utf8 comment '卡通数据';


CREATE TABLE IF NOT EXISTS `volume`(
   `volume_id` bigint(20) UNSIGNED AUTO_INCREMENT comment 'id',
   `cartoon_id` bigint(20) NOT NULL comment '卡通id',
   `volume_title` varchar(200) NOT NULL default '' comment '标题',
   `volume_link` varchar(500) NOT NULL default '' comment '链接',
   `volume_desc` varchar(1000) NOT NULL default '' comment '简介',
   `volume_heat` int(11) NOT NULL default 0 comment '热度或播放量',
   `volume_comment` int(11) NOT NULL default 0 comment '评论量',
   `volume_time` char(10) not null comment '时间',
   PRIMARY KEY (`volume_id`)
)ENGINE=InnoDB DEFAULT CHARSET=utf8 comment '单集数据';
