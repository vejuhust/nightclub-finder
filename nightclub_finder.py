#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib
import urllib2
import cookielib
import json
import md5
import StringIO
import gzip
import sqlite3
import os
import time
import datetime
import math
import re


#帐号密码
weixin_username = "**USER**"
weixin_password = "**PASSWORD**"



#百度地图的API Key
map_apikey_pool = [
                   "**PLACE_API1**",
                   "**PLACE_API2**",
                   "**PLACE_API3**",
                   "**PLACE_API4**",
                   "**PLACE_API5**"
                   ]
map_apikey_pointer = 0




#限定数值
search_result_limit = 8
search_keyword = [u"夜总会", u"酒吧"] #u"餐厅" #u"蘑菇" #u"洗手间" #u"酒吧" #u"夜总会" #
search_radius = 5000
database_filename = "message.db"
cookie_time_limit = 7200
weixin_refresh_interval = 3
weixin_timeout = 2



#各种常量
weixin_url_login = "http://mp.weixin.qq.com/cgi-bin/login"
weixin_url_message = "http://mp.weixin.qq.com/cgi-bin/getmessage?t=wxm-message&lang=zh_CN&count=50"
weixin_url_send = "http://mp.weixin.qq.com/cgi-bin/singlesend?t=ajax-response&lang=zh_CN"
weixin_url_wait = "http://mp.weixin.qq.com/cgi-bin/getnewmsgnum?t=ajax-getmsgnum&lastmsgid=%d"
map_url_geocoder = "http://api.map.baidu.com/geocoder?output=json&location=%f,%f&key=%s"
map_url_place = "http://api.map.baidu.com/place/search?&query=%s&location=%f,%f&radius=%d&output=json&key=%s"

weixin_headers = {
    'Accept-Encoding': 'gzip, deflate',
    'Content-Type' : 'application/x-www-form-urlencoded; charset=UTF-8',
    'Host' : 'mp.weixin.qq.com',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:16.0) Gecko/20100101 Firefox/16.0'
}

weixin_position_url_pattern = re.compile(r'^http\:\/\/url\.cn\/\w{6}$')



#向控制台输出反馈信息，无返回值
def console_message(message_string):
    date_string = time.strftime('%a, %d %b %Y %H:%M:%S %Z', time.localtime())
    print date_string + " " + message_string



#读取反馈页面内容，返回页面内容
def decode_context(retval):
    if retval.headers.has_key('content-encoding'):
        fileobj = StringIO.StringIO()
        fileobj.write(url.read())
        fileobj.seek(0)
        gzip_file = gzip.GzipFile(fileobj=fileobj)
        context = gzip_file.read()
    else:
        context = retval.read()
    return context



#转写电话号码以适应iPhone
def telephone_convert_to_dial(telephone_string):
    result = telephone_string.replace('(','-').replace(')','-').strip('-')
    return result



#将字符串坐标装化浮点字典
def position_string2float(latitude, longitude):
    return {'latitude' : float(latitude), 'longitude' : float(longitude)}

#空坐标
position_empty = position_string2float(0, 0)



#登陆微信，成功返回True，失败返回False
def weixin_login(username, password):
    global weixin_url_opener
    global weixin_headers
    #获取密码md5
    password_md5 = md5.new(password).hexdigest()
    #开启cookie支持
    cookiejar = cookielib.LWPCookieJar()
    weixin_url_opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar))
    #POST数据
    values = {
        'f' : 'json',
        'imgcode' : '',
        'pwd1' : password_md5,
        'pwd2' : password_md5,
        'register' : '0',
        'username' : username
    }
    #发送登陆操作
    request = urllib2.Request(url = weixin_url_login, headers = weixin_headers, data = urllib.urlencode(values))
    retval = weixin_url_opener.open(request)
    #分析登陆结果
    context = decode_context(retval)
    feedback = json.loads(context)
    if feedback['ErrCode'] == 0:
        console_message(u"微信成功登陆，QQ号码%s。" % username)
        return True
    else:
        console_message(u"微信登陆失败，反馈：%s。" % context)
        return False



