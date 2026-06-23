#
# 构建中国经典诗词数据集

# 首先，诗词不需要编号，因为后续还要增加和插入很多资料
# 其次，诗词的作者和朝代信息，一般是不需要修改的。
#                朝代暂时不需要考虑编码
#                作者需要有编号，因为作者是有可能重名的，id才可以保证不重名。尽管重名的可能性比较小。作者的编号策略暂时没想很明白

import os
import json     # json文件数据集，这个格式更通用
import re
import sqlite3  # 数据库，这样更方便查找
import sys
import time
# 要保证slite数据库和json文件的一致性，同时更新。
# 动态加载py文件中的所有内容
from importlib import import_module
from data_entity import *


#朝代转换成大写字母,用于数据库的编码, 第一个是A，第二个是B，以此类推. 默认未知的是 _, 待修正
def make_dynasty_id(dynasty_list, dynasty):
    dynasty_id = '_'
    if dynasty in dynasty_list:
        dynasty_id = chr(ord('A') + dynasty_list.index(dynasty))

    return dynasty_id

author_drop = ['梁振', '小伍', '与爱无关', '李燃心', '苏']
dynasty_drop = ['不详']

# 朝代列表 分为14个朝代（包括近代现代当代）
dynasty_list = ['先秦', '秦', '汉', '魏晋','南北朝', '隋', '唐', '五代', '宋', '金', '辽', '元', '明', '清', '近代', '现当代'] # , '不详' 不详的暂时不收录了
dynasty_id_dict = {dynasty:make_dynasty_id(dynasty_list, dynasty) for dynasty in dynasty_list}
dynasty_id2name_dict = {dynasty_id_dict[dynasty]:dynasty for dynasty in dynasty_list}

# pip install opencc-python-reimplemented # 安装 opencc，进行简体/繁体互转，opencc 是 C++ 实现的底层库，Python 封装后速度较快，适合批量处理
from opencc import OpenCC
sc2tc = OpenCC('s2t')  # 简体转繁体
tc2sc = OpenCC('t2s')  # 繁体转简体

