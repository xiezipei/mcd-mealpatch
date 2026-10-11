# MCP 集成说明

MealPatch 使用麦当劳官方 MCP Server：`https://mcp.mcd.cn`。说明与验证日期：2026-10-11。本项目为独立参赛作品，非麦当劳官方产品。

## 接入实现

实现位于[mealpatch/mcp.py](mealpatch/mcp.py)：Python标准库HTTP POST、JSON-RPC 2.0，执行initialize与notifications/initialized，再调用tools/call；支持JSON和SSE响应、Mcp-Session-Id会话头、协商后的MCP-Protocol-Version。已验证协议版本2024-11-05。单次请求30秒超时，不自动重试。

CLI直接读取本机环境变量MCD_MCP_TOKEN并构造Bearer认证，不要求另一个MCP客户端转发，不读取个人Codex配置。Token缺失、HTTP失败、协议错误、工具错误或success不为true均失败，不打印服务器原始正文或认证头。只使用structuredContent，不从说明文字猜业务JSON。

[mcp-config.example.json](mcp-config.example.json)是给支持该格式的MCP客户端参考的脱敏示例，不是CLI运行配置；CLI只读取环境变量。`${MCD_MCP_TOKEN}`是环境变量占位符，客户端是否支持自动展开需核对其文档，不能把占位符字面值当成可用Token。无需把真实Token写到本项目任何文件。

## 实际工具与业务价值

| 工具 | 实际用途 | 关键入参 |
| --- | --- | --- |
| query-nearby-stores | 按城市和地标获取真实可选自取门店，避免编造门店 | beType=1、searchType=2、city、keyword |
| query-meals | 取得当前门店商品编码、在售菜单与菜单基准价格 | storeCode、orderType=1、beType=1 |
| query-meal-detail | 确认规格与默认配置，拒绝需要套餐选配的商品 | 同上，加code |
| calculate-price | 对改前、改后整单分别官方核价，解释总额和逐人差异 | 同上，加items（productCode、quantity及默认modification） |

自取不传beCode，不传预约时间。首版不支持预约、外送、得来速、套餐选配或用户编辑特调。白名单不包括任何下单、支付、领券或取消工具。

## 调用与本地处理边界

1. 用户提供城市/地标，查门店后选择同一门店；演示明确选用测试门店。
2. 查菜单与详情，只添加真实菜单中的默认配置单品，保留默认特调参数。每行绑定稳定行ID与成员归属。
3. 在本地锁定A/C餐品，以calculate-price核验整个初版草稿。
4. 只替换B指定行。代码检查锁定冲突，版本递增，旧价失效。
5. 再查当前商品可用性和默认配置，整单再次calculate-price。默认配置发生变化时停止，要求重新确认。
6. 本地计算餐品差异与分账。官方price/subtotal用整数分，菜单元字符串用Decimal转分。重复商品按数量分配尾差；明细不足以解释总额时采用已核验基准占比并标注“约定分摊”。缺少基准时停止自动分账，明确同意均分后才能继续。
7. 展示未下单报告和预算检查，不调用创建订单。

餐品锁定、版本管理、差异解释和分账是本地实现，不是官方MCP返回的能力。分摊金额不应描述为官方逐人账单；锁定餐品不代表锁定分摊金额。

## 已发生的真实验证

2026-10-11，在广州天河智慧城高唐路餐厅（storeCode 1400828）读取125个菜单餐品，检查示例单品详情，并完成改前/改后核价。T05在线演示由产品Client实际执行相同链路，非仅协议握手或工具列表检查。

| 成员 | 改前餐品 | 改后餐品 | 改前（元） | 改后（元） |
| --- | --- | --- | ---: | ---: |
| A（锁定） | 巨无霸 | 不变 | 26.00 | 26.00 |
| B | 麦辣鸡腿汉堡＋中薯条 | 麦辣鸡腿汉堡＋小杯玉米杯 | 37.00 | 35.50 |
| C（锁定） | 板烧鸡腿堡 | 不变 | 23.50 | 23.50 |
| 总计 | | | 86.50 | 85.00 |

上述是历史验证结果，不承诺未来价格或供应不变。两次核价均无优惠，逐项小计之和等于总价。原始业务验证的脱敏金额/商品摘要保存在[examples/snapshot.json](examples/snapshot.json)；快照仅供离线复现，产品在线演示会重新调用官方工具，不把快照当实时报价。

```sh
python3 -m mealpatch demo --offline
python3 -m mealpatch demo --online
python3 -m unittest discover -s tests -v
```

## 隐私、安全与局限

- 未调用账户信息、领券、兑换、创建订单、取消订单或支付，未产生订单。
- 菜单个人常点字段移除后才展示，草稿仅使用用户指定成员ID；运行目录被Git忽略。
- Token通过请求头传给官方端点；不保存到快照、草稿或报告。异常使用安全摘要，不输出原始业务响应。
- 15项本地测试覆盖核心规则；离线示例与在线成功验证分开标注。真实优惠、附加费、多进程编辑以及其他客户端兼容性尚未验证。
- 本版本无第三方运行依赖，Python3.13已实测；标称3.11+尚未逐版本验证。

官方资料：[MCP使用指南](https://github.com/M-China/mcd-mcp-server)、[MCP开放平台](https://open.mcd.cn/mcp)、[赛事规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)。
