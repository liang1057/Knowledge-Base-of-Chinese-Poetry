# -*- coding: utf-8 -*-
# @Time    : 2026/04/16
# @Author  : Leon
# @Email   : liang1057@163.com
# @File    : data_loader.py
# @Project : 中华诗词知识库 Knowledge Base of Chinese Poetry (KBCP)
# @Description: 原始数据加载模块，将json的数据加载进内存中。
# @Reference: https://github.com/liang1057/Knowledge-Base-of-Chinese-Poetry
# @Update:   Leon 2026/04/17
# @Version: 0.0.1
'''
【注意】：json加载的数据是清洗之前的数据，关于朝代id、作者id等元数据，并不具有规范性和约束性，尚需治理
【注意】：考虑到后续收集的内容增多，归纳到一个大的json文件后修改是比较麻烦的，因此考虑将诗词数据按照朝代进行分类，每个朝代单独一个文件。
'''


import os
import json
import re
import sys
import time
import numpy as np
import argparse

global all_poems # 全部诗词. global关键字用于声明全局变量
global dynasty_drop, author_drop # 朝代黑名单, 作者黑名单
all_poems = None
author_drop = []  # 作者排除名单
dynasty_drop = [] # 朝代排除名单

# 朝代列表 分为14个朝代（包括近代现代当代）
dynasty_list = ['先秦', '秦', '汉', '魏晋','南北朝', '隋', '唐', '五代', '宋', '金', '辽', '元', '明', '清', '近代', '现当代'] # , '不详' 不详的暂时不收录了
dynasty_id_dict = {'先秦': 'A', '秦': 'B', '汉': 'C', '魏晋': 'D', '南北朝': 'E', '隋': 'F', '唐': 'G', '五代': 'H', '宋': 'I', '金': 'J', '辽': 'K', '元': 'L', '明': 'M', '清': 'N', '近代': 'O', '现当代': 'P'}
dynasty_id2name_dict = {'A': '先秦', 'B': '秦', 'C': '汉', 'D': '魏晋', 'E': '南北朝', 'F': '隋', 'G': '唐', 'H': '五代', 'I': '宋', 'J': '金', 'K': '辽', 'L': '元', 'M': '明', 'N': '清', 'O': '近代', 'P': '现当代'}


'''
# 诗词的格律 (注意，这个不是一个完整的功能，仅仅是与对应的功能抽取配合使用的)
'''
def get_poem_format(poem_str, content_txt, poem_format_dict, dynasty):
    poem_format = ''
    # 正则化匹配 '【 题 】：'到 '\n'之间的内容为诗词的format
    match = re.search(r'【题】：(.*?)\n', poem_str.replace('\r\n', '\n').replace('\r', '\n'))
    if match is None:
        match = re.search(r'【 题 】：(.*?)\n', poem_str.replace('\r\n', '\n').replace('\r', '\n'))
    if match:
        tmp_format = match.group(1).strip()
        if tmp_format in poem_format_dict:
            poem_format = tmp_format
    if poem_format == '':  # 如果正则化匹配不到，则从规则中匹配
        tmp_content = content_txt.replace('，', '\n').replace('。', '\n').replace('\n\n', '\n')  # 单拆成行
        if dynasty in ['唐', '宋', '金', '辽', '元', '明', '清', '近代', '现当代']:
            poem_txt = tmp_content.strip().replace('\r\n', '\n').replace('\n\n', '\n').replace('，', '\n').replace('。', '\n')
            poem_lines = poem_txt.split('\n')
            char_nums = np.array([len(l) for l in poem_lines])
            # 取 char_num 的众数，最多的
            main_num = np.argmax(np.bincount(char_nums))
            # main_num = np.max(char_nums)
            line_num = len(poem_lines)
            if main_num == 5 and line_num == 4:
                poem_format = '五言绝句'
            elif main_num == 7 and line_num == 4:
                poem_format = '七言绝句'
            elif main_num == 5 and line_num == 8:
                poem_format = '五言律诗'
            elif main_num == 7 and line_num == 8:
                poem_format = '七言律诗'
            elif main_num == 5 and line_num >= 8:
                poem_format = '五言长诗'
            elif main_num == 7 and line_num >= 8:
                poem_format = '七言长诗'
            else:
                poem_format = ''
    return poem_format


