# -*- coding: utf-8 -*-

# @Time    : 2022/1/9 0:24
# @Author  : yeshenyong
# @File    : config.py

import json
import os
import sys
import logging
import logging.config


def get_config():
    """ 获取config.json 文件信息 """
    config_path = os.path.split(os.path.realpath(__file__))[0] + os.sep + 'config.json'
    # print(os.path.join(os.path.split(os.path.realpath(__file__))[0], 'config.json'))
    if not os.path.isfile(config_path):
        logging.warning(u'当前路径：%s 不存在配置文件config.json' % (os.path.split(os.path.realpath(__file__))[0] + os.sep))

        sys.exit(-1)
    try:
        with open(config_path, encoding='utf-8') as f:
            config = json.loads(f.read())
            return config
    except ValueError:
        logging.error(u'config.json 格式不正确')
        sys.exit(-1)
