# 麦麦改单官 · MealPatch

为2～6人组织者管理下单前餐单：锁定其他人的选择，局部改餐，官方重新核价，解释分账差异。**不下单、不支付、不修改真实订单。**

适合帮同事或朋友汇总同店餐单、临时有人换小食或调整数量的组织者。首版由一位组织者串行操作，不是多人实时协作系统。本项目为独立参赛作品，非麦当劳官方产品，不提供医疗、营养或其他专业建议。

初版：Python 3.11+，标准库，无第三方运行依赖。本机Python 3.13验证；3.11尚未实际测试。仅支持同店到店取餐的默认配置单品，自动保留官方默认特调参数，但不支持编辑特调、套餐内部换件、随单购和用券优化。

## 安装

安装Python3.11或以上版本，将本项目下载/克隆到本机，解压后在本README所在目录打开终端。无需pip安装或额外服务，也可用GitHub的Code → Download ZIP下载。执行`python3 --version`检查版本。

```sh
git clone https://github.com/xiezipei/mcd-mealpatch.git
cd mcd-mealpatch
```

在该目录运行：

```sh
python3 -m mealpatch --help
python3 -m mealpatch demo --offline
python3 -m unittest discover -s tests -v
```

离线演示使用2026-10-11真实核价的脱敏历史快照，不是实时价格。首次克隆后的离线运行无需配置Token。

在线调用需要先从[麦当劳官方MCP开放平台](https://open.mcd.cn/mcp)登录激活并取得个人Token，在本机安全设置环境变量MCD_MCP_TOKEN，不要把真实Token提交到仓库或粘贴到对话中。程序不会读取Codex个人配置。macOS默认zsh可使用以下隐藏输入（不把Token字面值留在命令历史中）：

```zsh
read -rs 'MCD_MCP_TOKEN?请输入个人 MCP Token：'
export MCD_MCP_TOKEN
```

只输入Token本体，不包含Bearer前缀。用完可执行`unset MCD_MCP_TOKEN`。其他Shell请使用其安全环境变量设置方式。参考配置见[mcp-config.example.json](mcp-config.example.json)，CLI不读取该文件，客户端的占位符展开支持也各不相同。

```sh
python3 -m mealpatch demo --online
python3 -m mealpatch stores 广州 天河智慧城
python3 -m mealpatch init --store 1400828 --members A B C --budget 120
python3 -m mealpatch menu
python3 -m mealpatch detail 4810
python3 -m mealpatch add A 1100
python3 -m mealpatch add B 1440
python3 -m mealpatch add B 4810
python3 -m mealpatch add C 1406
python3 -m mealpatch report
```

以上门店/商品编码仅为历史测试示例，实际先查询确认。report显示行ID；将以下占位符替换成实际行ID：

```sh
python3 -m mealpatch lock A的行ID
python3 -m mealpatch lock C的行ID
python3 -m mealpatch quote
python3 -m mealpatch replace B中薯条的行ID 4437
python3 -m mealpatch quote
python3 -m mealpatch report
```

草稿默认保存在被Git忽略的.mealpatch/cart.json；用全局参数`--cart 路径`（放子命令前）选择独立草稿。init拒绝覆盖已有文件。请串行运行，不支持多个进程并发编辑。报告从终端显示，可自行保存到私人目录。不要发布个人运行草稿。

## 分账与失败

优先按官方商品小计归属汇总，重复商品按数量本地分配；无法完整解释总额则按已核验菜单基准金额约定分摊。缺少基准时不猜价格；只有用户明确同意均分才用quote --equal。全程整数分、最大余数法消除尾差，逐人合计等于整单金额。

锁定保护配置和份数，不锁价格。改餐会使旧价失效，超预算只提示，不擅自删餐。参数、网络、官方业务或校验失败时返回非零退出码且不更新草稿文件；查看report确认当前版本状态后再操作。失败消息不会打印服务器原始正文或凭据。

## 演示结果

完整材料见[演示说明](demo/README.md)、[约60秒讲解稿](demo/narration.md)和[实际报告文本](demo/result.md)。下面是实际CLI报告的只读展示页截图，不是产品交互界面。

![MealPatch历史核价演示，非实时价格，未下单](demo/result.png)

2026-10-11广州真实核价：A巨无霸26.00元、B麦辣鸡腿汉堡＋中薯条37.00元、C板烧鸡腿堡23.50元，共86.50元；锁定A/C后，B中薯条换小杯玉米杯，总价85.00元，B减少1.50元。此为历史案例，实时价格与库存以官方当次返回为准。运行demo --offline可复现报告，demo --online会重新查询，不硬编码历史总价。

## Skill入口

skills/mealpatch/SKILL.md是支持本地执行的AI客户端入口，可按客户端的Skill安装方式手动安装，并告知产品目录位置；未自动安装到个人配置，也未验证其他客户端兼容性。CLI可独立使用。

## 参赛资料与授权

- [MCP集成说明](MCP_INTEGRATION.md)：实际工具、调用流程、业务价值和验证边界。
- [官方参赛声明](CONTEST_DECLARATION.md)：按官方原文保留，发布前由负责人确认。
- [脱敏配置](mcp-config.example.json)：仅含环境变量占位符，无真实凭据。
- 当前未使用WorkBuddy开发或验证，不申报其专项奖励，不提供虚构的workbuddy.md。

源码、Skill与项目文档在本工作区新建；未复制竞品代码或素材，未打包竞品原文。仅含标准库代码及官方要求保留的声明、用于说明集成的脱敏商品/价格摘要，无品牌图片或Logo。项目代码采用[MIT许可证](LICENSE)。官方声明与品牌、数据的权利不因代码许可证而转授。

项目仓库：[xiezipei/mcd-mealpatch](https://github.com/xiezipei/mcd-mealpatch)。报名状态以官方Issue回复为准。官方入口：[活动仓库](https://github.com/M-China/mcd-developer-innovation-challenge)、[完整规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)。
