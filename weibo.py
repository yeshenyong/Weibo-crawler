# -*- coding: utf-8 -*-

# @Time    : 2022/1/9 0:24
# @Author  : yeshenyong
import codecs
import csv
import sys
from datetime import date, datetime, timedelta
import warnings
import os
import logging
import logging.config

import requests
from collections import OrderedDict

from config import get_config

logging_path = os.path.split(os.path.realpath(__file__))[0] + os.sep + 'logging.conf'
logging.config.fileConfig(logging_path)
logger = logging.getLogger('weibo')


def standardize_info(weibo_dict):
    """ 标准化信息，去除乱码 """
    for k, v in weibo_dict.items():
        if 'bool' not in str(type(v)) and 'int' not in str(
                type(v)) and 'list' not in str(
            type(v)) and 'long' not in str(type(v)):
            # print(str(type(v)))
            weibo_dict[k] = v.replace(u'\u200b', '').encode(
                sys.stdout.encoding, 'ignore').decode(sys.stdout.encoding)
    return weibo_dict


def string_to_int(string):
    """ 字符串转换为整数 """
    if isinstance(string, int):
        return string
    elif string.endswith(u'万+'):
        string = string[:-2] + '0000'
    elif string.endswith(u'万'):
        string = float(string[:-1]) * 10000
    elif string.endswith(u'亿'):
        string = float(string[:-1]) * 100000000
    return int(string)


