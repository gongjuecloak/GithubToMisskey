import os
import logging
from flask import Flask, request, jsonify
from misskey import Misskey
import jsonschema
from jsonschema import validate

# 配置日志记录器，设置日志级别为INFO，定义日志格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 定义统一的错误响应数据结构，添加error_code字段方便客户端做针对性处理
def generate_error_response(status_code, message, detail, error_code=None):
    response = {
       'status': 'error',
       'message': message,
       'detail': detail
    }
    if error_code:
        response['error_code'] = error_code
    return jsonify(response), status_code

# 定义push事件的JSON模式示例（可根据实际GitHub Webhook规范完善）
push_event_schema = {
    "type": "object",
    "properties": {
        "repository": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        },
        "ref": {"type": "string"},
        "commits": {
            "type": "array"
        }
    },
    "required": ["repository", "ref", "commits"]
}

def print_commit_author(commit):
    """打印提交作者信息的函数"""
    print(f"提交作者: {commit['author']['name']}")


def print_file_changes(commit):
    """打印文件变化信息的函数，包含修改、新增和删除的文件"""
    modified_files = commit.get('modified', [])
    added_files = commit.get('added', [])
    removed_files = commit.get('removed', [])
    print("文件变化（该提交中修改、新增和删除的文件）:")
    for file in modified_files:
        print(f"  [修改] {file}")
    for file in added_files:
        print(f"  [新增] {file}")
    for file in removed_files:
        print(f"  [删除] {file}")


def build_commit_info_text(commits):
    """
    构建包含所有提交相关信息（如更新日志、作者、文件变化等）的文本内容，包含完整的文件变化情况
    :param commits: 提交信息列表
    :return: 构建好的文本内容
    """
    all_info_text = ""
    if len(commits) > 100:  # 假设限制最多100个提交，可根据实际调整
        logger.error("提交数量过多，可能存在异常")
        raise ValueError("提交数量超过限制")
    for commit in commits:
        all_info_text += f"文档已更新～构建可能还需要一段时间，请耐心等待完成，预计1~5分钟:x11:\n\n"
        all_info_text += f"更新日志: {commit['message']}\n"
        all_info_text += f"更新作者: {commit['author']['name']}\n"
        all_info_text += "文件变化（该提交中修改、新增和删除的文件）:\n"
        all_info_text += "```\n"
        modified_files = commit.get('modified', [])
        added_files = commit.get('added', [])
        removed_files = commit.get('removed', [])
        for file in modified_files:
            all_info_text += f"  [修改] {file}\n"
        for file in added_files:
            all_info_text += f"  [新增] {file}\n"
        for file in removed_files:
            all_info_text += f"  [删除] {file}\n"
        all_info_text += "```\n"
    return all_info_text


def push_info_to_misskey(all_info_text):
    """
    将构建好的文本信息推送到Misskey平台
    :param all_info_text: 包含提交信息等的文本内容
    """
    misskey_url = os.environ.get('MISSKEY_URL', "填写你的misskey域名")  # 优先从环境变量获取，若不存在则使用默认值
    access_token = os.environ.get('MISSKEY_ACCESS_TOKEN', "填写misskey账号的ACCESS TOKEN")
    api = Misskey(misskey_url, i=access_token)
    try:
        api.notes_create(text=all_info_text)
        logger.info("已成功将提交信息和文件变化信息推送到Misskey")
    except Exception as e:
        logger.error(f"推送信息到Misskey时出错: {e}")
        # 根据不同的异常类型细化错误消息（这里简单示例，可根据实际情况完善）
        if "network" in str(e).lower():
            raise ConnectionError("与Misskey平台连接失败，请检查网络设置")
        elif "permission" in str(e).lower():
            raise PermissionError("Misskey平台访问权限验证失败，请检查访问令牌是否正确")
        else:
            raise