# ========== 数据预处理 ==========
def clean_poems(raw_file, cleaned_file):
    '''
    清洗诗词数据，包括：
    1. 朝代、作者、诗词格式等元数据清洗
    2. 诗词内容清洗
    3. 诗词内容格式化
    :return:
    '''

    dynasty_poem_dict = {}  # {朝代:{作者-题目:poem_data}}, 其中 poem_data是一个{}
    for d in dynasty_list:
        dynasty_poem_dict[d] = {}

    poem_format_dict = None # 诗词格式字典
    with open('./data/Poem_Format.json', 'r', encoding='utf-8') as f:
        poem_format_dict = json.load(f)

    with open(raw_file, 'r', encoding='utf-8') as f:
        raw_poems = json.load(f)

    for dynasty_key in raw_poems.keys():   # 原始数据 *_key 是未清洗的
        dynasty = dynasty_key.strip()
        for author_key in raw_poems[dynasty_key].keys():  # 原始数据 *_key 是未清洗的
            for poem_key in raw_poems[dynasty][author_key]: # 原始数据 *_key 是未清洗的
                poem = raw_poems[dynasty][author_key][poem_key]
                # 诗词元数据清洗
                # 诗词格式
                author = poem['author'].strip()
                if author in author_drop or dynasty in dynasty_drop:  # 过滤一些作者或指定的年代
                    continue
                dynasty_id = dynasty_id_dict[dynasty]  # poem[2].strip() # make_dynasty_id(dynasty)
                author_id = f'{dynasty_id}-{len(dynasty_poem_dict[dynasty]) + 1}' # 作者ID
                tmp_content = poem['content'].replace('\r\n', '\n').replace('\r', '\n').replace('[', '').replace(']', '').replace('&nbsp', '')
                for i_num in range(0, 10):
                    tmp_content = tmp_content.replace(f'{i_num}', '')

                if dynasty not in ['近代', '现当代']:  # 散文诗暂时先不替换，先按时代卡
                    tmp_content = tmp_content.replace('，\n', '，').replace('。\n', '。').replace('？\n', '？').replace('；\n', '；') # 去掉逗号和句号后面的换行，然后统一转成换行的
                    tmp_content = tmp_content.replace('，', '，\n').replace('。', '。\n').replace('？', '？\n').replace('；', '；\n')  # 统一转成换行的
                content_list = tmp_content.split('\n')
                for i in range(len(content_list) - 1, -1, -1):
                    if content_list[i].__contains__('【'):  # 去掉解释性的行
                        content_list.pop(i)
                content_txt = '\n'.join(content_list).strip()
                content_sc_list = content_txt.split('\n')  # 按行分割，简体中文的
                poem_format = get_poem_format(tmp_content, content_txt, poem_format_dict, dynasty)  # 获取诗词的格律
                discription = poem['discription'].replace('\r\n', '\n').replace('\r', '\n').replace('【注释】：', '').strip()
                title_list = poem['title'].strip().split('（')
                title = title_list[0]  # 去掉括号前的内容
                content_title = title_list[1].replace('）', '').strip() if len(title_list) > 1 else content_sc_list[0]  # 括号后的内容或第一句
                # 如果有重复，还需要修改。

                poem_data = {
                    "title": title,
                    "content_title": content_title,  # 正文题
                    "author": author,
                    "author_id": author_id,
                    "dynasty": dynasty,
                    "dynasty_id": dynasty_id,
                    "content": content_sc_list,
                    # "content_TC": content_tc,  # 繁体中文的不需要
                    "discription": discription,
                    "format": poem_format
                }

                # 将结构化的内容放入dict中，方便后面转换成json
                if dynasty in dynasty_poem_dict:
                    if author in dynasty_poem_dict[dynasty]:
                        dynasty_poem_dict[dynasty][author][f'{author}-{title}-{content_title}'] = poem_data
                    else:
                        dynasty_poem_dict[dynasty][author] = {f'{author}-{title}-{content_title}': poem_data}
                else:
                    dynasty_poem_dict[dynasty] = {author: {f'{author}-{title}-{content_title}': poem_data}}

    json_text = json.dumps(dynasty_poem_dict, ensure_ascii=False, indent=4) # 将字典转换为 JSON 字符串, 并确保非 ASCII 字符被正确处理, 并缩进为4个空格

    # 全部的诗词保存一个文件
    with open(cleaned_file, 'w', encoding='utf-8') as f:
        f.write(json_text)
        f.close()

