# -*- coding: utf-8 -*-

import sqlite3
import uuid
import codecs
import os
import numpy as np
import datetime
import json
from abc import ABC, abstractmethod # 抽象基类
from typing import Any, List, Tuple

# 连接数据库(如果不存在则创建)
global SYS_DB_CONNECT
global SYS_DB_CURSOR
SYS_DB_CURSOR = None
SYS_DB_CONNECT = None

def CreateID():
    return uuid.uuid1()

def Conn(dbName = './vadb.dat'):
    global SYS_DB_CONNECT
    global SYS_DB_CURSOR
    if SYS_DB_CONNECT == None:
        hasDB = os.path.exists(dbName)
        SYS_DB_CONNECT = sqlite3.connect(dbName)
        if SYS_DB_CONNECT == None:
            print("Opened database fault")
            return None
        else:
            print ("Opened database successfully")
        SYS_DB_CURSOR = SYS_DB_CONNECT.cursor()
        if hasDB == False:
            return None
    return  SYS_DB_CONNECT

def Cursor():
    global SYS_DB_CONNECT
    global SYS_DB_CURSOR
    if SYS_DB_CURSOR == None:
        hasDB = os.path.exists('./vadb.dat')
        SYS_DB_CONNECT = Conn('./vadb.dat') # sqlite3.connect('./vadb.dat')
        #SYS_DB_CONNECT = sqlite3.exec('./vadb.dat')
        if SYS_DB_CONNECT == None:
            print("Opened database fault")
            return None
        else:
            print ("Opened database successfully")
        SYS_DB_CURSOR = SYS_DB_CONNECT.cursor()
        if hasDB == False:
            return None

    return SYS_DB_CURSOR



def serialize(value: Any) -> Tuple[str, Any]:
    """
    将任意类型序列化为 SQLite 可存储格式。
    返回 (type_tag, storage_value)
    """
    if isinstance(value, str):
        return ("str", value)
    elif isinstance(value, int):
        return ("int", value)
    elif isinstance(value, float):
        return ("float", value)
    elif isinstance(value, list) and value and all(isinstance(x, str) for x in value):
        return ("list_str", json.dumps(value, ensure_ascii=False))
    elif isinstance(value, list) and value and all(isinstance(x, int) for x in value):
        return ("list_int", json.dumps(value))
    elif isinstance(value, list) and value and all(isinstance(x, float) for x in value):
        return ("list_float", json.dumps(value))
    elif isinstance(value, np.ndarray):
        return ("ndarray", json.dumps({
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "data": value.tobytes().hex()
        }))
    elif value is None:
        return ("null", None)
    else:
        return ("json", json.dumps(value, ensure_ascii=False, default=str))


def deserialize(type_tag: str, storage_value: Any) -> Any:
    """
    根据 type_tag 反序列化。
    """
    if type_tag == "str":
        return storage_value
    elif type_tag == "int":
        return int(storage_value)
    elif type_tag == "float":
        return float(storage_value)
    elif type_tag == "list_str":
        return json.loads(storage_value)
    elif type_tag == "list_int":
        return [int(x) for x in json.loads(storage_value)]
    elif type_tag == "list_float":
        return [float(x) for x in json.loads(storage_value)]
    elif type_tag == "ndarray":
        d = json.loads(storage_value)
        return np.frombuffer(bytes.fromhex(d["data"]), dtype=d["dtype"]).reshape(d["shape"])
    elif type_tag == "null":
        return None
    else:
        return json.loads(storage_value)

