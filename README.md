# GithubToMisskey

```
misskey_url = os.environ.get('MISSKEY_URL', "填写你的misskey域名")  # 优先从环境变量获取，若不存在则使用默认值
access_token = os.environ.get('MISSKEY_ACCESS_TOKEN', "填写misskey账号的ACCESS TOKEN")
```
MISSKEY_URL填写你的misskey域名
MISSKEY_ACCESS_TOKEN填写misskey账号的ACCESS TOKEN

修改完成后，运行 ```run.py``` 提示缺少什么依赖就安装什么依赖

运行后默认端口是5099，可自行修改

webhook的链接是 http://127.0.0.1:5099/github-webhook ，可以使用域名反代，反代后配置到对应仓库的webhook里，默认权限即可，接收到github信息后会解析更新中的文件变化（包括增删改）并发送到misskey中，效果可以看[这个账号](https://lzplus.top/@docs)