# ========== 数据加载 ==========
# 从json文件中加载所有诗词到内存中。
def load_all_poems():
    '''
    从总文件加载所有诗词到内存中。
    :return: 所有诗词的字典
    '''
    with open('./data/Poetry_China_all.json', 'r', encoding='utf-8') as f:
        all_poems = json.load(f)

    # 删除作者和朝代
    for dynasty in list(all_poems.keys()):
        if dynasty in dynasty_drop:
            all_poems.pop(dynasty) # 删除朝代
        else:
            for author in list(all_poems[dynasty].keys()):
                if author in author_drop:
                    all_poems[dynasty].pop(author) # 删除作者
    return all_poems


def save_all_poems(filename = './data/Poetry_China_all_update.json'):
    '''
    保存所有诗词。当内容、元数据被修改后，可以通过该方法进行保存。
    :param filename: 保存的文件名. 默认保存一个新的文件
    :return:
    '''
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_poems, f, ensure_ascii=False, indent=4)




def save_dynasty_poems(path='./data/'):
    '''
    将所有诗词按朝代保存到单独的json文件中
    【注意】这里的前提条件是必须有全部的诗词内容。实际上，该方法更多用于将全部诗词同步到各个朝代文件夹中
           可以在该方法的基础上进行修改，同步文件中的元数据也可以自定义，从而适应不同的场景要求。
    :param path: 保存路径
    :return:
    '''
    all_poems = load_all_poems()
    for i, dynasty in enumerate(all_poems.keys()):
        dynasty_data = all_poems[dynasty]
        file_name = os.path.join(path, f'{i+1}_Poetry_China_{dynasty}.json')
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(dynasty_data, f, ensure_ascii=False, indent=4)
            print(f"保存{dynasty}朝代诗词到文件 {file_name}")
    return


def merge_dynasty_poems(dynasty_list=None, obj_json_file='./data/Poetry_China_all_merged.json'):
    '''
    将所有朝代的诗词合并到一个json文件中
    :param file_list: 文件列表
    :param obj_json_file: 输出文件
    :return:
    '''
    if dynasty_list is None:  # 默认为16个朝代，两汉、两宋合并了
        dynasty_list = ['先秦', '秦', '汉', '魏晋', '南北朝', '隋', '唐', '五代', '宋', '金', '辽', '元', '明', '清', '近代', '现当代']

    for i, dynasty in enumerate(os.listdir(dynasty_list)):
        filename = f'./data/{i+1}_Poetry_China_{dynasty}.json'
        with open(filename, 'r', encoding='utf-8') as f:
            poem_data = json.load(f)
            all_poems[dynasty] = poem_data
            print(f"{dynasty}诗词")
    with open(obj_json_file, 'w', encoding='utf-8') as f:
        json.dump(all_poems, f, ensure_ascii=False, indent=4)
        print(f"合并诗词到文件 {obj_json_file}")
    return


