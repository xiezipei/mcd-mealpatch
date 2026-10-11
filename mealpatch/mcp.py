import json
import os
import urllib.request
import urllib.error


class MCPError(ValueError):
    pass


class Client:
    allowed = {'query-nearby-stores', 'query-meals', 'query-meal-detail', 'calculate-price'}

    def __init__(self):
        token = os.environ.get('MCD_MCP_TOKEN')
        if not token:
            raise MCPError('缺少 MCD_MCP_TOKEN；请在本机环境变量中配置，不要写入餐单或命令参数')
        self.headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
                        'Accept': 'application/json, text/event-stream'}
        self.counter = 0
        result = self.request('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                              'clientInfo': {'name': 'mealpatch', 'version': '0.1.0'}})
        self.headers['MCP-Protocol-Version'] = result['protocolVersion']
        self.request('notifications/initialized', notification=True)

    def request(self, method, params=None, notification=False):
        self.counter += 1
        body = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            body['params'] = params
        if not notification:
            body['id'] = self.counter
        req = urllib.request.Request('https://mcp.mcd.cn', data=json.dumps(body).encode(), headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                session = response.headers.get('Mcp-Session-Id')
                if session:
                    self.headers['Mcp-Session-Id'] = session
                raw = response.read().decode()
                if notification and not raw.strip():
                    return {}
                if 'text/event-stream' in response.headers.get('Content-Type', ''):
                    messages = []
                    for event in raw.replace('\r\n', '\n').split('\n\n'):
                        data = '\n'.join(line[5:].lstrip() for line in event.splitlines() if line.startswith('data:'))
                        if data:
                            messages.append(json.loads(data))
                    result = next(m for m in messages if m.get('id') == body.get('id'))
                else:
                    result = json.loads(raw)
                if result.get('id') != body.get('id') or 'error' in result or 'result' not in result:
                    raise MCPError('MCP协议失败；未保存报价')
                return result['result']
        except (urllib.error.URLError, TimeoutError, OSError):
            raise MCPError('MCP网络失败或超时；未保存报价') from None
        except (KeyError, ValueError, StopIteration):
            raise MCPError('MCP响应无法校验；未保存报价') from None

    def call(self, name, args):
        if name not in self.allowed:
            raise MCPError('仅允许门店、菜单、详情和核价工具')
        result = self.request('tools/call', {'name': name, 'arguments': args})
        data = result.get('structuredContent')
        if result.get('isError') or not isinstance(data, dict) or data.get('success') is not True:
            raise MCPError('官方业务调用失败或缺少结构化返回；不沿用历史报价')
        if name == 'query-meals':
            data.get('data', {}).pop('frequent', None)
        return data['data']