'''
# 诗词的格律 (注意，这个不是一个完整的功能，仅仅是与main中的功能抽取配合使用的)
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


# 从烟雨阁诗词软件库中提取的内容。 后面还需要重新更改，因为还要增加其他的源，这样的话，就不能单纯用同一个json文件或者追加的方式
def get_data_from_YYG(): # 从烟雨阁诗词软件库中提取的内容, 全部内容保存到 './data/Poetry_China_all.json'
    import pypyodbc
    # 请修改为你的 Access 数据库路径
    db_path = r"D:\Program Files\烟雨诗词库/YYGpoems2.mdb"  # 或 .mdb

    if not os.path.exists(db_path):
        print(f"⚠ 示例数据库不存在: {db_path}")
        print("请修改 db_path 变量指向你的 Access 文件")

    # Access 连接字符串
    conn_str = (
            r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
            r"DBQ=" + os.path.abspath(db_path) + ";"
    )
    conn = pypyodbc.connect(conn_str)
    cursor = conn.cursor()
    print(f"✓ 成功连接: {db_path}")

    """演示读取元数据"""
    # 收集数据，此时还没有清洗，只是搬过来即可
    # 诗词作者过滤

    print('抓取格律信息')
    poem_format_dict = {}
    if True: # 抓取所有的诗词格律
        tmp_poem_format = cursor.execute(f"SELECT * FROM PoemFormat").fetchall() # 抓取所有的诗词格律
        for i, p in enumerate(tmp_poem_format):
            poem_format_dict[p[1]] = p[2].strip()
        print(f'✓ 抓取格律信息 {len(poem_format_dict)} 条。')
        # 打印完成图标

        # 格律信息保存到JSON文件
        with open('./data/Poem_Format.json', 'w', encoding='utf-8') as f:
            json.dump(poem_format_dict, f, ensure_ascii=False, indent=4)

    print('抓取诗人信息')
    #author_id_raw2new = {}  # 原始id到新id，以免有错误
    author_dict_raw = {dynasty:[] for dynasty in dynasty_list} #
    author_info_dict = {}
    author_dict = {dynasty: [] for dynasty in author_dict_raw}  # 用来保存诗人信息，包括新id
    if True: # 抓取所有的诗人
        tmp_author_info = cursor.execute(f"SELECT * FROM author_china").fetchall() # 抓取所有的诗人信息
        print(f'✓ 抓取诗人信息: {len(tmp_author_info)}')
        for i, a in enumerate(tmp_author_info):
            author_id = a[2].strip()  # 这是原有的id，要替换成统一的id命名方式，因此这个在保存文件的时候要注意。
            author_info = a[1].strip() if a[1] is not None else ''
            author_info_dict[author_id] = author_info

        tmp_author = cursor.execute(f"SELECT * FROM author").fetchall()
        print(f'✓ 抓取诗人: {len(tmp_author)}')
        for i, a in enumerate(tmp_author):
            author_id = a[3].strip() # 原始的id，这个后面要替换成我的ID。因为朝代、顺序号可能都要变
            author_name = a[2].strip()
            author_dynasty = a[1].strip()
            if author_name in author_drop or author_dynasty in dynasty_drop:
                continue
            dynasty_id = dynasty_id_dict[author_dynasty]
            #author_new_id = f'{dynasty_id}-{len(author_dict_raw[author_dynasty]) + 1:04d}'  # 作者的统一ID
            #author_id_raw2new[author_id] = author_new_id
            data_item = {
                        "id": author_id,
                        "name": author_name,
                        "dynasty": author_dynasty,
                        "info": author_info_dict[author_id] if author_id in author_info_dict else '',
                        #"new_id": author_new_id,
                        }
            # 按朝代来做第一层
            if author_dynasty in author_dict_raw:
                if author_name in author_dict_raw[author_dynasty]:
                    print(f'⚠ 诗人重名: {author_name}',
                          f'已有{author_dict_raw[author_dynasty][author_name]["num"]}个，'
                          f'{author_dict_raw[author_dynasty][author_name]["dynasty"]}, 新的为{author_dynasty}')
                    author_dict_raw[author_name]['num'] += 1
                # 增加到容器中
                author_dict_raw[author_dynasty].append(data_item)
            else:
                author_dict_raw[author_dynasty] = [data_item]
        # 增加已知有遗漏的
        data_item_add = {
            'id': 'O0015',
            'name':'金庸',
            "dynasty": '现当代',
            "info": '（1924年3月10日—2018年10月30日），本名查良镛，祖籍浙江省海宁市，1948年移居香港。当代武侠小说作家、新闻学家、企业家',

        }
        author_dict_raw[data_item_add['dynasty']].append(data_item_add)
        # 保存到文件
        with open('./data/Author_(rawdata).json', 'w', encoding='utf-8') as f:
            json.dump(author_dict_raw, f, ensure_ascii=False, indent=4)

        # ret = input("Warning: 如有问题需要打开文件进行修改，修改完成请输入y，按回车...").strip()
        # if ret.lower() == 'y':
        #     print('继续进行')
        # else:
        #     print('退出程序')
        #     os.exit(0)
        print('⚠ Warning: 如有问题需要打开文件进行修改')

        # 整理info的内容，清洗一下
        for i, d in enumerate(author_dict):
            author_list = author_dict_raw[d]
            for j, a in enumerate(author_list):
                author_dynasty = a['dynasty']
                dynasty_id = dynasty_id_dict[author_dynasty]
                author_new_id = f'{dynasty_id}-{len(author_dict[author_dynasty]) + 1:04d}'  # 作者的统一ID
                author_name = a['name']
                str_info = a['info'].replace('【作者小传】：', '').replace('\r\n', '\n').replace('\n\n', '\n').replace('\r', '\n').strip()
                data_item = {
                    "author_id": author_new_id,
                    "author_name": author_name,
                    "dynasty": author_dynasty,
                    "dynasty_id": dynasty_id_dict[author_dynasty],
                    "info": str_info,
                }
                author_dict[author_dynasty].append(data_item)
        # 保存到文件
        with open('./data/Author.json', 'w', encoding='utf-8') as f:
            json.dump(author_dict, f, ensure_ascii=False, indent=4)

    def find_author(dynasty, author_name):
        if dynasty in author_dict:
            author_list = author_dict[dynasty]
            for j, a in enumerate(author_list):
                if a['author_name'] == author_name:
                    return a
        return None
    def find_author_by_old_id(author_id):
        for i, dynasty in enumerate(author_dict):
            author_list = author_dict_raw[dynasty]
            for j, a in enumerate(author_list):
                if a['id'] == author_id:
                    return a
        return None





    dynasty_poem_dict = {}  # {朝代:{作者:[poem_data]}},  其中 poem_data是一个{}
    for d in dynasty_list:
        dynasty_poem_dict[d] = {}

    time1 = time.time()
    print('抓取诗词')
    if True: # 抓取所有的诗词
        tmp_poem = cursor.execute(f"SELECT * FROM poem_china").fetchall() # 抓取所有的诗词
        print(f'✓ 抓取诗词: {len(tmp_poem)} 条')
        for i, poem in enumerate(tmp_poem):
            # 分解元数据项
            dynasty = poem[1].strip()
            if dynasty not in dynasty_list: # 去除一些朝代
                continue

            dynasty_id = dynasty_id_dict[dynasty]
            author = poem[3].strip()
            author_old_id = poem[4].strip()
            if author in author_drop or dynasty in dynasty_drop:  # 排除指定的作者和年代
                continue

            try:  # 这里只是提醒
                author_name = find_author_by_old_id(author_old_id)['name']
                if author_name != author:
                    print(f'⚠ 诗人名称不一致: {i}, old_id={author_old_id}, author_table={author_name}, poem_table={author}')
                    # 核查发现一般是旧的id标注错了，因此要修改成新的
                    if author.__contains__('危稹'):
                        author = '危稹'   # 这是一个已知错误
                    else:
                        try:
                            author_id = find_author(dynasty, author)['author_id']
                        except:
                            print(f'⚠ find_author 诗人信息缺失: {author} {dynasty}，id为空')
                            author_id = ''
                    print(f'    √诗人名称以诗词表为准={author}，将id修改为新的id={author_id}')
                else:
                    author_id = find_author(dynasty, author)['author_id']
            except:
                print(f'⚠ find_author_by_old_id 诗人信息缺失: old_id={author_old_id}, {author}, {dynasty}')
                author_id = ''

            title = poem[5].strip()
            content = poem[7]
            discription = ''
            if poem[8] is not None:
                discription = poem[8]

            poem_data = {
                "title": title,
                "author": author,
                "author_id": author_id,
                "dynasty": dynasty,
                "dynasty_id": dynasty_id,
                "content": content,
                "discription": discription,
            }
            # 将结构化的内容放入dict中，方便后面转换成json
            if dynasty in dynasty_poem_dict:
                if author in dynasty_poem_dict[dynasty]:
                    dynasty_poem_dict[dynasty][author].append(poem_data)
                else:
                    dynasty_poem_dict[dynasty][author] = [poem_data]
            else:
                dynasty_poem_dict[dynasty] = {author:[poem_data]}

            # # 下面是清洗后的
            # dynasty_id = dynasty_id_dict[dynasty] #poem[2].strip() # make_dynasty_id(dynasty)
            # author = poem[3].strip()
            # author_id = poem[4].strip()
            # title_list = poem[5].strip().split('（')
            # title = title_list[0] # 去掉括号前的内容
            # content_title = title_list[1].replace('）', '').strip() if len(title_list) > 1 else '' # 括号后的内容
            # tmp_content = poem[7].replace('\r\n', '\n').replace('\r', '\n')
            # if dynasty not in ['近代', '现当代']:  # 散文诗暂时先不替换，先按时代卡
            #     tmp_content = tmp_content.replace('，\n', '，').replace('。\n', '。')  # 去掉逗号和句号后面的换行，然后统一转成换行的
            #     tmp_content = tmp_content.replace('，', '，\n').replace('。', '。\n')  # 统一转成换行的
            # content_list = tmp_content.split('\n')
            # for i in range(len(content_list) - 1, -1, -1):
            #     if content_list[i].__contains__('【'):  # 去掉解释性的行
            #         content_list.pop(i)
            # content_txt = '\n'.join(content_list).strip()
            # #content_sc_list = content_txt.split('\n')  # 按行分割，简体中文的
            # poem_format = get_poem_format(tmp_content, content_txt, poem_format_dict, dynasty) # 获取诗词的格律
            #
            # if author_name in author_drop or author_dynasty in dynasty_drop: # 去除指定的作者
            #     continue
            #
            # discription = ''
            # if poem[8] is not None:
            #     discription = poem[8].replace('\r\n', '\n').replace('\r', '\n').replace('【注释】：', '').strip()
            #
            # poem_data = {
            #     "title": title,
            #     "content_title": content_title, # 正文题
            #     "author": author,
            #     "author_id": author_id,
            #     "dynasty": dynasty,
            #     "dynasty_id": dynasty_id,
            #     "content": content_txt,
            #     #"content_TC": content_tc,  # 繁体中文的不需要
            #     "discription": discription,
            #     "format": poem_format
            # }
            #
            # # 将结构化的内容放入dict中，方便后面转换成json
            # if dynasty in dynasty_poem_dict:
            #     if author in dynasty_poem_dict[dynasty]:
            #         dynasty_poem_dict[dynasty][author][f'{author}-{title}'] = poem_data
            #     else:
            #         dynasty_poem_dict[dynasty][author] = {f'{author}-{title}': poem_data}
            # else:
            #     dynasty_poem_dict[dynasty] = {author:{f'{author}-{title}': poem_data}}

        json_text = json.dumps(dynasty_poem_dict, ensure_ascii=False, indent=4) # 将字典转换为 JSON 字符串, 并确保非 ASCII 字符被正确处理, 并缩进为4个空格

        # 全部的诗词保存一个文件
        with open('./data/Poetry_China_all_(rawdata).json', 'w', encoding='utf-8') as f:
            f.write(json_text)
            f.close()

    # 各个朝代的统计， 每个朝代写一个文件
    author_count, poem_count = 0, 0
    author_dict = {}   # 诗人 {序号: [id, 姓名，朝代]}
    for i, dynasty in enumerate(dynasty_poem_dict.keys()):
        n = 0
        for j, author in enumerate(dynasty_poem_dict[dynasty].keys()):
            n += len(dynasty_poem_dict[dynasty][author])
            author_dict[len(author_dict)+1] = [author, dynasty]
        print(f'{i} {dynasty}  收集诗人: {len(dynasty_poem_dict[dynasty])}  收集诗篇: {n}')
        author_count += len(dynasty_poem_dict[dynasty])
        poem_count += n
    print(f'总收集诗人: {author_count}  总收集诗篇: {poem_count}')
    print(f'耗时: {(time.time()-time1):.2f} 秒')



if __name__ == '__main__':
    get_data_from_YYG()

    print('END')


    ''' --------------------------------------------------------  '''


    # # 诗词作者过滤
    # author_drop = ['梁振', '小伍', '与爱无关', '李燃心', '苏']
    #
    # # 从烟雨阁诗词库抓取数据
    # import pypyodbc
    # """演示读取元数据"""
    # # 请修改为你的 Access 数据库路径
    # db_path = r"D:\Program Files\烟雨诗词库/YYGpoems.mdb"  # 或 .mdb
    #
    # if not os.path.exists(db_path):
    #     print(f"⚠ 示例数据库不存在: {db_path}")
    #     print("请修改 db_path 变量指向你的 Access 文件")
    #
    # # Access 连接字符串
    # conn_str = (
    #         r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
    #         r"DBQ=" + os.path.abspath(db_path) + ";"
    # )
    # conn = pypyodbc.connect(conn_str)
    # cursor = conn.cursor()
    # print(f"✓ 成功连接: {db_path}")
    #
    # print('抓取格律信息')
    # poem_format_dict = {}
    # tmp = cursor.execute(f"SELECT * FROM PoemFormat").fetchall() # 抓取所有的诗词格律
    # for i, p in enumerate(tmp):
    #     poem_format_dict[p[1]] = p[2].strip()
    # print('✓ 抓取格律信息')
    # # 保存到JSON文件
    # with open('./data/Poem_Format.json', 'w', encoding='utf-8') as f:
    #     json.dump(poem_format_dict, f, ensure_ascii=False, indent=4)
    #
    #
    # # 从诗词中整理出朝代表
    # dynasty_poem_dict = {}  # {朝代:{作者-题目:poem_data}}, 其中 poem_data是一个{}
    # for d in dynasty_list:
    #     dynasty_poem_dict[d] = {}
    #
    # time1 = time.time()
    # tmp = cursor.execute(f"SELECT * FROM poem_china").fetchall() # 抓取所有的诗词
    # print(f'✓ 抓取诗词: {len(tmp)}')
    # for i, poem in enumerate(tmp):
    #     # 分解元数据项
    #     dynasty = poem[1].strip()
    #     dynasty_id = dynasty_id_dict[dynasty] #poem[2].strip() # make_dynasty_id(dynasty)
    #     author = poem[3].strip()
    #     author_id = poem[4].strip()
    #     title_list = poem[5].strip().split('（')
    #     title = title_list[0] # 去掉括号前的内容
    #     content_title = title_list[1].replace('）', '').strip() if len(title_list) > 1 else '' # 括号后的内容
    #     tmp_content = poem[7].replace('\r\n', '\n').replace('\r', '\n')
    #     if dynasty not in ['近代', '现当代']:  # 散文诗暂时先不替换，先按时代卡
    #         tmp_content = tmp_content.replace('，\n', '，').replace('。\n', '。')  # 去掉逗号和句号后面的换行，然后统一转成换行的
    #         tmp_content = tmp_content.replace('，', '，\n').replace('。', '。\n')  # 统一转成换行的
    #     content_list = tmp_content.split('\n')
    #     for i in range(len(content_list) - 1, -1, -1):
    #         if content_list[i].__contains__('【'):  # 去掉解释性的行
    #             content_list.pop(i)
    #     content_txt = '\n'.join(content_list).strip()
    #     content_sc_list = content_txt.split('\n')  # 按行分割，简体中文的
    #     poem_format = get_poem_format(tmp_content, content_txt) # 获取诗词的格律
    #
    #     if author in author_drop: # 去除一些作者
    #         continue
    #
    #     discription = ''
    #     if poem[8] is not None:
    #         discription = poem[8].replace('\r\n', '\n').replace('\r', '\n').replace('【注释】：', '').strip()
    #
    #     poem_data = {
    #         "title": title,
    #         "content_title": content_title, # 正文题
    #         "author": author,
    #         "author_id": author_id,
    #         "dynasty": dynasty,
    #         "dynasty_id": dynasty_id,
    #         "content": content_sc_list,
    #         #"content_TC": content_tc,  # 繁体中文的不需要
    #         "discription": discription,
    #         "format": poem_format
    #     }
    #
    #     # 将结构化的内容放入dict中，方便后面转换成json
    #     if dynasty in dynasty_poem_dict:
    #         if author in dynasty_poem_dict[dynasty]:
    #             dynasty_poem_dict[dynasty][author][f'{author}-{title}'] = poem_data
    #         else:
    #             dynasty_poem_dict[dynasty][author] = {f'{author}-{title}': poem_data}
    #     else:
    #         dynasty_poem_dict[dynasty] = {author:{f'{author}-{title}': poem_data}}
    #
    # json_text = json.dumps(dynasty_poem_dict, ensure_ascii=False, indent=4) # 将字典转换为 JSON 字符串, 并确保非 ASCII 字符被正确处理, 并缩进为4个空格
    #
    # # 全部的诗词保存一个文件
    # with open('Poetry_China_all.json', 'w', encoding='utf-8') as f:
    #     f.write(json_text)
    #     f.close()
    #
    # test_all_json = json.load(open('Poetry_China_all.json', 'r', encoding='utf-8')) # 读取 JSON 文件测试
    #
    # # 各个朝代的统计， 每个朝代写一个文件
    # author_count, poem_count = 0, 0
    # author_dict = {}   # 诗人 {序号: [id, 姓名，朝代]}
    # for i, dynasty in enumerate(dynasty_poem_dict.keys()):
    #     n = 0
    #     for j, author in enumerate(dynasty_poem_dict[dynasty].keys()):
    #         n += len(dynasty_poem_dict[dynasty][author])
    #         author_dict[len(author_dict)+1] = [author, dynasty]
    #     #print(k, '诗人:', len(dynasty_poem_dict[k]), '  诗篇:', n)
    #     print(f'{i} {dynasty}  收集诗人: {len(dynasty_poem_dict[dynasty])}  收集诗篇: {n}')
    #     author_count += len(dynasty_poem_dict[dynasty])
    #     poem_count += n
    # print(f'总收集诗人: {author_count}  总收集诗篇: {poem_count}')
    # print(f'耗时: {(time.time()-time1):.2f} 秒')
    #
    # # 诗人保存一个文件
    # json_author = json.dumps(author_dict, ensure_ascii=False, indent=4)
    # with open('诗人.json', 'w', encoding='utf-8') as f:
    #     f.write(json_author)
    #     f.close()
    # print('END')

    # ----------------------------------------

    #
    # poem_dict = {}
    # json_text = ''
    # for i, poem in enumerate(tmp):
    #     dynasty = poem[1]
    #     dynasty_id = poem[2] # make_dynasty_id(dynasty)
    #     author = poem[3]
    #     author_id = poem[4]
    #     title = poem[5]
    #     content_list = poem[7].split('【内容】：')
    #     content = ''
    #     if len(content_list) > 1:
    #         content = content_list[1].replace('\r', '\n').replace('\n\n', '\n').replace(' ', '&nbsp;') # 替换空格
    #         if content.startswith('\n'):
    #             content = content[1:]
    #     discription = ''
    #     if poem[8] is not None:
    #         discription = poem[8].replace('\r', '\n').replace('\n\n', '\n').replace('【注释】：', '')
    #
    #     json_data = {
    #         "title": title,
    #         "author": author,
    #         "author_id": author_id,
    #         "dynasty": dynasty,
    #         "dynasty_id": dynasty_id,
    #         "content": tc2sc.convert(content),
    #         "content_TC": sc2tc.convert(content),
    #         "discription": ""
    #     }
    #
    #     json_text += json.dumps(json_data, ensure_ascii=False, indent=4) # 将字典转换为 JSON 字符串, 并确保非 ASCII 字符被正确处理, 并缩进为4个空格
    #     json_text += '\n'
    #
    # with open('poem_china.json', 'w', encoding='utf-8') as f:
    #     f.write(json_text)
    #     f.close()
    #
    # all_json = json.load(open('poem_china.json', 'r', encoding='utf-8'))