'''
# 实体基类
'''
class EntityBase():
    def __init__(self):
        self.table_name = ''  # 表名
        self.col_name = []    # 字段名
        self.col_type = []    # 字段类型
        self.col_label = []   # 字段标签
        self.col_value = {}   # 字段值
        self.col_type_dict = {} # 字段类型字典

    '''
    # 创建ID，全局唯一
    '''
    def GenerateID(self, colID='KeyID'):
        id = uuid.uuid1()
        self.SetValue(colID, str(id))

    '''
    # 设置Table名称，令实体对应于一个指定的表
    '''
    def SetTableName(self, tName):
        self.table_name = tName

    '''
    # Table名称
    '''
    def TableName(self):
        return  self.table_name

    '''
    # 为实体设置数据：字段名、字段值
    '''
    def SetValue(self, colNmae, colValue):
        if self.col_name.__contains__(colNmae):
            #if self.col_type_dict[colNmae].lower() == 'varchar' and (type(colValue) is str):  # 如果字段类型是varchar，则将json转换成类型
            if self.col_type_dict[colNmae].lower() == 'varchar':
                self.col_value[colNmae] = json.dumps(colValue, ensure_ascii=False) # dict先转换成json格式的文本
            else:
                self.col_value[colNmae] = colValue  # 直接赋值，比如list或dict
            return True
        else:
            return False

    def Value(self, colNmae):
        if self.col_name.__contains__(colNmae):
            if self.col_type_dict[colNmae].lower() == 'varchar':
                return json.loads(self.col_value[colNmae])
            else:
                return self.col_value[colNmae]
        else:
            # if self.col_type == 'numeric':
            #     return 0
            # return ''
            return None

    '''
    # 为实体增加列。（这是用于构建实体定义和数据库的，不是用来做应用的，不可以随意调用）
    '''
    def AddColumn(self, colName, colType, colLabel=None):
        self.col_name.append(colName)
        self.col_type.append(colType)
        self.col_type_dict[colName] = colType
        if colType.lower() == 'text':
            self.col_value[colName] = ''
        elif colType.lower() == 'numeric' or colType.lower().__contains__('int') or colType.lower().__contains__('float') or colType == 'double':
            self.col_value[colName] = 0
        elif colType.lower() == 'datetime':
            dt = str(datetime.datetime.today()).split('.')[0]
            self.col_value[colName] = dt
        elif colType.lower() == 'varchar':
            self.col_value[colName] = ''
        else:
            self.col_value[colName] = None

        if colLabel==None:
            self.col_label.append(colName)
        else:
            self.col_label.append(colLabel)


    '''
    # 增加多个列
    '''
    def AddColumns(self, colNames, colTypes, colLabels=None):
        if colLabels==None:
            colLabels = colNames

        for i in range(len(colNames)):
            self.AddColumn(colNames[i], colTypes[i], colLabels[i])

    '''
    # 创建对应表的SQL语句
    '''
    def GET_SQL_Create_Table(self):
        sql = ''
        sql += "create table %s ("%(self.table_name)
        for i in range(len(self.col_name)):
            sql += "%s %s,"%(self.col_name[i], self.col_type[i])
        sql = sql[0 : len(sql)-1]
        sql += ")"
        return  sql

    '''
    # 将实体插入数据库
    '''
    def Insert_old(self):
        sql = ''
        sql += f'insert into {self.table_name} ('  # "insert into %s ("%(self.table_name)
        for i in range(len(self.col_name)):
            sql +=  f'{self.col_name[i]},' # "%s,"%(self.col_name[i])
        sql = sql[0 : len(sql)-1]
        sql += ") values ("
        for i in range(len(self.col_name)):
            if self.col_type[i] == 'numeric' or self.col_type[i].lower().__contains__('int') or self.col_type[i].lower().__contains__('float') or self.col_type[i] == 'double':
                sql += f"{self.col_value[self.col_name[i]]},"  # "%s,"%(self.col_value[self.col_name[i]])
            elif self.col_type[i] == 'varchar':  # 转换成字符串存起来
                tmp = str(self.col_value[self.col_name[i]]).replace("\'", '\"')   # json.dumps(self.col_value[self.col_name[i]])
                sql += f"\'{tmp}\',"
            else:
                sql += f"'{self.col_value[self.col_name[i]]}',"  # "'%s',"%(self.col_value[self.col_name[i]])
        sql = sql[0 : len(sql)-1]
        sql += ")"
        sql = sql.replace('None', 'null')
        c = Cursor()
        try:
            c.execute(sql)
            Conn().commit()
            #print('>>> create sql: ', sql)
        except:
            print('>>> error: ', sql)
            pass
    def Insert(self):
        str_col_names, str_ps = '', ''
        params_list = []
        for i in range(len(self.col_name)):
            str_col_names += f'{self.col_name[i]},'
            str_ps += '?,'
            params_list.append(self.col_value[self.col_name[i]])
        sql = f'INSERT INTO {self.table_name} ({str_col_names.strip(",")}) VALUES ({str_ps.strip(",")})'
        params = tuple(params_list)
        c = Cursor()
        try:
            c.execute(sql, params)
            Conn().commit()
            #print('>>> create sql: ', sql)
        except Exception as e:
            print('>>> error: ', e)
            pass

    '''
    # 将实体在数据库中更新
    '''
    def Update(self, tryModel=False):
        sql = ''
        sql += "UPDATE %s SET "%(self.table_name)
        for i in range(len(self.col_name)):
            if self.col_type[i] != 'numeric':
                sql += "%s='%s',"%(self.col_name[i], self.col_value[self.col_name[i]])
            else:
                sql += "%s=%s,"%(self.col_name[i], self.col_value[self.col_name[i]])
        sql = sql[0 : len(sql)-1]
        sql += " WHERE KeyID='%s'" % (self.col_value['KeyID'])
        if tryModel==True:
            try:
                Cursor().execute(sql)
                Conn().commit()
                #print('>>> create sql: ', sql)
            except:
                print('>>> error: ', sql)
                pass
        else:
            Cursor().execute(sql)
            Conn().commit()

    '''
    # 实体转换成String类型
    '''
    def ToString(self, swap=True):
        txt = ''
        for i in range(len(self.col_name)):
            txt += '%s(%s): %s'%(self.col_name[i], self.col_label[i], self.col_value[self.col_name[i]])
            if swap == True:
                txt += '\n'
            else:
                txt += ','
        return txt

    '''
    # 实体转换成Json
    '''
    def ToJson(self, ea=False):
        tDict = {}
        tDict['talbe_name'] = self.table_name
        tDict['column_name'] =  self.col_name
        tDict['column_type'] =  self.col_type
        tDict['column_label'] =  self.col_label
        tDict['column_value'] =  self.col_value
        jsn = json.dumps(tDict, ensure_ascii=ea)
        return jsn

        # txt = '{"%s":['%(self.table_name)
        # for i in range(len(self.col_name)):
        #     txt += '{'
        #     txt += '"col": "%s",'%(self.col_name[i])
        #     txt += '"label": "%s",'%(self.col_label[i])
        #     txt += '"format": "%s",'%(self.col_type[i])
        #     if self.col_type[i] == 'numeric':
        #         txt += '"value": %s'%(self.col_value[self.col_name[i]])
        #     else:
        #         txt += '"value": "%s"'%(self.col_value[self.col_name[i]])
        #     txt += '}'
        #     if i < len(self.col_name)-1:
        #         txt += ','
        # txt += ']}'
        # return txt

    def FromJson(self, jsn):
        tDict = json.loads(jsn)
        self.table_name = tDict['talbe_name']
        self.col_name = tDict['column_name']
        self.col_type = tDict['column_type']
        self.col_label = tDict['column_label']
        self.col_value = tDict['column_value']
        return