#判断是否为坐标消息，是的返回True，否则返回False
def weixin_is_position(content):
    if (((u'邮政编码' in content) or (u'中国' in content) or (u'市' in content)) and (u':<br/>http://' in content)) or (u'我的位置:<br/>http://' in content):
        return True
    else:
        return False



#获取微信消息并处理
def weixin_get_message():
    global weixin_url_opener
    global weixin_url_message
    global weixin_headers
    #访问内容页面
    request = urllib2.Request(url = weixin_url_message, headers = weixin_headers)
    retval = weixin_url_opener.open(request)
    #解析微信消息
    context = decode_context(retval)
    json_mark_head = '<script type="json" id="json-msgList">'
    json_mark_tail = '</script><script type="text/javascript">'
    if not json_mark_head in context:
        console_message(u"微信消息获取失败！")
        return
    json_first_pos = context.find(json_mark_head)
    json_second_pos = context.find(json_mark_tail, json_first_pos)
    messages_raw = context[json_first_pos + len(json_mark_head) : json_second_pos]
    messages_list = json.loads(messages_raw)
    messages_list.sort(lambda p1,p2 : cmp(int(p1['id']), int(p2['id'])))
    #依次处理未处理过的消息
    for message in messages_list:
        if not database_has(message):
            #按坐标和文字分类处理
            if weixin_is_position(message['content']):
                if not process_position_message(message):
                    #如果按坐标查询失败，同样按文字回复
                    process_text_message(message)
            else:
                process_text_message(message)
            


#微信消息等待
def weixin_wait():
    global weixin_url_opener
    global weixin_headers
    global weixin_url_wait
    global weixin_refresh_interval
    global cookie_start_time
    global weixin_timeout
    #获取最后一次处理过的消息的id
    if database_empty():
        weixin_last_message = 0
    else:
        weixin_last_message = database_lastmsgid()
    #准备请求信息
    url = weixin_url_wait % weixin_last_message
    value = {'ajax' : '1'}
    data = urllib.urlencode(value)
    request = urllib2.Request(url = url, headers = weixin_headers, data = data)
    while True:
        #等待weixin_refresh_interval秒
        time.sleep(weixin_refresh_interval)
        #判断cookies是否过期
        time_delta = time.time() - cookie_start_time
        if time_delta > cookie_time_limit :
            console_message(u"当前已登录%.2f，超过限额%d，即将重新登陆。" % (time_delta, cookie_time_limit))
            login_wrapper()
            cookie_start_time = time.time()
            return
        #发送刷新报文并考虑错误处理
        try:
            retval = weixin_url_opener.open(request, timeout = weixin_timeout)
        except urllib2.HTTPError, e:
            if hasattr(e, 'code'):
                console_message(u"微信POST心跳包HTTPError错误，代码：%s" % e.code)
            else:
                console_message(u"微信POST心跳包HTTPError错误，未知错误。" )
            #等待后重新登陆
            time.sleep(weixin_refresh_interval)
            login_wrapper()
            return
        except urllib2.URLError, e:
            if hasattr(e, 'reason'):
                console_message(u"微信POST心跳包URLError错误，错误原因：%s" % e.reason)
            else:
                console_message(u"微信POST心跳包URLError错误，未知错误。" )
            #等待后重新登陆
            time.sleep(weixin_refresh_interval)
            login_wrapper()
            return
        #分析反馈内容
        context = decode_context(retval)
        feedback = json.loads(context)
        if int(feedback['newTotalMsgCount']) > 0:
            console_message(u"收到新消息%s条。" % feedback['newTotalMsgCount'])
            return
        else:
            console_message(u"无新消息，继续等待%d秒。" % weixin_refresh_interval)



#发送微信消息，有600字限制
def weixin_send_message(userid, text):
    global weixin_url_opener
    global weixin_url_send
    global weixin_headers
    #POST数据
    values = {
        'ajax' : 'true',
        'content' : text.encode("utf-8"),
        'error' : 'false',
        'tofakeid' : userid,
        'type' : '1'
    }
    #发送POST操作
    request = urllib2.Request(url = weixin_url_send, headers = weixin_headers, data = urllib.urlencode(values))
    retval = weixin_url_opener.open(request)
    #分析发送结果
    context = decode_context(retval)
    feedback = json.loads(context)
    if feedback['msg'] == 'ok':
        console_message(u"微信回复成功，长度为%d，用户号%s。" % (len(text), userid))
        return True
    else:
        console_message(u"微信回复失败，反馈：%s。" % context)
        return False



