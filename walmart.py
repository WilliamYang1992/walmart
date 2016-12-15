# -*- coding:utf-8 -*-

"""
爬取沃尔玛网站指定产品的评论内容

Usage: walmart [options]

Options:
  -h --help                 Show this on screen.
  -v --version              Show version.
  -l --link=<link>          Product review page link
  -p --page=<page>          The number of pages that you want to scrap
  -t --translate            Translate title and content via Youdao API
  -f --filename=<filename>  Specify output file name

Example:
  walmart -l https://www.walmart.com/reviews/product/47055697 -p 10 -t walmart.xlsx

Remark:
  link can be multiple and just need to be separated with ';'
  e.g. walmart -l linka;linkb

"""

import re
import html
import json
import time
import requests

from docopt import docopt
from bs4 import BeautifulSoup
from json import JSONDecodeError
from openpyxl.workbook import Workbook
from requests.exceptions import SSLError
from requests.exceptions import ConnectionError


def write_result(workbook, review_item_list, sheet_index, sheet_name):
    """将得到的结果写入到指定的Excel文件里"""
    global need_translate

    if need_translate:
        print('正在通过有道翻译处理内容, 请耐心等待...\n')

    wb = workbook  # 获得Workbook对象句柄
    youdao = YouDao('1118867640', 'walmart')  # 创建有道翻译API对象
    if sheet_index == 0:
        ws = wb.active
        ws.title = sheet_name.replace(r'/', '|')[:30]  # Excel里sheet名字不可以太长
    else:
        # 新建另外一个sheet
        ws = wb.create_sheet(title=sheet_name.replace(r'/', '|')[:30])
    # 设置字段名
    if need_translate:
        ws.append(['Name', 'Date', 'Stars', 'Title', 'Trans_title', 'Content', 'Trans_content'])
    else:
        ws.append(['Name', 'Date', 'Stars', 'Title', 'Content'])

    for review_item in review_item_list:
        name, date, stars, title, content = (
            review_item['customer_name'], review_item['date'],
            review_item['stars'], review_item['title'], review_item['content']
        )
        if need_translate:
            trans_title = youdao.get_translation(title)
            trans_content = youdao.get_translation(content)
            ws.append([name, date, stars, title, trans_title, content, trans_content])
        else:
            ws.append([name, date, stars, title, content])