'''
# 批量添加
'''
def InsertMany(entityList = []):
    if entityList == []:
        return
    sql = "insert into %s VALUES("%(entityList[0].table_name)
    tValues = []
    for i in range(len(entityList[0].col_name)):
        sql += '?,'
    sql = sql[0:-1]
    sql += ')'

    for i in range(len(entityList)):
        if entityList == []:
            return
        tVals = []
        for j in range(len(entityList[0].col_name)):
            if entityList[0].col_name[j] == 'KeyID':
                tVals.append((str)(entityList[i].Value(entityList[0].col_name[j])))
            else:
                tVals.append(entityList[i].Value(entityList[0].col_name[j]))
        tValues.append(tVals)

    Conn().executemany(sql, tValues)


'''
# 批量提交
但是仍然不快
'''
def UpdateMany(self, entityList = []):
    #flag_List = entityList[0].col_name
    # id_List = []
    # for i in range(len(entityList)):
    #     id_List.append(entityList[i].Value('KeyID'))

    sql = "update %s SET "%(entityList[0].table_name)
    for i in range(len(entityList[0].col_name)):
        if entityList[0].col_name[i] == 'KeyID':
            continue
        # sql += "%s=" % (entityList[0].col_name[i]) + ("(%s),")
        if entityList[0].col_type[i] != 'numeric':
            #sql += "%s="%(entityList[0].col_name[i]) + ("'%s',")
            sql += "%s=" % (entityList[0].col_name[i]) + "(?),"
        else:
            sql += "%s=" % (entityList[0].col_name[i]) + "(?),"
            #sql += "%s=%s," % (entityList[0].col_name[i], entityList[0].col_value[entityList[0].col_name[i]])
            #sql += "%s=" % (entityList[0].col_name[i]) + ("%s,")
    sql = sql[0:-1]
    sql += " where KeyID=(?)"

    commit_id_list = [] #[(flag_List[i], id_List[i]) for i in range(len(id_List))]
    # sql = "update %s SET flag=(%s) where KeyID=(%s)"%(entityList[0].table_name)
    for i in range(len(entityList)):
        tVals = []
        for j in range(len(entityList[0].col_name)):
            if entityList[0].col_name[j] == 'KeyID':
                continue
                tVals.append((str)(entityList[i].Value(entityList[0].col_name[j])))
            else:
                tVals.append(entityList[i].Value(entityList[0].col_name[j]))
            # if entityList[0].col_type[i] != 'numeric':
            #     tVals.append((str)(entityList[i].Value(entityList[0].col_name[j])))
            # else:
            #     tVals.append((str)(entityList[i].Value(entityList[0].col_name[j])))
        tVals.append((str)(entityList[i].Value('KeyID')))
        commit_id_list.append(tVals)
    try:
        Cursor().executemany(sql, commit_id_list)  # commit_id_list上面已经说明
        Conn().commit()
    except Exception as e:
        print('>>> return', e)

    # tValues = []
    # for i in range(len(entityList[0].col_name)):
    #     sql += '?,'
    # sql = sql[0:-1]
    # sql += ')'
    #
    # for i in range(len(entityList)):
    #     tVals = []
    #     for j in range(len(entityList[0].col_name)):
    #         tVals.append((str)(entityList[i].Value(entityList[0].col_name[j])))
    #     tValues.append(tVals)
    #
    # Conn().executemany(sql, tValues)