#发送微信长消息，按600字切割
def weixin_send_longmessage(userid, text):
    #按600字切割分多次发送
    while len(text) > 0:
        error_times = 0
        #如果失败则最多尝试5次
        while not weixin_send_message(userid, text[0:600]):
            error_times += 1
            time.sleep(1)
            if error_times == 5:
                return False
        text = text[600:]
    return True



#处理坐标消息，即查询请求，成功处理后返回True，否则返回False
def process_position_message(message):
    global search_keyword
    #获取坐标URL
    mapurl = message['content'].split('<br/>')[-1]
    position = mapurl_to_position(mapurl)
    #坐标URL无效
    if (position == position_empty):
        return False
    #查询地址
    address = position_to_address(position)
    #查询场所
    console_message(u"%s[%s]请求查询: %s" % (message['nickName'], message['fakeId'], address))
    result = find_nightclub(position)
    result.sort(lambda p1,p2 : cmp(p1['distance'], p2['distance']))
    console_message(u"查询到%d家。" % len(result))
    #撰写信息
    text_message = compose_text_message(address, result)
    console_message(u"信息撰写完毕，长度为%d。" % len(text_message))
    #发送信息并返回执行结果
    if weixin_send_longmessage(message['fakeId'], text_message):
        #成功处理后信息标记入库
        database_insert(message, position)
        return True
    else:
        #失败处理后另外标记入库
        message['content'] = "[FAILED TO REPLY]" + message['content']
        database_insert(message, position)
        return False



#处理文字消息
def process_text_message(message):
    console_message(u"%s[%s]发来文字信息，长度为%d。" % (message['nickName'], message['fakeId'], len(message['content'])))
    content = message['content'].lower()
    if weixin_is_position(content):
        text = u"什么啦，你又给人家发奇奇怪怪的东西了！"
    elif 'test' in content:
        text = u"一看就是IT屌丝，真讨厌，test个毛线啊，人家服务很好的呢～"
    elif 'fuck' in content:
        text = u"F-*-C-K...All I need is U, %s!" % message['nickName']
    elif 'hello' in content:
        text = u"Bonjour, %s!" % message['nickName']
    elif 'love' in content:
        text = u"%s，你是个好人，我一直相信你可以找到更好的！加油！" % message['nickName']
    else:
        text = u"好啦好啦，我收到了，还有呢，还有呢？"
    
    if weixin_send_longmessage(message['fakeId'], text):
        #成功处理后信息标记入库
        database_insert(message)
        return True
    else:
        return False
    return True



#判断输入的string串是否为小数
def is_float_string(float_string):
    has_point = False
    for c in float_string:
        if not c.isdigit():
            if (c == ".") and (not has_point):
                has_point = True
            else:
                return False
    return True



#短URL转换为坐标，返回经纬度字典
def mapurl_to_position(position_url):
    global weixin_timeout
    #严格只接受匹配微信短URL的网址
    if not weixin_position_url_pattern.match(position_url):
        return position_empty
    #访问内容页面，页面由用户提供需要小心处理
    headers = {'Accept-Encoding': 'gzip,deflate'}
    request = urllib2.Request(url = position_url)
    try:
        retval = urllib2.urlopen(request, timeout = weixin_timeout)
    except urllib2.HTTPError, e:
        if hasattr(e, 'code'):
            console_message(u"无法打开用户所提交的URL，HTTPError错误代码：%s" % e.code)
        else:
            console_message(u"无法打开用户所提交的URL，HTTPError未知错误。" )
        return position_empty
    except urllib2.URLError, e:
        if hasattr(e, 'reason'):
            console_message(u"无法打开用户所提交的URL，URLError错误原因：%s" % e.reason)
        else:
            console_message(u"无法打开用户所提交的URL，URLError未知错误。" )
        return position_empty
    #retval = urllib2.urlopen(request)
    #解析页面内容，分析提取纬度和经度信息
    context = decode_context(retval)
    position_mark_first = 'center='
    position_mark_second = '&zoom'
    position_first_pos = context.find(position_mark_first)
    position_second_pos = context.find(position_mark_second, position_first_pos)
    #如果此网页非坐标页面，返回失败结果
    if (position_first_pos < 0) or (position_second_pos < 0):
        console_message(u"用户提交的URL中无座标信息。" )
        return position_empty
    position_raw = context[position_first_pos + len(position_mark_first) : position_second_pos]
    latitude, longitude = position_raw.split(',')
    #判断获取坐标的合法性并反馈结果
    if (is_float_string(latitude) and is_float_string(longitude)):
        return position_string2float(latitude, longitude)
    else:
        console_message(u"用户提交的URL中无有效座标。" )
        return position_empty



