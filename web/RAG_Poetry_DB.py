# -*- coding: utf-8 -*-
# @Time    : 2026/04/16
# @Author  : Leon
# @Email   : liang1057@163.com
# @File    : RAG_Poetry_DB.py
# @Project : 中华诗词知识库 Knowledge Base of Chinese Poetry (KBCP)
# @Description: Define the RelationDataBase for the RAG model.
# @Reference: https://github.com/liang1057/Knowledge-Base-of-Chinese-Poetry
# @Update:   Leon 2026/04/17
# @Version: 0.0.1


'''
根据已经整理好的Schema，进行关系型数据库整理。之所以使用关系型数据库而不是直接使用JSON（dict容器），是因为关系型数据库可以方便地进行多表关联查询，这对于RAG模型来说非常重要。
另一方面，整理的数据还要进行可视化编辑和修改，这个工作用数据库要比json文件更方便。
'''

from importlib import import_module
from RAG_Poem_Schema import *

# 用来生成对象实例。
def GenerateEntity(entity_name):
    newEntity = None
    if entity_name == 'poem':
        newEntity = table_poem()
    elif entity_name == 'author':
        newEntity = table_author()
    elif entity_name == 'dynasty':
        newEntity = table_dynasty()
    elif entity_name == 'vocab':
        newEntity = table_vocab()
    elif entity_name == 'myschema':
        newEntity = table_myschema()
    return newEntity

# 初始化schema表的内容
def init_table_data_myschema():
    tEntity = GenerateEntity('myschema')  # tname = ['schema_id', 'table_name', 'column_label', 'column_name', 'type']
    sr = SYS_RESOURCE()
    # 首先清空表 myschema, 执行sql
    sql = 'delete from myschema'
    cursor = runSQL(sql)
    if cursor is None:
        print('>>>> [waring] 清空表 myschema 失败')

    tIndex = 1
    for i, t in enumerate(sr.tables):
        # if t == 'myschema':
        #     continue
        try:
            # 尝试插入数据
            tableEntity = sr.tables[t]
            tEntity.SetValue('table_name', tableEntity.TableName())
            for j, col in enumerate(tableEntity.col_name):
                tEntity.SetValue('schema_id', f'S_{tIndex}'); tIndex +=1
                tEntity.SetValue('column_label', tableEntity.col_label[j])  # 标准字段中文名
                tEntity.SetValue('column_name', tableEntity.col_name[j])  # 标准字段键值
                tEntity.SetValue('type', tableEntity.col_type[j])  # 字段类型
                tEntity.Insert()
            print(f'>>>> [info] {i} 插入 表{tableEntity.TableName}到 schema表 信息成功')
        except Exception as e:
            # 如果插入数据失败，打印错误信息
            print('>>>> [error] insert false:', e)

# 初始化朝代表
def init_table_data_dynasty():
    tEntity = GenerateEntity('dynasty')
    # 首先清空表 dynasty, 执行sql
    sql = 'delete from dynasty'
    cursor = runSQL(sql)
    if cursor is None:
        print('>>>> [waring] 清空表 dynasty 失败')

    # 插入数据
    json_dynasty = json.load(open('./data/Dynasty.json', 'r', encoding='utf-8'))['dynasty']
    for i, d in enumerate(json_dynasty):
        try:
            tEntity.SetValue('dynasty_id', d['dynasty_id'])
            tEntity.SetValue('name', d['name'])
            tEntity.SetValue('another_name', d['another_name'])
            tEntity.SetValue('start_year', d['start_year'])
            tEntity.SetValue('end_year', d['end_year'])
            tEntity.SetValue('note', d['note'])
            tEntity.Insert()
        except Exception as e:
            print('>>>> [error] insert false:', e)
    return

class SYS_RESOURCE():
    def __init__(self):

        # 初始化方法，创建数据库表资源
        self.tables = {}  # 用于存储表的字典
        # 定义需要创建的表名列表
        table_names = ['poem', 'author', 'dynasty', 'vocab', 'myschema']
        # 遍历表名列表，为每个表创建实体对象并存储到字典中
        for t in table_names:
            t_entity = GenerateEntity(t)  # 生成表实体对象
            self.tables[t] = t_entity  # 将实体对象存入字典
        pass

    def CreateDB(self):
        """
        创建数据库表的方法
        遍历所有表，先尝试删除已存在的表，然后创建新表
        """
        # 遍历所有表
        for t in self.tables:
            # 获取创建表的SQL语句
            sql = self.tables[t].GET_SQL_Create_Table()
            try:
                # 构建删除表的SQL语句
                sql_drop = "drop table %s"%(self.tables[t].TableName())
                # 执行删除表操作（当前被注释掉）
                #Cursor().execute(sql_drop)
                Conn().execute(sql_drop)
            except:
                # 如果删除表失败，打印错误信息
                print('drop false table = %s'%(self.tables[t].TableName()))
                pass

            try:
                # 尝试创建新表
                Cursor().execute(self.tables[t].GET_SQL_Create_Table())
                print(f'create table {self.tables[t].TableName()} success')
            except:
                # 如果创建表失败，打印错误信息
                print('create false :', self.tables[t].GET_SQL_Create_Table())

        init_table_data_myschema() # 更新schema表的内容
        init_table_data_dynasty() # 更新朝代表的内容


