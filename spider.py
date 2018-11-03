import requests
from bs4 import BeautifulSoup
from urllib import parse
from requests.exceptions import RequestException
import json
import re
import pymongo
import os
from hashlib import md5
from multiprocessing import Pool
from config import *

client = pymongo.MongoClient(MONGO_URL,connect=False) #生成一个对象
db = client[MONGO_DB]

# 该项目集合了索引页和详情页的结构，索引页内容通过AJAX加载，详情页的内容是JSON格式存储在主页面中

def get_page_index(offset,keyword): #需要把将来改变的转化成变量
    global response
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'json',
        'count': '20',
        'cur_tab': '3',
        'from': 'gallery'
    }
    url = 'https://www.toutiao.com/search_content/?' + parse.urlencode(data) #urlencode 将字典形式接入到URL当中
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36"
    }
    try:
        response = requests.get(url,headers = header)
        if response.status_code == 200:
            return response.text
        else:
            print(response.status_code)
            return None
    except RequestException:
        print('请求失败',response.status_code)
        return None

def parse_page_index(html):
    if html != None:
        data = json.loads(html) #先把html转化成字典格式
        for data in data.get('data'):  #在函数中使用生成器，在下一步中只需遍历处理即可
            yield data.get('article_url')
    else:
        pass

def get_page_detail(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36'
    }
    try:
        response = requests.get(url,headers = headers)
        if response.status_code == 200:
            return response.text
        else:
            print(response.status_code)
            return None
    except RequestException:
        print('请求详情页失败',response.status_code)
        return None

def parse_page_detail(html,url):
    if html != None:
        soup = BeautifulSoup(html, 'lxml')
        title = soup.title.text
        target = soup.find(text=re.compile('BASE_DATA.galleryInfo'))
        result = re.search('\sgallery: JSON.parse\("(.+?)"\),\s', target, re.S)
        if result:
            data = json.loads(result.group(1).replace('\\', ''))
            sub_images = data['sub_images']
            images = [item.get('url') for item in sub_images] # 采用一句话创建一个URL列表
            for image in images:
                download_image(image)
            return {  # 返回整个字典形式，方便后期管理
                'title': title,
                'url': url,
                'images': images
            }
    else:
        pass

def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('存储到MongoDB成功',result)
        return True
    return False

def download_image(url):
    print('正在下载',url)
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=header)
        if response.status_code == 200:
            save_image(response.content)
        else:
            return None
    except RequestException:
        print('请求图片失败')
        return None

def save_image(content):
    file_path = '{0}/{1}.{2}'.format(os.getcwd(),md5(content),'jpg') # md5用于判断文件是否一样
    if not os.path.exists(file_path):
        with open(file_path,'wb') as f:
            f.write(content)
            f.close()

def main(offset):
    html = get_page_index(offset,KEYWORD)
    for url in parse_page_index(html):
        html_detail = get_page_detail(url)
        result = parse_page_detail(html_detail,url)
        if result:
            save_to_mongo(result)



if __name__ == '__main__':
    groups = [x*20 for x in range(GROUP_START,GROUP_END+1)] #构建offset的list
    pool = Pool()
    pool.map(main,groups)