#获取当前地图API Key
def map_get_apikey():
    global map_apikey_pool
    global map_apikey_pointer
    key = map_apikey_pool[map_apikey_pointer]
    return key



#更换当前地图API key
def map_switch_apikey():
    global map_apikey_pool
    global map_apikey_pointer
    map_apikey_total = len(map_apikey_pool)
    while map_apikey_pointer < map_apikey_total:
        key = map_apikey_pool[map_apikey_pointer]
        url = "http://api.map.baidu.com/place/search?&query=%s&location=39.915,116.404&radius=5000&output=json&key=%s" % (urllib.quote(u"银行".encode("utf-8")), key)
        request = urllib2.Request(url = url)
        retval = urllib2.urlopen(request)
        context = retval.read()
        feedback = json.loads(context)
        if (feedback.has_key('status')) and (feedback['status'] == 'OK'):
            console_message(u"地图API Key更新为[%s]。" % key)
            return key
        else:
            map_apikey_pointer += 1
            console_message(u"地图API Key[%s]失效。" % key)
    console_message(u"所有的地图API Key均已失效。程序终止。")
    exit()



#坐标转换为地址
def position_to_address(position):
    global map_url_geocoder
    while True:
        #访问内容页面
        url = map_url_geocoder % (position['latitude'], position['longitude'], map_get_apikey())
        request = urllib2.Request(url = url)
        retval = urllib2.urlopen(request)
        #确认信息获取
        context = decode_context(retval)
        feedback = json.loads(context)
        if feedback['status'] == "OK":
            break
        else:
            map_switch_apikey()
    #反馈地址结果
    return feedback['result']['formatted_address']



#计算坐标间的距离，返回km数
def position_distance(position1, position2):
    #常量和子函数
    EARTH_RADIUS = 6371
    def hav(theta):
        s = math.sin(theta / 2)
        return s * s
    #经纬度装换为弧度
    lat0 = math.radians(position1['latitude'])
    lat1 = math.radians(position2['latitude'])
    lng0 = math.radians(position1['longitude'])
    lng1 = math.radians(position2['longitude'])
    #用haversine公式计算结果
    dlng = math.fabs(lng0 - lng1)
    dlat = math.fabs(lat0 - lat1)
    h = hav(dlat) + math.cos(lat0) * math.cos(lat1) * hav(dlng)
    distance = 2 * EARTH_RADIUS * math.asin(math.sqrt(h))
    return distance



#查找夜总会
def find_nightclub(position):
    global map_url_place
    global search_keyword
    global search_radius
    result = []
    #对每一个关键词查询并统计
    for keyword in search_keyword:
        #查询内容
        while True:
            #访问内容页面
            url = map_url_place % (urllib.quote(keyword.encode("utf-8")),
                                   position['latitude'], position['longitude'],
                                   search_radius,
                                   map_get_apikey())
            request = urllib2.Request(url = url)
            retval = urllib2.urlopen(request)
            #确认信息已获取
            context = decode_context(retval)
            try:
                feedback = json.loads(context)
            except ValueError, e:
                console_message(u"[%s]查询时json解析错误：%s" % (keyword, e))
                feedback['results'] = []
                break
            else:
                if feedback['status'] == "OK":
                    break
                else:
                    map_switch_apikey()
        #提取信息
        for club in feedback['results']:
            if club.has_key('telephone'):
                #根据电话号码判去重复
                check = [i for i in result if i['telephone'] == club['telephone'] ]
                if len(check) != 0:
                    continue
                #提取信息
                position_club = position_string2float(club['location']['lat'], club['location']['lng'])
                item = {
                    'name' : club['name'],
                    'address' : club['address'],
                    'telephone' : club['telephone'],
                    'position' : position_club,
                    'distance' : position_distance(position, position_club) }
                result.append(item)
    #反馈结果
    return result



