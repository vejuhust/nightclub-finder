## 特别说明
改微信公众平台机器人所Hack的部分已经有API提供了。登陆微信公众平台网站后，[访问此地址](http://mp.weixin.qq.com/cgi-bin/indexpage?t=wxm-callbackapi-doc&lang=zh_CN)即可查看API具体信息。

## 代码准备
* 将\*\*USER\*\*替换为真实过微信帐号。
* 将\*\*PASSWORD\*\*替换为相对应的密码。
* 将\*\*PLACE_API1\*\*等替换为自行申请的百度[Place API](http://developer.baidu.com/map/place-api.htm)，目前每个Place API的key可以执行1000请求，所以请根据需求适当申请。

## 部署
Linux环境，需要Python 2.6支持。执行两条命令：

    export PYTHONIOENCODING=utf-8
    nohup python nightclub_finder.py &
    
## 待开发
1. 改善weixin_get_message()访问网页时未做异常处理应对50?错误
2. 使用官方API
3. console_message()输出至log文件
4. 发送图片指示地图