if __name__ == '__main__':
    from data_loader import *
    conn = Conn('./dataset/kbcp.db')

    # SYS_RESOURCE().CreateDB()  # 第一次运行的时候使用，或者重做数据库的时候使用

    # init_table_data_myschema()  # 更新schema表的内容
    # init_table_data_dynasty()  # 更新朝代表的内容
    #
    # tEntity_list = Query_Entity(tTabel='dynasty', GenerateEntity=GenerateEntity, param_dict={'name': '唐'})
    # for tEntity in tEntity_list:
    #     print(tEntity.ToString())
    #
    # tEntity_list = Query_Entity(tTabel='myschema', GenerateEntity=GenerateEntity, param_dict={'table_name': 'poem'})
    # for i, tEntity in enumerate(tEntity_list):
    #     print(i+1)
    #     print(tEntity.ToString())

    '''
    {
        "先秦": {
            "诗经": {
                "诗经-晨风（鴥彼晨风）": {
                    "title": "晨风（鴥彼晨风）",
                    "author": "诗经",
                    "author_id": "A0004",
                    "dynasty": "先秦",
                    "dynasty_id": "A",
                    "content": [
                        "",
                        "𫛣彼晨风，郁彼北林。未见君子，忧心钦钦。[1]",
                        "如何如何？忘我实多！",
                        "",
                        "山有苞栎，隰有六驳。未见君子，忧心靡乐。",
                        "如何如何？忘我实多！",
                        "",
                        "山有苞棣，隰有树檖。未见君子，忧心如醉。[2]",
                        "如何如何？忘我实多！"
                    ],
    '''
    # 抓取诗词（从json）
    author_drop = ['梁振', '小伍', '与爱无关', '李燃心', '苏']
    all_poems = load_all_poems()
    print("收录诗词的朝代")
    print(all_poems.keys())

    # 统计每个朝代的诗词数量
    entity_poem = GenerateEntity('poem')
    entity_author = GenerateEntity('author')
    entity_dynasty = GenerateEntity('dynasty')
    entity_vocab = GenerateEntity('vocab')
    entity_myschema = GenerateEntity('myschema')

    author_count, poem_count = 0, 0
    print("收录诗人的数量:")
    for i, dynasty in enumerate(all_poems.keys()):
        tmp_count = 0
        author_count += len(all_poems[dynasty])
        for j, author in enumerate(all_poems[dynasty].keys()):
            tmp_count += len(all_poems[dynasty][author])
            # 插入诗人
            print(f'插入 {dynasty} 的第 {j}/{len(all_poems[dynasty])} 诗人{author} 的诗词')
            for k, poem_key in enumerate(all_poems[dynasty][author]):
                poem = all_poems[dynasty][author][poem_key]
                if k==0:
                    try:
                        entity_author.SetValue('author_id', poem['author_id'])
                        entity_author.SetValue('name', author)
                        entity_author.SetValue('dynasty', dynasty)
                        entity_author.SetValue('dynasty_id', poem['dynasty_id'])
                        entity_author.SetValue('created_at', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        entity_author.SetValue('updated_at', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        entity_author.SetValue('review_status', '未审核')
                        entity_author.Insert()
                    except:
                        print(f"插入诗人失败: {author}")

                if poem['author'] in author_drop:
                    continue
                try:
                    # 插入诗词
                    entity_poem.SetValue('title', poem['title'])
                    entity_poem.SetValue('author', poem['author'])
                    # 合并字符串list为一个字符串
                    content = '\n'.join(poem['content'])
                    # 删除开头和结尾的 '\n'和空格
                    content = content.strip('\n').strip(' ')
                    # 删除[]和括号中的数字
                    content = content.replace('[', '').replace(']', '')
                    for i_num in range(1, 10):
                        content = content.replace(f'[{i_num}]', '')
                    entity_poem.SetValue('content', content)

                    entity_poem.SetValue('dynasty', dynasty)
                    entity_poem.SetValue('created_at', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    entity_poem.SetValue('updated_at', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    entity_poem.SetValue('data_version', '1.0')
                    entity_poem.SetValue('review_status', '未审核')
                    entity_poem.Insert()
                except:
                    print(f"插入诗词失败: {poem['title']}")


        poem_count += tmp_count
        print(f"    {i+1}. {dynasty} {len(all_poems[dynasty])}人 {tmp_count}首")
    print(f"总计收录诗人{author_count}人，诗词{poem_count}首")





    # 从烟雨阁诗词库抓取数据