def querry_poems_by_author(author_name, author_dynasty=None):
    '''
    查询某个作者的所有诗词
    【注】：这是示例性的方法，从json中进行更多查询，可以参考该方法进行编写。
    :param author_name: 作者名
    :param author_dynasty: 作者朝代
    :return: 作者的所有诗词, 如果没有找到，则返回空列表
    '''
    global all_poems
    if all_poems is None:  # 如果还没有加载过数据，则加载
        all_poems = load_all_poems()

    ret_poems = []
    # 如果指定了朝代，则只在该朝代中查找
    if author_dynasty is not None:
        if author_dynasty in all_poems.keys(): # 如果该朝代存在
            if author_name in all_poems[author_dynasty].keys(): # 如果该作者存在
                for k in all_poems[author_dynasty][author_name]:
                    ret_poems.append(all_poems[author_dynasty][author_name][k]) # 将所有诗词添加到列表中
    else:
        # 如果没有指定朝代，则遍历所有朝代
        for dynasty in all_poems.keys():  # 遍历所有朝代
            if author_name in all_poems[dynasty].keys():    # 如果该作者存在
                for k in  all_poems[dynasty][author_name]:  # 遍历该作者的所有诗词
                    ret_poems.append(all_poems[dynasty][author_name][k]) # 将所有诗词添加到列表中

    return ret_poems


# 示例
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='data_loader')
    parser.add_argument('--src', type=str, help='输入参数')
    parser.add_argument('--obj', type=str, help='输出参数')

    parser.add_argument('--clean', action='store_true', help='数据清洗')   # bash  python data_loader.py --clean --src ./data/Poetry_China_all_(rawdata).json --obj ./data/Poetry_China_all.json

    parser.add_argument('--merge', action='store_true', help='合并所有朝代的诗词到文件')
    parser.add_argument('--save', action='store_true', help='保存所有诗词到文件') # 保存所有诗词到文件, 当内容、元数据被修改后，可以通过该方法进行保存
    parser.add_argument('--save_dynasty', action='store_true', help='将所有诗词按朝代保存到单独的json文件中') # 将所有诗词按朝代保存到单独的json文件中, 实际上，该方法更多用于将全部诗词同步到各个朝代文件夹中


    parser.add_argument('--save_all', action='store_true', help='保存所有诗词到文件')

    args = parser.parse_args()

    # 如果是从命令行中启动，带有参数和具体执行目标
    if args.src is not None:
        if args.clean:
            clean_poems(raw_file=args.src, cleaned_file=args.obj)
        if args.merge:
            merge_dynasty_poems(dynasty_list=args.src, obj_json_file=args.obj)

        if args.save:
            save_all_poems(filename=args.obj)
        if args.save_dynasty:
            save_dynasty_poems(path=args.obj)

        sys.exit(0)

    #测试
    # 数据清洗
    # clean_poems(raw_file='./data/Poetry_China_all_(rawdata).json', cleaned_file='./data/Poetry_China_all.json')

    # 合并所有诗词
    # merge_dynasty_poems(file_list=None, obj_json_file='./data/Poetry_China_all.json')

    # 加载所有诗词 （该方法为已经合并了所有诗词的json）
    all_poems = load_all_poems()
    print("收录诗词的朝代")
    print(all_poems.keys())

    # 统计每个朝代的诗词数量
    author_count, poem_count = 0, 0
    print("收录诗人的数量:")
    for i, dynasty in enumerate(all_poems.keys()):
        tmp_count = 0
        author_count += len(all_poems[dynasty])
        for author in all_poems[dynasty].keys():
            tmp_count += len(all_poems[dynasty][author])
        poem_count += tmp_count
        print(f"    {i+1}. {dynasty} {len(all_poems[dynasty])}人 {tmp_count}首")
    print(f"总计收录诗人{author_count}人，诗词{poem_count}首")


    # 查询某个作者的所有诗词
    poem_libai = querry_poems_by_author('李白')
    print(f'李白的诗，收录{len(poem_libai)}篇')

    print('END')