class Weibo(object):

    def __init__(self, config):
        """ Weibo类初始化 """
        self.validate_config(config)    # 验证配置是否正确
        self.filter = config['filter']  # 取值范围为0、1, 程序默认值为0,代表要爬取用户的全部微博，1代表只爬取用户的原创微博
        self.remove_html_tag = config['remove_html_tag']  # 取值范围为0、1,0代表不移出微博中的html tag，1代表移出
        since_date = config['since_date']
        if isinstance(since_date, int):
            since_date = date.today() - timedelta(since_date)
        since_date = str(since_date)
        self.since_date = since_date  # 起始时间，即爬取发布日期从该值到现在的微博，形式为yyyy-mm-dd
        self.start_page = config.get('start_page', 1)  # 开始爬的页，如果中途被限制而结束可以用此定义开始页码
        self.write_mode = config['write_mode']  # 结果信息保存类型，为list形式，可包含csv、mongo和mysql三种类型
        self.original_pic_download = config['original_pic_download']  # 取值范围为0、1, 0代表不下载原创微博图片,1代表下载
        self.retweet_pic_download = config['retweet_pic_download']  # 取值范围为0、1, 0代表不下载转发微博图片,1代表下载
        self.original_video_download = config['original_video_download']  # 取值范围为0、1, 0代表不下载原创微博视频,1代表下载
        self.retweet_video_download = config['retweet_video_download']  # 取值范围为0、1, 0代表不下载转发微博视频,1代表下载
        self.download_comment = config['download_comment']  # 1代表下载评论,0代表不下载
        self.comment_max_download_count = config['comment_max_download_count']  # 如果设置了下评论，每条微博评论数会限制在这个值内
        self.result_dir_name = config.get('result_dir_name', 0)  # 结果目录名，取值为0或1，决定结果文件存储在用户昵称文件夹里还是用户id文件夹里
        cookie = config.get('cookie')  # 微博cookie，可填可不填

        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36'
        self.headers = {'User_Agent': user_agent, 'Cookie': cookie}
        self.mysql_config = config.get('mysql_config')  # MySQL数据库连接配置，可以不填
        user_id_list = config['user_id_list']
        query_list = config.get('query_list') or []
        # query_list代表要爬取的微博关键词，为空（[]）则爬取全部；
        if isinstance(query_list, str):
            query_list = query_list.split(',')
        self.query_list = query_list
        if not isinstance(user_id_list, list):
            if not os.path.isabs(user_id_list):
                user_id_list = os.path.split(
                    os.path.realpath(__file__))[0] + os.sep + user_id_list
            self.user_config_file_path = user_id_list  # 用户配置文件路径
            user_config_list = self.get_user_config_list(user_id_list)
        else:
            self.user_config_file_path = ''
            user_config_list = [{
                'user_id': user_id,
                'since_date': self.since_date,
                'query_list': query_list
            } for user_id in user_id_list]
        self.user_config_list = user_config_list  # 要爬取的微博用户的user_config列表
        self.user_config = {}  # 用户配置,包含用户id和since_date
        self.start_date = ''  # 获取用户第一条微博时的日期
        self.query = ''
        self.user = {}  # 存储目标微博用户信息
        self.got_count = 0  # 存储爬取到的微博数
        self.weibo = []  # 存储爬取到的所有微博信息
        self.weibo_id_list = []  # 存储爬取到的所有微博id

    def is_date(self, since_date):
        """" 判断日期格式是否正确 """
        try:
            datetime.strptime(since_date, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    def validate_config(self, config):
        """ 验证配置是否正确 """
        # 验证filter、original_pic_download、retweet_pic_download、original_video_download、retweet_video_download
        argument_list = [
            'filter', 'original_pic_download', 'retweet_pic_download',
            'original_video_download', 'retweet_video_download',
            'download_comment'
        ]
        for argument in argument_list:
            if config[argument] != 0 and config[argument] != 1:
                logger.warning(u'%s值应为0或1，请重新输入', config[argument])
                # 验证since_date
                since_date = config['since_date']
                if (not self.is_date(str(since_date))) and (not isinstance(
                        since_date, int)):
                    logger.warning(u'since_date值应为yyyy-mm-dd形式或整数,请重新输入')
                    sys.exit()

        # 验证query_list
        query_list = config.get('query_list') or []
        if (not isinstance(query_list, list)) and (not isinstance(
                query_list, str)):
            logger.warning(u'query_list值应为list类型或字符串,请重新输入')
            sys.exit()

        # 验证write_mode
        write_mode = ['csv', 'json', 'mongo', 'mysql', 'sqlite']
        if not isinstance(config['write_mode'], list):
            sys.exit(u'write_mode值应为list类型')
        for mode in config['write_mode']:
            if mode not in write_mode:
                logger.warning(
                    u'%s为无效模式，请从csv、json、mongo和mysql中挑选一个或多个作为write_mode',
                    mode)
                sys.exit()

        # 验证user_id_list
        user_id_list = config['user_id_list']
        if (not isinstance(user_id_list,
                           list)) and (not user_id_list.endswith('.txt')):
            logger.warning(u'user_id_list值应为list类型或txt文件路径')
            sys.exit()
        if not isinstance(user_id_list, list):
            if not os.path.isabs(user_id_list):
                user_id_list = os.path.split(
                    os.path.realpath(__file__))[0] + os.sep + user_id_list
            if not os.path.isfile(user_id_list):
                logger.warning(u'不存在%s文件', user_id_list)
                sys.exit()

        comment_max_count = config['comment_max_download_count']
        if not isinstance(comment_max_count, int):
            logger.warning(u'最大下载评论数应为整数类型')
            sys.exit()
        elif comment_max_count < 0:
            logger.warning(u'最大下载数应该为正整数')
            sys.exit()

    def get_json(self, params):
        """ 获取网页中的json数据 """
        url = 'https://m.weibo.cn/api/container/getIndex?'
        r = requests.get(url,
                         params=params,
                         headers=self.headers,
                         verify=False)
        return r.json()

    def user_to_csv(self):
        """ 将爬取到的用户信息写入csv文件 """
        file_dir = os.path.split(os.path.realpath(__file__))[0] + os.sep + 'weibo'
        if not os.path.isdir(file_dir):
            os.makedirs(file_dir)
        file_path = os.path.join(file_dir, 'user.csv')
        result_headers = [
            '用户id', '昵称', '性别', '生日', '所在地', '学习经历', '公司', '注册时间', '阳光信用',
            '微博数', '粉丝数', '关注数', '简介', '主页', '头像', '高清头像', '微博等级', '会员等级',
            '是否认证', '认证类型', '认证信息'
        ]
        result_data = [[
            v.encode('utf-8') if 'unicode' in str(type(v)) else v
            for v in self.user.values()
        ]]
        self.csv_helper(result_headers, result_data, file_path)

    def user_to_database(self):
        """ 将用户信息写入文件/数据库 """
        self.user_to_csv()
        if 'mysql' in self.write_mode:
            self.user_to_mysql()
        if 'mongo' in self.write_mode:
            self.user_to_mongo()
        if 'sqlite' in self.write_mode:
            self.user_to_sqlite()

    def csv_helper(self, headers, result_data, file_path):
        """ 将指定信息写入csv文件 """
        if not os.path.isfile(file_path):
            is_first_write = 1
        else:
            is_first_write = 0
        if sys.version < '3': # python2.x
            with open(file_path, 'ab') as f:
                f.write(codecs.BOM_UTF8)
                writer = csv.writer(f)
                if is_first_write:
                    writer.writerows([headers])
                writer.writerows(result_data)
        else:   # python 3.x
            with open(file_path, 'a', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                if is_first_write:
                    writer.writerows([headers])
                writer.writerows(result_data)
        if headers[0] == 'id':
            logger.info(u'%d条微博写入csv文件完毕，保存路径:', self.got_count)
        else:
            logger.info(u'%s 信息写入csv文件完毕，保存路径:', self.user['screen_name'])
        logger.info(file_path)

    def get_user_info(self):
        """ 获取用户信息 """
        params = {'containerid': '100505' + str(self.user_config['user_id'])}
        js = self.get_json(params)
        logger.info("js {}".format(js))
        if js['ok']:
            info = js['data']['userInfo']
            user_info = OrderedDict()
            user_info['id'] = self.user_config['user_id']
            user_info['screen_name'] = info.get('screen_name', '')
            user_info['gender'] = info.get('gender', '')
            params = {
                'containerid':
                    '230283' + str(self.user_config['user_id']) + '_-_INFO'
            }
            zh_list = [
                u'生日', u'所在地', u'小学', u'初中', u'高中', u'大学', u'公司', u'注册时间',
                u'阳光信用'
            ]
            en_list = [
                'birthday', 'location', 'education', 'education', 'education',
                'education', 'company', 'registration_time', 'sunshine'
            ]
            for i in en_list:
                user_info[i] = ''
            js = self.get_json(params)
            if js['ok']:
                cards = js['data']['cards']
                if isinstance(cards, list) and len(cards) > 1:
                    card_list = cards[0]['card_group'] + cards[1]['card_group']
                    for card in card_list:
                        if card.get('item_name') in zh_list:
                            user_info[en_list[zh_list.index(
                                card.get('item_name'))]] = card.get(
                                'item_content', '')
            user_info['statuses_count'] = string_to_int(
                info.get('statuses_count', 0))
            user_info['followers_count'] = string_to_int(
                info.get('followers_count', 0))
            user_info['follow_count'] = string_to_int(
                info.get('follow_count', 0))
            user_info['description'] = info.get('description', '')
            user_info['profile_url'] = info.get('profile_url', '')
            user_info['profile_image_url'] = info.get('profile_image_url', '')
            user_info['avatar_hd'] = info.get('avatar_hd', '')
            user_info['urank'] = info.get('urank', 0)
            user_info['mbrank'] = info.get('mbrank', 0)
            user_info['verified'] = info.get('verified', False)
            user_info['verified_type'] = info.get('verified_type', -1)
            user_info['verified_reason'] = info.get('verified_reason', '')
            user = standardize_info(user_info)
            self.user = user
            self.user_to_database()
            logger.info('finished get {}'.format(user_info))
            return user
        else:
            logger.info(u"被ban了")
            sys.exit()

    def print_user_info(self):
        """ 打印用户信息 """
        logger.info('+' * 100)
        logger.info(u'用户信息')
        logger.info(u'用户id：%s', self.user['id'])
        logger.info(u'用户昵称：%s', self.user['screen_name'])
        gender = u'女' if self.user['gender'] == 'f' else u'男'
        logger.info(u'性别：%s', gender)
        logger.info(u'生日：%s', self.user['birthday'])
        logger.info(u'所在地：%s', self.user['location'])
        logger.info(u'教育经历：%s', self.user['education'])
        logger.info(u'公司：%s', self.user['company'])
        logger.info(u'阳光信用：%s', self.user['sunshine'])
        logger.info(u'注册时间：%s', self.user['registration_time'])
        logger.info(u'微博数：%d', self.user['statuses_count'])
        logger.info(u'粉丝数：%d', self.user['followers_count'])
        logger.info(u'关注数：%d', self.user['follow_count'])
        logger.info(u'url：https://m.weibo.cn/profile/%s', self.user['id'])
        if self.user.get('verified_reason'):
            logger.info(self.user['verified_reason'])
        logger.info(self.user['description'])
        logger.info('+' * 100)

    def get_pages(self):
        """ 获取全部微博 """
        try:
            self.get_user_info()
            self.print_user_info()
        except Exception as e:
            logger.exception(e)

    def initialize_info(self, user_config):
        """ 初始化爬虫信息 """
        self.weibo = []
        self.user = {}
        self.user_config = user_config
        self.got_count = 0  # 存储爬取到的微博数
        self.weibo_id_list

    def start(self):
        """" 运行爬虫 """
        try:
            for user_config in self.user_config_list:
                if len(user_config['query_list']):
                    for query in user_config['query_list']:
                        self.query = query
                        self.initialize_info(user_config)
                        self.get_pages()
                else:
                    self.initialize_info(user_config)
                    self.get_pages()
                logger.info(u'信息抓取完毕')
                logger.info('*' * 100)
                # if self.user_config_file_path and self.user:
                #     self.update_user_config_file(self.user_config_file_path)
        except Exception as e:
            logger.exception(e)


def main():
    try:
        config = get_config()
        wb = Weibo(config)
        wb.start()  # 爬取微博信息
    except Exception as e:
        logger.exception(e)


if __name__ == '__main__':
    main()
