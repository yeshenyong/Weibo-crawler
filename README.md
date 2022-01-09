# 微博爬虫

> 主要用于个人数据分析，做用户分析，情感分析，粉丝分析


#### warning 模块
Python 数据分析时， 不管是调用模型还是调整参数，都充满了满篇红色，有些可忽略，有些不可忽略

解决方法是利用两行代码

``` python
import warnings
warnings.filterwarnings('ignore')
```

#### codecs 模块
有一点需要清楚的是，当python要做编码转换的时候，会借助于内部的编码，转换过程是这样的：
        原有编码 -> 内部编码 -> 目的编码 


