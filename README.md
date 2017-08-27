###思路简介
####相关数据库
 使用的mysql存储用户数据具体表结构见 db.sql，redis存储token
*  user_info:存储用户id和密码
*  user_contacts:存储用户的联系人关系以及未读消息数
*  msg_record:存储消息信息

####后台逻辑介绍
后台web框架使用tornado，使用http和websocket协议。服务器会分别维护所有在线页面的联系人页面websocket以及聊天页面websocket。当发现相关用户页面在线且信息有更新则通过websocket下发内容，具体代码见http_service.py。
数据库相关逻辑代码在controller.py。
页面html以及js都在static目录
相对于第一版本,增加了rabbit_mq,将联系人更新和聊天信息更新的相关逻辑放在db_module模块中,好处在于可以使得tornado的http_service能够多实例，如果A与B对话，并且websocket分别在建立在不同的进程上，db_module通过rabbit_mq发送广播的形式，通知对应的tornado进程去下发websocket消息

####页面以及相关逻辑：
* 登录页面 ：输入账号和密码进行登录，如果此账号不存在则直接注册，登录成功后会返回一个token并跳转到联系人列表，token与该用户绑定，token存在redis中，有效期为1小时，每次对token进行验证都会延长有效期。
* 联系人列表页面：  成功进入页面后会建立一个websocket，并要求服务器下发联系人列表信息，后面添加和删除联系人都通过websocket发送请求，如果联系人信息或者未读消息数有更新，服务器会通过websocket下发消息给前端，告知最新的联系人列表信息。
* 聊天页面：进入聊天页面后，会建立一个聊天websocket，并要求服务器下发历史消息，后面发送，删除，获取消息都通过websocket发送请求。服务器会在消息内容，条目，读取状态有更新的情况下，主动下发消息，告知最新的消息列表。

####注：
* 启动方法，在demo目录下 ./start.sh
* 配置文件在 config下面，需要配置一个mysql数据库，redis数据库，tornado监听端口，日志输出文件和级别, rabbit_mq服务器地址
* 使用nginx需要配置支持websocket
* 样例链接： http://121.52.235.231:41205/page/login.html
* 部署需要安装erlang环境，且安装rabbit_mq
