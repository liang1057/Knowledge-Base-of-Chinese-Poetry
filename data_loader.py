# -*- coding: utf-8 -*-
# @Time    : 2026/04/16
# @Author  : Leon
# @Email   : liang1057@163.com
# @File    : data_loader.py
# @Software: PyCharm
# @Description: 数据加载模块
# @Reference: https://github.com/luojia-ai/luojia_aishici
# @Version: 0.0.1


import os
import json

global all_poems # 全部诗词. global关键字用于声明全局变量
global dynasty_drop, author_drop # 朝代黑名单, 作者黑名单
all_poems = None
author_drop = []  # 作者排除名单
dynasty_drop = [] # 朝代排除名单

# ========== 数据加载 ==========
# 从json文件中加载所有诗词
def load_all_poems():
    '''
    加载所有诗词
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


def querry_poems_by_author(author_name, author_dynasty=None):
    '''
    查询某个作者的所有诗词
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
                for k in  all_poems[author_dynasty][author_name]:
                    ret_poems.append(all_poems[author_dynasty][author_name][k])
    else:
        # 如果没有指定朝代，则遍历所有朝代
        for dynasty in all_poems.keys():
            if author_name in all_poems[dynasty].keys():
                for k in  all_poems[dynasty][author_name]:
                    ret_poems.append(all_poems[dynasty][author_name][k])

    return ret_poems



# 示例
if __name__ == '__main__':
    # 加载所有诗词
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
        print(f"{i+1}. {dynasty} {len(all_poems[dynasty])}人 {tmp_count}首")
    print(f"总计收录诗人{author_count}人，诗词{poem_count}首")


    # 查询某个作者的所有诗词
    poem_libai = querry_poems_by_author('李白')
    print(f'李白的诗，收录{len(poem_libai)}篇')

    print('END')