'''
# 创建指定的实体
# 这个需要重构，默认只能返回None
'''
# def GenerateEntity(className):
#     """子类必须实现此方法"""
#     return None


'''
# 根据ID查找实体
'''
def Query_Entity_byID(tTabel, tID, GenerateEntity):
    sql = "select * from data_project where KeyID='%s'"%(tID)
    cursor = Cursor().execute(sql)
    for row in cursor:
        tEntity = GenerateEntity(tTabel)
        for i in range( len(tEntity.col_name)):
            tEntity.SetValue(tEntity.col_name[i], row[i])
        return tEntity
    return None

'''
# 根据属性查找实体
# param_dict=None 为全部
'''
def Query_Entity(tTabel, GenerateEntity, param_dict=None):
    if tTabel == None:
        return []
    tmpEntity = GenerateEntity(tTabel)
    strWhere = ''
    if param_dict != None:
        strWhere = "where ( "
        for p in param_dict:
            # print('>>> p = ', p)
            if tmpEntity.col_name.__contains__(p):
                tIndex = tmpEntity.col_name.index(p)
                tType = tmpEntity.col_type[tIndex]
                if tType == 'numeric':
                    strWhere += "%s=%s,"%(p, param_dict[p])
                else:
                    strWhere += "%s='%s',"%(p, param_dict[p])
        strWhere = strWhere[0: len(strWhere)-1] + ")"
    else:
        strWhere = ''
    sql = "select * from %s %s"%(tTabel, strWhere.replace(',', ' and '))
    retEntities = []
    # print(sql)
    cursor = Cursor().execute(sql)
    for row in cursor:
        tEntity = GenerateEntity(tTabel)
        for i in range( len(tEntity.col_name)):
            tEntity.SetValue(tEntity.col_name[i], row[i])
        retEntities.append(tEntity)
    return retEntities


'''
# 执行sql语句
# sql 为执行语句
'''
def runSQL(sql):
    try:
        cursor = Cursor().execute(sql)
        return cursor
    except Exception as e:
        print('>>>> run sql false:', e)
        return None


'''
# 根据属性查找一个实体
# param_dict 为查询条件
'''
def Query_One_Entity(tTabel, param_dict, GenerateEntity):
    if tTabel == None:
        return []
    tmpEntity = GenerateEntity(tTabel)
    strWhere = "where ( "
    for p in param_dict:
        # print('>>> p = ', p)
        if tmpEntity.col_name.__contains__(p):
            tIndex = tmpEntity.col_name.index(p)
            tType = tmpEntity.col_type[tIndex]
            if tType == 'numeric':
                strWhere += "%s=%s,"%(p, param_dict[p])
            else:
                strWhere += "%s='%s',"%(p, param_dict[p])
    strWhere = strWhere[0: len(strWhere)-1] + ")"
    sql = "select * from %s %s limit 1"%(tTabel, strWhere.replace(',', ' and '))
    # print(sql)
    cursor = Cursor().execute(sql)
    for row in cursor:
        tEntity = GenerateEntity(tTabel)
        for i in range( len(tEntity.col_name)):
            tEntity.SetValue(tEntity.col_name[i], row[i])
        return tEntity
    return None

'''
# 工区表
'''

#if __name__=='__main__':
    # 创建工区数据库
    # Conn(dbName = './vadb-2021.dat')
    # table = myTable
    # try:
    #     Cursor().execute(table.GET_SQL_Create_Table())
    # except:
    #     print('create false :', table.GET_SQL_Create_Table())