def save_info_to_file(all_info_text):
    """
    将所有信息保存到文本文件中，这里以当前目录下的'github_push_info.txt'为例，可根据实际需求调整路径
    :param all_info_text: 包含提交信息等的文本内容
    """
    with open('github_push_info.txt', 'a') as file:  # 'a'表示追加模式，如果文件不存在则创建
        file.write(all_info_text)


@app.route('/github-webhook', methods=['POST'])
def github_webhook():
    if request.method == 'POST':
        data = request.get_json(silent=True)
        if data is None:
            logger.error("请求体数据不是合法的JSON格式")
            return generate_error_response(400, '请求体数据不是合法的JSON格式', '无法将请求体解析为JSON格式', error_code='INVALID_JSON')
        try:
            validate(data, push_event_schema)  # 验证数据是否符合push事件的JSON模式
        except jsonschema.ValidationError as ve:
            logger.error(f"请求体数据不符合预期的GitHub Webhook格式: {ve}")
            return generate_error_response(400, '请求体数据格式不符合要求', str(ve), error_code='INVALID_SCHEMA')

        event_type = request.headers.get('X-GitHub-Event')
        logger.info(f"接收到的GitHub事件类型: {event_type}")

        if event_type == 'push':
            try:
                handle_github_push_event(data)
            except KeyError as ke:
                logger.error(f"处理推送事件时键不存在错误: {ke}")
                return generate_error_response(500, '处理推送事件键不存在错误', str(ke), error_code='KEY_MISSING')
            except ValueError as ve:
                logger.error(f"处理推送事件时出现值错误: {ve}")
                return generate_error_response(400, '提交数量异常', str(ve), error_code='VALUE_ERROR')
            except ConnectionError as ce:
                logger.error(f"与外部平台连接出错: {ce}")
                return generate_error_response(500, '与Misskey平台连接失败', str(ce), error_code='CONNECTION_ERROR')
            except PermissionError as pe:
                logger.error(f"权限验证出错: {pe}")
                return generate_error_response(500, 'Misskey平台访问权限验证失败', str(pe), error_code='PERMISSION_ERROR')
            except Exception as e:
                logger.error(f"处理GitHub推送事件时出错: {e}")
                return generate_error_response(500, '处理推送事件失败', str(e), error_code='GENERAL_ERROR')
        elif event_type == 'pull_request':
            try:
                handle_github_pull_request_event(data)
            except Exception as e:
                logger.error(f"处理GitHub拉取请求事件时出错: {e}")
                return generate_error_response(500, '处理拉取请求事件失败', str(e), error_code='PULL_REQUEST_ERROR')
        else:
            logger.warning(f"未知GitHub事件类型: {event_type}")
            print(f"未知GitHub事件类型: {event_type}")
        return jsonify({'status': 'success'}), 200
    else:
        return jsonify({'status': 'method not allowed'}), 405


def handle_github_push_event(data):
    """
    处理GitHub推送事件的函数，接收从GitHub Webhook传来的数据
    参数data是解析后的请求体JSON数据，包含了推送事件相关详细信息
    """
    repo_name = data.get('repository', {}).get('name')
    branch_name = data.get('ref').split('/')[-1]  # 简单提取分支名称，可能需根据实际格式调整
    logger.info(f"处理GitHub推送事件，仓库: {repo_name}，分支: {branch_name}")

    commits = data.get('commits', [])
    all_info_text = build_commit_info_text(commits)
    push_info_to_misskey(all_info_text)
    save_info_to_file(all_info_text)


def handle_github_pull_request_event(data):
    """
    处理GitHub Pull Request事件的函数，接收从GitHub Webhook传来的数据
    参数data是解析后的请求体JSON数据，包含了拉取请求事件相关详细信息
    """
    logger.info(f"处理GitHub Pull Request事件: {data}")
    # 这里可以添加更详细的拉取请求事件处理逻辑，如获取拉取请求状态、评论等
    # 如果处理过程中发生错误，会被外层的异常处理捕获并记录日志、返回错误响应


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5099))
    app.run(port=port, threaded=True)  # 启用多线程处理，提高并发能力（适用于I/O密集型任务）