class YouDao:
    """有道翻译API"""

    def __init__(self, key=None, keyfrom=None):
        """init"""
        self.key = key if key is not None else '920905315'
        self.keyfrom = keyfrom if keyfrom is not None else 'WalmartSpider'
        self.url = 'http://fanyi.youdao.com/openapi.do'

    def get_translation(self, content):
        """获取翻译内容"""
        time.sleep(1)  # 加适当延时, 防止API屏蔽不响应
        if len(content) <= 200:  # 有道翻译API每次不能提交超过200字符大小的内容
            trans_url = self.url + '?keyfrom=' + self.keyfrom + '&key=' + self.key + \
                        '&type=data&doctype=json&version=1.1&q=' + str(content)
            json_text = requests.get(trans_url).text
            try:
                json_result = json.loads(json_text)
            except JSONDecodeError:
                json_result = None
                print('JSONDecodeError, 获取内容失败')
            try:
                trans_result = json_result['translation'][0]  # 因为返回的是列表, 所以获取第一个值
            except (KeyError, TypeError):
                trans_result = ''
                print("Error, 翻译失败")
            return str(trans_result)
        else:
            combined_content = ''
            for i in range(0, len(content) // 200):
                trans_content = self.get_translation(content[i * 200:200 * (i + 1)])
                combined_content += str(trans_content)
            return combined_content  # 返回合并后的内容


def check_filename(filename):
    """check and modify filename"""
    if filename.endswith('xlsx'):
        return filename
    elif filename.endswith('.xls'):
        return filename[:-2] + 'xlsx'
    else:
        if filename[-1:] == '.':
            return filename + 'xlsx'
        else:
            return filename + '.xlsx'


def get_total_pages():
    """get the number of review pages"""
    global base_url
    page_list = []
    for url in base_url.split(';'):
        try:
            req = requests.get(url)
        except (SSLError, ConnectionError) as e:
            print('连接错误, 获取评论页数失败')
            return
        bs_obj = BeautifulSoup(req.text, 'html.parser')
        # 这里用正则表达式获取总评论条数
        match = re.search('\d+', bs_obj.select_one('.heading-e').get_text())
        if match:
            total_reviews = match.group(0)
            page_list.append(int(total_reviews) // 20 + 1)  # 每页有20条评论, 除以20+1后得到总页数
        else:
            page_list.append(1)
    return page_list


def get_product_name(product_url):
    """get product name"""
    try:
        req = requests.get(product_url)
    except (SSLError, ConnectionError):
        print('连接错误, 获取产品名字失败')
        return
    bs_obj = BeautifulSoup(req.text, 'html.parser')
    product_name = bs_obj.select_one('.review-product-name').get_text()
    return product_name


def main(arguments):
    """main entrance"""
    global file_name
    global page_total
    global base_url
    global need_translate

    base_url_pool = [base_url]  # 初始化链接池为默认连接
    if arguments['--link'] is not None:
        base_url = arguments['--link']
        base_url_pool = base_url.split(';')  # 如果同时输入了多个产品链接, 则以';'分隔
    if arguments['--filename'] is not None:
        file_name = arguments['--filename']
        file_name = check_filename(file_name)
    if arguments['--page'] is not None:
        page_total = int(arguments['--page'])
    else:
        num = get_total_pages()
        if num is not None:
            page_total = num  # 得到一个列表, 其中分别包含各个产品的评论页数
    if arguments['--translate']:
        need_translate = True

    wb = Workbook()  # 创建Workbook对象
    sheet_index = 0  # sheet的索引值

    for base_url in base_url_pool:
        item = {}  # 用于记录每条评论的相关属性
        review_item_list = []  # 收集所有得到的item, 用于最后输出到Excel文档
        start_urls = [base_url]
        # 按照格式预先设置了所有评论页面的URL, 用于下面的爬取
        start_urls.extend([base_url + '?limit=20&page={}&sort=relevancy'.format(i)
                           for i in range(2, page_total[sheet_index] + 1)])

        page, review_count = 1, 0  # 设置页数和条目数初始值
        product_name = get_product_name(base_url)

        print('开始爬取产品: {0}\n产品链接地址为: {1}'.format(product_name, base_url))
        for url in start_urls:  # 遍历每个评论页面
            print('\n........正在爬取第{}页........\n'.format(page))
            try:
                req = requests.get(url)
            except Exception as e:
                print(str(e))
            if req.status_code is not 200:
                continue
            bs_obj = BeautifulSoup(req.text, 'html.parser')
            review_list = bs_obj.find('div', class_='js-review-list')
            if review_list:
                reviews = review_list.find_all(
                    'div', class_='customer-review-body')
                if len(reviews) == 0:
                    print("没有找到评论数据")
                    page += 1
                    continue
                else:
                    for review in reviews:
                        print('已爬取第{}条评论'.format(review_count + 1))
                        # 获得客户名
                        customer_name = review.find('h3', class_='visuallyhidden').get_text()[19:]
                        # 获得日期
                        date = review.find('span', class_='customer-review-date').get_text()
                        # 获得标题
                        title = review.find('div', 'customer-review-title').get_text()
                        # 获得星级评分
                        stars = review.select_one('.customer-stars > .visuallyhidden').get_text()[0:3]
                        # 获得评论内容
                        content = review.select_one('.customer-review-text').get_text()

                        # 将属性添加到item内
                        item['customer_name'] = customer_name
                        item['date'] = date
                        item['title'] = title
                        item['stars'] = stars
                        item['content'] = content.strip()
                        # 复制到review_item_list里
                        review_item_list.append(item.copy())

                        review_count += 1  # 评论计数
            page += 1  # 页面计数
        try:
            # 输出数据到Excel(.xlsx)文档
            write_result(wb, review_item_list, sheet_index, product_name)
            print('\n')
            print('爬取产品{0}完成\n共{1}页, {2}条评论\n'.format(product_name, page_total[sheet_index], review_count))
        except OSError as e:
            print(str(e))
            print("发生错误!!不能写入excel文件!")
        sheet_index += 1
    print('正在写入文件..., ', end='')
    wb.save(filename=file_name)  # 保存Excel文档
    print('已成功写入文件{0}\n'.format(file_name))


if __name__ == '__main__':
    __version__ = 'V0.26'
    ##############################################################################
    # 设置如下变量值可以开始爬产品的评论内容, 仅当不添加对应命令行参数时才会启用,
    # "page_total"是评论的总页数, "base_url"是产品页面点击查看所有评论后跳转的网址,
    # "file_name"是保存的文件名, is_translate设置是否将标题和内容翻译, 以上设置好即可开始爬取
    # page_total不再使用, 由get_total_pages()获得, 仅当get_total_pages()函数失败返回None值时用该值代替
    page_total = 10
    base_url = 'https://www.walmart.com/reviews/product/47055697'
    file_name = r'walmart.xlsx'
    need_translate = False
    ##############################################################################

    options = docopt(__doc__, version=__version__)
    if options['--version']:
        print(__version__)
    else:
        print("爬取环境准备中...请耐心等候")
        main(options)