#根据内容撰写信息
def compose_text_message(address, club):
    global search_result_limit
    counter = len(club)
    if counter == 0:
        #对于查询结果为空的情况
        text = u"当前位置是%s，客官请移步，方圆十里已经找不到乐子了。" % address
    else:
        #最多显示search_result_limit家
        counter = min(search_result_limit, counter)
        text = u"您所在的%s附近找到%d家，具体信息如下：\n\n" % (address, counter)
        for index in range(0,counter):
            #避免地址过短
            address = club[index]['address']
            if len(address) < 10:
                address = position_to_address(club[index]['position'])
            #转写电话号码以适应iPhone
            telephone = telephone_convert_to_dial(club[index]['telephone'])
            text += u"%d、%s\n距离%.2f公里\n地址：%s\n电话：%s\n\n" % (index + 1,
                     club[index]['name'],
                     club[index]['distance'],
                     address,
                     telephone)
    #返回信息
    return text



#载入或初始化数据库
def database_start(database_filename):
    global database_connection
    #判断数据库是否已经存在
    if os.path.isfile(database_filename):
        new_database = False
    else:
        new_database = True
    #建立链接或创建数据库
    database_connection = sqlite3.connect(database_filename)
    #在新创建的数据库中创建表
    if new_database:
        database_cursor = database_connection.cursor()
        database_cursor.execute(
                                """create table message (
                                    id integer not null primary key,
                                    dateTime integer not null,
                                    fakeId integer not null,
                                    nickName text not null,
                                    content text null,
                                    latitude real null,
                                    longitude real null,
                                    unique (id, fakeId) )""")
        database_cursor.close()



#数据库中插入数据
def database_insert(message, position = position_empty):
    global database_connection
    database_cursor = database_connection.cursor()
    database_cursor.execute(
                            """insert into message
                                (id, dateTime, fakeId, nickName, content, latitude, longitude)
                                values (:id, :dateTime, :fakeId, :nickName, :content, :latitude, :longitude)""",
                            {   'id' : int(message['id']),
                            'dateTime' : int(message['dateTime']),
                            'fakeId' : int(message['fakeId']),
                            'nickName' : message['nickName'],
                            'content' : message['content'],
                            'latitude' : position['latitude'],
                            'longitude' : position['longitude']   })
    database_cursor.close()
    database_connection.commit()



#数据库查询数据是否存在
def database_has(message):
    global database_connection
    database_cursor = database_connection.cursor()
    database_cursor.execute(
                            """select count(*) from message where id=:id""",
                            {   'id' : int(message['id'])   })
    if database_cursor.fetchone()[0] == 0:
        result = False
    else:
        result = True
    database_cursor.close()
    return result



#获取最后一个处理的信息的id
def database_lastmsgid():
    global database_connection
    database_cursor = database_connection.cursor()
    database_cursor.execute(
                            """select id from message order by id desc, id limit 1""")
    id = database_cursor.fetchone()[0]
    database_cursor.close()
    return id



#数据库是否为空
def database_empty():
    global database_connection
    database_cursor = database_connection.cursor()
    database_cursor.execute(
                            """select count(*) from message""")
    if database_cursor.fetchone()[0] == 0:
        result = True
    else:
        result = False
    database_cursor.close()
    return result



#登陆微信
def login_wrapper():
    global cookie_start_time
    error_times = 0
    #如果失败则多次尝试
    while not weixin_login(weixin_username, weixin_password):
        time.sleep(5)
        error_times += 1
        if error_times == 5:
            exit()
    #记录登陆时间
    cookie_start_time = time.time()



if __name__ == "__main__":
    #登陆微信
    login_wrapper()
    #初始化数据库
    database_start(database_filename)
    #伺服循环
    while True:
        #处理微信消息
        weixin_get_message()
        #等待新信息
        weixin_wait()
