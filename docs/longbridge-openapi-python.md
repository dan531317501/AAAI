# 长桥 OpenAPI Python 完整参考

> 基于长桥 Developers 官方中文文档与官方文档仓库整理，抓取/核对日期：2026-08-06。本文以 Python SDK 为主，同时覆盖官方文档中明确给出的 HTTP/SSE API。
>
> 费用说明是权限口径，不是券商交易费报价：同一个接口可能因市场、标的和账户权限返回不同数据。凡官方开发者文档未公开具体价格的地方，明确写成“未公开/需账号权限”，不作猜测。

## 1. 结论先看：免费与收费

| 大类 | 接口规模 | 免费/基础 | 收费/条件 | 关键边界 |
| --- | ---: | --- | --- | --- |
| Quote（行情） | 37 | 行情权限独立于 App/PC/Web（24 个明确基础免费） | 基础行情、静态/分析数据；部分 Quote 方法按市场变化（3 个明确收费，10 个条件/账户权限） | 港股 LV2 经纪队列；美股期权 OPRA；港股实时/高级数据按权限；美股/港股股票基础行情通常随 OpenAPI 提供；港股十档和美股期权另计 |
| Fundamental（基本面） | 47 | 只读基本面（47 个明确基础免费） | 官方文档未标注额外数据卡收费（0 个明确收费，0 个条件/账户权限） | 未公开统一价格；可能受市场覆盖和账户权限影响 |
| Market（市场状态与日历） | 14 | 市场状态、排行、日历（14 个明确基础免费） | 官方文档未标注额外数据卡收费（0 个明确收费，0 个条件/账户权限） | 未公开统一价格；部分数据依赖基础行情权限/数据中心 |
| News & Contents（资讯、社区与股单） | 16 | 资讯、社区、股单（16 个明确基础免费） | 官方文档未标注额外数据卡收费（0 个明确收费，0 个条件/账户权限） | 未公开统一价格；发帖/回复有频率限制；读取与写入都需认证 |
| Screener（选股器） | 5 | 策略与筛选（5 个明确基础免费） | 官方文档未标注额外数据卡收费（0 个明确收费，0 个条件/账户权限） | 未公开统一价格；策略可见范围由账户权限决定 |
| Trade（交易与资产） | 19 | 交易、成交、资产（0 个明确基础免费） | 无额外行情卡分类（0 个明确收费，19 个条件/账户权限） | 交易佣金/平台费用不在 API 文档中报价；调用等同线上交易；下单前必须人工复核 |
| Account（账户、组合与定投） | 20 | 组合、提醒、定投（0 个明确基础免费） | 无额外行情卡分类（0 个明确收费，20 个条件/账户权限） | 产品费用未在开发者文档公开；需要账户/交易级授权 |
| AI Agent（Workspace 与对话） | 4 | Workspace、Agent、对话（0 个明确基础免费） | 无公开统一价格表（0 个明确收费，4 个条件/账户权限） | 可能受 Workspace/产品计费影响；需成员权限；对话支持阻塞和 SSE 两种模式 |

### 收费结论（官方明确口径）

- **明确基础免费**：官方权限配置将 `basic` 定义为开通 OpenAPI 后自动获得、无需额外购买；静态信息、计算指标、资金流、市场温度、交易日、标的列表、财经披露等页面属于这一口径。
- **明确收费/订阅**：港股十档盘口与经纪队列需要 LV2 高级行情；美股期权实时行情需要 OPRA 美股期权行情卡。
- **同接口的条件收费**：`quote`、`depth`、`trades`、`intraday`、`candlesticks`、历史 K 线等方法，股票基础数据通常可用基础权限，但港股实时/高级档位和美股期权会随标的触发额外权限。
- **非行情卡能力**：Trade/Account/AI 的文档没有公开统一价目；本参考只标注认证、区域和产品权限，不把它们假定为“免费”。

## 2. 快速开始

### 2.1 安装

```bash
python -m pip install longbridge
```

官方 Python 包已从 `longport` 更名为 `longbridge`；旧包已弃用。

### 2.2 API 地址与标的代码

| 用途 | 默认地址 | 中国大陆可用地址 |
| --- | --- | --- |
| HTTP API | `https://openapi.longbridge.com` | `https://openapi.longbridge.cn` |
| Quote WebSocket | `wss://openapi-quote.longbridge.com/v2` | `wss://openapi-quote.longbridge.cn/v2` |
| Trade WebSocket | `wss://openapi-trade.longbridge.com/v2` | `wss://openapi-trade.longbridge.cn/v2` |

标的代码统一为 `ticker.region`：`AAPL.US`、`700.HK`、`600519.SH`、`399001.SZ`。官方当前文档说明 SG 实时行情暂不通过 Developers API 提供。

### 2.3 OAuth 2.0（推荐）

```python
from longbridge.openapi import Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(
    lambda url: print(f"请打开浏览器授权：{url}")
)
config = Config.from_oauth(oauth)
```

OAuth Token 由 SDK 持久化并自动刷新；官方文档给出的默认存储位置是 `~/.longbridge/openapi/tokens/<client_id>`。不要把 OAuth Token、App Secret 或旧版 Access Token 写入日志、提交到仓库或放进模型可见的工具参数。

### 2.4 旧版 API Key（兼容）

```bash
export LONGBRIDGE_APP_KEY="..."
export LONGBRIDGE_APP_SECRET="..."
export LONGBRIDGE_ACCESS_TOKEN="..."
```

```python
from longbridge.openapi import Config

config = Config.from_apikey_env()
# 或：Config.from_apikey(app_key, app_secret, access_token)
```

旧版 Access Token 默认 90 天后过期；OAuth Token 与旧版 Access Token 不是同一种凭证。

### 2.5 同步/异步上下文

同步上下文通常是 `QuoteContext(config)`、`TradeContext(config)` 等；异步上下文使用对应的 `Async*Context.create(config)`，各接口条目会同时收录官方 Python 同步与异步示例（若官方页面提供）。

### 2.6 时间、区域与错误处理

- getting-started 对 SDK 时间字段的总原则是 UTC Unix Timestamp；具体接口仍以其字段表为准。官方 changelog 另说明 CLI JSON 的部分时间序列/历史输出已改为 RFC 3339，不能把 CLI 输出格式直接套到所有 SDK 返回对象。
- `.com`/`.cn` 是接入点，不改变数据和鉴权；`ap`/`us` 是账户数据中心，决定部分 US-only API 是否可用。US 数据中心账户必须使用 `.com`。
- 官方未在 getting-started 中给出统一公开的全局限流数值；应按接口页面的限制处理 `429`，对临时 `5xx` 使用有限次数指数退避，并保留请求参数和业务错误码。社区创建/回复页面给出了单独的频率限制，见对应条目。
- Trade 下单、改单和撤单都是线上真实交易能力；开发调试必须使用明确不会成交的参数，并在生产环境增加人工确认、幂等键/订单状态核验和异常告警。

## 3. Python 通用调用模板

```python
from longbridge.openapi import Config, OAuthBuilder, QuoteContext

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
quotes = ctx.quote(["AAPL.US", "700.HK"] )
for quote in quotes:
    print(quote)
```

以下条目中的参数表、响应表、错误码和 Python 代码均从官方中文页面提取；HTTP 方法/路径仅在官方页面明确提供时显示。

## 4. API 总览与共享对象

### 概览

- **官方页面**：[概览](https://open.longbridge.com/zh-CN/docs/quote/overview)

### 行情接口概览

<table>
    <tr>
        <td>类型</td>
        <td>功能简介</td>
    </tr>
    <tr>
        <td rowspan="20">拉取</td>
        <td><a href="./pull/static">获取标的基础信息</a></td>
    </tr>
    <tr>
        <td><a href="./pull/quote">获取标的实时行情</a></td>
    </tr>
    <tr>
        <td><a href="./pull/option-quote">获取期权实时行情</a></td>
    </tr>
    <tr>
        <td><a href="./pull/warrant-quote">获取轮证实时行情</a></td>
    </tr>
    <tr>
        <td><a href="./pull/depth">获取标的盘口</a></td>
    </tr>
    <tr>
        <td><a href="./pull/brokers">获取标的经纪队列</a></td>
    </tr>
    <tr>
        <td><a href="./pull/broker-ids">获取券商席位 id</a></td>
    </tr>
    <tr>
        <td><a href="./pull/trade">获取标的成交明细</a></td>
    </tr>
    <tr>
        <td><a href="./pull/intraday">获取标的分时</a></td>
    </tr>
    <tr>
        <td><a href="./pull/candlestick">获取标的 K 线</a></td>
    </tr>
    <tr>
        <td><a href="./pull/optionchain-date">获取标的的期权链到期日列表</a></td>
    </tr>
    <tr>
        <td><a href="./pull/optionchain-date-strike">获取标的的期权链到期日期权标的列表</a></td>
    </tr>
    <tr>
        <td><a href="./pull/issuer">获取轮证发行商 id</a></td>
    </tr>
    <tr>
        <td><a href="./pull/warrant-filter">获取轮证筛选列表</a></td>
    </tr>
    <tr>
        <td><a href="./pull/trade-session">获取各市场当日交易时段</a></td>
    </tr>
    <tr>
        <td><a href="./pull/trade-day">获取市场交易日</a></td>
    </tr>
    <tr>
        <td><a href="./pull/capital_flow_intraday">获取标的当日资金流向</a></td>
    </tr>
    <tr>
        <td><a href="./pull/capital_distribution">获取标的当日资金分布</a></td>
    </tr>
    <tr>
        <td><a href="./pull/calc-index">获取标的计算指标</a></td>
    </tr>
    <tr>
        <td><a href="./pull/history-candlestick">获取标的历史 k 线</a></td>
    </tr>
    <tr>
        <td rowspan="3">订阅</td>
        <td><a href="./subscribe/subscription">获取已订阅标的行情</a></td>
    </tr>
    <tr>
        <td><a href="./subscribe/subscribe">订阅行情数据</a></td>
    </tr>
    <tr>
        <td><a href="./subscribe/unsubscribe">取消订阅行情数据</a></td>
    </tr>
    <tr>
        <td rowspan="4">推送</td>
        <td><a href="./push/quote">实时价格推送</a></td>
    </tr>
    <tr>
        <td><a href="./push/depth">实时盘口订阅</a></td>
    </tr>
    <tr>
        <td><a href="./push/broker">实时经纪队列订阅</a></td>
    </tr>
    <tr>
        <td><a href="./push/trade">实时成交明细订阅</a></td>
    </tr>
    <tr>
        <td rowspan="4">个性化</td>
        <td><a href="./individual/watchlist_create_group">创建自选股分组</a></td>
    </tr>
    <tr>
        <td><a href="./individual/watchlist_delete_group">删除自选股分组</a></td>
    </tr>
    <tr>
        <td><a href="./individual/watchlist_groups">获取自选股分组</a></td>
    </tr>
    <tr>
        <td><a href="./individual/watchlist_update_group">更新自选股分组</a></td>
    </tr>
    <tr>
        <td rowspan="1">标的</td>
        <td><a href="./security/security_list">获取标的列表</a></td>
    </tr>
</table>

#### 标的代码说明

标的代码使用 `ticker.region` 格式，`ticker` 表示标的代码，各个市场的标的代码示例：

- 美股市场：`region` 为 `US`，例如：`AAPL.US`
- 港股市场：`region` 为 `HK`，例如：`700.HK`
- A 股市场：`region` 上交所为 `SH`，深交所为 `SZ`，例如：`399001.SZ`，`600519.SH`

> **新加坡市场（SG）：** 新加坡市场的实时行情暂未通过 Longbridge Developers（API / CLI / MCP）开放，如需查询新加坡股票行情，请使用 [Longbridge 客户端](https://longbridge.com/download)查询。

#### 接入方式

1. 使用私有协议，长连接方式进行接入，接入方法请参考 <a href="../socket/protocol/overview" target="_blank">二进制通信协议</a>。
2. 使用 SDK 进行接入，[SDK 介绍及下载地址](https://open.longbridge.com/sdk)。

#### 业务数据序列化方式

行情的请求、响应、推送数据作为业务数据，存放在私有协议的数据包 body 部分。
我们使用 [Protobuf](https://developers.google.cn/protocol-buffers) 协议对业务数据进行序列化，相较于常见的文本协议（如 JSON, XML 等），Protobuf 协议具有如下优点：

- 序列化时间快
- 数据包体积小
- 较强的版本前向后向兼容性

行情 Protobuf 协议文档[下载地址](https://github.com/longbridge/openapi-protobufs/blob/main/quote/api.proto)。

#### 行情权限等级

所有行情接口均需要 OpenAPI 行情权限。**OpenAPI 行情权限与手机客户端/PC/网页端权限完全独立**，需单独开通。

| 权限等级             | 包含内容                                                | 获取方式                                              |
| -------------------- | ------------------------------------------------------- | ----------------------------------------------------- |
| **基础行情**         | 美/A 股实时报价；港股 BMP（约 15 分钟延迟，不支持推送） | 开通 OpenAPI 后自动获得                               |
| **LV1 实时**（港股） | 港股实时报价 + WebSocket 推送支持                       | 通过行情商城购买「LV1 实时行情 (OpenAPI)」            |
| **LV2 订阅**         | Level 2 买卖盘（depth）、港股经纪商队列（brokers）      | 通过行情商城购买 LV2 订阅卡                           |
| **盘前盘后**（美股） | 美股盘前/盘后延伸时段数据                               | 已包含在 US LV1 中免费提供，设置 `LONGBRIDGE_ENABLE_OVERNIGHT=true` 即可 |

查看当前权限：[开发者中心](https://open.longbridge.com/dashboard)。购买行情卡：**Longbridge App → 我的 → 我的行情 → 行情商城**。

### 命名词典

- **官方页面**：[命名词典](https://open.longbridge.com/zh-CN/docs/quote/objects)

### 行情命名词典

#### TradeStatus - 交易状态

交易状态

| ID  | 描述            |
| --- | --------------- |
| 0   | 正常交易        |
| 1   | 停牌            |
| 2   | 退市            |
| 3   | 熔断            |
| 4   | 新股待上市      |
| 5   | 代码变更        |
| 6   | 待开盘          |
| 7   | 拆合股暂停交易  |
| 8   | 已到期 (衍生品) |
| 9   | 轮证待上市      |
| 10  | 终止交易        |

##### Protobuf

```protobuf
enum TradeStatus {
  NORMAL = 0;
  HALTED = 1;
  DELISTED = 2;
  FUSE = 3;
  PREPARE_LIST = 4;
  CODE_MOVED = 5;
  TO_BE_OPENED = 6;
  SPLIT_STOCK_HALTS = 7;
  EXPIRED = 8;
  WARRANT_PREPARE_LIST = 9;
  SUSPEND_TRADE = 10;
}
```

#### TradeSession - 交易时段

交易时段

| ID  | 描述     |
| --- | -------- |
| 0   | 盘中交易 |
| 1   | 盘前交易 |
| 2   | 盘后交易 |
| 3   | 夜盘交易 |

##### Protobuf

```protobuf
enum TradeSession {
  NORMAL_TRADE = 0;
  PRE_TRADE = 1;
  POST_TRADE = 2;
}
```

#### Period - K 线周期

| ID   | 描述            |
| ---- | --------------- |
| 1    | 一分钟 k 线     |
| 2    | 两分钟 k 线     |
| 3    | 三分钟 k 线     |
| 5    | 五分钟 k 线     |
| 10   | 十分钟 k 线     |
| 15   | 十五分钟 k 线   |
| 20   | 二十分钟 k 线   |
| 30   | 三十分钟 k 线   |
| 45   | 四十五分钟 k 线 |
| 60   | 六十分钟 k 线   |
| 120  | 两小时 k 线     |
| 180  | 三小时 k 线     |
| 240  | 四小时 k 线     |
| 1000 | 日 k 线         |
| 2000 | 周 k 线         |
| 3000 | 月 k 线         |
| 3500 | 季 k 线         |
| 4000 | 年 k 线         |

##### Protobuf

```protobuf
enum Period {
  UNKNOWN_PERIOD = 0;
  ONE_MINUTE = 1;
  FIVE_MINUTE = 5;
  FIFTEEN_MINUTE = 15;
  THIRTY_MINUTE = 30;
  SIXTY_MINUTE = 60;
  DAY = 1000;
  WEEK = 2000;
  MONTH = 3000;
  YEAR = 4000;
}
```

#### AdjustType - K 线复权类型

| ID  | 描述   |
| --- | ------ |
| 0   | 除权   |
| 1   | 前复权 |

##### Protobuf

```protobuf
enum AdjustType {
  NO_ADJUST = 0;
  FORWARD_ADJUST = 1;
}
```

#### SubType - 订阅数据的类型

| ID  | 描述     |
| --- | -------- |
| 1   | 价格     |
| 2   | 买卖盘口 |
| 3   | 经纪队列 |
| 4   | 逐笔明细 |

##### Protobuf

```protobuf
enum SubType {
  UNKNOWN_TYPE = 0;
  QUOTE = 1;
  DEPTH = 2;
  BROKERS = 3;
  TRADE = 4;
}
```

#### CalcIndex - 计算指标

| ID  | 描述         | 支持的标的类型   |
| --- | ------------ | ---------------- |
| 1   | 最新价       | 所有类型         |
| 2   | 涨跌额       | 所有类型         |
| 3   | 涨跌幅       | 所有类型         |
| 4   | 成交量       | 所有类型         |
| 5   | 成交额       | 所有类型         |
| 6   | 年初至今涨幅 | 期权、轮证无数据 |
| 7   | 换手率       | 期权、轮证无数据 |
| 8   | 总市值       | 期权、轮证无数据 |
| 9   | 资金流向     | 期权、轮证无数据 |
| 10  | 振幅         | 期权、轮证无数据 |
| 11  | 量比         | 期权、轮证无数据 |
| 12  | 市盈率 (TTM) | 期权、轮证无数据 |
| 13  | 市净率       | 期权、轮证无数据 |
| 14  | 股息率 (TTM) | 期权、轮证无数据 |
| 15  | 五日涨幅     | 期权、轮证无数据 |
| 16  | 十日涨幅     | 期权、轮证无数据 |
| 17  | 半年涨幅     | 期权、轮证无数据 |
| 18  | 五分钟涨幅   | 期权、轮证无数据 |
| 19  | 到期日       | 仅期权、轮证适用 |
| 20  | 行权价       | 仅期权、轮证适用 |
| 21  | 上限价       | 仅轮证适用       |
| 22  | 下限价       | 仅轮证适用       |
| 23  | 街货量       | 仅轮证适用       |
| 24  | 街货比       | 仅轮证适用       |
| 25  | 溢价率       | 仅期权、轮证适用 |
| 26  | 价内/价外    | 仅轮证适用       |
| 27  | 隐含波动率   | 仅期权、轮证适用 |
| 28  | 对冲值       | 仅轮证适用       |
| 29  | 收回价       | 仅轮证适用       |
| 30  | 距收回价     | 仅轮证适用       |
| 31  | 有效杠杆     | 仅轮证适用       |
| 32  | 杠杆比率     | 仅轮证适用       |
| 33  | 换股比率     | 仅轮证适用       |
| 34  | 打和点       | 仅轮证适用       |
| 35  | 未平仓数     | 仅期权适用       |
| 36  | Delta        | 仅期权适用       |
| 37  | Gamma        | 仅期权适用       |
| 38  | Theta        | 仅期权适用       |
| 39  | Vega         | 仅期权适用       |
| 40  | Rho          | 仅期权适用       |

##### Protobuf

```protobuf
enum CalcIndex {
  CALCINDEX_UNKNOWN = 0;
  CALCINDEX_LAST_DONE = 1;
  CALCINDEX_CHANGE_VAL = 2;
  CALCINDEX_CHANGE_RATE = 3;
  CALCINDEX_VOLUME = 4;
  CALCINDEX_TURNOVER = 5;
  CALCINDEX_YTD_CHANGE_RATE = 6;
  CALCINDEX_TURNOVER_RATE = 7;
  CALCINDEX_TOTAL_MARKET_VALUE = 8;
  CALCINDEX_CAPITAL_FLOW = 9;
  CALCINDEX_AMPLITUDE = 10;
  CALCINDEX_VOLUME_RATIO = 11;
  CALCINDEX_PE_TTM_RATIO = 12;
  CALCINDEX_PB_RATIO = 13;
  CALCINDEX_DIVIDEND_RATIO_TTM = 14;
  CALCINDEX_FIVE_DAY_CHANGE_RATE = 15;
  CALCINDEX_TEN_DAY_CHANGE_RATE = 16;
  CALCINDEX_HALF_YEAR_CHANGE_RATE = 17;
  CALCINDEX_FIVE_MINUTES_CHANGE_RATE = 18;
  CALCINDEX_EXPIRY_DATE = 19;
  CALCINDEX_STRIKE_PRICE = 20;
  CALCINDEX_UPPER_STRIKE_PRICE = 21;
  CALCINDEX_LOWER_STRIKE_PRICE = 22;
  CALCINDEX_OUTSTANDING_QTY = 23;
  CALCINDEX_OUTSTANDING_RATIO = 24;
  CALCINDEX_PREMIUM = 25;
  CALCINDEX_ITM_OTM = 26;
  CALCINDEX_IMPLIED_VOLATILITY = 27;
  CALCINDEX_WARRANT_DELTA = 28;
  CALCINDEX_CALL_PRICE = 29;
  CALCINDEX_TO_CALL_PRICE = 30;
  CALCINDEX_EFFECTIVE_LEVERAGE = 31;
  CALCINDEX_LEVERAGE_RATIO = 32;
  CALCINDEX_CONVERSION_RATIO = 33;
  CALCINDEX_BALANCE_POINT = 34;
  CALCINDEX_OPEN_INTEREST = 35;
  CALCINDEX_DELTA = 36;
  CALCINDEX_GAMMA = 37;
  CALCINDEX_THETA = 38;
  CALCINDEX_VEGA = 39;
  CALCINDEX_RHO = 40;
}
```

#### Board - 标的板块

| 板块             | 描述                             |
| ---------------- | -------------------------------- |
| USMain           | 美股主板                         |
| USPink           | 粉单市场                         |
| USDJI            | 道琼斯指数                       |
| USNSDQ           | 纳斯达克指数                     |
| USSector         | 美股行业概念                     |
| USOption         | 美股期权                         |
| USOptionS        | 美股特殊期权（收盘时间为 16:15） |
| HKEquity         | 港股股本证券                     |
| HKPreIPO         | 港股暗盘                         |
| HKWarrant        | 港股轮证                         |
| HKHS             | 恒生指数                         |
| HKSector         | 港股行业概念                     |
| SHMainConnect    | 上证主板 - 互联互通              |
| SHMainNonConnect | 上证主板 - 非互联互通            |
| SHSTAR           | 科创板                           |
| CNIX             | 沪深指数                         |
| CNSector         | 沪深行业概念                     |
| SZMainConnect    | 深证主板 - 互联互通              |
| SZMainNonConnect | 深证主板 - 非互联互通            |
| SZGEMConnect     | 创业板 - 互联互通                |
| SZGEMNonConnect  | 创业板 - 非互联互通              |
| SGMain           | 新加坡主板                       |
| STI              | 新加坡海峡指数                   |
| SGSector         | 新加坡行业概念                   |

### 概述

- **官方页面**：[概述](https://open.longbridge.com/zh-CN/docs/quote/subscribe/overview)

Streaming 通过 WebSocket 订阅的方式提供实时行情数据。无需轮询，只需订阅指定标的和数据类型，服务端会在行情变动时主动推送更新到你的连接。

#### 工作原理

1. **建立连接** — 通过 SDK 或[二进制通信协议](../../socket/protocol/overview)连接到 Longbridge WebSocket 服务。
2. **订阅** — 调用[订阅](./subscribe)接口，指定需要接收推送的标的和数据类型（报价、盘口、逐笔、经纪队列）。
3. **接收推送** — 行情发生变动时，服务端实时推送数据到你的连接。
4. **取消订阅** — 调用[取消订阅](./unsubscribe)停止接收特定标的或数据类型的推送。

#### 订阅类型

| 类型 | 说明 |
|------|------|
| `Quote` | 实时买卖价及成交价 |
| `Depth` | Level 2 买卖盘口 |
| `Brokers` | 经纪队列数据 |
| `Trade` | 实时逐笔成交 |

#### 订阅 vs. 直接查询

订阅适合需要实时增量更新的场景。如需一次性或按需查询，可使用以下拉取接口：

| 数据 | 拉取接口 |
|------|----------|
| 报价 | [实时报价](../stocks/quote) |
| 盘口 | [盘口](../stocks/depth) |
| 经纪队列 | [经纪队列](../stocks/brokers) |
| 逐笔明细 | [逐笔明细](../stocks/trade) |
| 分时数据 | [分时数据](../stocks/intraday) |
| K 线 | [K 线](../stocks/candlestick) |

#### 注意事项

- 订阅状态与当前连接绑定，断线后自动清除。
- 可通过[获取订阅信息](./subsciption)随时查询当前活跃的订阅列表。
- 可订阅的数据类型取决于你的行情权限，详见[行情权限等级](../overview#行情权限等级)。

### 概览

- **官方页面**：[概览](https://open.longbridge.com/zh-CN/docs/fundamental/overview)

### 基本面 API 概览

研究与市场数据接口，涵盖公司基本面、市场结构和财经日历。所有接口均为只读，通过 SDK 调用。

#### FundamentalContext

公司层面的财务数据与企业信息。

| 方法 | 说明 |
|---|---|
| [company_profile](./fundamental/company-profile) | 公司概况、行业及基本信息 |
| [financial_report](./fundamental/financial-report) | 利润表、资产负债表和现金流量表 |
| [valuations](./fundamental/valuations) | PE、PB、PS、EV/EBITDA 等估值指标 |
| [ratings](./fundamental/ratings) | 机构评级与目标价 |
| [dividends](./fundamental/dividends) | 历史分红记录 |
| [fund_holdings](./fundamental/fund-holdings) | 机构及基金持仓 |
| [shareholders](./fundamental/shareholders) | 主要股东 |
| [executives](./fundamental/executives) | 管理层与董事会成员 |
| [corporate_actions](./fundamental/corporate-actions) | 拆股、送股、配股等公司行动 |

#### MarketContext

市场层面数据，包括指数成分、经纪商持仓和异动扫描。

| 方法 | 说明 |
|---|---|
| [market_status](./market/market-status) | 各市场当前交易状态 |
| [trading_stats](./market/trading-stats) | 标的盘中交易统计 |
| [index_components](./market/index-components) | 指数成分股列表 |
| [ah_premium](./market/ah-premium) | 两地上市股票的 A/H 股溢价率 |
| [broker_positions](./market/broker-positions) | 港股经纪商持仓（中央结算） |
| [unusual_items](./market/unusual-items) | 异常价格或成交量异动 |

#### CalendarContext

[财经事件日历](https://longbridge.com/calendar/macrodata)，用于跟踪财报、分红和宏观数据发布。

| 方法 | 说明 |
|---|---|
| [earnings_calendar](./calendar/earnings-calendar) | 即将发布和近期的财报日期 |
| [dividend_calendar](./calendar/dividend-calendar) | 除权除息日和派息日 |
| [ipo_calendar](./calendar/ipo-calendar) | 新股认购和上市日期 |
| [split_calendar](./calendar/split-calendar) | 股票拆分生效日期 |
| [macro_calendar](./calendar/macro-calendar) | 宏观经济数据发布计划 |

### 概览

- **官方页面**：[概览](https://open.longbridge.com/zh-CN/docs/content/overview)

### 资讯与社区接口概览

资讯与社区接口提供[个股资讯](https://longbridge.com/news)、社区讨论和股单管理能力。所有接口均通过 HTTP 请求访问，也可以使用 [SDK](https://open.longbridge.com/sdk) 调用。

<table>
    <thead>
    <tr>
        <td>类型</td>
        <td>介绍</td>
    </tr>
    </thead>
    <tbody>
    <tr>
        <td rowspan="1">资讯</td>
        <td><a href="./news/news">个股资讯</a></td>
    </tr>
    <tr>
        <td rowspan="6">讨论</td>
        <td><a href="./topics/topics">标的社区讨论</a></td>
    </tr>
    <tr>
        <td><a href="./topics/my-topics">我的讨论</a></td>
    </tr>
    <tr>
        <td><a href="./topics/create-topic">创建讨论</a></td>
    </tr>
    <tr>
        <td><a href="./topics/topic-detail">讨论详情</a></td>
    </tr>
    <tr>
        <td><a href="./topics/topic-replies">讨论回复</a></td>
    </tr>
    <tr>
        <td><a href="./topics/create-topic-reply">创建讨论回复</a></td>
    </tr>
    <tr>
        <td rowspan="9">股单</td>
        <td><a href="./sharelist/list-sharelist">股单列表</a></td>
    </tr>
    <tr>
        <td><a href="./sharelist/create-sharelist">创建股单</a></td>
    </tr>
    <tr>
        <td><a href="./sharelist/update-sharelist">更新股单</a></td>
    </tr>
    <tr>
        <td><a href="./sharelist/delete-sharelist">删除股单</a></td>
    </tr>
    <tr>
        <td><a href="./sharelist/sharelist-detail">股单详情</a></td>
    </tr>
    <tr>
        <td><a href="./sharelist/popular-sharelist">热门股单</a></td>
    </tr>
    <tr>
        <td><a href="./sharelist/add-securities">添加标的到股单</a></td>
    </tr>
    <tr>
        <td><a href="./sharelist/remove-securities">从股单移除标的</a></td>
    </tr>
    <tr>
        <td><a href="./sharelist/sort-securities">股单标的排序</a></td>
    </tr>
    </tbody>
</table>

### 概览

- **官方页面**：[概览](https://open.longbridge.com/zh-CN/docs/trade/trade-overview)

### 交易接口总览

<table>
    <thead>
    <tr>
        <td>类型</td>
        <td>功能简介</td>
    </tr>
    </thead>
    <tbody>
    <tr>
        <td rowspan="7">交易</td>
        <td><a href="./order/submit">委托下单</a></td>
    </tr>
    <tr>
        <td><a href="./order/replace">改单</a></td>
    </tr>
    <tr>
        <td><a href="./order/withdraw">撤单</a></td>
    </tr>
    <tr>
        <td><a href="./order/today_orders">获取当日订单</a></td>
    </tr>
    <tr>
        <td><a href="./order/history_orders">获取历史订单</a></td>
    </tr>
    <tr>
        <td><a href="./execution/today_executions">获取当日成交明细</a></td>
    </tr>
    <tr>
        <td><a href="./execution/history_executions">获取历史成交明细</a></td>
    </tr>
    <tr>
        <td rowspan="4">资产</td>
        <td><a href="./asset/account">获取账户资金信息</a></td>
    </tr>
    <tr>
        <td><a href="./asset/cashflow">获取资金流水信息</a></td>
    </tr>
    <tr>
        <td><a href="./asset/fund">获取基金持仓信息</a></td>
    </tr>
    <tr>
        <td><a href="./asset/stock">获取股票持仓信息</a></td>
    </tr>
    </tbody>
</table>

### 交易命名词典

- **官方页面**：[交易命名词典](https://open.longbridge.com/zh-CN/docs/trade/trade-definition)

#### OrderType

- 说明：港股支持订单类型

| 枚举值  | 描述                        |
| ------- | --------------------------- |
| LO      | 限价单                      |
| ELO     | 增强限价单                  |
| MO      | 市价单                      |
| AO      | 竞价市价单                  |
| ALO     | 竞价限价单                  |
| ODD     | 碎股单挂单                  |
| LIT     | 触价限价单                  |
| MIT     | 触价市价单                  |
| TSLPAMT | 跟踪止损限价单 (跟踪金额)   |
| TSLPPCT | 跟踪止损限价单 (跟踪涨跌幅) |
| SLO     | 特殊限价单，不支持改单      |

- 说明：美股支持订单类型

| 枚举值  | 描述                        |
| ------- | --------------------------- |
| LO      | 限价单                      |
| MO      | 市价单                      |
| LIT     | 触价限价单                  |
| MIT     | 触价市价单                  |
| TSLPAMT | 跟踪止损限价单 (跟踪金额)   |
| TSLPPCT | 跟踪止损限价单 (跟踪涨跌幅) |

#### OrderStatus

- 说明：订单状态

| 枚举值               | 描述              |
| -------------------- | ----------------- |
| NotReported          | 待提交            |
| ReplacedNotReported  | 待提交 (改单成功) |
| ProtectedNotReported | 待提交 (保价订单) |
| VarietiesNotReported | 待提交 (条件单)   |
| FilledStatus         | 已成交            |
| WaitToNew            | 已提待报          |
| NewStatus            | 已委托            |
| WaitToReplace        | 修改待报          |
| PendingReplaceStatus | 待修改            |
| ReplacedStatus       | 已修改            |
| PartialFilledStatus  | 部分成交          |
| WaitToCancel         | 撤销待报          |
| PendingCancelStatus  | 待撤回            |
| RejectedStatus       | 已拒绝            |
| CanceledStatus       | 已撤单            |
| ExpiredStatus        | 已过期            |
| PartialWithdrawal    | 部分撤单          |

#### Market

- 说明：市场

| 枚举值 | 描述 |
| ------ | ---- |
| HK     | 港股 |
| US     | 美股 |

#### WebSocket 推送通知

- WebSocket 推送通知字段说明

| 字段名             | 类型   | 注释                                                                                                                                 |
| ------------------ | ------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| side               | string | 买卖方向<br/><br/>**可选值**<br/>`Buy` - 买入<br />`Sell` - 卖出                                                                     |
| stock_name         | string | 公司名称                                                                                                                             |
| submitted_quantity | string | 委托数量                                                                                                                             |
| symbol             | string | 订单标的                                                                                                                             |
| order_type         | string | [订单类型](./trade-definition#ordertype)                                                                                             |
| submitted_price    | string | 委托价格                                                                                                                             |
| executed_quantity  | string | 成交数量                                                                                                                             |
| executed_price     | string | 成交价格                                                                                                                             |
| order_id           | string | 订单 id                                                                                                                              |
| currency           | string | 结算货币                                                                                                                             |
| status             | string | [订单状态](./trade-definition#orderstatus)                                                                                           |
| submitted_at       | string | 下单时间，格式为时间戳 (秒)                                                                                                          |
| updated_at         | string | 最近更新时间                                                                                                                         |
| trigger_price      | string | 触发价格                                                                                                                             |
| msg                | string | 拒绝理由，备注信息                                                                                                                   |
| tag                | string | 订单标记<br/><br/>**可选值**<br/>`Normal` - 普通订单<br />`GTC` - 长期单<br />`Grey` - 暗盘单                                        |
| trigger_status     | string | 条件单触发状态<br/><br/>**可选值**<br/>`NOT_USED` - 未激活 <br />`DEACTIVE` - 已失效<br />`ACTIVE` - 已激活<br />`RELEASED` - 已触发 |
| trigger_at         | string | 触发时间                                                                                                                             |
| trailing_amount    | string | 条件单跟踪金额                                                                                                                       |
| trailing_percent   | string | 条件单跟踪涨跌幅                                                                                                                     |
| limit_offset       | string | 指定价差                                                                                                                             |
| account_no         | string | 用户端账号                                                                                                                           |
| remark         | string | 备注                                                                                                                           |
| last_share         | string | 最新成交数量																																													 |
| last_price         | string | 最新成交价格																																													 |

##### 示例

```json
{
	"event": "order_changed_lb",
	"data": {
		"side": "Buy",
		"stock_name": "腾讯控股",
		"submitted_quantity": "1000",
		"symbol": "700.HK",
		"order_type": "LO",
		"submitted_price": "213.2",
		"executed_quantity": "1000",
		"executed_price": "213.2",
		"order_id": "27",
		"currency": "HKD",
		"status": "NewStatus",
		"submitted_at": "1562761893",
		"updated_at": "1562761893",
		"trigger_price": "213.0",
		"msg": "Insufficient Qty - 1000",
		"tag": "GTC",
		"trigger_status": "ACTIVE",
		"trigger_at": "1562761893",
		"trailing_amount": "5",
		"trailing_percent": "1",
		"limit_offset": "0.01",
		"account_no": "HK123445",
		"last_share": "100",
		"last_price": "234",
		"remark": "abc"
	}
}
```

### 概览

- **官方页面**：[概览](https://open.longbridge.com/zh-CN/docs/account/overview)

### 账户 API 概览

账户管理接口，涵盖组合分析、股价提醒、定投计划和股单管理。大多数接口需要交易级别的认证权限。

#### PortfolioContext

组合盈亏分析与外汇汇率查询。

| 方法 | 说明 |
|---|---|
| [profit_analysis_summary](./portfolio/profit-analysis-summary) | 组合整体盈亏汇总 |
| [profit_analysis_detail](./portfolio/profit-analysis-detail) | 按持仓明细的盈亏拆分 |
| [profit_analysis_by_market](./portfolio/profit-analysis-by-market) | 按市场分组的盈亏统计 |
| [capital_flow](./portfolio/capital-flow) | 账户资金流水记录 |
| [exchange_rates](./portfolio/exchange-rates) | 支持币种的当前汇率 |

#### AlertContext

创建和管理标的股价提醒。

| 方法 | 说明 |
|---|---|
| [list_alerts](./alert/list-alerts) | 查看所有有效的股价提醒 |
| [create_alert](./alert/create-alert) | 创建新的股价提醒 |
| [update_alert](./alert/update-alert) | 修改已有提醒 |
| [delete_alert](./alert/delete-alert) | 删除股价提醒 |

#### DCAContext

管理定期定额投资（定投）计划。

| 方法 | 说明 |
|---|---|
| [list_dca](./dca/list-dca) | 查看所有定投计划 |
| [create_dca](./dca/create-dca) | 新建定投计划 |
| [dca_history](./dca/dca-history) | 查看定投计划的执行记录 |
| [delete_dca](./dca/delete-dca) | 取消定投计划 |

#### SharelistContext

创建和管理社区股单（可分享给他人的自选列表）。

| 方法 | 说明 |
|---|---|
| [list_sharelist](./sharelist/list-sharelist) | 查看所有股单 |
| [create_sharelist](./sharelist/create-sharelist) | 新建股单 |
| [update_sharelist](./sharelist/update-sharelist) | 更新股单 |
| [delete_sharelist](./sharelist/delete-sharelist) | 删除股单 |

### SSE 事件

- **官方页面**：[SSE 事件](https://open.longbridge.com/zh-CN/docs/ai/chat/events)

流式模式（`Accept: text/event-stream`）下，[发起对话](/zh-CN/docs/ai/chat/conversation)和[继续对话](/zh-CN/docs/ai/chat/continue)会以一系列 SSE 事件推送运行过程。本页列出所有事件类型及解析方式。

#### 帧格式

每一帧 SSE 都使用同样的信封结构：SSE 的 `event` 字段恒为 `message`，`data` 字段是一个 JSON 对象：

```
event: message
data: {"event":"<event_type>","workflow_run_id":"745910371102313","data":{...}}
```

| 名称            | 类型   | 说明                                             |
| --------------- | ------ | ------------------------------------------------ |
| event           | string | 事件类型，按此字段分发处理                       |
| workflow_run_id | string | 本次运行的 ID，为数字 ID 的字符串形式（如 `"745910371102313"`），同一次运行的所有事件中该值一致 |
| data            | object | 事件负载，结构随事件类型而不同（见下文）         |

解析规则：

- **按 `data.event` 分发**，而不是 SSE 的 `event` 字段（它恒为 `message`）。
- **忽略未知事件类型。** 事件类型可能随时新增，只处理已知事件的客户端可保持向前兼容。
- 除特别说明外，`started_at` / `finished_at` 为 Unix 秒级时间戳，`elapsed_time` 为秒数。

#### 典型事件序列

一次运行始于 `chat_started`、止于 `chat_finished`，中间的事件取决于运行结果：

**成功：**

```
chat_started → workflow_started → thinking_started → message (type=think) ...
→ node_tool_use_started / node_tool_use_finished ...
→ thinking_finished → message (type=answer) ...
→ workflow_finished (status=succeeded) → chat_finished
```

**中断**（Agent 需要你补充信息，通过[继续对话](/zh-CN/docs/ai/chat/continue)恢复）：

```
chat_started → workflow_started → ... → human_interaction_required → chat_finished
```

注意：中断的运行**不会**发送 `workflow_finished`；继续被中断的运行时，恢复后的流**不会**再次发送 `workflow_started`。

**失败：**

```
chat_started → workflow_started → ... → workflow_finished (status=failed) → chat_finished
```

#### 最简客户端

纯问答场景只需处理四种事件，其余事件都是可选的过程展示：

| 事件                         | 处理方式                                               |
| ---------------------------- | ------------------------------------------------------ |
| `message`（`type=answer`）   | 将 `data.text` 追加到正在展示的回答中                  |
| `human_interaction_required` | 展示问题，携带答案调用继续对话接口                     |
| `workflow_finished`          | 读取最终 `status` 和 `outputs.answer`；失败时展示错误  |
| `chat_finished`              | 关闭流，本次运行结束                                   |

#### 会话生命周期

##### chat_started

每个流的第一个事件。会话和消息记录已创建；保存 `chat_uid`（用于追问）和 `message_id`（用于中断后继续）。

| 名称       | 类型   | 说明                       |
| ---------- | ------ | -------------------------- |
| chat_id    | int64  | 会话内部 ID                |
| chat_uid   | string | 会话标识，用于后续请求     |
| message_id | int64  | 本轮消息 ID                |

```json
{"event":"chat_started","workflow_run_id":"745910371102313","data":{"chat_id":1001,"chat_uid":"ct_9f2c1a5b","message_id":42}}
```

##### chat_finished

每个流的最后一个事件，之后服务端关闭连接。

| 名称          | 类型   | 说明                           |
| ------------- | ------ | ------------------------------ |
| chat_id       | int64  | 会话内部 ID                    |
| chat_uid      | string | 会话标识                       |
| message_id    | int64  | 本轮消息 ID                    |
| error         | string | 错误详情，成功时为空           |
| error_message | string | 面向用户的错误信息，成功时为空 |

#### 运行生命周期

##### workflow_started

Agent 运行已开始。通过继续对话恢复被中断的运行时不会发送此事件。

| 名称        | 类型   | 说明                                                   |
| ----------- | ------ | ------------------------------------------------------ |
| workflow_id | int64  | 该 Agent 底层工作流的 ID                               |
| started_at  | int64  | 开始时间（Unix 秒）                                    |
| inputs      | object | 运行输入                                               |
| hit_cache   | bool   | 为 `true` 时表示答案命中缓存，流会直接进入回答阶段     |

##### workflow_finished

运行已结束——成功、失败或被用户停止。在此读取最终结果。

| 名称          | 类型     | 说明                                                       |
| ------------- | -------- | ---------------------------------------------------------- |
| status        | string   | `succeeded` / `failed` / `stopped`                         |
| outputs       | object   | 运行输出；`outputs.answer` 为完整的最终回答文本            |
| elapsed_time  | number   | 运行耗时（秒）                                             |
| error         | string   | 本地化的错误描述，仅 `status` 为 `failed` 时存在           |
| error_code    | int32    | 错误码，仅 `status` 为 `failed` 时存在                     |
| error_message | string   | 面向用户的错误信息，仅失败时存在                           |
| error_args    | object   | 额外错误上下文（如 `workflow_run_id`），可能省略           |
| process_data  | object[] | 运行经过的过程阶段，仅用于展示                             |

```json
{"event":"workflow_finished","workflow_run_id":"745910371102313","data":{"status":"succeeded","elapsed_time":3.21,"outputs":{"answer":"特斯拉（TSLA.US）近期..."}}}
```

说明：

- `outputs.answer` 是权威的完整回答。如果你通过 `message` 事件拼接了回答，可用它校验或替换。
- `status` 为 `stopped`（用户停止运行）时，`outputs.answer` 为已生成的部分回答。

#### 回答流式输出

##### message

增量文本片段。这是频率最高的事件，按到达顺序拼接 `text` 即可。

| 名称                 | 类型   | 说明                                                                     |
| -------------------- | ------ | ------------------------------------------------------------------------ |
| text                 | string | 增量文本片段                                                             |
| type                 | string | `answer` — 最终回答文本；`think` — 推理过程；`process` — 阶段进度描述    |
| key                  | string | 片段所属流段的标识。相同 `key` 的片段构成一个连续块，渲染时按 `key` 分组 |
| started_at           | int64  | 该流段开始时间（Unix 秒）                                                |
| stage                | string | 阶段标识，仅 `type=process` 时存在                                       |
| stage_title          | string | 阶段进行中的标题，仅 `type=process` 时存在                               |
| stage_finished_title | string | 阶段完成后的标题，仅 `type=process` 时存在                               |
| outputs              | object | 附加在片段上的额外负载，通常不存在                                       |

```json
{"event":"message","workflow_run_id":"745910371102313","data":{"text":"特斯拉","type":"answer","key":"n_llm_1:answer","started_at":1752048000}}
```

解析：

- 只有 `type=answer` 的片段属于用户可见的回答，全部拼接后与 `workflow_finished.outputs.answer` 一致。
- `type=think` 的片段是 Agent 的中间推理，可放入可折叠的「思考」区域展示，也可忽略。
- `type=process` 的片段描述阶段进度，附带 `stage` 系列字段用于分组。

#### 思考阶段

##### thinking_started

Agent 进入推理阶段（分析问题、规划工具调用）。在它与 `thinking_finished` 之间可能出现 `type=think` 的 `message` 事件和工具调用事件。

| 名称       | 类型  | 说明                 |
| ---------- | ----- | -------------------- |
| started_at | int64 | 开始时间（Unix 秒）  |

##### thinking_finished

推理阶段结束，随后是回答文本（`type=answer` 的 `message`）。

| 名称         | 类型  | 说明                 |
| ------------ | ----- | -------------------- |
| finished_at  | int64 | 结束时间（Unix 秒）  |
| elapsed_time | int32 | 推理耗时（秒）       |

#### 工具调用

Agent 在生成回答的过程中会调用工具（行情、账户、联网搜索等）。每次调用都由一对 started/finished 事件包裹——用 `tool_use_id` 配对。

这对事件覆盖**所有普通工具调用**。只有两种特殊调用改用各自的事件族上报：派生子智能体（`subagent_*`，见下文）和把另一个 Agent 作为工具调用（`agent_tool_*`，见下文）。如果你的 Agent 没有使用这两项能力，所有工具调用都只会以 `node_tool_use_started` / `node_tool_use_finished` 出现。

##### node_tool_use_started

一次工具调用已开始。

| 名称           | 类型     | 说明                                                            |
| -------------- | -------- | --------------------------------------------------------------- |
| tool_use_id    | string   | 本次调用的唯一 ID，用于与 finished 事件配对                     |
| tool_name      | string   | 工具的本地化展示名（用于界面显示）                              |
| tool_func_name | string   | 与语言无关的稳定工具标识，按工具类型处理逻辑时用它              |
| tool_args      | string   | 调用参数（JSON 字符串）                                         |
| tips           | string   | 可直接展示的进度文案（如「正在联网搜索…」）                     |
| tip_chips      | string[] | 与 `tips` 配套的短标签，可能省略                                |
| iteration      | int      | 轮次编号。同一轮（相同 `iteration`）的调用是并行执行的          |
| started_at     | int64    | 开始时间（Unix 秒）                                             |

##### node_tool_use_finished

工具调用已结束。

| 名称           | 类型     | 说明                                     |
| -------------- | -------- | ---------------------------------------- |
| tool_use_id    | string   | 与 started 事件的 `tool_use_id` 一致     |
| status         | string   | `succeeded` / `failed`                   |
| error          | string   | 失败时的错误描述                         |
| elapsed_time   | number   | 调用耗时（秒）                           |
| started_at     | int64    | 开始时间（Unix 秒）                      |
| tool_name      | string   | 本地化展示名                             |
| tool_func_name | string   | 稳定工具标识                             |
| tool_args      | string   | 调用参数（JSON 字符串）                  |
| tool_type      | string   | 工具类别                                 |
| tips           | string   | 进度文案                                 |
| tip_chips      | string[] | 短标签，可能省略                         |
| iteration      | int      | 轮次编号                                 |
| is_thinking    | bool     | 为 `true` 表示调用发生在思考阶段         |
| outputs        | object   | 过滤后的调用结果，见下                   |

`outputs` 只携带用于展示的字段：

| 字段                      | 说明                             |
| ------------------------- | -------------------------------- |
| outputs.references        | 工具结果引用的来源               |
| outputs.reference_domains | 引用来源的域名                   |
| outputs.query             | 工具执行的查询                   |
| outputs.text              | 工具的原始响应文本               |
| outputs.tool_args         | 解析后的请求参数                 |
| outputs.data              | 结构化结果，仅部分工具存在       |

```json
{"event":"node_tool_use_finished","workflow_run_id":"745910371102313","data":{"tool_use_id":"call_abc123","status":"succeeded","elapsed_time":1.42,"tool_name":"联网搜索","tool_func_name":"web_search","tool_args":"{\"query\":\"TSLA stock news\"}","tool_type":"builtin","tips":"已联网搜索","iteration":1,"is_thinking":true,"outputs":{"query":"TSLA stock news","references":[{"index":1,"title":"...","url":"..."}]}}}
```

#### 子智能体事件

Agent 派生子智能体处理子任务时，其生命周期使用独立的事件族上报，而不是 `node_tool_use_*`。

##### subagent_started

| 名称        | 类型   | 说明                                       |
| ----------- | ------ | ------------------------------------------ |
| node_id     | string | 派生子智能体的节点 ID                      |
| tool_use_id | string | 本次派生的唯一 ID，与 finished 事件配对    |
| started_at  | int64  | 开始时间（Unix 秒）                        |
| goal        | string | 分配给子智能体的目标                       |
| prompt      | string | 交给子智能体的完整任务提示词               |
| subagent_id | string | 子智能体标识，可能省略                     |
| tools       | array  | 授予子智能体的工具列表，可能省略           |

##### subagent_progress

子智能体每调用一次自己的工具就发送一次，用于在子智能体卡片内实时渲染时间线。

| 名称                 | 类型   | 说明                                             |
| -------------------- | ------ | ------------------------------------------------ |
| node_id              | string | 派生子智能体的节点 ID                            |
| parent_tool_call_id  | string | 所属 `subagent_started` 事件的 `tool_use_id`     |
| subagent_tool_name   | string | 子智能体调用的工具名                             |
| subagent_tool_args   | string | 该调用的参数（JSON 字符串）                      |
| subagent_status      | string | 该调用的状态：`running` / `succeeded` / `failed` |
| subagent_duration_ms | int64  | 该调用耗时（**毫秒**）                           |
| subagent_iteration   | int    | 子智能体内部的轮次编号                           |
| started_at           | int64  | 开始时间（Unix 秒）                              |

##### subagent_finished

| 名称         | 类型   | 说明                                                                     |
| ------------ | ------ | ------------------------------------------------------------------------ |
| node_id      | string | 派生子智能体的节点 ID                                                    |
| tool_use_id  | string | 与 `subagent_started` 的 `tool_use_id` 一致                              |
| status       | string | `succeeded` / `failed`                                                   |
| started_at   | int64  | 开始时间（Unix 秒）                                                      |
| elapsed_time | number | 子智能体总耗时（秒）                                                     |
| error        | string | 失败时的错误描述                                                         |
| outputs      | object | 子智能体结果：通常包含 `goal`、`result` 和 `subagent_tools`（其工具调用时间线） |

#### Agent 工具事件

Agent 把另一个 Agent 作为工具调用时，该内部运行使用 `agent_tool_*` 事件族上报，结构与子智能体事件相似。

##### agent_tool_started

| 名称            | 类型     | 说明                                    |
| --------------- | -------- | --------------------------------------- |
| node_id         | string   | 调用方节点 ID                           |
| tool_use_id     | string   | 本次调用的唯一 ID，与 finished 事件配对 |
| agent_tool_name | string   | 被调用 Agent 的标识                     |
| title           | string   | 展示标题，可能省略                      |
| started_at      | int64    | 开始时间（Unix 秒）                     |
| tool_args       | string   | 调用参数（JSON 字符串）                 |
| tool_name       | string   | 本地化展示名                            |
| tips            | string   | 进度文案，可能省略                      |
| tip_chips       | string[] | 短标签，可能省略                        |
| is_thinking     | bool     | 为 `true` 表示发生在思考阶段            |

##### agent_tool_progress

被委托 Agent 每进行一次内部工具调用就发送一次。

| 名称                | 类型   | 说明                                                 |
| ------------------- | ------ | ---------------------------------------------------- |
| node_id             | string | 调用方节点 ID                                        |
| parent_tool_call_id | string | 所属 `agent_tool_started` 事件的 `tool_use_id`       |
| agent_tool_name     | string | 被调用 Agent 的标识                                  |
| inner_tool_name     | string | 被委托 Agent 调用的内部工具名                        |
| inner_tool_args     | string | 该内部调用的参数（JSON 字符串）                      |
| status              | string | 内部调用的状态：`running` / `succeeded` / `failed`   |
| duration_ms         | int64  | 内部调用耗时（**毫秒**）                             |
| started_at          | int64  | 开始时间（Unix 秒）                                  |
| is_thinking         | bool   | 为 `true` 表示发生在思考阶段                         |

##### agent_tool_finished

| 名称            | 类型     | 说明                                          |
| --------------- | -------- | --------------------------------------------- |
| node_id         | string   | 调用方节点 ID                                 |
| tool_use_id     | string   | 与 `agent_tool_started` 的 `tool_use_id` 一致 |
| agent_tool_name | string   | 被调用 Agent 的标识                           |
| status          | string   | `succeeded` / `failed`                        |
| started_at      | int64    | 开始时间（Unix 秒）                           |
| elapsed_time    | number   | 总耗时（秒）                                  |
| error           | string   | 失败时的错误描述                              |
| tool_args       | string   | 调用参数（JSON 字符串）                       |
| outputs         | object   | 被委托 Agent 的结果                           |
| tool_type       | string   | 工具类别                                      |
| tips            | string   | 进度文案，可能省略                            |
| tip_chips       | string[] | 短标签，可能省略                              |
| is_thinking     | bool     | 为 `true` 表示发生在思考阶段                  |

#### 中断

##### human_interaction_required

运行已暂停：Agent 需要你补充信息或确认。收集 `questions` 的答案后调用[继续对话](/zh-CN/docs/ai/chat/continue)——答案以 `tool_call_id` 为键。

| 名称           | 类型     | 说明                                                        |
| -------------- | -------- | ----------------------------------------------------------- |
| node_id        | string   | 触发中断的节点 ID                                           |
| tool_call_id   | string   | 本次询问的 ID，继续对话时作为 `answers_by_tool_call` 的外层键 |
| questions      | object[] | 需要回答的问题                                              |
| ∟ question     | string   | 问题文本，继续对话时作为 `answers_by_tool_call` 的内层键    |
| ∟ options      | object[] | 选项，为空表示自由输入                                      |
| ∟∟ description | string   | 选项文本                                                    |
| ∟ multi_select | boolean  | 是否可多选                                                  |
| message_id     | int64    | 被暂停消息的 ID，用于继续对话接口的 URL                     |
| chat_id        | int64    | 所属会话的 ID                                               |

```json
{"event":"human_interaction_required","workflow_run_id":"745910371102313","data":{"node_id":"n_ask_human","tool_call_id":"call_abc123","questions":[{"question":"你想查看哪个时间范围？","options":[{"description":"近一周"},{"description":"近一月"}],"multi_select":false}],"message_id":43,"chat_id":1001}}
```

此事件之后流以 `chat_finished` 结束；被中断的运行不会发送 `workflow_finished`。

#### 辅助事件

以下事件均为信息性事件，最简客户端可全部忽略。

##### query_masked

用户提问中的敏感内容在处理前被脱敏。展示时用 `masked_query` 替换原始提问。

| 名称         | 类型   | 说明           |
| ------------ | ------ | -------------- |
| raw_query    | string | 原始用户提问   |
| masked_query | string | 脱敏后的提问   |

##### plan_changed

Agent 创建或更新了任务计划。

| 名称       | 类型   | 说明                     |
| ---------- | ------ | ------------------------ |
| node_id    | string | 规划节点的 ID            |
| started_at | int64  | 变更时间（Unix 秒）      |
| outputs    | object | 当前计划内容             |

此事件额外携带一个顶层 `tool_name` 字段（与 `data` 同级），标识规划工具。

##### context_compress_started / context_compress_finished

长对话会触发上下文压缩，这两个事件包裹压缩过程。与其他事件不同，这里的时间戳是 RFC 3339 字符串。

`context_compress_started`：

| 名称       | 类型   | 说明                 |
| ---------- | ------ | -------------------- |
| started_at | string | 开始时间（RFC 3339） |
| inputs     | object | 压缩输入摘要         |

`context_compress_finished`：

| 名称       | 类型   | 说明                 |
| ---------- | ------ | -------------------- |
| created_at | string | 结束时间（RFC 3339） |
| inputs     | object | 压缩输入摘要         |
| outputs    | object | 压缩结果摘要         |

## 5. 分类索引

- [Quote（行情）](#quote)：37 个接口
- [Fundamental（基本面）](#fundamental)：47 个接口
- [Market（市场状态与日历）](#market)：14 个接口
- [News & Contents（资讯、社区与股单）](#content)：16 个接口
- [Screener（选股器）](#screener)：5 个接口
- [Trade（交易与资产）](#trade)：19 个接口
- [Account（账户、组合与定投）](#account)：20 个接口
- [AI Agent（Workspace 与对话）](#ai)：4 个接口

## 6. Quote（行情）

行情 API 的权限独立于 App/PC/Web 行情权限；免费与收费通常由市场和标的类型共同决定。

### 1. 免费/基础权限

| 接口 | Python SDK | 权限/费用 |
| --- | --- | --- |
| [关键指标](https://open.longbridge.com/zh-CN/docs/quote/pull/calc-index) | QuoteContext.calc_indexes(...) | 免费/基础 |
| [资金分布](https://open.longbridge.com/zh-CN/docs/quote/pull/capital-distribution) | QuoteContext.capital_distribution(...) | 免费/基础 |
| [Tesla 今日资金流向时序](https://open.longbridge.com/zh-CN/docs/quote/pull/capital-flow-intraday) | QuoteContext.capital_flow(...) | 免费/基础 |
| [监管文件](https://open.longbridge.com/zh-CN/docs/quote/pull/filings) | QuoteContext.filings(...) | 免费/基础 |
| [沽空数据（美股 / 港股）](https://open.longbridge.com/zh-CN/docs/quote/pull/short-positions) | QuoteContext.short_positions(...) | 免费/基础 |
| [每日沽空成交量](https://open.longbridge.com/zh-CN/docs/quote/pull/short-trades) | QuoteContext.short_trades(...) | 免费/基础 |
| [期权成交量](https://open.longbridge.com/zh-CN/docs/quote/pull/option-volume) | QuoteContext.option_volume(...) | 免费/基础 |
| [日度成交量](https://open.longbridge.com/zh-CN/docs/quote/pull/option-volume-daily) | QuoteContext.option_volume_daily(...) | 免费/基础 |
| [期权链](https://open.longbridge.com/zh-CN/docs/quote/pull/optionchain-date-strike) | QuoteContext.option_chain_info_by_date(...) | 免费/基础 |
| [到期日列表](https://open.longbridge.com/zh-CN/docs/quote/pull/optionchain-date) | QuoteContext.option_chain_expiry_date_list(...) | 免费/基础 |
| [券商席位 ID](https://open.longbridge.com/zh-CN/docs/quote/pull/broker-ids) | QuoteContext.participants(...) | 免费/基础 |
| [基本信息](https://open.longbridge.com/zh-CN/docs/quote/pull/static) | QuoteContext.static_info(...) | 免费/基础 |
| [美股加密货币概览](https://open.longbridge.com/zh-CN/docs/quote/stocks/us_crypto_overview) | QuoteContext.us_crypto_overview(...) | 免费/基础 |
| [查看当前 WebSocket 实时订阅状态](https://open.longbridge.com/zh-CN/docs/quote/subscribe/subscription) | QuoteContext.subscriptions(...) | 免费/基础 |
| [订阅行情](https://open.longbridge.com/zh-CN/docs/quote/subscribe/subscribe) | QuoteContext.subscribe(...) | 免费/基础 |
| [unsubscribe](https://open.longbridge.com/zh-CN/docs/quote/subscribe/unsubscribe) | QuoteContext.unsubscribe(...) | 免费/基础 |
| [发行商列表](https://open.longbridge.com/zh-CN/docs/quote/pull/issuer) | QuoteContext.warrant_issuers(...) | 免费/基础 |
| [腾讯相关权证列表](https://open.longbridge.com/zh-CN/docs/quote/pull/warrant-filter) | QuoteContext.warrant_list(...) | 免费/基础 |
| [实时报价](https://open.longbridge.com/zh-CN/docs/quote/pull/warrant-quote) | QuoteContext.warrant_quote(...) | 免费/基础 |
| [更新置顶](https://open.longbridge.com/zh-CN/docs/quote/watchlist/update-pinned) | QuoteContext.update_pinned(...) | 免费/基础 |
| [创建新的自选股分组](https://open.longbridge.com/zh-CN/docs/quote/watchlist/watchlist_create_group) | QuoteContext.create_watchlist_group(...) | 免费/基础 |
| [删除指定分组（ID 通过 longbridge watchlist 查询）](https://open.longbridge.com/zh-CN/docs/quote/watchlist/watchlist_delete_group) | QuoteContext.delete_watchlist_group(...) | 免费/基础 |
| [查看所有自选股分组及标的](https://open.longbridge.com/zh-CN/docs/quote/watchlist/watchlist_groups) | QuoteContext.watchlist(...) | 免费/基础 |
| [向分组添加标的](https://open.longbridge.com/zh-CN/docs/quote/watchlist/watchlist_update_group) | QuoteContext.update_watchlist_group(...) | 免费/基础 |

#### 1.1 关键指标

- **Python SDK**：`QuoteContext.calc_indexes(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[关键指标](https://open.longbridge.com/zh-CN/docs/quote/pull/calc-index)

该接口用于获取标的计算指标数据，根据请求指定的计算指标返回数据。

:::info
[业务指令](../../socket/biz_command)：`26`
:::

#### Request

##### Parameters

| Name       | Type     | Required | Description                                                                                                                         |
| ---------- | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| symbols    | string[] | 是       | 标的代码列表，使用 `ticker.region` 格式，例如：`[700.HK]` <br /><br />**校验规则：**<br />每次请求支持传入的标的数量上限是 `500` 个 |
| calc_index | init32[] | 是       | 计算指标，例如：`[1,2,3]`，详见 [CalcIndex](../objects#calcindex---计算指标)                                                        |

##### Protobuf

```protobuf
message SecurityCalcQuoteRequest {
  repeated string symbols = 1;
  repeated CalcIndex calc_index = 2;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, CalcIndex, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.calc_indexes(["700.HK", "AAPL.US"], [CalcIndex.LastDone, CalcIndex.ChangeRate])
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, CalcIndex, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.calc_indexes(["700.HK", "AAPL.US"], [CalcIndex.LastDone, CalcIndex.ChangeRate])
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name                       | Type     | Description                                  |
| -------------------------- | -------- | -------------------------------------------- |
| security_calc_index        | object[] | 标的指标数据                                 |
| ∟ symbol                   | string   | 标的代码                                     |
| ∟ last_done                | string   | 最新价                                       |
| ∟ change_val               | string   | 涨跌额                                       |
| ∟ change_rate              | string   | 涨跌幅 (返回百分比数据，不包含`%`符号)       |
| ∟ volume                   | int64    | 成交量                                       |
| ∟ turnover                 | string   | 成交额                                       |
| ∟ ytd_change_rate          | string   | 年初至今涨幅 (返回百分比数据，不包含`%`符号) |
| ∟ turnover_rate            | string   | 换手率 (返回百分比数据，不包含`%`符号)       |
| ∟ total_market_value       | string   | 总市值                                       |
| ∟ capital_flow             | string   | 流入资金                                     |
| ∟ amplitude                | string   | 振幅 (返回百分比数据，不包含`%`符号)         |
| ∟ volume_ratio             | string   | 量比                                         |
| ∟ pe_ttm_ratio             | string   | 市盈率 (TTM）                                |
| ∟ pb_ratio                 | string   | 市净率                                       |
| ∟ dividend_ratio_ttm       | string   | 股息率 (TTM)                                 |
| ∟ five_day_change_rate     | string   | 五日涨幅 (返回百分比数据，不包含`%`符号)     |
| ∟ ten_day_change_rate      | string   | 十日涨幅 (返回百分比数据，不包含`%`符号)     |
| ∟ half_year_change_rate    | string   | 半年涨幅 (返回百分比数据，不包含`%`符号)     |
| ∟ five_minutes_change_rate | string   | 五分钟涨幅 (返回百分比数据，不包含`%`符号)   |
| ∟ expiry_date              | string   | 到期日                                       |
| ∟ strike_price             | string   | 行权价                                       |
| ∟ upper_strike_price       | string   | 上限价                                       |
| ∟ lower_strike_price       | string   | 下限价                                       |
| ∟ outstanding_qty          | int64    | 街货量                                       |
| ∟ outstanding_ratio        | string   | 街货比 (返回百分比数据，不包含`%`符号)       |
| ∟ premium                  | string   | 溢价率 (返回百分比数据，不包含`%`符号)       |
| ∟ itm_otm                  | string   | 价内/价外 (返回百分比数据，不包含`%`符号)    |
| ∟ implied_volatility       | string   | 隐含波动率 (返回百分比数据，不包含`%`符号)   |
| ∟ warrant_delta            | string   | 对冲值                                       |
| ∟ call_price               | string   | 收回价                                       |
| ∟ to_call_price            | string   | 距收回价 (返回百分比数据，不包含`%`符号)     |
| ∟ effective_leverage       | string   | 有效杠杆                                     |
| ∟ leverage_ratio           | string   | 杠杆比率                                     |
| ∟ conversion_ratio         | string   | 换股比率                                     |
| ∟ balance_point            | string   | 打和点                                       |
| ∟ open_interest            | int64    | 未平仓数                                     |
| ∟ delta                    | string   | Delta                                        |
| ∟ gamma                    | string   | Gamma                                        |
| ∟ theta                    | string   | Theta，原始值需除以 100 得到标准的每股每天值    |
| ∟ vega                     | string   | Vega，原始值需除以 100 得到标准的每股每 1% IV 值 |
| ∟ rho                      | string   | Rho，原始值需除以 100 得到标准的每股每 1% 利率值  |

##### Protobuf

```protobuf
message SecurityCalcIndex {
  string symbol = 1;
  string last_done = 2;
  string change_val = 3;
  string change_rate = 4;
  int64 volume = 5;
  string turnover = 6;
  string ytd_change_rate = 7;
  string turnover_rate = 8;
  string total_market_value = 9;
  string capital_flow = 10;
  string amplitude = 11;
  string volume_ratio = 12;
  string pe_ttm_ratio = 13;
  string pb_ratio = 14;
  string dividend_ratio_ttm = 15;
  string five_day_change_rate = 16;
  string ten_day_change_rate = 17;
  string half_year_change_rate = 18;
  string five_minutes_change_rate = 19;
  string expiry_date = 20;
  string strike_price = 21;
  string upper_strike_price = 22;
  string lower_strike_price = 23;
  int64  outstanding_qty = 24;
  string outstanding_ratio = 25;
  string premium = 26;
  string itm_otm = 27;
  string implied_volatility = 28;
  string warrant_delta = 29;
  string call_price = 30;
  string to_call_price = 31;
  string effective_leverage = 32;
  string leverage_ratio = 33;
  string conversion_ratio = 34;
  string balance_point = 35;
  int64 open_interest = 36;
  string delta = 37;
  string gamma = 38;
  string theta = 39;
  string vega = 40;
  string rho = 41;
}

message SecurityCalcQuoteResponse {
  repeated SecurityCalcIndex security_calc_index = 1;
}
```

##### Response JSON Example

```json
{
  "securityCalcIndex": [
    {
      "symbol": "AAPL.US",
      "lastDone": "131.880",
      "changeVal": "-5.2500",
      "changeRate": "-3.83",
      "volume": "122207099",
      "turnover": "16269088361.000",
      "ytdChangeRate": "-25.63",
      "turnoverRate": "0.76",
      "totalMarketValue": "2134501670280.00",
      "capitalFlow": "14664053535.556",
      "amplitude": "2.74",
      "volumeRatio": "3.22",
      "peTtmRatio": "21.26",
      "pbRatio": "31.71",
      "dividendRatioTtm": "0.64",
      "fiveDayChangeRate": "-9.76",
      "tenDayChangeRate": "-11.87",
      "halfYearChangeRate": "-7.01",
      "fiveMinutesChangeRate": "0.00"
    },
    {
      "symbol": "69672.HK",
      "lastDone": "0.010",
      "changeRate": "0.00",
      "expiryDate": "20221024",
      "strikePrice": "379.880",
      "outstandingQty": "6090000",
      "outstandingRatio": "7.61",
      "premium": "0.67",
      "itmOtm": "0.65",
      "callPrice": "375.880",
      "toCallPrice": "-100.00",
      "leverageRatio": "75.48",
      "balancePoint": "374.880"
    },
    {
      "symbol": "AAPL220617C137000.US",
      "lastDone": "1.17",
      "changeVal": "-2.04",
      "changeRate": "-63.55",
      "volume": "23499",
      "turnover": "3903660.00",
      "expiryDate": "20220617",
      "strikePrice": "137.00",
      "premium": "11709.40",
      "impliedVolatility": "43.54",
      "openInterest": "5210",
      "delta": "0.263",
      "gamma": "0.043",
      "theta": "-1.266",
      "vega": "5.660",
      "rho": "0.580"
    },
    {
      "symbol": "HSI.HK",
      "lastDone": "21119.650",
      "changeVal": "52.070",
      "changeRate": "0.25",
      "volume": "96449546281",
      "turnover": "96449546281.000",
      "ytdChangeRate": "-9.74",
      "amplitude": "1.86",
      "volumeRatio": "0.59",
      "fiveDayChangeRate": "-1.91",
      "tenDayChangeRate": "-0.02",
      "halfYearChangeRate": "-11.83",
      "fiveMinutesChangeRate": "0.00"
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                     |
| ---------- | ---------- | -------------- | ---------------------------- |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败       |
| 3          | 301606     | 限流           | 降低请求频次                 |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理     |
| 7          | 301600     | 请求标的不存在 | 检查请求的 `symbol` 是否正确 |
| 7          | 301603     | 标的无行情     | 标的没有请求的行情数据       |
| 7          | 301604     | 无权限         | 没有获取标的行情的权限       |

#### 1.2 资金分布

- **Python SDK**：`QuoteContext.capital_distribution(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[资金分布](https://open.longbridge.com/zh-CN/docs/quote/pull/capital-distribution)

该接口用于获取标的当日的资金分布。

:::info
[业务指令](../../socket/biz_command)：`25`
:::

#### Request

##### Parameters

| Name   | Type   | Required | Description                                          |
| ------ | ------ | -------- | ---------------------------------------------------- |
| symbol | string | 是       | 标的代码，使用 `ticker.region` 格式，例如： `700.HK` |

##### Protobuf

```protobuf
message SecurityRequest {
  string symbol = 1;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.capital_distribution("700.HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.capital_distribution("700.HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name        | Type     | Description    |
| ----------- | -------- | -------------- |
| symbol      | string   | 标的代码       |
| timestamp   | int64    | 数据更新时间戳 |
| capital_in  | object[] | 流入资金       |
| ∟ large     | string   | 大单           |
| ∟ medium    | string   | 中单           |
| ∟ small     | string   | 小单           |
| capital_out | object[] | 流出资金       |
| ∟ large     | string   | 大单           |
| ∟ medium    | string   | 中单           |
| ∟ small     | string   | 小单           |

##### Protobuf

```protobuf
message CapitalDistributionResponse {
  message CapitalDistribution {
    string large = 1;
    string medium = 2;
    string small = 3;
  }
  string symbol = 1;
  int64 timestamp = 2;
  CapitalDistribution capital_in = 3;
  CapitalDistribution capital_out = 4;
}
```

##### Response JSON Example

```json
{
  "symbol": "700.HK",
  "timestamp": "1655107800",
  "capital_in": {
    "large": "935389700.000",
    "medium": "2056032380.000",
    "small": "828715920.000"
  },
  "capital_out": {
    "large": "1175331560.000",
    "medium": "2271829740.000",
    "small": "751648940.000"
  }
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                     |
| ---------- | ---------- | -------------- | ---------------------------- |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败       |
| 3          | 301606     | 限流           | 降低请求频次                 |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理     |
| 7          | 301600     | 请求标的不存在 | 检查请求的 `symbol` 是否正确 |
| 7          | 301603     | 标的无行情     | 标的没有请求的行情数据       |
| 7          | 301604     | 无权限         | 没有获取标的行情的权限       |

#### 1.3 Tesla 今日资金流向时序

- **Python SDK**：`QuoteContext.capital_flow(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[Tesla 今日资金流向时序](https://open.longbridge.com/zh-CN/docs/quote/pull/capital-flow-intraday)

﻿---
id: quote_capital_flow_intraday
title: 资金流向
slug: /quote/pull/capital-flow-intraday
sidebar_position: 17
---

该接口用于获取标的当日的资金流向。

:::info
[业务指令](../../socket/biz_command)：`24`
:::

#### Request

##### Parameters

| Name   | Type   | Required | Description                                          |
| ------ | ------ | -------- | ---------------------------------------------------- |
| symbol | string | 是       | 标的代码，使用 `ticker.region` 格式，例如： `700.HK` |

##### Protobuf

```protobuf
message CapitalFlowIntradayRequest {
  string symbol = 1;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.capital_flow("700.HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.capital_flow("700.HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name               | Type     | Description    |
| ------------------ | -------- | -------------- |
| symbol             | string   | 标的代码       |
| capital_flow_lines | object[] | 资金流向数据   |
| ∟ inflow           | string   | 净流入         |
| ∟ timestamp        | int64    | 分钟开始时间戳 |

##### Protobuf

```protobuf
message CapitalFlowIntradayResponse {
  message CapitalFlowLine {
    string inflow = 1;
    int64 timestamp = 2;
  }
  string symbol = 1;
  repeated CapitalFlowLine capital_flow_lines = 2;
}
```

##### Response JSON Example

```json
{
  "symbol": "700.HK",
  "capital_flow_lines": [
    { "inflow": "-310255860.000", "timestamp": "1655106960" },
    { "inflow": "-314011220.000", "timestamp": "1655107020" },
    { "inflow": "-314011220.000", "timestamp": "1655107080" },
    { "inflow": "-314011220.000", "timestamp": "1655107140" },
    { "inflow": "-314011220.000", "timestamp": "1655107200" }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                     |
| ---------- | ---------- | -------------- | ---------------------------- |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败       |
| 3          | 301606     | 限流           | 降低请求频次                 |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理     |
| 7          | 301600     | 请求标的不存在 | 检查请求的 `symbol` 是否正确 |
| 7          | 301603     | 标的无行情     | 标的没有请求的行情数据       |
| 7          | 301604     | 无权限         | 没有获取标的行情的权限       |

#### 1.4 监管文件

- **Python SDK**：`QuoteContext.filings(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[监管文件](https://open.longbridge.com/zh-CN/docs/quote/pull/filings)
- **HTTP**：`GET /v1/quote/filings`

获取指定股票的公告列表。

#### Request

##### Query Parameters

| Name   | Type   | Required | Description                                    |
| ------ | ------ | -------- | ---------------------------------------------- |
| symbol | string | YES      | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US` |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.filings("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.filings("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "627391979864985729",
        "title": "苹果 | 4 - Apple Inc. (0000320193) (Issuer)",
        "description": "",
        "file_name": "4 - Apple Inc. (0000320193) (Issuer)",
        "file_urls": [
          "https://www.sec.gov/Archives/edgar/data/320193/000178052526000005/xslF345X05/wk-form4_1773786674.xml"
        ],
        "publish_at": "1773786677"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                                      |
| ------ | ----------- | ------------------------------------------- |
| 200    | 返回成功    | [filings_response](#schemafilings_response) |
| 500    | 内部错误    | None                                        |

#### Schemas

##### filings_response

| Name          | Type      | Required | Description              |
| ------------- | --------- | -------- | ------------------------ |
| items         | object[]  | true     | 公告列表                 |
| ∟ id          | string    | true     | 公告 ID                  |
| ∟ title       | string    | true     | 标题                     |
| ∟ description | string    | true     | 摘要                     |
| ∟ file_name   | string    | true     | 文件名                   |
| ∟ file_urls   | string[]  | true     | 文件链接列表             |
| ∟ publish_at  | string    | true     | 发布时间，Unix 时间戳（秒） |

#### 1.5 沽空数据（美股 / 港股）

- **Python SDK**：`QuoteContext.short_positions(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[沽空数据（美股 / 港股）](https://open.longbridge.com/zh-CN/docs/quote/pull/short-positions)

获取美股或港股沽空持仓数据。市场根据代码后缀自动识别：`.HK` → 港交所沽空数据（每日更新）；其他 → 美股 FINRA 沽空数据（双月更新）。

#### Parameters

> **SDK 方法参数。**

| Name   | Type    | Required | Description                                                      |
| ------ | ------- | -------- | ---------------------------------------------------------------- |
| symbol | string  | YES      | 证券代码，例如 `TSLA.US` 或 `700.HK`                            |
| count  | integer | NO       | 返回记录数（1–100，默认 20）                                     |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

### 美股示例
resp = ctx.short_positions("TSLA.US", 20)
print(resp)

### 港股示例
resp = ctx.short_positions("700.HK", 20)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    # 美股示例
    resp = await ctx.short_positions("TSLA.US", 20)
    print(resp)

    # 港股示例
    resp = await ctx.short_positions("700.HK", 20)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | 见下方 Schema |
| 400    | 请求错误    | None   |

#### Schemas

##### 美股响应（`.US` 代码）

| Name                     | Type     | Required | Description                               |
| ------------------------ | -------- | -------- | ----------------------------------------- |
| data                     | object[] | false    | 沽空持仓记录                              |
| ∟ timestamp              | string   | false    | 结算日期（RFC 3339 格式，例如 `2022-03-15T04:00:00Z`） |
| ∟ current_shares_short   | string   | false    | 沽空持仓股数                              |
| ∟ avg_daily_share_volume | string   | false    | 日均成交量                                |
| ∟ days_to_cover          | string   | false    | 沽空回补天数                              |
| ∟ rate                   | string   | false    | 沽空比率                                  |
| ∟ close                  | string   | false    | 当日收盘价                                |

##### 港股响应（`.HK` 代码）

| Name        | Type     | Required | Description                    |
| ----------- | -------- | -------- | ------------------------------ |
| data        | object[] | false    | 沽空持仓记录                   |
| ∟ timestamp | string   | false    | 交易日期（RFC 3339 格式，例如 `2022-03-15T04:00:00Z`） |
| ∟ amount    | string   | false    | 沽空金额（港元）               |
| ∟ balance   | string   | false    | 沽空持仓余额                   |
| ∟ cost      | string   | false    | 当日收盘价                     |
| ∟ rate      | string   | false    | 沽空比率                       |

#### 1.6 每日沽空成交量

- **Python SDK**：`QuoteContext.short_trades(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[每日沽空成交量](https://open.longbridge.com/zh-CN/docs/quote/pull/short-trades)

获取个股每日沽空成交量数据，支持美股（FINRA）和港股（HKEX）。美股数据每两周更新一次，港股数据每个交易日更新。

#### Parameters

> **SDK 方法参数。**

| Name   | Type    | Required | Description                                               |
| ------ | ------- | -------- | --------------------------------------------------------- |
| symbol | string  | YES      | 证券代码，支持美股（如 `TSLA.US`）和港股（如 `700.HK`）  |
| count  | integer | NO       | 返回记录数（1–100，默认 20）                              |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.short_trades("TSLA.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.short_trades("TSLA.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

美股（`.US` 后缀）：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "timestamp": "2026-05-15T04:00:00Z",
      "nus_amount": "5748485",
      "ny_amount": "0",
      "total_amount": "15778974",
      "rate": "0.3643",
      "close": "300.230"
    }
  ]
}
```

港股（`.HK` 后缀）：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "timestamp": "2026-05-17T16:00:00Z",
      "amount": "2926000",
      "balance": "1318056100.00",
      "total_amount": "29497076",
      "rate": "0.0992",
      "close": "449.2"
    }
  ]
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ShortTradesResponse](#ShortTradesResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### US Response（`.US` 代码）

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| data | object[] | 否 | 每日沽空成交量列表 |
| ∟ timestamp | string | 否 | 交易日期（RFC 3339 格式，例如 `2026-05-15T04:00:00Z`） |
| ∟ nus_amount | string | 否 | 纳斯达克沽空成交量（股） |
| ∟ ny_amount | string | 否 | 纽交所沽空成交量（股） |
| ∟ total_amount | string | 否 | 当日总成交量 |
| ∟ rate | string | 否 | 沽空比率（沽空量 ÷ 总成交量） |
| ∟ close | string | 否 | 当日收盘价 |

##### HK Response（`.HK` 代码）

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| data | object[] | 否 | 每日沽空成交量列表 |
| ∟ timestamp | string | 否 | 交易日期（RFC 3339 格式，例如 `2026-05-15T04:00:00Z`） |
| ∟ amount | string | 否 | 当日沽空成交金额（港元） |
| ∟ balance | string | 否 | 沽空持仓余额 |
| ∟ total_amount | string | 否 | 当日总成交金额 |
| ∟ rate | string | 否 | 沽空比率（沽空金额 ÷ 总成交金额） |
| ∟ close | string | 否 | 当日收盘价 |

#### 1.7 期权成交量

- **Python SDK**：`QuoteContext.option_volume(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[期权成交量](https://open.longbridge.com/zh-CN/docs/quote/pull/option-volume)

获取今日认购/认沽期权成交量快照。

#### Parameters

> **SDK 方法参数。**

| Name   | Type   | Required | Description                                    |
| ------ | ------ | -------- | ---------------------------------------------- |
| symbol | string | YES      | US stock symbol, e.g. `AAPL.US`, `TSLA.US`    |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.option_volume("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.option_volume("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "symbol": "AAPL.US",
    "call_volume": 284512,
    "put_volume": 195830
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | Success     | [option_volume_rsp](#option_volume_rsp) |
| 400    | Bad request | None   |

#### Schemas

##### option_volume_rsp

| Name        | Type   | Required | Description                 |
| ----------- | ------ | -------- | --------------------------- |
| symbol      | string | true     | Security symbol             |
| call_volume | int64  | true     | Total call volume for today |
| put_volume  | int64  | true     | Total put volume for today  |

#### 1.8 日度成交量

- **Python SDK**：`QuoteContext.option_volume_daily(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[日度成交量](https://open.longbridge.com/zh-CN/docs/quote/pull/option-volume-daily)

获取美股期权的历史每日认购/认沽成交量和未平仓量数据。

#### Parameters

> **SDK 方法参数。**

| Name      | Type    | Required | Description                                                               |
| --------- | ------- | -------- | ------------------------------------------------------------------------- |
| symbol    | string  | YES      | Underlying US stock symbol, e.g. `AAPL.US`, `TSLA.US`                     |
| timestamp | integer | NO       | Start Unix timestamp (seconds); `0` returns the most recent (default `0`) |
| count     | integer | NO       | Number of trading days to return (default `30`)                           |

> Go SDK 使用 `start` / `end` 日期区间（`time.Time`）而非 `timestamp` / `count`。

#### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.option_volume_daily("AAPL.US", count=30)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.option_volume_daily("AAPL.US", count=30)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "symbol": "AAPL.US",
    "stats": [
      {
        "symbol": "AAPL.US",
        "date": "2026-05-07",
        "call_volume": 284512,
        "put_volume": 195830,
        "call_open_interest": 1824500,
        "put_open_interest": 1532100,
        "total_volume": 480342,
        "total_open_interest": 3356600,
        "pc_vol": 0.6886,
        "pc_oi": 0.8398
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | Success     | [option_volume_daily_rsp](#option_volume_daily_rsp) |
| 400    | Bad request | None   |

#### Schemas

##### option_volume_daily_rsp

| Name                   | Type     | Required | Description                    |
| ---------------------- | -------- | -------- | ------------------------------ |
| symbol                 | string   | true     | Security symbol                |
| stats                  | object[] | true     | Daily volume records           |
| ∟ symbol               | string   | true     | Security symbol                |
| ∟ date                 | string   | true     | Date in `YYYY-MM-DD` format    |
| ∟ call_volume          | int64    | true     | Call volume on that day        |
| ∟ put_volume           | int64    | true     | Put volume on that day         |
| ∟ call_open_interest   | int64    | true     | Call open interest             |
| ∟ put_open_interest    | int64    | true     | Put open interest              |
| ∟ total_volume         | int64    | true     | Total options volume           |
| ∟ total_open_interest  | int64    | true     | Total options open interest    |
| ∟ pc_vol               | float    | true     | Put/call volume ratio          |
| ∟ pc_oi                | float    | true     | Put/call open interest ratio   |

#### 1.9 期权链

- **Python SDK**：`QuoteContext.option_chain_info_by_date(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[期权链](https://open.longbridge.com/zh-CN/docs/quote/pull/optionchain-date-strike)

该接口用于获取标的的期权链到期日期权标的列表。

:::info

[业务指令](../../socket/biz_command)：`21`

:::

#### Request

##### Parameters

| Name        | Type   | Required | Description                                                                                         |
| ----------- | ------ | -------- | --------------------------------------------------------------------------------------------------- |
| symbol      | string | 是       | 标的代码，使用 `ticker.region` 格式，例如：`700.HK`                                                 |
| expiry_date | string | 是       | 期权到期日，使用 `YYMMDD` 格式，例如：`20220429`，通过 [期权到期日](./optionchain_date.md) 接口获取 |

##### Protobuf

```protobuf
message OptionChainDateStrikeInfoRequest {
  string symbol = 1;
  string expiry_date = 2;
}
```

##### Request Example

###### Python 示例

```python
from datetime import date
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.option_chain_info_by_date("AAPL.US", date(2023, 1, 20))
print(resp)
```

###### Python 异步示例

```python
import asyncio
from datetime import date
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.option_chain_info_by_date("AAPL.US", date(2023, 1, 20))
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name              | Type     | Description        |
| ----------------- | -------- | ------------------ |
| strike_price_info | object[] | 到期日期权标的列表 |
| ∟ price           | string   | 行权价             |
| ∟ call_symbol     | string   | CALL 期权标的代码  |
| ∟ put_symbol      | string   | PUT 期权标的代码   |
| ∟ standard        | bool     | 是否标准期权       |

##### Protobuf

```protobuf
message OptionChainDateStrikeInfoResponse {
  repeated StrikePriceInfo strike_price_info = 1;
}

message StrikePriceInfo {
  string price = 1;
  string call_symbol = 2;
  string put_symbol = 3;
  bool  standard = 4;
}
```

##### Response JSON Example

```json
{
  "strike_price_info": [
    {
      "price": "100",
      "call_symbol": "AAPL220429C100000.US",
      "put_symbol": "AAPL220429P100000.US",
      "standard": true
    },
    {
      "price": "105",
      "call_symbol": "AAPL220429C105000.US",
      "put_symbol": "AAPL220429P105000.US",
      "standard": true
    },
    {
      "price": "110",
      "call_symbol": "AAPL220429C110000.US",
      "put_symbol": "AAPL220429P110000.US",
      "standard": true
    },
    {
      "price": "115",
      "call_symbol": "AAPL220429C115000.US",
      "put_symbol": "AAPL220429P115000.US",
      "standard": true
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                                    |
| ---------- | ---------- | -------------- | ------------------------------------------- |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败                      |
| 3          | 301606     | 限流           | 降低请求频次                                |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理                    |
| 7          | 301600     | 请求数据非法   | 检查请求的 `symbol`，`expiry_date` 数据格式 |

#### 1.10 到期日列表

- **Python SDK**：`QuoteContext.option_chain_expiry_date_list(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[到期日列表](https://open.longbridge.com/zh-CN/docs/quote/pull/optionchain-date)

该接口用于获取标的的期权链到期日列表。

:::info

[业务指令](../../socket/biz_command)：`20`

:::

#### Request

##### Parameters

| Name   | Type   | Required | Description                                         |
| ------ | ------ | -------- | --------------------------------------------------- |
| symbol | string | 是       | 标的代码，使用 `ticker.region` 格式，例如：`700.HK` |

##### Protobuf

```protobuf
message SecurityRequest {
  string symbol = 1;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.option_chain_expiry_date_list("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.option_chain_expiry_date_list("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name        | Type     | Description                                    |
| ----------- | -------- | ---------------------------------------------- |
| expiry_date | string[] | 标的对应的期权链到期日列表，使用 `YYMMDD` 格式 |

##### Protobuf

```protobuf
message OptionChainDateListResponse {
  repeated string expiry_date = 1;
}
```

##### Response JSON Example

```json
{
  "expiry_date": [
    "20220422",
    "20220429",
    "20220506",
    "20220513",
    "20220520",
    "20220527",
    "20220603",
    "20220617",
    "20220715",
    "20220819",
    "20220916",
    "20221021",
    "20221118",
    "20230120",
    "20230317",
    "20230616",
    "20230915",
    "20240119",
    "20240621"
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                     |
| ---------- | ---------- | -------------- | ---------------------------- |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败       |
| 3          | 301606     | 限流           | 降低请求频次                 |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理     |
| 7          | 301600     | 请求标的不存在 | 检查请求的 `symbol` 是否正确 |

#### 1.11 券商席位 ID

- **Python SDK**：`QuoteContext.participants(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[券商席位 ID](https://open.longbridge.com/zh-CN/docs/quote/pull/broker-ids)

该接口用于获取券商席位 ID 数据 (可每天同步一次)。

:::info
[业务指令](../../socket/biz_command)：`16`
:::

#### Request

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.participants()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.participants()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name                       | Type     | Description           |
| -------------------------- | -------- | --------------------- |
| participant_broker_numbers | object[] | 券商席位              |
| ∟ broker_ids               | int32[]  | 券商对应的多个席位 ID |
| ∟ participant_name_cn      | string   | 券商名称 (简)         |
| ∟ participant_name_en      | string   | 券商名称 (英)         |
| ∟ participant_name_hk      | string   | 券商名称 (繁)         |

##### Protobuf

```protobuf
message ParticipantBrokerIdsResponse {
  repeated ParticipantInfo participant_broker_numbers = 1;
}

message ParticipantInfo {
  repeated int32 broker_ids = 1;
  string participant_name_cn = 2;
  string participant_name_en = 3;
  string participant_name_hk = 4;
}
```

##### Response JSON Example

```json
{
  "participant_broker_numbers": [
    {
      "broker_ids": [7738, 7739],
      "participant_name_cn": "华兴金融 (香港)",
      "participant_name_en": "China Renaissance(HK)",
      "participant_name_hk": "華興金融 (香港)"
    },
    {
      "broker_ids": [6390, 6396, 6398, 6399],
      "participant_name_cn": "国信 (香港)",
      "participant_name_en": "Guosen(HK)",
      "participant_name_hk": "國信 (香港)"
    },
    {
      "broker_ids": [3168, 3169],
      "participant_name_cn": "泰嘉",
      "participant_name_en": "Tiger",
      "participant_name_hk": "泰嘉"
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                 |
| ---------- | ---------- | -------------- | ------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败   |
| 3          | 301606     | 限流           | 降低请求频次             |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理 |

#### 1.12 基本信息

- **Python SDK**：`QuoteContext.static_info(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[基本信息](https://open.longbridge.com/zh-CN/docs/quote/pull/static)

该接口用于获取标的的基础信息。

:::info
[业务指令](../../socket/biz_command)：`10`
:::

#### Request

##### Parameters

| Name   | Type     | Required | Description                                                                                                                         |
| ------ | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| symbol | string[] | 是       | 标的代码列表，使用 `ticker.region` 格式，例如：`[700.HK]` <br /><br />**校验规则：**<br />每次请求支持传入的标的数量上限是 `500` 个 |

##### Protobuf

```protobuf
message MultiSecurityRequest {
  repeated string symbol = 1;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.static_info(["700.HK", "AAPL.US", "TSLA.US", "NFLX.US"])
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.static_info(["700.HK", "AAPL.US", "TSLA.US", "NFLX.US"])
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name                 | Type     | Description                                                                                      |
| -------------------- | -------- | ------------------------------------------------------------------------------------------------ |
| secu_static_info     | object[] | 标的基础数据列表                                                                                 |
| ∟ symbol             | string   | 标的代码                                                                                         |
| ∟ name_cn            | string   | 中文简体标的名称                                                                                 |
| ∟ name_en            | string   | 英文标的名称                                                                                     |
| ∟ name_hk            | string   | 中文繁体标的名称                                                                                 |
| ∟ exchange           | string   | 标的所属交易所                                                                                   |
| ∟ currency           | string   | 交易币种 <br /><br />**可选值：**<br />`CNY` <br />`USD` <br />`SGD` <br />`HKD`                 |
| ∟ lot_size           | int32    | 每手股数                                                                                         |
| ∟ total_shares       | int64    | 总股本                                                                                           |
| ∟ circulating_shares | int64    | 流通股本                                                                                         |
| ∟ hk_shares          | int64    | 港股股本 (仅港股)                                                                                |
| ∟ eps                | string   | 每股盈利                                                                                         |
| ∟ eps_ttm            | string   | 每股盈利 (TTM)                                                                                   |
| ∟ bps                | string   | 每股净资产                                                                                       |
| ∟ dividend_yield     | string   | 股息                                                                                             |
| ∟ stock_derivatives  | int32[]  | 如果标的是正股，可提供的衍生品行情类型 <br /><br />**可选值：**<br />`1` - 期权 <br />`2` - 轮证 |
| ∟ board              | string   | 标的所属板块，详见 [Board](../objects#board---标的板块)                                          |

##### Protobuf

```protobuf
message SecurityStaticInfoResponse {
  repeated StaticInfo secu_static_info = 1;
}

message StaticInfo {
  string symbol = 1;
  string name_cn = 2;
  string name_en = 3;
  string name_hk = 4;
  string listing_date = 5;
  string exchange = 6;
  string currency = 7;
  int32 lot_size = 8;
  int64 total_shares = 9;
  int64 circulating_shares = 10;
  int64 hk_shares = 11;
  string eps = 12;
  string eps_ttm = 13;
  string bps = 14;
  string dividend_yield = 15;
  repeated int32 stock_derivatives = 16;
  string board = 17;
}
```

##### Response JSON Example

```json
{
  "secu_static_info": [
    {
      "symbol": "700.HK",
      "name_cn": "腾讯控股",
      "name_en": "TENCENT",
      "name_hk": "騰訊控股",
      "exchange": "SEHK",
      "currency": "HKD",
      "lot_size": 100,
      "total_shares": 9612464038,
      "circulating_shares": 9612464038,
      "hk_shares": 9612464038,
      "eps": "28.4394",
      "eps_ttm": "28.4394",
      "bps": "103.40413",
      "dividend_yield": "1.6",
      "stock_derivatives": [2],
      "board": "HKEquity"
    },
    {
      "symbol": "AAPL.US",
      "name_cn": "苹果",
      "name_en": "Apple Inc.",
      "exchange": "NASD",
      "currency": "USD",
      "lot_size": 1,
      "total_shares": 1631944100,
      "circulating_shares": 16302661350,
      "eps": "5.669",
      "eps_ttm": "6.0771",
      "bps": "4.40197",
      "dividend_yield": "0.85",
      "stock_derivatives": [1],
      "board": "USMain"
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                                   |
| ---------- | ---------- | -------------- | ------------------------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败                     |
| 3          | 301606     | 限流           | 降低请求频次                               |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理                   |
| 7          | 301607     | 接口限制       | 请求的标的数量超限，请减少单次请求标的数量 |

#### 1.13 美股加密货币概览

- **Python SDK**：`QuoteContext.us_crypto_overview(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[美股加密货币概览](https://open.longbridge.com/zh-CN/docs/quote/stocks/us_crypto_overview)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股加密货币交易对的概览信息——历史最高/最低价、资产详情和货币信息。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | 加密货币交易对，例如 `DOGEUSD.BKKT` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
resp = ctx.us_crypto_overview("DOGEUSD.BKKT")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)
    resp = await ctx.us_crypto_overview("DOGEUSD.BKKT")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### 响应字段

| 字段 | 类型 | 描述 |
| ---- | ---- | ---- |
| symbol | string | 交易对代码 |
| name | string | 资产名称 |
| ticker | string | 简短代码 |
| base_asset | string | 基础资产代码 |
| currency | string | 计价货币 |
| all_time_high | string | 历史最高价 |
| all_time_high_date | string | 历史最高价日期 |
| all_time_low | string | 历史最低价 |
| all_time_low_date | string | 历史最低价日期 |

#### Response

##### Response Example

```json
{
  "symbol": "DOGEUSD.BKKT",
  "name": "Dogecoin",
  "ticker": "DOGE",
  "base_asset": "DOGE",
  "currency": "USD",
  "all_time_high": "0.7376",
  "all_time_high_date": "2021-05-08",
  "all_time_low": "0.0000869",
  "all_time_low_date": "2015-05-06",
  "ipo_date": "2013-12-06",
  "shares": "147000000000",
  "official_web_address": "https://dogecoin.com"
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [CryptoOverview](#CryptoOverview) |
| 400    | 请求错误 | None   |

#### Schemas

##### CryptoOverview

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | 交易对代码，如 `DOGEUSD.BKKT` |
| name | string | 是 | 资产名称 |
| ticker | string | 是 | 简短代码 |
| base_asset | string | 是 | 基础资产代码，如 `DOGE` |
| currency | string | 是 | 计价货币，如 `USD` |
| all_time_high | string | 是 | 历史最高价 |
| all_time_high_date | string | 是 | 历史最高价日期 |
| all_time_low | string | 是 | 历史最低价 |
| all_time_low_date | string | 是 | 历史最低价日期 |
| ipo_date | string | 否 | 初始上市日期 |
| issue_price | string | 否 | 初始发行价格 |
| shares | string | 否 | 流通总量 |
| official_web_address | string | 否 | 官方网站 URL |
| logo | string | 否 | 资产 Logo URL |
| wiki_url | string | 否 | Wikipedia URL |
| profile | string | 否 | 资产简介（JSON 字符串） |

#### 1.14 查看当前 WebSocket 实时订阅状态

- **Python SDK**：`QuoteContext.subscriptions(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[查看当前 WebSocket 实时订阅状态](https://open.longbridge.com/zh-CN/docs/quote/subscribe/subscription)

﻿---
id: quote_subscription
title: 获取订阅信息
slug: subscription
sidebar_position: 4
---

该接口用于获取当前连接已订阅的标的行情。

:::info

[业务指令](../../socket/biz_command)：`5`

:::

#### Request

##### Protobuf

```protobuf
message SubscriptionRequest {
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, SubType, OAuthBuilder
oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

ctx.subscribe(["700.HK", "AAPL.US"], [SubType.Quote])
resp = ctx.subscriptions()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, SubType, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    await ctx.subscribe(["700.HK", "AAPL.US"], [SubType.Quote])
    resp = await ctx.subscriptions()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name       | Type     | Description                                                         |
| ---------- | -------- | ------------------------------------------------------------------- |
| sub_list   | object[] | 订阅的数据                                                          |
| ∟ symbol   | string   | 标的代码                                                            |
| ∟ sub_type | []int32  | 订阅的数据类型，详见 [SubType](../objects#subtype---订阅数据的类型) |

##### Protobuf

```protobuf
message SubscriptionResponse {
  repeated SubTypeList sub_list = 1;
}

message SubTypeList {
  string symbol = 1;
  repeated SubType sub_type = 2;
}
```

##### Response JSON Example

```json
{
  "sub_list": [
    {
      "symbol": "700.HK",
      "sub_type": [1, 2, 3]
    },
    {
      "symbol": "AAPL.US",
      "sub_type": [2]
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                 |
| ---------- | ---------- | -------------- | ------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败   |
| 3          | 301606     | 限流           | 降低请求频次             |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理 |

#### 1.15 订阅行情

- **Python SDK**：`QuoteContext.subscribe(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[订阅行情](https://open.longbridge.com/zh-CN/docs/quote/subscribe/subscribe)

该接口用于订阅标的行情数据。

:::info

[业务指令](../../socket/biz_command)：`6`

:::

#### Request

##### Parameters

| Name          | Type     | Required | Description                                                                                                                                            |
| ------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| symbol        | string[] | 是       | 订阅的标的代码，例如：`[700.HK]` <br /><br />**校验规则：**<br />每次请求支持传入的标的数量上限是 `500` 个 <br /> 每个用户同时订阅标的数量最多为 `500` |
| sub_type      | int32[]  | 是       | 订阅的数据类型，例如：`[1,2]`，详见 [SubType](../objects#subtype---订阅数据的类型)                                                                     |
| is_first_push | bool     | 是       | 订阅后是否立刻进行一次数据推送。( trade 不支持)                                                                                                        |

##### Protobuf

```protobuf
message SubscribeRequest {
  repeated string symbol = 1;
  repeated SubType sub_type = 2;
  bool is_first_push = 3;
}
```

##### Request Example

###### Python 示例

```python
from time import sleep
from longbridge.openapi import QuoteContext, Config, SubType, PushQuote, OAuthBuilder

def on_quote(symbol: str, event: PushQuote):
    print(symbol, event)

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
ctx.set_on_quote(on_quote)

ctx.subscribe(["700.HK", "AAPL.US"], [SubType.Quote])
sleep(30)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, SubType, PushQuote, OAuthBuilder

async def main() -> None:
    async def on_quote(symbol: str, event: PushQuote) -> None:
        print(symbol, event)

    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)
    ctx.set_on_quote(on_quote)

    await ctx.subscribe(["700.HK", "AAPL.US"], [SubType.Quote])
    await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

返回本次请求订阅成功的标的和类型。

| Name       | Type     | Description                                                          |
| ---------- | -------- | -------------------------------------------------------------------- |
| sub_list   | object[] | 订阅的数据                                                           |
| ∟ symbol   | string   | 标的代码                                                             |
| ∟ sub_type | int32[]  | 订阅的数据类型，详见：[SubType](../objects#subtype---订阅数据的类型) |

##### Protobuf

```protobuf
message SubscriptionResponse {
  repeated SubTypeList sub_list = 1;
}

message SubTypeList {
  string symbol = 1;
  repeated SubType sub_type = 2;
}
```

##### Response JSON Example

```json
{
  "sub_list": [
    {
      "symbol": "700.HK",
      "sub_type": [1, 2, 3]
    },
    {
      "symbol": "AAPL.US",
      "sub_type": [2]
    }
  ]
}
```

#### 接口限制

:::caution

- 港股 BMP 行情不支持行情数据推送。

:::

#### 错误码

| 协议错误码 | 业务错误码 | 描述             | 排查建议                 |
| ---------- | ---------- | ---------------- | ------------------------ |
| 3          | 301600     | 无效的请求       | 请求参数有误或解包失败   |
| 3          | 301606     | 限流             | 降低请求频次             |
| 7          | 301602     | 服务端内部错误   | 请重试或联系技术人员处理 |
| 7          | 301605     | 订阅数量超出限制 | 取消部分订阅             |
| 7          | 301600     | 请求参数有误     | 检查请求的 `sub_type`    |

#### 1.16 unsubscribe

- **Python SDK**：`QuoteContext.unsubscribe(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[unsubscribe](https://open.longbridge.com/zh-CN/docs/quote/subscribe/unsubscribe)

﻿---
id: quote_unsubscribe
title: 取消订阅
slug: unsubscribe
sidebar_position: 3
---

该接口用于取消订阅标的行情数据。

:::info

[业务指令](../../socket/biz_command)：`7`

:::

#### Request

##### Parameters

| Name      | Type     | Required | Description                                                                                                        |
| --------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
| symbol    | string[] | 是       | 订阅的标的代码，例如：`[700.HK]` <br /><br />**校验规则：**<br />每次请求支持传入的标的数量上限是 `500` 个         |
| sub_type  | int32[]  | 是       | 订阅的数据类型，例如：`[1,2]`，详见 [SubType](../objects#subtype---订阅数据的类型)                                 |
| unsub_all | bool     | 是       | 是否全部取消。<br />- `symbol` 为空时，取消所有标的的订阅。<br />- `symbol` 不为空时，取消这些标的的所有类型订阅。 |

##### Protobuf

```protobuf
message UnsubscribeRequest {
  repeated string symbol = 1;
  repeated SubType sub_type = 2;
  bool unsub_all = 3;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, SubType, OAuthBuilder
oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

ctx.subscribe(["700.HK", "AAPL.US"], [SubType.Quote])
ctx.unsubscribe(["AAPL.US"], [SubType.Quote])
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, SubType, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    await ctx.subscribe(["700.HK", "AAPL.US"], [SubType.Quote])
    await ctx.unsubscribe(["AAPL.US"], [SubType.Quote])

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Protobuf

```protobuf
message UnsubscribeResponse{
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                 |
| ---------- | ---------- | -------------- | ------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败   |
| 3          | 301606     | 限流           | 降低请求频次             |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理 |
| 7          | 301600     | 请求参数有误   | 检查请求的 `sub_type`    |

#### 1.17 发行商列表

- **Python SDK**：`QuoteContext.warrant_issuers(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[发行商列表](https://open.longbridge.com/zh-CN/docs/quote/pull/issuer)

该接口用于获取轮证发行商 ID 数据 (可每天同步一次)。

:::info

[业务指令](../../socket/biz_command)：`22`

:::

#### Request

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.warrant_issuers()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.warrant_issuers()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Parameters

| Name        | Type     | Description   |
| ----------- | -------- | ------------- |
| issuer_info | object[] | 发行机构信息  |
| ∟ id        | int32    | 机构 ID       |
| ∟ name_cn   | string   | 机构名称 (简) |
| ∟ name_en   | string   | 机构名称 (英) |
| ∟ name_hk   | string   | 机构名称 (繁) |

##### Protobuf

```protobuf
message IssuerInfoResponse {
  repeated IssuerInfo issuer_info = 1;
}

message IssuerInfo {
  int32 id = 1;
  string name_cn = 2;
  string name_en = 3;
  string name_hk = 4;
}
```

##### Response JSON Example

```json
{
  "issuer_info": [
    {
      "id": 15,
      "name_cn": "瑞银",
      "name_en": "UB",
      "name_hk": "瑞銀"
    },
    {
      "id": 14,
      "name_cn": "汇丰",
      "name_en": "HS",
      "name_hk": "滙豐"
    },
    {
      "id": 12,
      "name_cn": "花旗",
      "name_en": "CT",
      "name_hk": "花旗"
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                 |
| ---------- | ---------- | -------------- | ------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败   |
| 3          | 301606     | 限流           | 降低请求频次             |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理 |

#### 1.18 腾讯相关权证列表

- **Python SDK**：`QuoteContext.warrant_list(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[腾讯相关权证列表](https://open.longbridge.com/zh-CN/docs/quote/pull/warrant-filter)

﻿---
id: quote_warrant_filter
title: 筛选器
slug: /quote/pull/warrant-filter
sidebar_position: 14
---

该接口用于获取轮证行情列表数据，支持按不同字段排序和筛选轮证。

:::info

[业务指令](../../socket/biz_command)：`23`

:::

#### Request

##### Parameters

| Name          | Type    | Required | Description                                                                                                                                        |
| ------------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| symbol        | string  | 是       | 标的代码，使用 `ticker.region` 格式，例如：`700.HK`                                                                                                |
| filter_config | object  | 是       | 筛选条件                                                                                                                                           |
| ∟ sort_by     | int32   | 是       | 根据哪一项数据进行排序，例如：`0`，序号见响应数据 `OrderSequence` 字段。                                                                           |
| ∟ sort_order  | int32   | 是       | 升降顺序，例如：`1` <br /><br />**可选值：**<br />`0` - 升序<br />`1` - 降序                                                                       |
| ∟ sort_offset | int32   | 是       | 分页的第一条数据偏移量，例如 `0`                                                                                                                   |
| ∟ sort_count  | int32   | 是       | 分页的每一页数量，例如 `20`, 填 `0` 时不分页                                                                                                       |
| ∟ type        | int32[] | 否       | 筛选轮证类型 例如：`[0,1]` <br /><br />**可选值：**<br />`0` - 认购<br />`1` - 认沽<br />`2` - 牛证<br />`3` - 熊证<br />`4` - 界内证              |
| ∟ issuer      | int32[] | 否       | 筛选发行商，例如：`[12,14]`，[发行商 ID](./issuer) 通过接口获取                                                                                    |
| ∟ expiry_date | int32[] | 否       | 筛选轮证过期时间，例如：`[1]` <br /><br />**可选值：**<br />`1` - 低于 3 个月<br />`2` - 3 - 6 个月<br />`3` - 6 - 12 个月<br />`4` - 大于 12 个月 |
| ∟ price_type  | int32[] | 否       | 筛选价内价外，例如：`[2]` <br /><br />**可选值：**<br />`1` - 价内<br />`2` - 价外                                                                 |
| ∟ status      | int32[] | 否       | 筛选状态，例如：`[2]` <br /><br />**可选值：**<br />`2`- 终止交易<br />`3` - 等待上市<br />`4` - 正常                                              |
| language      | int32   | 是       | 响应的语言，例如：`[1]` <br /><br />**可选值：**<br />`0` - 简体<br />`1` - English<br />`2` - 繁体                                                |

##### Protobuf

```protobuf
message WarrantFilterListRequest {
  string symbol = 1;
  FilterConfig filter_config = 2;
  int32 language = 3;
}

message FilterConfig {
  int32 sort_by = 1;
  int32 sort_order = 2;
  int32 sort_offset = 3;
  int32 sort_count = 4;
  repeated int32 type = 5;
  repeated int32 issuer = 6;
  repeated int32 expiry_date = 7;
  repeated int32 price_type = 8;
  repeated int32 status = 9;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, WarrantSortBy, SortOrderType, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.warrant_list("700.HK", WarrantSortBy.LastDone, SortOrderType.Ascending)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, WarrantSortBy, SortOrderType, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.warrant_list("700.HK", WarrantSortBy.LastDone, SortOrderType.Ascending)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name                 | Type     | Description                                                                               | OrderSequence | Support_Call/Put | Support_Bull/Bear | Support_Inline |
| -------------------- | -------- | ----------------------------------------------------------------------------------------- | ------------- | ---------------- | ----------------- | -------------- |
| warrant_list         | object[] | 涡轮筛选数据列表                                                                          |               |                  |                   |                |
| ∟ symbol             | string   | 标的代码                                                                                  |               | true             | true              | true           |
| ∟ name               | string   | 标的名称                                                                                  |               | true             | true              | true           |
| ∟ last_done          | string   | 最新价                                                                                    | 0             | true             | true              | true           |
| ∟ change_rate        | string   | 涨跌幅                                                                                    | 1             | true             | true              | true           |
| ∟ change_val         | string   | 涨跌额                                                                                    | 2             | true             | true              | true           |
| ∟ volume             | int64    | 成交量                                                                                    | 3             | true             | true              | true           |
| ∟ turnover           | string   | 成交额                                                                                    | 4             | true             | true              | true           |
| ∟ expiry_date        | string   | 到期日，使用 `YYMMDD` 格式                                                                | 5             | true             | true              | true           |
| ∟ strike_price       | string   | 行权价                                                                                    | 6             | true             | true              | false          |
| ∟ upper_strike_price | string   | 上限价                                                                                    | 7             | false            | false             | true           |
| ∟ lower_strike_price | string   | 下限价                                                                                    | 8             | false            | false             | true           |
| ∟ outstanding_qty    | string   | 街货量                                                                                    | 9             | true             | true              | true           |
| ∟ outstanding_ratio  | string   | 街货比                                                                                    | 10            | true             | true              | true           |
| ∟ premium            | string   | 溢价率                                                                                    | 11            | true             | true              | true           |
| ∟ itm_otm            | string   | 价内/价外                                                                                 | 12            | true             | true              | false          |
| ∟ implied_volatility | string   | 引伸波幅                                                                                  | 13            | true             | false             | false          |
| ∟ delta              | string   | 对冲值                                                                                    | 14            | true             | false             | false          |
| ∟ call_price         | string   | 收回价                                                                                    | 15            | false            | true              | false          |
| ∟ to_call_price      | string   | 距收回价                                                                                  | 16            | false            | true              | false          |
| ∟ effective_leverage | string   | 有效杠杆                                                                                  | 17            | true             | false             | false          |
| ∟ leverage_ratio     | string   | 杠杆比率                                                                                  | 18            | true             | true              | true           |
| ∟ conversion_ratio   | string   | 换股比率                                                                                  | 19            | true             | true              | false          |
| ∟ balance_point      | string   | 打和点                                                                                    | 20            | true             | true              | false          |
| ∟ status             | int32    | 状态，<br /><br />**可选值：**<br />`2`- 终止交易<br />`3` - 等待上市<br />`4` - 正常交易 | 21            | true             | true              | true           |
| total_count          | int32    | 符合条件的轮证总数量                                                                      |               |                  |                   |                |

##### Protobuf

```protobuf
message WarrantFilterListResponse {
  repeated FilterWarrant warrant_list = 1;
  int32 total_count = 2;
}

message FilterWarrant {
  string symbol = 1;
  string name = 2;
  string last_done = 3;
  string change_rate = 4;
  string change_val = 5;
  int64 volume = 6;
  string turnover = 7;
  string expiry_date = 8;
  string strike_price = 9;
  string upper_strike_price = 10;
  string lower_strike_price = 11;
  string outstanding_qty = 12;
  string outstanding_ratio = 13;
  string premium = 14;
  string itm_otm = 15;
  string implied_volatility = 16;
  string delta = 17;
  string call_price = 18;
  string to_call_price = 19;
  string effective_leverage = 20;
  string leverage_ratio = 21;
  string conversion_ratio = 22;
  string balance_point = 23;
  string status = 24;
}
```

##### Response JSON Example

```json
{
  "warrant_list": [
    {
      "symbol": "13157.HK",
      "name": "腾讯麦银二七沽 A",
      "last_done": "2.26",
      "change_rate": "-0.0216450216450218",
      "change_val": "-0.050000000000000266",
      "turnover": "0",
      "expiry_date": "20220705",
      "strike_price": "442.233",
      "upper_strike_price": "0",
      "lower_strike_price": "0",
      "outstanding_qty": "5000",
      "outstanding_ratio": "0.0003",
      "premium": "0.016784269662921222",
      "itm_otm": "0.23524476916014864",
      "implied_volatility": "0.5275",
      "delta": "-0.8524",
      "call_price": "0",
      "effective_leverage": "-2.627683451852457",
      "leverage_ratio": "3.0826882353970637",
      "conversion_ratio": "48.544",
      "balance_point": "332.52356000000003",
      "status": 4
    },
    {
      "symbol": "13649.HK",
      "name": "腾讯摩通二五沽 A",
      "last_done": "1.14",
      "change_rate": "0",
      "change_val": "0",
      "turnover": "0",
      "expiry_date": "20220518",
      "strike_price": "445.223",
      "upper_strike_price": "0",
      "lower_strike_price": "0",
      "outstanding_qty": "80000",
      "outstanding_ratio": "0.0004",
      "premium": "0.010810703725606",
      "itm_otm": "0.24038066317328624",
      "implied_volatility": "0.5997",
      "delta": "-0.7964",
      "call_price": "0",
      "effective_leverage": "-2.4335424241487873",
      "leverage_ratio": "3.055678583813144",
      "conversion_ratio": "97.087",
      "balance_point": "334.54382000000004",
      "status": 4
    }
  ],
  "total_count": 1197
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                     |
| ---------- | ---------- | -------------- | ---------------------------- |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败       |
| 3          | 301606     | 限流           | 降低请求频次                 |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理     |
| 7          | 301600     | 请求标的不存在 | 检查请求的 `symbol` 是否正确 |
| 7          | 301603     | 标的无行情     | 标的没有请求的行情数据       |
| 7          | 301604     | 无权限         | 没有获取标的行情的权限       |
| 7          | 301607     | 接口限制       | 减少每页数据数量             |

#### 1.19 实时报价

- **Python SDK**：`QuoteContext.warrant_quote(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[实时报价](https://open.longbridge.com/zh-CN/docs/quote/pull/warrant-quote)

该接口用于获取港股轮证标的的实时行情，包括轮证的特有数据。

:::info

[业务指令](../../socket/biz_command)：`13`

:::

#### Request

##### Parameters

| Name   | Type     | Required | Description                                                                                                                           |
| ------ | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| symbol | string[] | 是       | 标的代码列表，使用 `ticker.region` 格式，例如：`[13447.HK]` <br /><br />**校验规则：**<br />每次请求支持传入的标的数量上限是 `500` 个 |

##### Protobuf

```protobuf
message MultiSecurityRequest {
  repeated string symbol = 1;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.warrant_quote(["21125.HK"])
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.warrant_quote(["21125.HK"])
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name                  | Type     | Description                                                                                                                                 |
| --------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| secu_quote            | object[] | 期权标的行情数据列表                                                                                                                        |
| ∟ symbol              | string   | 标的代码                                                                                                                                    |
| ∟ last_done           | string   | 最新价                                                                                                                                      |
| ∟ prev_close          | string   | 昨收价                                                                                                                                      |
| ∟ open                | string   | 开盘价                                                                                                                                      |
| ∟ high                | string   | 最高价                                                                                                                                      |
| ∟ low                 | string   | 最低价                                                                                                                                      |
| ∟ timestamp           | int64    | 最新成交的时间戳                                                                                                                            |
| ∟ volume              | int64    | 成交量                                                                                                                                      |
| ∟ turnover            | string   | 成交额                                                                                                                                      |
| ∟ trade_status        | int32    | 标的交易状态，详见[TradeStatus](../objects#tradestatus---交易状态)                                                                          |
| ∟ warrant_extend      | object   | 轮证扩展行情                                                                                                                                |
| ∟∟ implied_volatility | string   | 引申波幅                                                                                                                                    |
| ∟∟ expiry_date        | string   | 到期日，使用：`YYMMDD` 格式                                                                                                                 |
| ∟∟ last_trade_date    | string   | 最后交易日，使用：`YYMMDD` 格式                                                                                                             |
| ∟∟ outstanding_ratio  | string   | 街货比                                                                                                                                      |
| ∟∟ outstanding_qty    | int64    | 街货量                                                                                                                                      |
| ∟∟ conversion_ratio   | string   | 换股比率                                                                                                                                    |
| ∟∟ category           | string   | 轮证类型 <br /><br />**可选值：**<br />`Call` - 认购证 <br />`Put` - 认沽证 <br />`Bull` - 牛证 <br />`Bear` - 熊证 <br />`Inline` - 界内证 |
| ∟∟ strike_price       | string   | 行权价                                                                                                                                      |
| ∟∟ upper_strike_price | string   | 上限价                                                                                                                                      |
| ∟∟ lower_strike_price | string   | 下限价                                                                                                                                      |
| ∟∟ call_price         | string   | 收回价                                                                                                                                      |
| ∟∟ underlying_symbol  | string   | 对应的正股标的代码                                                                                                                          |

##### Protobuf

```protobuf
message WarrantQuoteResponse {
  repeated WarrantQuote secu_quote = 2;
}

message WarrantQuote {
  string symbol = 1;
  string last_done = 2;
  string prev_close = 3;
  string open = 4;
  string high = 5;
  string low = 6;
  int64 timestamp = 7;
  int64 volume = 8;
  string turnover = 9;
  TradeStatus trade_status = 10;
  WarrantExtend warrant_extend = 11;
}

message WarrantExtend {
  string implied_volatility = 1;
  string expiry_date = 2;
  string last_trade_date = 3;
  string outstanding_ratio = 4;
  int64  outstanding_qty = 5;
  string conversion_ratio = 6;
  string category = 7;
  string strike_price = 8;
  string upper_strike_price = 9;
  string lower_strike_price = 10;
  string call_price = 11;
  string underlying_symbol = 12;
}
```

##### Response JSON Example

```json
{
  "secu_quote": [
    {
      "symbol": "66642.HK",
      "last_done": "0.345",
      "prev_close": "0.365",
      "open": "0.345",
      "high": "0.345",
      "low": "0.345",
      "timestamp": 1651130421,
      "volume": 200000,
      "turnover": "69000.000",
      "warrant_extend": {
        "implied_volatility": "0.319",
        "expiry_date": "20220830",
        "last_trade_date": "20220829",
        "outstanding_ratio": "0.0001",
        "outstanding_qty": 20000,
        "conversion_ratio": "10000",
        "category": "Bear",
        "strike_price": "23200.000",
        "upper_strike_price": "0.000",
        "lower_strike_price": "0.000",
        "call_price": "23100.000",
        "underlying_symbol": "HSI.HK"
      }
    },
    {
      "symbol": "14993.HK",
      "last_done": "0.073",
      "prev_close": "0.066",
      "open": "0.069",
      "high": "0.076",
      "low": "0.069",
      "timestamp": 1651130930,
      "volume": 320825000,
      "turnover": "23401125.000",
      "warrant_extend": {
        "implied_volatility": "0.404",
        "expiry_date": "20220927",
        "last_trade_date": "20220921",
        "outstanding_ratio": "0.0247",
        "outstanding_qty": 2465000,
        "conversion_ratio": "10",
        "category": "Call",
        "strike_price": "70.050",
        "upper_strike_price": "0.000",
        "lower_strike_price": "0.000",
        "call_price": "0.000",
        "underlying_symbol": "2318.HK"
      }
    }
  ]
}
```

#### 接口限制

:::caution

- 港股 BMP 行情，超过 20 支的港股标的将响应延迟行情。

:::

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                                   |
| ---------- | ---------- | -------------- | ------------------------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败                     |
| 3          | 301606     | 限流           | 降低请求频次                               |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理                   |
| 7          | 301607     | 接口限制       | 请求的标的数量超限，请减少单次请求标的数量 |

#### 1.20 更新置顶

- **Python SDK**：`QuoteContext.update_pinned(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[更新置顶](https://open.longbridge.com/zh-CN/docs/quote/watchlist/update-pinned)
- **HTTP**：`PUT /watchlist/groups`

在自选股分组中置顶或取消置顶指定证券，以控制显示顺序。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name      | Type   | Required | Description                                              |
| --------- | ------ | -------- | -------------------------------------------------------- |
| id        | string | YES      | Watchlist group ID                                       |
| symbol    | string | YES      | Security symbol to pin or unpin, e.g. `AAPL.US`         |
| is_pinned | bool   | YES      | Set to `true` to pin the security, `false` to unpin it  |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

ctx.update_pinned(group_id="2630", symbol="AAPL.US", is_pinned=True)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    await ctx.update_pinned(group_id="2630", symbol="AAPL.US", is_pinned=True)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | Success     | None   |
| 400    | Bad request | None   |

#### Schemas

No response schemas. The endpoint returns an empty `data` object on success.

#### 1.21 创建新的自选股分组

- **Python SDK**：`QuoteContext.create_watchlist_group(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[创建新的自选股分组](https://open.longbridge.com/zh-CN/docs/quote/watchlist/watchlist_create_group)
- **HTTP**：`POST /v1/watchlist/groups`

﻿---
slug: watchlist_create_group
sidebar_position: 2
title: 创建分组
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

创建自选股分组

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name       | Type     | Required | Description                                                                                                                    |
| ---------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
| name       | string   | YES      | 分组名称，例如 `信息产业组`                                                                                                    |
| securities | string[] | NO       | 股票列表，例如 `["BABA.US","AAPL.US"]`<br /> 分组下股票的展示顺序，与此列表的顺序一致<br /> 如果不传此参数，则创建一个空的分组 |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
group_id = ctx.create_watchlist_group(name = "Watchlist1", securities = ["700.HK", "AAPL.US"])
print(group_id)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)
    group_id = ctx.create_watchlist_group(name = "Watchlist1", securities = ["700.HK", "AAPL.US"])
    print(group_id)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "data": {
    "id": 10086
  }
}
```

##### Response Status

| Status | Description | Schema                                                |
| ------ | ----------- | ----------------------------------------------------- |
| 200    | 返回成功    | [create_group_response](#schemacreate_group_response) |
| 500    | 内部错误    | None                                                  |

<aside className="success">
</aside>

#### Schemas

##### create_group_response

| Name | Type    | Required | Description |
| ---- | ------- | -------- | ----------- |
| id   | integer | false    | 分组 ID     |

#### 1.22 删除指定分组（ID 通过 longbridge watchlist 查询）

- **Python SDK**：`QuoteContext.delete_watchlist_group(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[删除指定分组（ID 通过 longbridge watchlist 查询）](https://open.longbridge.com/zh-CN/docs/quote/watchlist/watchlist_delete_group)
- **HTTP**：`DELETE /v1/watchlist/groups`

﻿---
slug: watchlist_delete_group
sidebar_position: 3
title: 删除分组
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

删除自选股分组

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name  | Type    | Required | Description                                                                                                               |
| ----- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| id    | integer | YES      | 分组 ID，例如 `10086`                                                                                                     |
| purge | boolean | YES      | 是否清除分组下的股票<br /> 为 `true`，则此分组下的股票将被取消关注<br /> 为 `false`，则此分组下的股票会保留在`全部`分组中 |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
ctx.delete_watchlist_group(10086)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)
    ctx.delete_watchlist_group(10086)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 返回成功    | None   |
| 500    | 内部错误    | None   |

<aside className="success">
</aside>

#### 1.23 查看所有自选股分组及标的

- **Python SDK**：`QuoteContext.watchlist(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[查看所有自选股分组及标的](https://open.longbridge.com/zh-CN/docs/quote/watchlist/watchlist_groups)
- **HTTP**：`GET /v1/watchlist/groups`

﻿---
slug: watchlist_groups
sidebar_position: 1
title: 关注分组
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

获取自选股分组

#### Request

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
resp = ctx.watchlist()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)
    resp = await ctx.watchlist()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "data": {
    "groups": [
      {
        "id": 28020,
        "name": "all",
        "securities": [
          {
            "symbol": "700.HK",
            "market": "HK",
            "name": "腾讯控股",
            "watched_price": "364.4",
            "watched_at": 1652855022,
            "is_pinned": true
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                                    |
| ------ | ----------- | ----------------------------------------- |
| 200    | 返回成功    | [groups_response](#schemagroups_response) |
| 500    | 内部错误    | None                                      |

<aside className="success">
</aside>

#### Schemas

##### groups_response

| Name             | Type     | Required | Description  |
| ---------------- | -------- | -------- | ------------ |
| groups           | object[] | false    | 分组         |
| ∟ id             | integer  | true     | 分组 ID      |
| ∟ name           | string   | true     | 名称         |
| ∟ securities     | object[] | true     | 股票         |
| ∟∟ symbol        | string   | true     | 代码         |
| ∟∟ market        | string   | true     | 市场         |
| ∟∟ name          | string   | true     | 名称         |
| ∟∟ watched_price | string   | true     | 关注时的价格 |
| ∟∟ watched_at    | integer  | true     | 关注时间     |
| ∟∟ is_pinned     | boolean  | true     | 是否置顶     |

#### 1.24 向分组添加标的

- **Python SDK**：`QuoteContext.update_watchlist_group(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[向分组添加标的](https://open.longbridge.com/zh-CN/docs/quote/watchlist/watchlist_update_group)
- **HTTP**：`PUT /v1/watchlist/groups`

﻿---
slug: watchlist_update_group
sidebar_position: 4
title: 管理分组标的
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

更新自选股分组

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name       | Type     | Required | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ---------- | -------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| id         | integer  | YES      | 分组 ID，例如 `10086`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| name       | string   | NO       | 分组名称，例如 `信息产业组`<br /> 如果不传递此参数，则分组名称不会更新                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| securities | string[] | NO       | 股票列表，例如 `["BABA.US","AAPL.US"]`<br /> 配合下面的 `mode` 参数，可完成添加股票、移除股票、对关注列表进行排序等操作                                                                                                                                                                                                                                                                                                                                                                                                |
| mode       | string   | NO       | 操作方法<br /> **可选值：**<br /> `add` - 添加<br /> `remove` - 移除<br /> `replace` - 替换<br /><br /> 选 `add` 时，将上面列表中的股票依序添加到此分组中<br /><br /> 选 `remove` 时，将上面列表中的股票从此分组中移除<br /><br /> 选 `replace` 时，将上面列表中的股票全量覆盖此分组下的股票<br /> 假如原来分组中的股票为 `APPL.US, BABA.US, TSLA.US`，使用 `["BABA.US","AAPL.US","MSFT.US"]` 更新后变为 `["BABA.US","AAPL.US","MSFT.US"]`，对比之前，移除了 `TSLA.US`，添加了 `MSFT.US`，`BABA.US,AAPL.US` 调整了顺序 |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, SecuritiesUpdateMode, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
ctx.update_watchlist_group(10086, name="WatchList2", securities=["700.HK", "AAPL.US"], mode=SecuritiesUpdateMode.Replace)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, SecuritiesUpdateMode, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)
    ctx.update_watchlist_group(10086, name="WatchList2", securities=["700.HK", "AAPL.US"], mode=SecuritiesUpdateMode.Replace)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 返回成功    | None   |
| 500    | 内部错误    | None   |

<aside className="success">
</aside>

### 2. 收费/订阅权限

| 接口 | Python SDK | 权限/费用 |
| --- | --- | --- |
| [期权实时报价](https://open.longbridge.com/zh-CN/docs/quote/pull/option-quote) | QuoteContext.option_quote(...) | 收费/订阅：OPRA 美股期权实时行情。 |
| [经纪队列](https://open.longbridge.com/zh-CN/docs/quote/pull/brokers) | QuoteContext.brokers(...) | 收费/订阅：港股 LV2 高级行情，提供经纪队列。 |
| [实时经纪队列订阅](https://open.longbridge.com/zh-CN/docs/quote/push/broker) | QuoteContext.set_on_brokers(...) | 收费/订阅：港股 LV2 高级行情，提供经纪队列。 |

#### 2.1 期权实时报价

- **Python SDK**：`QuoteContext.option_quote(...)`
- **权限/费用**：收费/订阅：OPRA 美股期权实时行情。
- **官方页面**：[期权实时报价](https://open.longbridge.com/zh-CN/docs/quote/pull/option-quote)

该接口用于获取美股期权标的的实时行情，包括期权的特有数据。

:::info
[业务指令](../../socket/biz_command)：`12`
:::

#### Request

##### Parameters

| Name   | Type     | Required | Description                                                                                                                                                                                  |
| ------ | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| symbol | string[] | 是       | 标的代码列表，通过[期权链接口](./optionchain-date-strike.md) 获取期权标的的 symbol，例如：`[BABA230120C160000.US]` <br /><br />**校验规则：**<br />每次请求支持传入的标的数量上限是 `500` 个 |

##### Protobuf

```protobuf
message MultiSecurityRequest {
  repeated string symbol = 1;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.option_quote(["AAPL230317P160000.US"])
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.option_quote(["AAPL230317P160000.US"])
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name                     | Type     | Description                                                         |
| ------------------------ | -------- | ------------------------------------------------------------------- |
| secu_quote               | object[] | 期权标的行情数据列表                                                |
| ∟ symbol                 | string   | 标的代码                                                            |
| ∟ last_done              | string   | 最新价                                                              |
| ∟ prev_close             | string   | 昨收价                                                              |
| ∟ open                   | string   | 开盘价                                                              |
| ∟ high                   | string   | 最高价                                                              |
| ∟ low                    | string   | 最低价                                                              |
| ∟ timestamp              | int64    | 最新成交的时间戳                                                    |
| ∟ volume                 | int64    | 成交量                                                              |
| ∟ turnover               | string   | 成交额                                                              |
| ∟ trade_status           | int32    | 标的交易状态，详见 [TradeStatus](../objects#tradestatus---交易状态) |
| ∟ option_extend          | object   | 期权扩展行情                                                        |
| ∟∟ implied_volatility    | string   | 隐含波动率                                                          |
| ∟∟ open_interest         | int64    | 未平仓数                                                            |
| ∟∟ expiry_date           | string   | 到期日，使用：`YYMMDD` 格式                                         |
| ∟∟ strike_price          | string   | 行权价                                                              |
| ∟∟ contract_multiplier   | string   | 合约乘数                                                            |
| ∟∟ contract_type         | string   | 期权类型 <br /><br />**可选值：**<br />`A` - 美式 <br />`U` - 欧式  |
| ∟∟ contract_size         | string   | 合约规模                                                            |
| ∟∟ direction             | string   | 方向 <br /><br />**可选值：**<br />`P` - put <br />`C` - call       |
| ∟∟ historical_volatility | string   | 对应正股的历史波动率                                                |
| ∟∟ underlying_symbol     | string   | 对应的正股标的代码                                                  |

##### Protobuf

```protobuf
message OptionQuoteResponse {
  repeated OptionQuote secu_quote = 1;
}

message OptionQuote {
  string symbol = 1;
  string last_done = 2;
  string prev_close = 3;
  string open = 4;
  string high = 5;
  string low = 6;
  int64 timestamp = 7;
  int64 volume = 8;
  string turnover = 9;
  TradeStatus trade_status = 10;
  OptionExtend option_extend = 11;
}

message OptionExtend {
  string implied_volatility = 1;
  int64 open_interest = 2;
  string expiry_date = 3;
  string strike_price = 4;
  string contract_multiplier = 5;
  string contract_type = 6;
  string contract_size = 7;
  string direction = 8;
  string historical_volatility = 9;
  string underlying_symbol = 10;
}
```

##### Response JSON Example

```json
{
  "secu_quote": [
    {
      "symbol": "AAPL220429P162500.US",
      "last_done": "7.78",
      "prev_close": "4.13",
      "open": "4.43",
      "high": "7.80",
      "low": "4.43",
      "timestamp": 1651003200,
      "volume": 3082,
      "turnover": "1813434.00",
      "option_extend": {
        "implied_volatility": "0.592",
        "open_interest": 11463,
        "expiry_date": "20220429",
        "strike_price": "162.50",
        "contract_multiplier": "100",
        "contract_type": "A",
        "contract_size": "100",
        "direction": "P",
        "historical_volatility": "0.2750",
        "underlying_symbol": "AAPL.US"
      }
    },
    {
      "symbol": "AAPL220429C150000.US",
      "last_done": "9.25",
      "prev_close": "13.87",
      "open": "13.80",
      "high": "13.80",
      "low": "9.15",
      "timestamp": 1651003200,
      "volume": 413,
      "turnover": "436835.00",
      "option_extend": {
        "implied_volatility": "0.702",
        "open_interest": 800,
        "expiry_date": "20220429",
        "strike_price": "150.00",
        "contract_multiplier": "100",
        "contract_type": "A",
        "contract_size": "100",
        "direction": "C",
        "historical_volatility": "0.2750",
        "underlying_symbol": "AAPL.US"
      }
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                                   |
| ---------- | ---------- | -------------- | ------------------------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败                     |
| 3          | 301606     | 限流           | 降低请求频次                               |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理                   |
| 7          | 301607     | 接口限制       | 请求的标的数量超限，请减少单次请求标的数量 |

#### 2.2 经纪队列

- **Python SDK**：`QuoteContext.brokers(...)`
- **权限/费用**：收费/订阅：港股 LV2 高级行情，提供经纪队列。
- **官方页面**：[经纪队列](https://open.longbridge.com/zh-CN/docs/quote/pull/brokers)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可查询任意标的，包括美股。
:::

该接口用于获取标的的实时经纪队列数据。

:::info
[业务指令](../../socket/biz_command)：`15`
:::

#### Request

##### Parameters

| Name   | Type   | Required | Description                                          |
| ------ | ------ | -------- | ---------------------------------------------------- |
| symbol | string | 是       | 标的代码，使用 `ticker.region` 格式，例如： `700.HK` |

##### Protobuf

```protobuf
message SecurityRequest {
  string symbol = 1;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.brokers("700.HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.brokers("700.HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name         | Type     | Description                                                |
| ------------ | -------- | ---------------------------------------------------------- |
| symbol       | string   | 标的代码                                                   |
| ask_brokers  | object[] | 卖盘经纪队列                                               |
| ∟ position   | int32    | 档位                                                       |
| ∟ broker_ids | int32[]  | 券商席位 ID，通过[获取券商席位 ID ](./broker-ids) 接口获取 |
| bid_brokers  | object[] | 买盘经纪队列                                               |
| ∟ position   | int32    | 档位                                                       |
| ∟ broker_ids | int32[]  | 券商席位 ID，通过[获取券商席位 ID ](./broker-ids) 接口获取 |

##### Protobuf

```protobuf
message SecurityBrokersResponse {
  string symbol = 1;
  repeated Brokers ask_brokers = 2;
  repeated Brokers bid_brokers = 3;
}

message Brokers {
  int32 position = 1;
  repeated int32 broker_ids = 2;
}
```

##### Response JSON Example

```json
{
  "symbol": "700.HK",
  "ask_brokers": [
    {
      "position": 1,
      "broker_ids": [7358, 9057, 9028, 7364]
    },
    {
      "position": 2,
      "broker_ids": [6968, 3448, 3348, 1049, 4973, 6997, 3448, 5465, 6997]
    }
  ],
  "bid_brokers": [
    {
      "position": 1,
      "broker_ids": [6996, 5465, 8026, 8304, 4978]
    },
    {
      "position": 2
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                     |
| ---------- | ---------- | -------------- | ---------------------------- |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败       |
| 3          | 301606     | 限流           | 降低请求频次                 |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理     |
| 7          | 301600     | 请求标的不存在 | 检查请求的 `symbol` 是否正确 |
| 7          | 301603     | 标的无行情     | 标的没有请求的行情数据       |
| 7          | 301604     | 无权限         | 没有获取标的行情的权限       |

#### 2.3 实时经纪队列订阅

- **Python SDK**：`QuoteContext.set_on_brokers(...)`
- **权限/费用**：收费/订阅：港股 LV2 高级行情，提供经纪队列。
- **官方页面**：[实时经纪队列订阅](https://open.longbridge.com/zh-CN/docs/quote/push/broker)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

已订阅标的的实时经纪队列数据推送。

:::info

[业务指令](../../socket/protocol/push)：`103`

:::

#### 数据格式

##### Properties

| Name         | Type     | Description                       |
| ------------ | -------- | --------------------------------- |
| symbol       | string   | 标的代码，例如：`AAPL.US`         |
| sequence     | int64    | 序列号                            |
| ask_brokers  | object[] | 卖盘经纪队列                      |
| ∟ position   | int32    | 档位                              |
| ∟ broker_ids | int32[]  | [券商席位 Id](../pull/broker-ids) |
| bid_brokers  | object[] | 买盘经纪队列                      |
| ∟ position   | int32    | 档位                              |
| ∟ broker_ids | int32[]  | [券商席位 Id](../pull/broker-ids) |

##### Protobuf

```protobuf
message PushBrokers {
  string symbol = 1;
  int64 sequence = 2;
  repeated Brokers ask_brokers = 3;
  repeated Brokers bid_brokers = 4;
}

message Brokers {
  int32 position = 1;
  repeated int32 broker_ids = 2;
}
```

##### Example

```python
from time import sleep
from longbridge.openapi import QuoteContext, Config, SubType, PushBrokers, OAuthBuilder

def on_brokers(symbol: str, event: PushBrokers):
    print(symbol, event)

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
ctx.set_on_brokers(on_brokers)

ctx.subscribe(["700.HK", "AAPL.US"], [SubType.Brokers])
sleep(30)
```

##### JSON Example

```json
{
  "symbol": "700.HK",
  "sequence": 160808750000000,
  "ask_brokers": [
    {
      "position": 1,
      "broker_ids": [7358, 9057, 9028, 7364]
    },
    {
      "position": 2,
      "broker_ids": [6968, 3448, 3348, 1049, 4973, 6997, 3448, 5465, 6997]
    }
  ],
  "bid_brokers": [
    {
      "position": 1,
      "broker_ids": [6996, 5465, 8026, 8304, 4978]
    },
    {
      "position": 2,
      "broker_ids": [7358, 9057, 9028, 7364]
    }
  ]
}
```

### 3. 按市场/标的条件权限

| 接口 | Python SDK | 权限/费用 |
| --- | --- | --- |
| [K 线](https://open.longbridge.com/zh-CN/docs/quote/pull/candlestick) | QuoteContext.candlesticks(...) | 按市场/标的 |
| [盘口](https://open.longbridge.com/zh-CN/docs/quote/pull/depth) | QuoteContext.depth(...) | 按市场/标的 |
| [历史 K 线](https://open.longbridge.com/zh-CN/docs/quote/pull/history-candlestick) | QuoteContext.history_candlesticks_by_offset(...) | 按市场/标的 |
| [分时数据](https://open.longbridge.com/zh-CN/docs/quote/pull/intraday) | QuoteContext.intraday(...) | 按市场/标的 |
| [实时报价](https://open.longbridge.com/zh-CN/docs/quote/pull/quote) | QuoteContext.quote(...) | 按市场/标的 |
| [逐笔明细](https://open.longbridge.com/zh-CN/docs/quote/pull/trade) | QuoteContext.trades(...) | 按市场/标的 |
| [K 线](https://open.longbridge.com/zh-CN/docs/quote/push/candlestick) | QuoteContext.set_on_candlestick(...) | 按市场/标的 |
| [实时盘口订阅](https://open.longbridge.com/zh-CN/docs/quote/push/depth) | QuoteContext.set_on_depth(...) | 按市场/标的 |
| [实时价格订阅](https://open.longbridge.com/zh-CN/docs/quote/push/quote) | QuoteContext.set_on_quote(...) | 按市场/标的 |
| [实时成交明细订阅](https://open.longbridge.com/zh-CN/docs/quote/push/trade) | QuoteContext.set_on_trades(...) | 按市场/标的 |

#### 3.1 K 线

- **Python SDK**：`QuoteContext.candlesticks(...)`
- **权限/费用**：基础免费；港股高级行情或美股期权可能需要额外行情卡
- **官方页面**：[K 线](https://open.longbridge.com/zh-CN/docs/quote/pull/candlestick)

该接口用于获取标的的 K 线数据。

:::info
注意：本接口只能获取到最近 1000 根 K 线，如需获取较长的历史数据，请访问接口：获取标的历史 K 线。
:::

:::info

[业务指令](../../socket/biz_command)：`19`

:::

#### Request

##### Parameters

| Name          | Type   | Required | Description                                                                  |
| ------------- | ------ | -------- | ---------------------------------------------------------------------------- |
| symbol        | string | 是       | 标的代码，使用 `ticker.region` 格式，例如：`700.HK`                          |
| period        | int32  | 是       | k 线周期，例如：`1000`，详见 [Period](../objects#period---k-线周期)          |
| count         | int32  | 是       | 数据数量，例如：`100`<br /><br />**校验规则：** <br />请求数量最大为 `1000`  |
| adjust_type   | int32  | 是       | 复权类型，例如：`0`，详见 [AdjustType](../objects#adjusttype---k-线复权类型) |
| trade_session | int32  | 否       | 交易时段，0: 盘中，100: 所有（盘前，盘中，盘后，夜盘）<br/><br/>注意：夜盘数据已包含在 US LV1 中免费提供，仅支持美股；开启 `enable_overnight` 参数即可获取 |

##### Protobuf

```protobuf
message SecurityCandlestickRequest {
  string symbol = 1;
  Period period = 2;
  int32 count = 3;
  AdjustType adjust_type = 4;
  int32 trade_session = 5;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, Period, AdjustType, TradeSessions, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

### 获取 700.HK 的盘中 K 线
resp = ctx.candlesticks("700.HK", Period.Day, 10, AdjustType.NoAdjust)
print(resp)

### 获取 700.HK 的所有 K 线
resp = ctx.candlesticks("700.HK", Period.Day, 10, AdjustType.NoAdjust, trade_session=TradeSessions.All)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, Period, AdjustType, TradeSessions, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    # 获取 700.HK 的盘中 K 线
    resp = await ctx.candlesticks("700.HK", Period.Day, 10, AdjustType.NoAdjust)
    print(resp)

    # 获取 700.HK 的所有 K 线
    resp = await ctx.candlesticks("700.HK", Period.Day, 10, AdjustType.NoAdjust, trade_session=TradeSessions.All)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name            | Type     | Description                                                       |
| --------------- | -------- | ----------------------------------------------------------------- |
| symbol          | string   | 标的代码，例如：`AAPL.US`                                         |
| candlesticks    | object[] | K 线数据                                                          |
| ∟ close         | string   | 当前周期收盘价                                                    |
| ∟ open          | string   | 当前周期开盘价                                                    |
| ∟ low           | string   | 当前周期最低价                                                    |
| ∟ high          | string   | 当前周期最高价                                                    |
| ∟ volume        | int64    | 当前周期成交量                                                    |
| ∟ turnover      | string   | 当前周期成交额                                                    |
| ∟ timestamp     | int64    | 当前周期的时间戳                                                  |
| ∟ trade_session | int32    | 交易時段，详见 [TradeSession](../objects#tradesession---交易时段) |

##### Protobuf

```protobuf
message SecurityCandlestickResponse {
  string symbol = 1;
  repeated Candlestick candlesticks = 2;
}

message Candlestick {
  string close = 1;
  string open = 2;
  string low = 3;
  string high = 4;
  int64 volume = 5;
  string turnover = 6;
  int64 timestamp = 7;
}
```

##### Response JSON Example

```json
{
  "symbol": "700.HK",
  "candlesticks": [
    {
      "close": "362.000",
      "open": "364.600",
      "low": "361.600",
      "high": "368.800",
      "volume": 10853604,
      "turnover": "3954556819.000",
      "timestamp": 1650384000
    },
    {
      "close": "348.000",
      "open": "352.000",
      "low": "343.000",
      "high": "356.200",
      "volume": 25738562,
      "turnover": "8981529950.000",
      "timestamp": 1650470400
    },
    {
      "close": "340.600",
      "open": "334.800",
      "low": "334.200",
      "high": "343.000",
      "volume": 28031299,
      "turnover": "9492674293.000",
      "timestamp": 1650556800
    },
    {
      "close": "327.400",
      "open": "332.200",
      "low": "325.200",
      "high": "338.600",
      "volume": 25788422,
      "turnover": "8541441823.000",
      "timestamp": 1650816000
    },
    {
      "close": "335.800",
      "open": "332.200",
      "low": "330.600",
      "high": "341.600",
      "volume": 27288328,
      "turnover": "9166022626.000",
      "timestamp": 1650902400
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                                                                 |
| ---------- | ---------- | -------------- | ------------------------------------------------------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败                                                   |
| 3          | 301606     | 限流           | 降低请求频次                                                             |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理                                                 |
| 7          | 301600     | 请求数据非法   | 检查请求的 `symbol`，`count`，`adjust_type`, `period` 数据是否在正确范围 |
| 7          | 301603     | 标的无行情     | 标的没有请求的行情数据                                                   |
| 7          | 301604     | 无权限         | 没有获取标的行情的权限                                                   |
| 7          | 301607     | 接口限制       | 请求的数据数量超限，减少数据数量                                         |

#### 3.2 盘口

- **Python SDK**：`QuoteContext.depth(...)`
- **权限/费用**：基础免费；港股高级行情或美股期权可能需要额外行情卡
- **官方页面**：[盘口](https://open.longbridge.com/zh-CN/docs/quote/pull/depth)

该接口用于获取标的的盘口数据。

:::info

[业务指令](../../socket/biz_command)：`14`

:::

#### Request

##### Parameters

| Name   | Type   | Required | Description                                         |
| ------ | ------ | -------- | --------------------------------------------------- |
| symbol | string | 是       | 标的代码，使用 `ticker.region` 格式，例如：`700.HK` |

##### Protobuf

```protobuf
message SecurityRequest {
  string symbol = 1;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.depth("700.HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.depth("700.HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name        | Type     | Description |
| ----------- | -------- | ----------- |
| symbol      | string   | 标的代码    |
| ask         | object[] | 卖盘        |
| ∟ position  | int32    | 档位        |
| ∟ price     | string   | 价格        |
| ∟ volume    | int64    | 挂单量      |
| ∟ order_num | int64    | 订单数量    |
| bid         | object[] | 买盘        |
| ∟ position  | int32    | 档位        |
| ∟ price     | string   | 价格        |
| ∟ volume    | int64    | 挂单量      |
| ∟ order_num | int64    | 订单数量    |

##### Protobuf

```protobuf
message SecurityDepthResponse {
  string symbol = 1;
  repeated Depth ask = 2;
  repeated Depth bid = 3;
}

message Depth {
  int32 position = 1;
  string price = 2;
  int64 volume = 3;
  int64 order_num = 4;
}
```

##### Response JSON Example

```json
{
  "symbol": "700.HK",
  "ask": [
    {
      "position": 1,
      "price": "335.000",
      "volume": 500,
      "order_num": 1
    },
    {
      "position": 2,
      "price": "335.200",
      "volume": 400,
      "order_num": 1
    },
    {
      "position": 3,
      "price": "335.400",
      "volume": 500,
      "order_num": 2
    },
    {
      "position": 4,
      "price": "335.600",
      "volume": 1200,
      "order_num": 3
    },
    {
      "position": 5,
      "price": "335.800",
      "volume": 14000,
      "order_num": 8
    }
  ],
  "bid": [
    {
      "position": 1,
      "price": "334.800",
      "volume": 69400,
      "order_num": 13
    },
    {
      "position": 2,
      "price": "334.600",
      "volume": 266600,
      "order_num": 27
    },
    {
      "position": 3,
      "price": "334.400",
      "volume": 61300,
      "order_num": 29
    },
    {
      "position": 4,
      "price": "334.200",
      "volume": 125900,
      "order_num": 31
    },
    {
      "position": 5,
      "price": "334.000",
      "volume": 194600,
      "order_num": 94
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                     |
| ---------- | ---------- | -------------- | ---------------------------- |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败       |
| 3          | 301606     | 限流           | 降低请求频次                 |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理     |
| 7          | 301600     | 请求标的不存在 | 检查请求的 `symbol` 是否正确 |
| 7          | 301603     | 标的无行情     | 标的没有请求的行情数据       |
| 7          | 301604     | 无权限         | 没有获取标的行情的权限       |

#### 3.3 历史 K 线

- **Python SDK**：`QuoteContext.history_candlesticks_by_offset(...)`
- **权限/费用**：基础免费；港股高级行情或美股期权可能需要额外行情卡
- **官方页面**：[历史 K 线](https://open.longbridge.com/zh-CN/docs/quote/pull/history-candlestick)

该接口用于获取标的的历史 K 线数据。

:::info

[业务指令](../../socket/biz_command)：`27`

:::

#### Request

##### Parameters

| Name           | Type   | Required | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| -------------- | ------ | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| symbol         | string | 是       | 标的代码，使用 `ticker.region` 格式，例如：`700.HK`                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| period         | int32  | 是       | k 线周期，例如：`1000`，详见 [Period](../objects#period---k-线周期)                                                                                                                                                                                                                                                                                                                                                                                                                    |
| adjust_type    | int32  | 是       | 复权类型，例如：`0`，详见 [AdjustType](../objects#adjusttype---k-线复权类型)                                                                                                                                                                                                                                                                                                                                                                                                           |
| query_type     | int32  | 是       | 查询方式 <br /><br />**可选值：**<br />`1` - 按偏移查询 <br />`2` - 按日期区间查询                                                                                                                                                                                                                                                                                                                                                                                                     |
| date_request   | object | 否       | 按日期查询时必填                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ∟ start_date   | string | 否       | 开始日期，格式为 `YYYYMMDD`，例如：20231016 <br /><br />**参数说明：**<br /> 1. start_date 和 end_date 均不填：返回最新的 1000 根 K 线；<br />2. 仅填 start_date：返回 start_date 与最新交易日区间内的 K 线。若此区间内 K 线超过 1000 根，则优先返回靠近 start_date 的 1000 根 K 线；<br /> 3. 仅填 end_date：返回 end_date 及以前的 1000 根 K 线；<br />4. start_date 和 end_date 均填：返回此区间内的 K 线数据。若此区间内 K 线超过 1000 根，则优先返回靠近 end_date 的 1000 根 K 线 |
| ∟ end_date     | string | 否       | 结束日期，格式为 `YYYYMMDD`，例如：20231016                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| offset_request | object | 否       | 按偏移查询时必填                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ∟ direction    | int32  | 是       | 查询方向 <br /><br />**可选值：**<br />`0` - 向历史数据方向查找 <br />`1` - 向最新数据方向查找                                                                                                                                                                                                                                                                                                                                                                                         |
| ∟ date         | string | 否       | 查询日期，格式为 `YYYYMMDD`，例如：20231016，为空时使用标的所在市场的最新交易日                                                                                                                                                                                                                                                                                                                                                                                                        |
| ∟ minute       | string | 否       | 查询时间，格式为 `HHMM`，例如：09:35，仅在查询分钟级别 K 线时有效                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ∟ count        | int32  | 否       | 查询数量，填写范围 `[1,1000]`，为空时默认查询 `10` 条                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| trade_session  | int32  | 否       | 交易时段，0: 盘中，100: 所有延长时段（盘前，盘中，盘后，夜盘）<br/><br/>注意：夜盘数据已包含在 US LV1 中免费提供，仅支持美股；开启 `enable_overnight` 参数即可获取                                                                                                                                                                                                                                                                                                                     |

##### Protobuf

```protobuf
message SecurityHistoryCandlestickRequest {

  message OffsetQuery {
    Direction direction = 1;
    string date = 2;
    string minute = 3;
    int32 count = 4;
  }

  message DateQuery {
    string start_date = 1;
    string end_date = 2;
  }

  string symbol = 1;
  Period period = 2;
  AdjustType adjust_type = 3;
  HistoryCandlestickQueryType query_type = 4;
  OffsetQuery offset_request = 5;
  DateQuery date_request = 6;
}
```

##### Request Example

###### Python 示例

```python
from datetime import datetime, date
from longbridge.openapi import QuoteContext, Config, Period, AdjustType, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

### Query after 2023-01-01
resp = ctx.history_candlesticks_by_offset("700.HK", Period.Day, AdjustType.NoAdjust, True, 10, datetime(2023, 1, 1))
print(resp)

### Query before 2023-01-01
resp = ctx.history_candlesticks_by_offset("700.HK", Period.Day, AdjustType.NoAdjust, False, 10, datetime(2023, 1, 1))
print(resp)

### Query 2023-01-01 to 2023-02-01
resp = ctx.history_candlesticks_by_date("700.HK", Period.Day, AdjustType.NoAdjust, date(2023, 1, 1), date(2023, 2, 1))
print(resp)
```

###### Python 异步示例

```python
import asyncio
from datetime import datetime, date
from longbridge.openapi import AsyncQuoteContext, Config, Period, AdjustType, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    # Query after 2023-01-01
    resp = await ctx.history_candlesticks_by_offset("700.HK", Period.Day, AdjustType.NoAdjust, True, 10, datetime(2023, 1, 1))
    print(resp)

    # Query before 2023-01-01
    resp = await ctx.history_candlesticks_by_offset("700.HK", Period.Day, AdjustType.NoAdjust, False, 10, datetime(2023, 1, 1))
    print(resp)

    # Query 2023-01-01 to 2023-02-01
    resp = await ctx.history_candlesticks_by_date("700.HK", Period.Day, AdjustType.NoAdjust, date(2023, 1, 1), date(2023, 2, 1))
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name            | Type     | Description                                                       |
| --------------- | -------- | ----------------------------------------------------------------- |
| symbol          | string   | 标的代码，例如：`AAPL.US`                                         |
| candlesticks    | object[] | K 线数据                                                          |
| ∟ close         | string   | 当前周期收盘价                                                    |
| ∟ open          | string   | 当前周期开盘价                                                    |
| ∟ low           | string   | 当前周期最低价                                                    |
| ∟ high          | string   | 当前周期最高价                                                    |
| ∟ volume        | int64    | 当前周期成交量                                                    |
| ∟ turnover      | string   | 当前周期成交额                                                    |
| ∟ timestamp     | int64    | 当前周期的时间戳                                                  |
| ∟ trade_session | int32    | 交易時段，详见 [TradeSession](../objects#tradesession---交易时段) |

##### Protobuf

```protobuf
message SecurityCandlestickResponse {
  string symbol = 1;
  repeated Candlestick candlesticks = 2;
}

message Candlestick {
  string close = 1;
  string open = 2;
  string low = 3;
  string high = 4;
  int64 volume = 5;
  string turnover = 6;
  int64 timestamp = 7;
}
```

##### Response JSON Example

```json
{
  "symbol": "700.HK",
  "candlesticks": [
    {
      "close": "362.000",
      "open": "364.600",
      "low": "361.600",
      "high": "368.800",
      "volume": 10853604,
      "turnover": "3954556819.000",
      "timestamp": 1650384000
    },
    {
      "close": "348.000",
      "open": "352.000",
      "low": "343.000",
      "high": "356.200",
      "volume": 25738562,
      "turnover": "8981529950.000",
      "timestamp": 1650470400
    },
    {
      "close": "340.600",
      "open": "334.800",
      "low": "334.200",
      "high": "343.000",
      "volume": 28031299,
      "turnover": "9492674293.000",
      "timestamp": 1650556800
    },
    {
      "close": "327.400",
      "open": "332.200",
      "low": "325.200",
      "high": "338.600",
      "volume": 25788422,
      "turnover": "8541441823.000",
      "timestamp": 1650816000
    },
    {
      "close": "335.800",
      "open": "332.200",
      "low": "330.600",
      "high": "341.600",
      "volume": 27288328,
      "turnover": "9166022626.000",
      "timestamp": 1650902400
    }
  ]
}
```

#### 权限说明

依据用户的资产和交易情况，不同类型的用户每月可查询历史数据的标的数量如下表：

- 额度按照自然月计算，每月初额度加满，上月剩余额度不累计到本月。一个自然月内重复请求同一只标的的历史 K 线，仅统计一次。
- 新入金的账户，额度会在下个交易日自动生效；当账户的总资产或交易笔数增加、且达到更高等级时，额度会在下一个交易日生效。
- 总资产：用户的港股、美股、A 股等证券账户的总资产，按照汇率换算成港元。取用户上个自然月最后一个交易日的总资产与最近一个完整交易日的总资产的较大值。
- 月交易笔数：用户有成交的订单数量，一个订单部分成交、或多次全部成交、或一次全部成交均算 1 笔。取用户上个自然月的成交笔数与当前自然月的成交笔数的较大值。

<table>
  <tr>
    <th>用户类型</th>
    <th >每月可查询的标的数量上限（只）</th>
  </tr>
  <tr>
    <td>用户开户</td>
    <td><center>100</center></td>
  </tr>
  <tr>
    <td>总资产达 1 万 HKD  </td>
    <td><center>400</center></td>
  </tr>
  <tr>
    <td>总资产达 8 万 HKD</td>
    <td><center>600</center></td>
  </tr>
  <tr>
    <td>总资产达 40 万 HKD 或 月交易笔数大于 160 笔</td>
    <td><center>1000</center></td>
  </tr>
  <tr>
    <td>总资产达 400 万 HKD 或 月交易笔数大于 1600 笔</td>
    <td><center>2000</center></td>
  </tr>
  <tr>
    <td>总资产达 600 万 HKD 或 月交易笔数大于 2500 笔</td>
    <td><center>3000</center></td>
  </tr>
</table>

#### 历史 K 线区间说明

<table>
  <tr>
    <th>市场</th>
    <th>日/周/月/年 K 线</th>
    <th>分钟 K 线</th>
    <th>说明</th>
  </tr>
  <tr>
    <td>港股</td>
    <td>2004-06 至今</td>
    <td>2008-11 至今</td>
    <td rowspan="3">
      <strong>依据用户总资产，可查询的历史分钟 K 线时长如下：</strong><br />
      （1）用户总资产 ＜ 8 万港币：可查询近 3 年的历史分钟 K 线数据（按自然月计算，如当前为 2026 年 5 月，则可查 2023 年 5 月至今）。<br />
      （2）用户总资产 ≥ 8 万港币：可查询近 8 年的历史分钟 K 线数据（按自然月计算，如当前为 2026 年 5 月，则可查 2018 年 5 月至今）。若实际数据不足 8 年，则支持查询自最早可用数据起的所有记录。<br />
      如需查询更长周期的历史数据，可联系客服咨询。
    </td>
  </tr>
  <tr>
    <td>美股</td>
    <td>2010-06 至今</td>
    <td>2003-09 至今</td>
  </tr>
  <tr>
    <td>A 股</td>
    <td>1999-11 至今</td>
    <td>2022-08 至今</td>
  </tr>
  <tr>
    <td>美股期权</td>
    <td>-</td>
    <td>-</td>
    <td>美股期权历史数据目前暂不支持，待后续开放更长时段的数据</td>
  </tr>
</table>

#### 频次限制

:::caution

- 每 30 秒内最多请求 60 次历史 K 线接口。

:::

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                                                                 |
| ---------- | ---------- | -------------- | ------------------------------------------------------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败                                                   |
| 3          | 301606     | 限流           | 降低请求频次                                                             |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理                                                 |
| 7          | 301600     | 请求数据非法   | 检查请求的 `symbol`，`count`，`adjust_type`, `period` 数据是否在正确范围 |
| 7          | 301603     | 标的无行情     | 标的没有请求的行情数据                                                   |
| 7          | 301604     | 无权限         | 没有获取标的行情的权限                                                   |
| 7          | 301607     | 接口限制       | 超过当月能够查询的标的数量上限                                           |

#### 3.4 分时数据

- **Python SDK**：`QuoteContext.intraday(...)`
- **权限/费用**：基础免费；港股高级行情或美股期权可能需要额外行情卡
- **官方页面**：[分时数据](https://open.longbridge.com/zh-CN/docs/quote/pull/intraday)

该接口用于获取标的的当日分时数据。

:::info

[业务指令](../../socket/biz_command)：`18`

:::

#### Request

##### Parameters

| Name   | Type   | Required | Description                                         |
| ------ | ------ | -------- | --------------------------------------------------- |
| symbol | string | 是       | 标的代码，使用 `ticker.region` 格式，例如：`700.HK` |

##### Protobuf

```protobuf
message SecurityIntradayRequest {
  string symbol = 1;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.intraday("700.HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.intraday("700.HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name        | Type     | Description               |
| ----------- | -------- | ------------------------- |
| symbol      | string   | 标的代码，例如：`AAPL.US` |
| lines       | object[] | 分时数据                  |
| ∟ price     | string   | 当前分钟的收盘价格        |
| ∟ timestamp | int64    | 当前分钟的开始时间        |
| ∟ volume    | int64    | 成交量                    |
| ∟ turnover  | string   | 成交额                    |
| ∟ avg_price | string   | 均价                      |

##### Protobuf

```protobuf
message SecurityIntradayResponse{
  string symbol = 1;
  repeated Line lines = 2;
}

message Line {
  string price = 1;
  int64 timestamp = 2;
  int64 volume = 3;
  string turnover = 4;
  string avg_price = 5;
}
```

##### Response JSON Example

```json
{
  "symbol": "700.HK",
  "lines": [
    {
      "price": "330.400",
      "timestamp": 1651023000,
      "volume": 375870,
      "turnover": "123949699.000",
      "avg_price": "329.767470"
    },
    {
      "price": "331.200",
      "timestamp": 1651023060,
      "volume": 233095,
      "turnover": "77269032.800",
      "avg_price": "330.427416"
    },
    {
      "price": "330.400",
      "timestamp": 1651023120,
      "volume": 192565,
      "turnover": "63711556.000",
      "avg_price": "330.530719"
    },
    {
      "price": "330.800",
      "timestamp": 1651023180,
      "volume": 143397,
      "turnover": "47471072.400",
      "avg_price": "330.608989"
    },
    {
      "price": "330.800",
      "timestamp": 1651023240,
      "volume": 141834,
      "turnover": "46890605.600",
      "avg_price": "330.608078"
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                     |
| ---------- | ---------- | -------------- | ---------------------------- |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败       |
| 3          | 301606     | 限流           | 降低请求频次                 |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理     |
| 7          | 301600     | 请求标的不存在 | 检查请求的 `symbol` 是否正确 |
| 7          | 301603     | 标的无行情     | 标的没有请求的行情数据       |
| 7          | 301604     | 无权限         | 没有获取标的行情的权限       |

#### 3.5 实时报价

- **Python SDK**：`QuoteContext.quote(...)`
- **权限/费用**：基础免费；港股高级行情或美股期权可能需要额外行情卡
- **官方页面**：[实时报价](https://open.longbridge.com/zh-CN/docs/quote/pull/quote)

该接口用于获取标的的实时行情 (支持所有类型标的）。如需查看这些实时数据流汇聚而成的实时指数、板块热力图与宏观市场概览，可参考 [长桥全球市场](https://longbridge.com/en/markets)。

:::info
[业务指令](../../socket/biz_command)：`11`
:::

#### Request

##### Parameters

| Name   | Type     | Required | Description                                                                                                                         |
| ------ | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| symbol | string[] | 是       | 标的代码列表，使用 `ticker.region` 格式，例如：`[700.HK]` <br /><br />**校验规则：**<br />每次请求支持传入的标的数量上限是 `500` 个 |

##### Protobuf

```protobuf
message MultiSecurityRequest {
  repeated string symbol = 1;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.quote(["700.HK", "AAPL.US", "TSLA.US", "NFLX.US"])
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.quote(["700.HK", "AAPL.US", "TSLA.US", "NFLX.US"])
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name                | Type     | Description                                                                     |
| ------------------- | -------- | ------------------------------------------------------------------------------- |
| secu_quote          | object[] | 标的实时行情数据列表                                                            |
| ∟ symbol            | string   | 标的代码                                                                        |
| ∟ last_done         | string   | 最新价                                                                          |
| ∟ prev_close        | string   | 昨收价                                                                          |
| ∟ open              | string   | 开盘价                                                                          |
| ∟ high              | string   | 最高价                                                                          |
| ∟ low               | string   | 最低价                                                                          |
| ∟ timestamp         | int64    | 最新成交的时间戳                                                                |
| ∟ volume            | int64    | 成交量                                                                          |
| ∟ turnover          | string   | 成交额                                                                          |
| ∟ trade_status      | int32    | 标的交易状态，详见 [TradeStatus](../objects#tradestatus---交易状态)             |
| ∟ pre_market_quote  | object   | 美股盘前交易行情                                                                |
| ∟∟ last_done        | string   | 最新价                                                                          |
| ∟∟ timestamp        | int64    | 最新成交的时间戳                                                                |
| ∟∟ volume           | int64    | 成交量                                                                          |
| ∟∟ turnover         | string   | 成交额                                                                          |
| ∟∟ high             | string   | 最高价                                                                          |
| ∟∟ low              | string   | 最低价                                                                          |
| ∟∟ prev_close       | string   | 上一个交易阶段的收盘价                                                          |
| ∟ post_market_quote | object   | 美股盘后交易行情                                                                |
| ∟∟ last_done        | string   | 最新价                                                                          |
| ∟∟ timestamp        | int64    | 最新成交的时间戳                                                                |
| ∟∟ volume           | int64    | 成交量                                                                          |
| ∟∟ turnover         | string   | 成交额                                                                          |
| ∟∟ high             | string   | 最高价                                                                          |
| ∟∟ low              | string   | 最低价                                                                          |
| ∟∟ prev_close       | string   | 上一个交易阶段的收盘价                                                          |
| ∟ overnight_quote   | object   | 美股夜盘交易行情<br/><br/>注意：需开启 `enable_overnight` 参数获取，否则会返回 null（夜盘行情已包含在 US LV1 中免费提供，仅支持美股） |
| ∟∟ last_done        | string   | 最新价                                                                          |
| ∟∟ timestamp        | int64    | 最新成交的时间戳                                                                |
| ∟∟ volume           | int64    | 成交量                                                                          |
| ∟∟ turnover         | string   | 成交额                                                                          |
| ∟∟ high             | string   | 最高价                                                                          |
| ∟∟ low              | string   | 最低价                                                                          |
| ∟∟ prev_close       | string   | 上一个交易阶段的收盘价                                                          |

##### 注意

###### `overnight_quote` 参数细节

只有当我们在配置的时候开启了 `enable_overnight` 参数，才会返回 `overnight_quote` 字段。

```py
config = Config(
    app_key="your_app_key",
    app_secret="your_app_secret",
    access_token="your_access_token",
    enable_overnight=True)
```

或者设置环境变量 `LONGBRIDGE_ENABLE_OVERNIGHT` 为 `true`（兼容旧版 `LONGPORT_ENABLE_OVERNIGHT`）。

##### Protobuf

```protobuf
message SecurityQuoteResponse {
  repeated SecurityQuote secu_quote = 1;
}

message SecurityQuote {
  string symbol = 1;
  string last_done = 2;
  string prev_close = 3;
  string open = 4;
  string high = 5;
  string low = 6;
  int64 timestamp = 7;
  int64 volume = 8;
  string turnover = 9;
  TradeStatus trade_status = 10;
  PrePostQuote pre_market_quote = 11;
  PrePostQuote post_market_quote = 12;
}

message PrePostQuote {
  string last_done = 1;
  int64 timestamp = 2;
  int64 volume = 3;
  string turnover = 4;
  string high = 5;
  string low = 6;
  string prev_close = 7;
}
```

##### Response JSON Example

```json
{
  "secu_quote": [
    {
      "symbol": "700.HK",
      "last_done": "338.000",
      "prev_close": "334.800",
      "open": "340.600",
      "high": "340.600",
      "low": "333.000",
      "timestamp": 1651115955,
      "volume": 7310881,
      "turnover": "2461463161.000"
    },
    {
      "symbol": "AAPL.US",
      "last_done": "156.570",
      "prev_close": "156.800",
      "open": "155.910",
      "high": "159.790",
      "low": "155.380",
      "timestamp": 1651089600,
      "volume": 88063191,
      "turnover": "13865092584.000",
      "pre_market_quote": {
        "last_done": "155.880",
        "timestamp": 1651066201,
        "volume": 1575504,
        "turnover": "246653442.000",
        "high": "158.400",
        "low": "155.100",
        "prev_close": "156.800"
      },
      "post_market_quote": {
        "last_done": "158.770",
        "timestamp": 1651103995,
        "volume": 6188441,
        "turnover": "970874184.759",
        "high": "159.400",
        "low": "156.400",
        "prev_close": "156.570"
      }
    }
  ]
}
```

#### 接口限制

:::caution

- 港股 BMP 行情，超过 20 支的港股标的将响应延迟行情。

:::

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                                   |
| ---------- | ---------- | -------------- | ------------------------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败                     |
| 3          | 301606     | 限流           | 降低请求频次                               |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理                   |
| 7          | 301607     | 接口限制       | 请求的标的数量超限，请减少单次请求标的数量 |

#### 3.6 逐笔明细

- **Python SDK**：`QuoteContext.trades(...)`
- **权限/费用**：基础免费；港股高级行情或美股期权可能需要额外行情卡
- **官方页面**：[逐笔明细](https://open.longbridge.com/zh-CN/docs/quote/pull/trade)

该接口用于获取标的的成交明细数据。

:::info

[业务指令](../../socket/biz_command)：`17`

:::

#### Request

##### Parameters

| Name   | Type   | Required | Description                                                              |
| ------ | ------ | -------- | ------------------------------------------------------------------------ |
| symbol | string | 是       | 标的代码，使用 `ticker.region` 格式，例如：`700.HK`                      |
| count  | int32  | 是       | 请求的逐笔明细数量 <br /><br />**校验规则：**<br />请求数量最大为 `1000` |

##### Protobuf

```protobuf
message SecurityTradeRequest {
  string symbol = 1;
  int32 count = 2;
}
```

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.trades("700.HK", 10)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.trades("700.HK", 10)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name            | Type     | Description                                                                        |
| --------------- | -------- | ---------------------------------------------------------------------------------- |
| symbol          | string   | 标的代码                                                                           |
| trades          | object[] | 逐笔明细数据                                                                       |
| ∟ price         | string   | 价格                                                                               |
| ∟ volume        | int64    | 成交量                                                                             |
| ∟ timestamp     | int64    | 成交时间                                                                           |
| ∟ trade_type    | string   | [交易类型说明](#交易类型)                                                          |
| ∟ direction     | int32    | 交易方向 <br /><br />**可选值：**<br />`0` - neutral<br />`1` - down<br />`2` - up |
| ∟ trade_session | int32    | 交易时段，详见 [TradeSession](../objects#tradesession---交易时段)                  |

###### 交易类型

港股

- `*` - 场外交易
- `D` - 碎股交易
- `M` - 非自动对盘
- `P` - 开市前成交盘
- `U` - 竞价交易
- `X` - 同一券商非自动对盘
- `Y` - 同一券商自动对盘
- ` ` - 自动对盘

美股

- ` ` - 自动对盘
- `A` - 收购
- `B` - 批量交易
- `D` - 分配
- `F` - 跨市扫盘单
- `G` - 批量卖出
- `H` - 离价交易
- `I` - 碎股交易
- `K` - 第 155 条交易（纽交所规则）
- `M` - 交易所收盘价
- `P` - 前参考价
- `Q` - 交易所开盘价
- `S` - 拆单交易
- `V` - 附属交易
- `W` - 平均价成交
- `X` - 跨市场交易
- `1` - 停售股票（常规交易）

##### Protobuf

```protobuf
message SecurityTradeResponse {
  string symbol = 1;
  repeated Trade trades = 2;
}

message Trade {
  string price = 1;
  int64 volume = 2;
  int64 timestamp = 3;
  string trade_type = 4;
  int32 direction = 5;
  TradeSession trade_session = 6;
}
```

##### Response JSON Example

```json
{
  "symbol": "AAPL.US",
  "trades": [
    {
      "price": "158.760",
      "volume": 1,
      "timestamp": 1651103979,
      "trade_type": "I",
      "direction": 0,
      "trade_session": 2
    },
    {
      "price": "158.745",
      "volume": 1,
      "timestamp": 1651103985,
      "trade_type": "I",
      "direction": 0,
      "trade_session": 2
    },
    {
      "price": "158.800",
      "volume": 1,
      "timestamp": 1651103995,
      "trade_type": "I",
      "direction": 0,
      "trade_session": 2
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                         |
| ---------- | ---------- | -------------- | -------------------------------- |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败           |
| 3          | 301606     | 限流           | 降低请求频次                     |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理         |
| 7          | 301600     | 请求标的不存在 | 检查请求的 `symbol` 是否正确     |
| 7          | 301603     | 标的无行情     | 标的没有请求的行情数据           |
| 7          | 301604     | 无权限         | 没有获取标的行情的权限           |
| 7          | 301607     | 接口限制       | 请求的数据数量超限，减少数据数量 |

#### 3.7 K 线

- **Python SDK**：`QuoteContext.set_on_candlestick(...)`
- **权限/费用**：基础免费；港股高级行情或美股期权可能需要额外行情卡
- **官方页面**：[K 线](https://open.longbridge.com/zh-CN/docs/quote/push/candlestick)

已订阅标的的实时 K 线数据推送。回调在当前 K 线更新时触发（Realtime 模式）或在一根 K 线周期结束时触发（Confirmed 模式）。

:::tip

本页介绍的是**推送** API（`subscribe_candlesticks`）。如需按需拉取历史 K 线数据，请参见 [K 线 - 拉取](/quote/stocks/candlestick)。

:::

:::info

[业务指令](../../socket/protocol/push)：`105`

:::

#### 数据格式

##### Properties

| Name                | Type     | Description                                                                              |
|---------------------|----------|------------------------------------------------------------------------------------------|
| symbol              | string   | 标的代码，例如：`AAPL.US`                                                                |
| period              | int32    | K 线周期，详见 [Period](../objects#period---candlestick-period)                          |
| candlestick         | object   | K 线数据                                                                                 |
| ∟ close             | string   | 收盘价                                                                                   |
| ∟ open              | string   | 开盘价                                                                                   |
| ∟ high              | string   | 最高价                                                                                   |
| ∟ low               | string   | 最低价                                                                                   |
| ∟ volume            | int64    | 成交量                                                                                   |
| ∟ turnover          | string   | 成交额                                                                                   |
| ∟ timestamp         | int64    | K 线时间（Unix 时间戳）                                                                  |
| ∟ trade_session     | int32    | 交易时段，详见 [TradeSession](../objects#tradesession---交易时段)                        |

##### Protobuf

```protobuf
message PushCandlestick {
  string symbol = 1;
  Period period = 2;
  Candlestick candlestick = 3;
}

message Candlestick {
  string close = 1;
  string open = 2;
  string high = 3;
  string low = 4;
  int64 volume = 5;
  string turnover = 6;
  int64 timestamp = 7;
  TradeSession trade_session = 8;
}
```

##### Example

```python
from time import sleep
from longbridge.openapi import QuoteContext, Config, Period, PushCandlestick, OAuthBuilder

def on_candlestick(symbol: str, event: PushCandlestick):
    print(symbol, event)

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
ctx.set_on_candlestick(on_candlestick)

ctx.subscribe_candlesticks("700.HK", Period.Min_1)
sleep(30)
```

##### JSON Example

```json
{
  "symbol": "700.HK",
  "period": 1,
  "candlestick": {
    "close": "162.500",
    "open": "160.000",
    "high": "163.000",
    "low": "159.800",
    "volume": 123456,
    "turnover": "19987654.000",
    "timestamp": 1651103700,
    "trade_session": 0
  }
}
```

#### 3.8 实时盘口订阅

- **Python SDK**：`QuoteContext.set_on_depth(...)`
- **权限/费用**：基础免费；港股高级行情或美股期权可能需要额外行情卡
- **官方页面**：[实时盘口订阅](https://open.longbridge.com/zh-CN/docs/quote/push/depth)

已订阅标的的实时盘口数据推送。

:::info

[业务指令](../../socket/protocol/push)：`102`

:::

#### 数据格式

##### Properties

| Name        | Type     | Description               |
| ----------- | -------- | ------------------------- |
| symbol      | string   | 标的代码，例如：`AAPL.US` |
| sequence    | int64    | 序列号                    |
| ask         | object[] | 卖盘                      |
| ∟ position  | int32    | 档位                      |
| ∟ price     | string   | 价格                      |
| ∟ volume    | int64    | 挂单量                    |
| ∟ order_num | int64    | 订单数量                  |
| bid         | object[] | 买盘                      |
| ∟ position  | int32    | 档位                      |
| ∟ price     | string   | 价格                      |
| ∟ volume    | int64    | 挂单量                    |
| ∟ order_num | int64    | 订单数量                  |

##### Protobuf

```protobuf
message PushDepth {
  string symbol = 1;
  int64 sequence = 2;
  repeated Depth ask = 3;
  repeated Depth bid = 4;
}

message Depth {
  int32 position = 1;
  string price = 2;
  int64 volume = 3;
  int64 order_num = 4;
}
```

##### Example

```python
from time import sleep
from longbridge.openapi import QuoteContext, Config, SubType, PushDepth, OAuthBuilder

def on_depth(symbol: str, event: PushDepth):
    print(symbol, event)

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
ctx.set_on_depth(on_depth)

ctx.subscribe(["700.HK", "AAPL.US"], [SubType.Depth])
sleep(30)
```

##### JSON Example

```json
{
  "symbol": "700.HK",
  "sequence": 160808750000000,
  "ask": [
    {
      "position": 1,
      "price": "335.000",
      "volume": 500,
      "order_num": 1
    },
    {
      "position": 2,
      "price": "335.200",
      "volume": 400,
      "order_num": 1
    },
    {
      "position": 3,
      "price": "335.400",
      "volume": 500,
      "order_num": 2
    },
    {
      "position": 4,
      "price": "335.600",
      "volume": 1200,
      "order_num": 3
    },
    {
      "position": 5,
      "price": "335.800",
      "volume": 14000,
      "order_num": 8
    }
  ],
  "bid": [
    {
      "position": 1,
      "price": "334.800",
      "volume": 69400,
      "order_num": 13
    },
    {
      "position": 2,
      "price": "334.600",
      "volume": 266600,
      "order_num": 27
    },
    {
      "position": 3,
      "price": "334.400",
      "volume": 61300,
      "order_num": 29
    },
    {
      "position": 4,
      "price": "334.200",
      "volume": 125900,
      "order_num": 31
    },
    {
      "position": 5,
      "price": "334.000",
      "volume": 194600,
      "order_num": 94
    }
  ]
}
```

#### 3.9 实时价格订阅

- **Python SDK**：`QuoteContext.set_on_quote(...)`
- **权限/费用**：基础免费；港股高级行情或美股期权可能需要额外行情卡
- **官方页面**：[实时价格订阅](https://open.longbridge.com/zh-CN/docs/quote/push/quote)

已订阅标的的实时价格订阅，推送的数据结构中，只有有变化的字段才会填充数据。

:::info

[业务指令](../../socket/protocol/push)：`101`

:::

#### 数据格式

##### Properties

| Name             | Type   | Description                                                                           |
| ---------------- | ------ | ------------------------------------------------------------------------------------- |
| symbol           | string | 标的代码，例如：`AAPL.US`                                                             |
| sequence         | int64  | 序列号                                                                                |
| last_done        | string | 最新价                                                                                |
| open             | string | 开盘价                                                                                |
| high             | string | 最高价                                                                                |
| low              | string | 最低价                                                                                |
| timestamp        | int64  | 最新成交的时间戳                                                                      |
| volume           | int64  | 成交量                                                                                |
| turnover         | string | 成交额                                                                                |
| trade_status     | int32  | 交易状态，详见 [TradeStatus](../objects#tradestatus---交易状态)                       |
| trade_session    | int32  | 交易时段，详见 [TradeSession](../objects#tradesession---交易时段)                     |
| current_volume   | int32  | 两次推送之间增加的成交量                                                              |
| current_turnover | string | 两次推送之间增加的成交额                                                              |
| tag              | int32  | 价格数据标签 <br /><br />**可选值：**<br />`0` - 实时行情<br />`1` - 收盘后的修正数据 |

##### Protobuf

```protobuf
message PushQuote {
  string symbol = 1;
  int64 sequence = 2;
  string last_done = 3;
  string open = 4;
  string high = 5;
  string low = 6;
  int64 timestamp = 7;
  int64 volume = 8;
  string turnover = 9;
  TradeStatus trade_status = 10;
  TradeSession trade_session = 11;
}
```

##### Example

```python
from time import sleep
from longbridge.openapi import QuoteContext, Config, SubType, PushQuote, OAuthBuilder

def on_quote(symbol: str, event: PushQuote):
    print(symbol, event)

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
ctx.set_on_quote(on_quote)

ctx.subscribe(["700.HK", "AAPL.US"], [SubType.Quote])
sleep(30)
```

##### JSON Example

```json
{
  "symbol": "AAPL.US",
  "sequence": 160808750000000,
  "last_done": "156.570",
  "open": "155.910",
  "high": "159.790",
  "low": "155.380",
  "timestamp": 1651089600,
  "volume": 88063191,
  "turnover": "13865092584.000",
  "trade_status": 0,
  "trade_session": 0,
  "current_volume": 111234,
  "current_turnover": "23234343454.000",
  "tag": 0
}
```

#### 3.10 实时成交明细订阅

- **Python SDK**：`QuoteContext.set_on_trades(...)`
- **权限/费用**：基础免费；港股高级行情或美股期权可能需要额外行情卡
- **官方页面**：[实时成交明细订阅](https://open.longbridge.com/zh-CN/docs/quote/push/trade)

已订阅的标的的实时逐笔成交明细推送。

:::info

[业务指令](../../socket/protocol/push)：`104`

:::

#### 数据格式

##### Properties

| Name            | Type     | Description                                                                        |
| --------------- | -------- | ---------------------------------------------------------------------------------- |
| symbol          | string   | 标的代码，例如：`AAPL.US`                                                          |
| sequence        | int64    | 序列号                                                                             |
| trades          | object[] | 逐笔明细数据                                                                       |
| ∟ price         | string   | 价格                                                                               |
| ∟ volume        | int64    | 成交量                                                                             |
| ∟ timestamp     | int64    | 成交时间                                                                           |
| ∟ trade_type    | string   | [交易类型说明](#交易类型)                                                          |
| ∟ direction     | int32    | 交易方向 <br /><br />**可选值：**<br />`0` - neutral<br />`1` - down<br />`2` - up |
| ∟ trade_session | int32    | 交易时段，详见 [TradeSession](../objects#tradesession---交易时段)                  |

###### 交易类型

港股

- `*` - 场外交易
- `D` - 碎股交易
- `M` - 非自动对盘
- `P` - 开市前成交盘
- `U` - 竞价交易
- `X` - 同一券商非自动对盘
- `Y` - 同一券商自动对盘
- ` ` - 自动对盘

美股

- ` ` - 自动对盘
- `A` - 收购
- `B` - 批量交易
- `D` - 分配
- `F` - 跨市扫盘单
- `G` - 批量卖出
- `H` - 离价交易
- `I` - 碎股交易
- `K` - 第 155 条交易（纽交所规则）
- `M` - 交易所收盘价
- `P` - 前参考价
- `Q` - 交易所开盘价
- `S` - 拆单交易
- `V` - 附属交易
- `W` - 平均价成交
- `X` - 跨市场交易
- `1` - 停售股票（常规交易）

##### Protobuf

```protobuf
message PushTrade {
  string symbol = 1;
  int64 sequence = 2;
  repeated Trade trade = 3;
}

message Trade {
  string price = 1;
  int64 volume = 2;
  int64 timestamp = 3;
  string trade_type = 4;
  int32 direction = 5;
  TradeSession trade_session = 6;
}
```

##### Example

```python
from time import sleep
from longbridge.openapi import QuoteContext, Config, SubType, PushTrades, OAuthBuilder

def on_trades(symbol: str, event: PushTrades):
    print(symbol, event)

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
ctx.set_on_trades(on_trades)

ctx.subscribe(["700.HK", "AAPL.US"], [SubType.Trade])
sleep(30)
```

##### JSON Example

```json
{
  "symbol": "700.HK",
  "sequence": 160808750000000,
  "trades": [
    {
      "price": "158.760",
      "volume": 1,
      "timestamp": 1651103979,
      "trade_type": "I",
      "direction": 0,
      "trade_session": 2
    },
    {
      "price": "158.745",
      "volume": 1,
      "timestamp": 1651103985,
      "trade_type": "I",
      "direction": 0,
      "trade_session": 2
    },
    {
      "price": "158.800",
      "volume": 1,
      "timestamp": 1651103995,
      "trade_type": "I",
      "direction": 0,
      "trade_session": 2
    }
  ]
}
```


## 7. Fundamental（基本面）

官方当前开发者文档未标注额外数据卡收费；接口仍需有效 OpenAPI/账户权限。

### 1. 免费/基础权限

| 接口 | Python SDK | 权限/费用 |
| --- | --- | --- |
| [业务分部（当前期）](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/business-segments) | FundamentalContext.business_segments(...) | 免费/基础 |
| [业务分部（历史趋势）](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/business-segments-history) | FundamentalContext.business_segments_history(...) | 免费/基础 |
| [回购数据](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/buyback) | FundamentalContext.buyback(...) | 免费/基础 |
| [公司概况](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/company-profile) | FundamentalContext.company_profile(...) | 免费/基础 |
| [机构共识](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/consensus) | FundamentalContext.consensus(...) | 免费/基础 |
| [公司行动](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/corporate-actions) | FundamentalContext.corporate_actions(...) | 免费/基础 |
| [分红详情](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/dividend-detail) | FundamentalContext.dividend_detail(...) | 免费/基础 |
| [分红历史](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/dividends) | FundamentalContext.dividends(...) | 免费/基础 |
| [高管团队](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/executives) | FundamentalContext.executives(...) | 免费/基础 |
| [财务报告](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/financial-report) | FundamentalContext.financial_report(...) | 免费/基础 |
| [财报快照（AI 摘要 + 预测对比）](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/financial-report-snapshot) | FundamentalContext.financial_report_snapshot(...) | 免费/基础 |
| [EPS 预测](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/forecast-eps) | FundamentalContext.forecast_eps(...) | 免费/基础 |
| [基金持仓](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/fund-holdings) | FundamentalContext.fund_holdings(...) | 免费/基础 |
| [行业子板块层级树](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/industry-peers) | FundamentalContext.industry_peers(...) | 免费/基础 |
| [行业排行榜](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/industry-rank) | FundamentalContext.industry_rank(...) | 免费/基础 |
| [行业估值对比](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/industry-valuation) | FundamentalContext.industry_valuation(...) | 免费/基础 |
| [行业估值分布](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/industry-valuation-dist) | FundamentalContext.industry_valuation_dist(...) | 免费/基础 |
| [机构评级](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/institution-rating) | FundamentalContext.institution_rating(...) | 免费/基础 |
| [机构评级详情](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/institution-rating-detail) | FundamentalContext.institution_rating_detail(...) | 免费/基础 |
| [机构评级分布时间线](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/institution-rating-views) | FundamentalContext.institution_rating_views(...) | 免费/基础 |
| [投资关系](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/invest-relation) | FundamentalContext.invest_relation(...) | 免费/基础 |
| [宏观经济指标列表](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/macroeconomic-indicators) | FundamentalContext.macroeconomic_indicators(...) | 免费/基础 |
| [宏观经济历史数据](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/macroeconomic) | FundamentalContext.macroeconomic(...) | 免费/基础 |
| [经营数据](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/operating) | FundamentalContext.operating(...) | 免费/基础 |
| [分析师评级](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/ratings) | FundamentalContext.ratings(...) | 免费/基础 |
| [股东持仓详情](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/shareholder-detail) | FundamentalContext.shareholder_detail(...) | 免费/基础 |
| [大股东排行](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/shareholder-top) | FundamentalContext.shareholder_top(...) | 免费/基础 |
| [主要股东](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/shareholders) | FundamentalContext.shareholders(...) | 免费/基础 |
| [美股分析师一致预期](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_analyst_consensus) | FundamentalContext.us_analyst_consensus(...) | 免费/基础 |
| [美股公司分红](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_company_dividends) | FundamentalContext.us_company_dividends(...) | 免费/基础 |
| [美股公司概览](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_company_overview) | FundamentalContext.us_company_overview(...) | 免费/基础 |
| [美股 ETF 分红信息](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_etf_dividend_info) | FundamentalContext.us_etf_dividend_info(...) | 免费/基础 |
| [美股 ETF 文件](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_etf_files) | FundamentalContext.us_etf_files(...) | 免费/基础 |
| [美股财务概览](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_financial_overview) | FundamentalContext.us_financial_overview(...) | 免费/基础 |
| [美股财务报表](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_financial_statement) | FundamentalContext.us_financial_statement(...) | 免费/基础 |
| [美股关键财务指标](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_key_financial_metrics) | FundamentalContext.us_key_financial_metrics(...) | 免费/基础 |
| [美股估值概览](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_valuation_overview) | FundamentalContext.us_valuation_overview(...) | 免费/基础 |
| [多股估值对比](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/valuation-comparison) | FundamentalContext.valuation_comparison(...) | 免费/基础 |
| [估值历史](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/valuation-history) | FundamentalContext.valuation_history(...) | 免费/基础 |
| [估值指标](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/valuations) | FundamentalContext.valuations(...) | 免费/基础 |
| [A/H 溢价](https://open.longbridge.com/zh-CN/docs/fundamental/market/ah-premium) | MarketContext.ah_premium(...) | 免费/基础 |
| [A/H 溢价盘中数据](https://open.longbridge.com/zh-CN/docs/fundamental/market/ah-premium-intraday) | MarketContext.ah_premium_intraday(...) | 免费/基础 |
| [经纪商每日持仓历史](https://open.longbridge.com/zh-CN/docs/fundamental/market/broker-holding-daily) | MarketContext.broker_holding_daily(...) | 免费/基础 |
| [经纪商持仓详情](https://open.longbridge.com/zh-CN/docs/fundamental/market/broker-holding-detail) | MarketContext.broker_holding_detail(...) | 免费/基础 |
| [经纪商持仓](https://open.longbridge.com/zh-CN/docs/fundamental/market/broker-positions) | MarketContext.broker_positions(...) | 免费/基础 |
| [指数成分股](https://open.longbridge.com/zh-CN/docs/fundamental/market/index-components) | MarketContext.index_components(...) | 免费/基础 |
| [成交统计](https://open.longbridge.com/zh-CN/docs/fundamental/market/trading-stats) | MarketContext.trading_stats(...) | 免费/基础 |

#### 1.1 业务分部（当前期）

- **Python SDK**：`FundamentalContext.business_segments(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[业务分部（当前期）](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/business-segments)

获取上市公司当前报告期的业务分部收入占比。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.business_segments("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.business_segments("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "20260331",
    "total": "124300000000",
    "currency": "USD",
    "business": [
      {"name": "iPhone", "percent": "56.19"},
      {"name": "Services", "percent": "21.96"},
      {"name": "Mac", "percent": "8.04"},
      {"name": "iPad", "percent": "7.00"},
      {"name": "Wearables", "percent": "6.81"}
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [BusinessSegmentsResponse](#BusinessSegmentsResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### BusinessSegmentsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 否 | 报告期，格式 YYYYMMDD，例如 `20260331` |
| total | string | 否 | 当期总收入 |
| currency | string | 否 | 货币代码，例如 `USD` |
| business | object[] | 否 | 业务分部列表 |
| ∟ name | string | 否 | 业务分部名称 |
| ∟ percent | string | 否 | 收入占比（百分比，例如 `40.56`） |

#### 1.2 业务分部（历史趋势）

- **Python SDK**：`FundamentalContext.business_segments_history(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[业务分部（历史趋势）](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/business-segments-history)

获取上市公司按报告期的历史业务分部收入趋势。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |
| report | string | 否 | 报告类型：`qf`（季报）/ `saf`（半年报）/ `af`（年报） |
| cate | string | 否 | 分部类别过滤 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.business_segments_history("AAPL.US", report="qf")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.business_segments_history("AAPL.US", report="qf")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "historical": [
      {
        "date": "20260331",
        "total": "124300000000",
        "currency": "USD",
        "business": [
          {"name": "美洲", "percent": "40.80", "value": "31968000000"},
          {"name": "欧洲", "percent": "23.64", "value": "18521000000"},
          {"name": "大中华区", "percent": "20.72", "value": "16233000000"}
        ],
        "regionals": []
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [BusinessSegmentsHistoryResponse](#BusinessSegmentsHistoryResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### BusinessSegmentsHistoryResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| historical | object[] | 否 | 历史报告期列表 |
| ∟ date | string | 否 | 报告期，格式 YYYYMMDD，例如 `20260331` |
| ∟ total | string | 否 | 当期总收入 |
| ∟ currency | string | 否 | 货币代码 |
| ∟ business | object[] | 否 | 业务分部列表 |
| ∟ ∟ name | string | 否 | 业务分部名称 |
| ∟ ∟ percent | string | 否 | 收入占比（百分比，例如 `40.80`） |
| ∟ ∟ value | string | 否 | 绝对收入数值 |
| ∟ regionals | object[] | 否 | 地区分部列表（当前通常为空数组） |
| ∟ ∟ name | string | 否 | 地区名称 |
| ∟ ∟ percent | string | 否 | 收入占比（百分比） |
| ∟ ∟ value | string | 否 | 绝对收入数值 |

#### 1.3 回购数据

- **Python SDK**：`FundamentalContext.buyback(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[回购数据](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/buyback)

获取股票回购数据，包括历史回购金额及回购比例。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.buyback("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.buyback("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "buyback_history": [
      {
        "fiscal_year": "FY2024",
        "fiscal_year_range": "2024-01-01~2024-12-31",
        "net_buyback": "94949000000",
        "net_buyback_yield": "0.0241",
        "net_buyback_growth_rate": "-0.1233"
      }
    ],
    "buyback_ratios": [
      {
        "net_buyback_payout_ratio": "0.9502",
        "net_buyback_to_cashflow_ratio": "0.8821"
      }
    ],
    "recent_buybacks": {
      "currency": "USD",
      "net_buyback_ttm": "94949000000",
      "net_buyback_yield_ttm": "0.0241"
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [BuybackDataResponse](#BuybackDataResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### BuybackDataResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| buyback_history | object[] | 否 | 年度回购历史，见 [BuybackHistoryItem](#BuybackHistoryItem) |
| buyback_ratios | object[] | 否 | 回购比率历史，见 [BuybackRatios](#BuybackRatios) |
| recent_buybacks | object | 否 | 近 12 个月回购汇总 |

##### BuybackHistoryItem

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| fiscal_year | string | 否 | 财年 |
| fiscal_year_range | string | 否 | 财年日期区间 |
| currency | string | 否 | 货币 |
| net_buyback | string | 否 | 净回购金额 |
| net_buyback_growth_rate | string | 否 | 回购增长率 |
| net_buyback_yield | string | 否 | 回购收益率 |

##### BuybackRatios

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| net_buyback_payout_ratio | string | 否 | 回购支付比率 |
| net_buyback_to_cashflow_ratio | string | 否 | 回购占自由现金流比率 |

##### RecentBuybacks

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| currency | string | 否 | 货币 |
| net_buyback_ttm | string | 否 | 净回购金额（近 12 个月） |
| net_buyback_yield_ttm | string | 否 | 回购收益率（近 12 个月） |

#### 1.4 公司概况

- **Python SDK**：`FundamentalContext.company_profile(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[公司概况](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/company-profile)

获取公司基本资料，包括成立年份、员工人数、总部地址和业务描述。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.company_profile("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.company_profile("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "company_name": "Apple Inc.",
    "name": "Apple",
    "ticker": "AAPL",
    "market": "NasdaqGS",
    "founded": "1976",
    "employees": "166000",
    "manager": "Timothy D. Cook",
    "website": "www.apple.com",
    "phone": "(408) 996-1010",
    "address": "One Apple Park Way, Cupertino, California, United States",
    "profile": "Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, a...",
    "region": "US",
    "sector": 0,
    "year_end": "September 27",
    "icon": "https://assets.lbkrs.com/ticker/ST/US/AAPL.png"
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [CompanyProfileResponse](#CompanyProfileResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### CompanyProfileResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| name | string | 否 | 中文名称 |
| company_name | string | 否 | 完整公司名称 |
| ticker | string | 否 | 股票代码 |
| market | string | 否 | 上市交易所 |
| sector | integer | 否 | 行业 |
| category | string | 否 | 公司类别 |
| founded | string | 否 | 成立年份 |
| listing_date | string | 否 | 上市日期 |
| employees | string | 否 | 员工人数 |
| chairman | string | 否 | 董事长 |
| manager | string | 否 | CEO / 总经理 |
| secretary | string | 否 | 公司秘书 |
| address | string | 否 | 注册地址 |
| office_address | string | 否 | 办公地址 |
| email | string | 否 | 联系邮箱 |
| website | string | 否 | 公司官网 |
| profile | string | 否 | 业务描述 |
| icon | string | 否 | 股票图标 URL |
| region | string | 否 | 地区 |
| shares_offered | string | 否 | 发行总股数 |
| issue_price | string | 否 | 发行价格 |
| year_end | string | 否 | 财年截止日 |
| zip_code | string | 否 | 邮政编码 |
| phone | string | 否 | 电话号码 |
| fax | string | 否 | 传真 |
| legal_repr | string | 否 | 法定代表人 |
| legal_counsel | string | 否 | 法律顾问 |
| accounting_firm | string | 否 | 会计师事务所 |
| audit_inst | string | 否 | 审计机构 |
| securities_rep | string | 否 | 证券代表 |
| bus_license | string | 否 | 营业执照号 |
| ads_ratio | string | 否 | ADS 比例 |

#### 1.5 机构共识

- **Python SDK**：`FundamentalContext.consensus(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[机构共识](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/consensus)

获取机构共识预测，包括营收、EPS 和净利润预测。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `TSLA.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.consensus("TSLA.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.consensus("TSLA.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "currency": "USD",
    "current_index": 3,
    "current_period": "qf",
    "opt_periods": [
      "qf",
      "af",
      "saf"
    ],
    "list": [
      {
        "fiscal_year": 2026,
        "fiscal_period": "Q2 FY2026",
        "period_text": "Q2 FY2026",
        "details": [
          {
            "key": "revenue",
            "name": "Revenue",
            "estimate": "95000000000",
            "actual": "",
            "comp": "",
            "comp_value": null,
            "comp_desc": "",
            "description": "",
            "is_released": false
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [FinancialConsensus](#FinancialConsensus) |
| 400    | 请求错误    | None   |

#### Schemas

##### FinancialConsensus

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码 |
| list | object[] | 是 | 共识预测期列表，见 [ConsensusListItem](#ConsensusListItem) |
| list[].period | string | 否 | 财报期（如 FY2024） |
| list[].revenue | int64 | 否 | 共识营收预测 |
| list[].eps | double | 否 | 共识 EPS 预测 |
| list[].net_income | int64 | 否 | 共识净利润预测 |
| list[].analyst_count | int32 | 否 | 参与预测的分析师数量 |

#### 1.6 公司行动

- **Python SDK**：`FundamentalContext.corporate_actions(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[公司行动](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/corporate-actions)

获取指定证券的公司行动历史，包括拆股、合并、分拆和配股等。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |
| start_date | string | 否 | 开始日期，格式 `YYYY-MM-DD` |
| end_date | string | 否 | 结束日期，格式 `YYYY-MM-DD` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.corporate_actions("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.corporate_actions("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "622620",
        "action": "DividendExDate",
        "act_type": "Distribution Plan",
        "act_desc": "Cash dividend 0.27 USD",
        "date": "20260514",
        "date_str": "05.14",
        "date_type": "Payment Date",
        "date_zone": "EST",
        "delay_content": "",
        "is_delay": false,
        "recent": false,
        "live": null
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [CorporateActionsResponse](#CorporateActionsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### CorporateActionsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| items | object[] | true | 公司行动列表， |
| ∟ id | string | false | 行动 ID |
| ∟ act_desc | string | false | 行动描述 |
| ∟ act_type | string | false | 行动类型分类 |
| ∟ action | string | false | 行动代码（如 `DividendExDate`） |
| ∟ date | string | false | 生效日期 |
| ∟ date_str | string | false | 简短展示日期（MM.DD） |
| ∟ date_type | string | false | 日期类型标签（如 Payment Date） |
| ∟ date_zone | string | false | 时区（如 EST） |
| ∟ delay_content | string | false | 延迟内容描述 |
| ∟ is_delay | boolean | false | 是否延迟 |
| ∟ live | boolean | false | 是否实时 |
| ∟ recent | boolean | false | 是否为近期事件 |

#### 1.7 分红详情

- **Python SDK**：`FundamentalContext.dividend_detail(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[分红详情](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/dividend-detail)

获取详细分红信息，包括宣告日、除息日和派发日。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.dividend_detail("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.dividend_detail("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "id": "12345",
        "symbol": "AAPL.US",
        "ex_date": "2026-02-07",
        "payment_date": "2026-02-13",
        "record_date": "2026-02-10",
        "desc": "Cash dividend 0.25 USD"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [DividendList](#DividendList) |
| 400    | 请求错误    | None   |

#### Schemas

##### DividendList

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| list | object[] | true | 分红记录列表，见 [DividendItem](#DividendItem) |
| ∟ id | string | false | Dividend event ID |
| ∟ symbol | string | false | Security symbol |
| ∟ desc | string | false | Dividend description |
| ∟ ex_date | string | false | Ex-dividend date (YYYY-MM-DD) |
| ∟ record_date | string | false | Record date (YYYY-MM-DD) |
| ∟ payment_date | string | false | Payment date (YYYY-MM-DD) |

#### 1.8 分红历史

- **Python SDK**：`FundamentalContext.dividends(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[分红历史](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/dividends)

获取指定证券的分红历史及即将公布的分红信息。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |
| start_date | string | 否 | 开始日期，格式 `YYYY-MM-DD` |
| end_date | string | 否 | 结束日期，格式 `YYYY-MM-DD` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.dividends("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.dividends("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "id": "12345",
        "symbol": "AAPL.US",
        "ex_date": "2026-02-07",
        "payment_date": "2026-02-13",
        "record_date": "2026-02-10",
        "desc": "Cash dividend 0.25 USD"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [DividendsResponse](#DividendsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### DividendsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| list | object[] | true | 分红记录列表，见 [DividendItem](#DividendItem) |
| ∟ id | string | false | Dividend event ID |
| ∟ symbol | string | false | Security symbol |
| ∟ desc | string | false | Dividend description |
| ∟ ex_date | string | false | 除息日 |
| ∟ payment_date | string | false | Payment date |
| ∟ record_date | string | false | Record date |

#### 1.9 高管团队

- **Python SDK**：`FundamentalContext.executives(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[高管团队](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/executives)

获取公司关键高管列表（CEO、CFO 等）。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.executives("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.executives("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "professional_list": [
      {
        "forward_url": "https://longbridge.com/wiki/stocks/ST.US.AAPL#company-manager",
        "professionals": [
          {
            "biography": "Tim Cook is the CEO of Apple Inc.",
            "id": "12345",
            "name": "Timothy D. Cook",
            "name_en": "Timothy D. Cook",
            "name_zhcn": "蒂姆·库克",
            "photo": "https://cdn.example.com/timcook.jpg",
            "title": "Chief Executive Officer",
            "wiki_url": "https://en.wikipedia.org/wiki/Tim_Cook"
          }
        ],
        "symbol": "AAPL.US",
        "total": 9
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [ExecutiveResponse](#ExecutiveResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### ExecutiveResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| professional_list | object[] | 是 | 高管分组列表，见 [ExecutiveGroup](#ExecutiveGroup) |

##### ExecutiveGroup

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码 |
| forward_url | string | 否 | 公司高管页面链接 |
| total | integer | 否 | 高管总数 |
| professionals | object[] | 是 | 高管列表，见 [Executive](#Executive) |

##### Executive

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | 否 | 高管 ID |
| name | string | 是 | 显示名称 |
| name_en | string | 否 | 英文名称 |
| name_zhcn | string | 否 | 中文名称 |
| title | string | 否 | 职位 |
| biography | string | 否 | 简历 |
| photo | string | 否 | 照片链接 |
| wiki_url | string | 否 | 维基百科链接 |

#### 1.10 财务报告

- **Python SDK**：`FundamentalContext.financial_report(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[财务报告](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/financial-report)

获取任意上市公司的利润表、资产负债表和现金流量表。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |
| kind | string | 是 | 报表类型：`IncomeStatement`（利润表）、`BalanceSheet`（资产负债表）、`CashFlow`（现金流量表）、`All`（全部） |
| period | string | 是 | 报告期：`Annual`（年报）、`SemiAnnual`（中报）、`Q1`/`Q2`/`Q3`/`ThreeQ`（季报）、`QuarterlyFull`（累计季报） |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.financial_report("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.financial_report("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": {
      "IS": {
        "indicators": [
          {
            "title": "Income Statement",
            "short_title": "IS",
            "currency": "USD",
            "has_yoy": true,
            "entry": "IS",
            "periods": [
              "FY2025",
              "FY2024"
            ],
            "accounts": [
              {
                "field": "EPS",
                "name": "Earnings Per Share(USD)",
                "percent": false,
                "tip": "",
                "values": [
                  {
                    "period": "FY 2025",
                    "year": 2025,
                    "fp_end": "1758945600",
                    "value": "7.46",
                    "ratio": "",
                    "yoy": "0.227"
                  }
                ]
              }
            ]
          }
        ]
      }
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [FinancialReportsResponse](#FinancialReportsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### FinancialReportsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| list | object | true | 按报表类型分组的数据（key 为报表类型代码，如 `IS`、`BS`、`CF`） |

##### FinancialReportIndicator

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| title | string | false | 指标标题 |
| short_title | string | false | 短标题 |
| currency | string | false | 货币 |
| has_yoy | boolean | false | 是否有同比数据 |
| entry | string | false | 条目标识符 |
| periods | string[] | false | 可用报告期列表 |
| accounts | object[] | false | 财务科目列表，见 [FinancialAccount](#FinancialAccount) |

##### FinancialAccount

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| field | string | true | 字段标识符 |
| name | string | false | 字段显示名称 |
| percent | boolean | false | 是否为百分比值 |
| tip | string | false | 提示说明 |
| values | object[] | false | 按报告期的历史数值，见 [FinancialValue](#FinancialValue) |

##### FinancialValue

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| period | string | true | 报告期标签（如 `FY 2024`） |
| year | integer | false | 财政年度 |
| fp_end | string | false | 报告期结束时间戳 |
| value | string | false | 报告值 |
| ratio | string | false | 比率值 |
| yoy | string | false | 同比增长率 |

#### 1.11 财报快照（AI 摘要 + 预测对比）

- **Python SDK**：`FundamentalContext.financial_report_snapshot(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[财报快照（AI 摘要 + 预测对比）](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/financial-report-snapshot)

获取 AI 生成的财报摘要、营收/EBIT/EPS 预测对比（超预期/低于预期），以及关键财务指标。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |
| report | string | 否 | 报告类型：`qf`（季报）/ `saf`（半年报）/ `af`（年报） |
| fiscal_year | uint32 | 否 | 财政年度，例如 `2024` |
| fiscal_period | string | 否 | 财政季度，例如 `1` / `2` / `3` / `4` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.financial_report_snapshot("AAPL.US", report="qf", fiscal_year=2024, fiscal_period="4")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.financial_report_snapshot("AAPL.US", report="qf", fiscal_year=2024, fiscal_period="4")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "name": "苹果",
    "ticker": "AAPL",
    "fp_start": "2025.12.28",
    "fp_end": "2026.03.28",
    "currency": "USD",
    "report_desc": "概要：苹果（AAPL）的营业收入是 1112 亿（+16.6%）；每股收益是 2.01（+21.82%）。",
    "fo_revenue": {"value": "111184000000.0000", "yoy": "16.6", "cmp_desc": "", "est_value": ""},
    "fo_ebit": {"value": "35885000000.0000", "yoy": "21.28", "cmp_desc": "", "est_value": ""},
    "fo_eps": {"value": "2.0100", "yoy": "21.82", "cmp_desc": "", "est_value": ""},
    "fr_revenue": {"value": "111184000000.0000", "yoy": "16.6"},
    "fr_profit": {"value": "29578000000.0000", "yoy": "19.36"},
    "fr_roe_ttm": "141.4705",
    "fr_profit_margin": "26.6027",
    "fr_debt_assets_ratio": "71.3025"
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [FinancialReportSnapshotResponse](#FinancialReportSnapshotResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### FinancialReportSnapshotResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| name | string | 否 | 公司名称 |
| ticker | string | 否 | 证券代码（不含市场后缀，例如 `AAPL`） |
| fp_start | string | 否 | 财政期开始日期，格式 `YYYY.MM.DD` |
| fp_end | string | 否 | 财政期结束日期，格式 `YYYY.MM.DD` |
| currency | string | 否 | 货币代码 |
| report_desc | string | 否 | AI 生成的财报摘要 |
| fo_revenue | object | 否 | 营收预测对比，见 [ForecastMetric](#ForecastMetric) |
| fo_ebit | object | 否 | EBIT 预测对比，见 [ForecastMetric](#ForecastMetric) |
| fo_eps | object | 否 | EPS 预测对比，见 [ForecastMetric](#ForecastMetric) |
| fr_revenue | object | 否 | 营收财务数据，见 [ReportedMetric](#ReportedMetric) |
| fr_profit | object | 否 | 净利润财务数据，见 [ReportedMetric](#ReportedMetric) |
| fr_operate_cash | object | 否 | 经营现金流，见 [ReportedMetric](#ReportedMetric) |
| fr_invest_cash | object | 否 | 投资现金流，见 [ReportedMetric](#ReportedMetric) |
| fr_finance_cash | object | 否 | 融资现金流，见 [ReportedMetric](#ReportedMetric) |
| fr_total_assets | object | 否 | 总资产，见 [ReportedMetric](#ReportedMetric) |
| fr_total_liability | object | 否 | 总负债，见 [ReportedMetric](#ReportedMetric) |
| fr_roe_ttm | string | 否 | 净资产收益率 TTM（百分比，例如 `141.47`） |
| fr_profit_margin | string | 否 | 净利率（百分比） |
| fr_profit_margin_ttm | string | 否 | 净利率 TTM（百分比） |
| fr_asset_turn_ttm | string | 否 | 资产周转率 TTM（百分比） |
| fr_leverage_ttm | string | 否 | 杠杆率 TTM（百分比） |
| fr_debt_assets_ratio | string | 否 | 资产负债率（百分比） |

##### ForecastMetric

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| value | string | 否 | 实际值 |
| yoy | string | 否 | 同比增速（百分比，例如 `16.6`） |
| cmp_desc | string | 否 | 超预期/低于预期描述（可能为空） |
| est_value | string | 否 | 一致预期值（可能为空） |

##### ReportedMetric

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| value | string | 否 | 数值 |
| yoy | string | 否 | 同比增速（百分比） |

#### 1.12 EPS 预测

- **Python SDK**：`FundamentalContext.forecast_eps(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[EPS 预测](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/forecast-eps)

获取 EPS 预测及分析师共识估值。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `TSLA.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.forecast_eps("TSLA.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.forecast_eps("TSLA.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "forecast_end_date": "1727827200",
        "forecast_eps_highest": "3.71",
        "forecast_eps_lowest": "2.37",
        "forecast_eps_mean": "2.998",
        "forecast_eps_median": "3.02",
        "forecast_start_date": "1727827200",
        "institution_down": 0,
        "institution_total": 0,
        "institution_up": 0
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ForecastEps](#ForecastEps) |
| 400    | 请求错误    | None   |

#### Schemas

##### ForecastEps

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| items | object[] | true | List of EPS forecast periods |
| ∟ forecast_start_date | string | false | Forecast period start date |
| ∟ forecast_end_date | string | false | Forecast period end date |
| ∟ forecast_eps_mean | string | false | Mean EPS estimate |
| ∟ forecast_eps_median | string | false | Median EPS estimate |
| ∟ forecast_eps_highest | string | false | Highest EPS estimate |
| ∟ forecast_eps_lowest | string | false | Lowest EPS estimate |
| ∟ institution_total | integer | false | Total contributing institutions |
| ∟ institution_up | integer | false | Institutions revising up |
| ∟ institution_down | integer | false | Institutions revising down |

#### 1.13 基金持仓

- **Python SDK**：`FundamentalContext.fund_holdings(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[基金持仓](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/fund-holdings)

获取持有指定证券的基金列表，含持股数量和持股比例。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.fund_holdings("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.fund_holdings("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "lists": [
      {
        "symbol": "TSLT.US",
        "code": "TSLT",
        "name": "2x Long TSLA ETF",
        "position_ratio": "101.02",
        "report_date": "2026-05-07",
        "currency": "USD"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [FundHoldersResponse](#FundHoldersResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### FundHoldersResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| lists | object[] | 是 | 基金持仓列表， |
| ∟ symbol | string | 是 | 基金代码（含市场后缀） |
| ∟ code | string | 否 | 基金简码 |
| ∟ name | string | 否 | 基金名称 |
| ∟ position_ratio | string | 否 | 持仓占比（%） |
| ∟ report_date | string | 否 | 报告日期 |
| ∟ currency | string | 否 | 货币 |

#### 1.14 行业子板块层级树

- **Python SDK**：`FundamentalContext.industry_peers(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[行业子板块层级树](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/industry-peers)

获取行业分组的层级子板块树，含各节点股票数量、日涨跌幅和年初至今涨跌幅。Counter ID 可从 `industry_rank` 返回结果中获取。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| counter_id | string | 是 | 行业唯一标识（BK/市场/ID 格式），来源于 `industry_rank` |
| market | string | 是 | 市场代码：`US` / `HK` / `CN` / `SG` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.industry_peers("BK/US/IN00258", "US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.industry_peers("BK/US/IN00258", "US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "top": {"name": "All Industries", "market": "US"},
    "chain": {
      "name": "Technology",
      "counter_id": "BK/US/IN00258",
      "stock_num": 542,
      "chg": "0.0231",
      "ytd_chg": "0.0875",
      "next": [
        {
          "name": "在线消费电子产品零售",
          "counter_id": "",
          "stock_num": 4,
          "chg": "0.0268",
          "ytd_chg": "-0.1869",
          "next": []
        }
      ]
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [IndustryPeersResponse](#IndustryPeersResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### IndustryPeersResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| top | object | 否 | 顶层行业信息，见 [IndustryPeersTop](#IndustryPeersTop) |
| chain | object | 否 | 行业层级树根节点，见 [IndustryPeerNode](#IndustryPeerNode) |

##### IndustryPeersTop

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| name | string | 否 | 顶层行业名称 |
| market | string | 否 | 市场代码 |

##### IndustryPeerNode

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| name | string | 否 | 板块名称 |
| counter_id | string | 否 | 板块唯一标识（根节点有值，子节点为空字符串） |
| stock_num | integer | 否 | 板块内股票数量 |
| chg | string | 否 | 当日涨跌幅（小数，可能为空字符串） |
| ytd_chg | string | 否 | 年初至今涨跌幅（小数，可能为空字符串） |
| next | object[] | 否 | 子板块列表，结构与当前节点相同（递归） |

#### 1.15 行业排行榜

- **Python SDK**：`FundamentalContext.industry_rank(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[行业排行榜](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/industry-rank)

按市场和指标获取行业排行榜。返回的 Counter ID 可直接传入 `industry_peers` 查询子行业树。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| market | string | 是 | 市场代码：`US` / `HK` / `CN` / `SG` |
| indicator | string | 是 | 排行指标：`leading-gainer` / `today-trend` / `popularity` / `market-cap` / `revenue` / `revenue-growth` / `net-profit` / `net-profit-growth` |
| sort_type | string | 是 | 排序方式：`single`（单一排序）/ `multi`（多维排序） |
| limit | uint32 | 是 | 返回条数，默认 20 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.industry_rank("US", "leading-gainer", "single", 20)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.industry_rank("US", "leading-gainer", "single", 20)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "lists": [
          {
            "name": "Technology",
            "counter_id": "BK/US/IN00258",
            "chg": "0.0231",
            "leading_name": "NVIDIA",
            "leading_ticker": "NVDA.US",
            "leading_chg": "0.0512",
            "value_name": "",
            "value_data": ""
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [IndustryRankResponse](#IndustryRankResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### IndustryRankResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| items | object[] | 否 | 排行分组列表 |
| ∟ lists | object[] | 否 | 行业条目列表 |
| ∟ ∟ name | string | 否 | 行业名称 |
| ∟ ∟ counter_id | string | 否 | 行业唯一标识（`BK/市场/ID` 格式），可直接传入 `industry_peers` |
| ∟ ∟ chg | string | 否 | 当日涨跌幅（小数） |
| ∟ ∟ leading_name | string | 否 | 涨幅领先个股名称 |
| ∟ ∟ leading_ticker | string | 否 | 涨幅领先个股代码 |
| ∟ ∟ leading_chg | string | 否 | 涨幅领先个股涨跌幅（小数） |
| ∟ ∟ value_name | string | 否 | 指标名称（按指标类型填充，可能为空） |
| ∟ ∟ value_data | string | 否 | 指标数值（可能为空） |

#### 1.16 行业估值对比

- **Python SDK**：`FundamentalContext.industry_valuation(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[行业估值对比](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/industry-valuation)

获取同行业内的同类公司估值对比数据。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `TSLA.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.industry_valuation("TSLA.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.industry_valuation("TSLA.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "symbol": "AAPL.US",
        "name": "Apple Inc.",
        "market": "US",
        "currency": "USD",
        "pe": "28.50",
        "pb": "45.2",
        "ps": "7.8",
        "eps": "6.08",
        "bps": "4.50"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [IndustryValuationList](#IndustryValuationList) |
| 400    | 请求错误    | None   |

#### Schemas

##### IndustryValuationList

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| list | object[] | true | 同行公司列表，见 [IndustryValuationItem](#IndustryValuationItem) |
| ∟ symbol | string | false | 证券代码 |
| ∟ name | string | false | Company name |
| ∟ currency | string | false | Reporting currency |
| ∟ pe | string | false | Price-to-Earnings ratio |
| ∟ bps | string | false | Book value per share |
| ∟ eps | string | false | Earnings per share |
| ∟ dps | string | false | Dividends per share |
| ∟ div_yld | string | false | Dividend yield |
| ∟ div_payout_ratio | string | false | Dividend payout ratio |
| ∟ five_y_avg_dps | string | false | 5-year average DPS |
| ∟ assets | string | false | Total assets |
| ∟ history | object[] | false | Historical valuation data |

#### 1.17 行业估值分布

- **Python SDK**：`FundamentalContext.industry_valuation_dist(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[行业估值分布](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/industry-valuation-dist)

获取该证券所在行业的估值分布直方图。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.industry_valuation_dist("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.industry_valuation_dist("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "pe": {
      "value": "28.5",
      "high": "120.0",
      "low": "5.0",
      "median": "22.0",
      "ranking": "35",
      "rank_index": "12",
      "rank_total": "30"
    },
    "pb": {
      "value": "45.2",
      "high": "200.0",
      "low": "1.0",
      "median": "8.0",
      "ranking": "85",
      "rank_index": "25",
      "rank_total": "30"
    },
    "ps": {
      "value": "7.8",
      "high": "30.0",
      "low": "0.5",
      "median": "4.0",
      "ranking": "70",
      "rank_index": "21",
      "rank_total": "30"
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [IndustryValuationDist](#IndustryValuationDist) |
| 400    | 请求错误    | None   |

#### Schemas

##### IndustryValuationDist

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码 |
| metric | string | 否 | 估值指标（如 pe、pb、ps） |
| symbol_value | double | 否 | 该证券自身的估值指标数值 |
| buckets | object[] | 否 | 分布直方图区间列表 |
| buckets[].range_start | double | 否 | 区间下界 |
| buckets[].range_end | double | 否 | 区间上界 |
| buckets[].count | int32 | 否 | 该区间内的公司数量 |

#### 1.18 机构评级

- **Python SDK**：`FundamentalContext.institution_rating(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[机构评级](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/institution-rating)

获取分析师机构评级快照（评级分布及平均目标价）。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `TSLA.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.institution_rating("TSLA.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.institution_rating("TSLA.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "latest": {
      "evaluate": {
        "buy": 18,
        "hold": 17,
        "sell": 4,
        "no_opinion": 4,
        "over": 5,
        "under": 3,
        "total": 51,
        "start_date": "1778198400",
        "end_date": "0"
      },
      "industry_id": 87676,
      "industry_mean": 10,
      "industry_median": 4,
      "industry_name": "Automobiles",
      "industry_rank": 1,
      "industry_total": 30,
      "target": {
        "highest_price": "600.000",
        "lowest_price": "123.000",
        "prev_close": "428.35",
        "start_date": "1778198400",
        "end_date": "0"
      }
    },
    "summary": {
      "ccy_symbol": "$",
      "change": "0",
      "recommend": "Buy",
      "updated_at": "1778198400",
      "evaluate": {
        "buy": 18,
        "hold": 17,
        "sell": 4
      },
      "target": {
        "average_target": "350.00",
        "highest_price": "600.000",
        "lowest_price": "123.000"
      }
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [InstitutionRatingResponse](#InstitutionRatingResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### InstitutionRatingResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| latest | object | 是 | 最新机构评级快照 |
| latest.evaluate | object | 是 | 评级分布 |
| latest.evaluate.buy | integer | 否 | 买入评级数量 |
| latest.evaluate.hold | integer | 否 | 持有评级数量 |
| latest.evaluate.sell | integer | 否 | 卖出评级数量 |
| latest.evaluate.over | integer | 否 | 跑赢市场数量 |
| latest.evaluate.under | integer | 否 | 跑输市场数量 |
| latest.evaluate.no_opinion | integer | 否 | 无评级数量 |
| latest.evaluate.total | integer | 否 | 机构总数 |
| latest.evaluate.start_date | string | 否 | 统计周期开始日期 |
| latest.evaluate.end_date | string | 否 | 统计周期结束日期 |
| latest.industry_id | integer | 否 | 行业 ID |
| latest.industry_name | string | 否 | 行业名称 |
| latest.industry_rank | integer | 否 | 行业内排名 |
| latest.industry_total | integer | 否 | 行业标的总数 |
| latest.industry_mean | integer | 否 | 行业平均评分 |
| latest.industry_median | integer | 否 | 行业中位数评分 |
| latest.target | object | 否 | 目标价区间 |
| latest.target.highest_price | string | 否 | 最高目标价 |
| latest.target.lowest_price | string | 否 | 最低目标价 |
| latest.target.prev_close | string | 否 | 前收盘价 |
| latest.target.start_date | string | 否 | 统计周期开始日期 |
| latest.target.end_date | string | 否 | 统计周期结束日期 |
| summary | object | 否 | 综合评级快照 |
| summary.recommend | object | 否 | 评级分布映射 |
| summary.change | string | 否 | 价格变动值 |
| summary.ccy_symbol | string | 否 | 货币符号 |
| summary.evaluate | object | 否 | 评级分布数量 |
| summary.evaluate.buy | integer | 否 | 买入数量 |
| summary.evaluate.strong_buy | integer | 否 | 强力买入数量 |
| summary.evaluate.hold | integer | 否 | 持有数量 |
| summary.evaluate.sell | integer | 否 | 卖出数量 |
| summary.evaluate.under | integer | 否 | 跑输数量 |
| summary.target | string | 否 | 一致平均目标价 |
| summary.updated_at | string | 否 | 最后更新日期字符串 |

#### 1.19 机构评级详情

- **Python SDK**：`FundamentalContext.institution_rating_detail(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[机构评级详情](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/institution-rating-detail)

获取历史分析师评级及目标价详情。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `TSLA.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.institution_rating_detail("TSLA.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.institution_rating_detail("TSLA.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "ccy_symbol": "$",
    "evaluate": {
      "list": [
        {
          "date": "2021/05/14",
          "buy": 3,
          "hold": 11,
          "sell": 2,
          "strong_buy": 9,
          "under": 6
        }
      ]
    },
    "target": {
      "list": [
        {
          "broker_name": "Goldman Sachs",
          "date": "2026-04-30",
          "rating": "Buy",
          "target_price": "250.00"
        }
      ]
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [InstitutionRatingDetail](#InstitutionRatingDetail) |
| 400    | 请求错误    | None   |

#### Schemas

##### InstitutionRatingDetail

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| list | object[] | 是 | 评级详情列表 |
| list[].symbol | string | 是 | 证券代码 |
| list[].broker | string | 否 | 券商名称 |
| list[].analyst | string | 否 | 分析师姓名 |
| list[].rating | string | 否 | 评级（如 Buy、Hold、Sell） |
| list[].target_price | double | 否 | 目标价 |
| list[].date | string | 否 | 评级日期（YYYY-MM-DD） |

#### 1.20 机构评级分布时间线

- **Python SDK**：`FundamentalContext.institution_rating_views(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[机构评级分布时间线](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/institution-rating-views)

获取按月统计的机构评级（买入/持有/卖出）分布时间线，最新月份在前。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.institution_rating_views("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.institution_rating_views("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "elist": [
      {
        "date": 1746057600,
        "buy": "18",
        "over": "5",
        "hold": "17",
        "under": "3",
        "sell": "4",
        "total": "51"
      },
      {
        "date": 1743379200,
        "buy": "17",
        "over": "6",
        "hold": "18",
        "under": "3",
        "sell": "5",
        "total": "53"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [InstitutionRatingViewsResponse](#InstitutionRatingViewsResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### InstitutionRatingViewsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| elist | object[] | 否 | 月度评级分布列表，最新月份在前 |
| ∟ date | integer | 否 | Unix 时间戳（秒） |
| ∟ buy | string | 否 | 买入评级数量 |
| ∟ over | string | 否 | 跑赢市场评级数量 |
| ∟ hold | string | 否 | 持有评级数量 |
| ∟ under | string | 否 | 跑输市场评级数量 |
| ∟ sell | string | 否 | 卖出评级数量 |
| ∟ total | string | 否 | 机构总数 |

#### 1.21 投资关系

- **Python SDK**：`FundamentalContext.invest_relation(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[投资关系](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/invest-relation)

获取投资关系数据，包括母公司、子公司及主要持股。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `700.HK` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.invest_relation("700.HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.invest_relation("700.HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "forward_url": "https://longbridge.com/wiki/stocks/ST.HK.700#invest",
    "invest_securities": [
      {
        "symbol": "HUYA.US",
        "company_id": "12345",
        "company_name": "虎牙直播",
        "company_name_en": "Huya Inc.",
        "company_name_zhcn": "虎牙直播",
        "currency": "USD",
        "percent_of_shares": "19.00",
        "shares_rank": "1",
        "shares_value": "19000000"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [InvestRelations](#InvestRelations) |
| 400    | 请求错误    | None   |

#### Schemas

##### InvestRelations

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| forward_url | string | false | Company investment relations page URL |
| invest_securities | object[] | false | List of investment holdings |
| ∟ symbol | string | false | 证券代码 |
| ∟ company_id | string | false | Company ID |
| ∟ company_name | string | false | Display company name |
| ∟ company_name_en | string | false | English company name |
| ∟ company_name_zhcn | string | false | Chinese company name |
| ∟ currency | string | false | Currency |
| ∟ percent_of_shares | string | false | Ownership percentage |
| ∟ shares_rank | string | false | Rank by shares held |
| ∟ shares_value | string | false | Value of shares held |

#### 1.22 宏观经济指标列表

- **Python SDK**：`FundamentalContext.macroeconomic_indicators(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[宏观经济指标列表](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/macroeconomic-indicators)

列出 Longbridge 支持的宏观经济指标，可按国家/地区筛选。

#### 参数

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| country | MacroeconomicCountry | 否 | 按国家/地区筛选。不填返回全部。 |
| keyword | string | 否 | 按指标名称模糊搜索（不区分大小写） |
| offset | int | 否 | 分页偏移量，默认 0 |
| limit | int | 否 | 每页最大条数，默认 100，最大 1000 |

##### MacroeconomicCountry

| 枚举值 | 国家/地区 |
| ------ | --------- |
| HK | 香港 |
| CN | 中国大陆 |
| US | 美国 |
| EU | 欧元区 |
| JP | 日本 |
| SG | 新加坡 |

#### 请求示例

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder, MacroeconomicCountry

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.macroeconomic_indicators(country=MacroeconomicCountry.UnitedStates, limit=50)
print(resp)
```

#### 响应

##### 响应示例

```json
{
  "count": 619,
  "list": [
    {
      "indicator_code": "61744",
      "country": "US",
      "name": "Non-Farm Payroll",
      "periodicity": "Monthly",
      "describe": "Employment situation report...",
      "importance": 3
    }
  ]
}
```

#### 数据结构

##### MacroeconomicIndicatorListResponse

| 字段 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| list | MacroeconomicIndicator[] | 是 | 指标列表 |
| count | int | 是 | 满足条件的指标总数 |

##### MacroeconomicIndicator

| 字段 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| indicator_code | string | 是 | 指标代码（用于 `macroeconomic` 查询） |
| country | string | 是 | 国家/地区名称 |
| name | string | 是 | 指标名称  |
| periodicity | string | 是 | 发布频率（如 `Monthly`、`Quarterly`） |
| describe | string | 是 | 指标说明  |
| importance | int | 是 | 重要性（1=低、2=中、3=高） |

#### 1.23 宏观经济历史数据

- **Python SDK**：`FundamentalContext.macroeconomic(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[宏观经济历史数据](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/macroeconomic)

获取指定宏观经济指标的历史发布数据，包括实际值、预测值、前值和下次发布时间。

#### 参数

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| indicator_code | string | 是 | 指标代码，来自 `macroeconomic_indicators` |
| start_date | string | 否 | 开始日期，格式 `YYYY-MM-DD` |
| end_date | string | 否 | 结束日期，格式 `YYYY-MM-DD` |
| offset | int | 否 | 分页偏移量，默认 0 |
| limit | int | 否 | 最大返回条数，默认 100，最大 100 |

#### 请求示例

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.macroeconomic("61744", start_date="2024-01-01", end_date="2024-12-31")
print(resp)
```

#### 响应

##### 响应示例

```json
{
  "count": 24,
  "info": {
    "indicator_code": "61744",
    "country": "US",
    "name": "Non-Farm Payroll",
    "periodicity": "Monthly",
    "describe": "...",
    "importance": 3
  },
  "data": [
    {
      "period": "2024-12-01",
      "release_at": 1735900200,
      "actual_value": "256000",
      "previous_value": "212000",
      "forecast_value": "165000"
    }
  ]
}
```

#### 数据结构

##### MacroeconomicResponse

| 字段 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| info | MacroeconomicIndicator | 是 | 指标元数据 |
| data | Macroeconomic[] | 是 | 历史数据点列表 |
| count | int | 是 | 数据总条数 |

##### Macroeconomic

| 字段 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| period | string | 是 | 统计周期（如 `2024-12-01`、`2024-Q4`） |
| release_at | int | 否 | 发布时间 Unix 时间戳 |
| actual_value | string | 是 | 实际值 |
| previous_value | string | 是 | 前值 |
| forecast_value | string | 是 | 市场预期值 |

#### 1.24 经营数据

- **Python SDK**：`FundamentalContext.operating(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[经营数据](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/operating)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可查询任意标的，包括美股。
:::

按财报期获取经营数据及核心财务指标摘要。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |
| period | string | 否 | 财报期筛选，如 `q1`、`q2`、`q3`、`q4`、`annual` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.operating("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.operating("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "id": "12345",
        "report": "af",
        "title": "FY2025 Annual Report Summary",
        "txt": "Management discussion...",
        "latest": true,
        "web_url": "https://longbridge.com/wiki/...",
        "financial": {
          "code": "700",
          "currency": "HKD",
          "name": "Tencent",
          "region": "HK",
          "report": "af",
          "indicators": [
            {
              "field_name": "operating_revenue",
              "indicator_name": "Revenue",
              "indicator_value": "6786 亿",
              "yoy": "0.0800"
            }
          ]
        }
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [OperatingList](#OperatingList) |
| 400    | 请求错误    | None   |

#### Schemas

##### OperatingListResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| list | object[] | true | 经营数据报告列表，见 [OperatingItem](#OperatingItem) |

##### OperatingItem

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | false | 内部报告 ID |
| report | string | false | 报告期代码（如 `af` = 年报） |
| title | string | false | 报告标题 |
| txt | string | false | 管理层讨论文本 |
| latest | boolean | false | 是否为最新报告 |
| web_url | string | false | 完整报告页面链接 |
| financial | object | false | 关键财务指标 |

##### OperatingFinancial

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| code | string | false | 股票代码 |
| name | string | false | 公司名称 |
| currency | string | false | 报告货币 |
| region | string | false | 市场地区 |
| report | string | false | 报告期代码 |
| indicators | object[] | false | 财务指标列表，见 [OperatingIndicator](#OperatingIndicator) |

##### OperatingIndicator

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| field_name | string | true | 字段名称（如 `operating_revenue`） |
| indicator_name | string | false | 显示名称 |
| indicator_value | string | false | 格式化数值 |
| yoy | string | false | 同比变化率 |

#### 1.25 分析师评级

- **Python SDK**：`FundamentalContext.ratings(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[分析师评级](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/ratings)

获取指定证券的机构分析师评级和一致预期数据。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.ratings("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.ratings("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "industry_name": "Technology Hardware, Storage and Peripherals",
    "industry_rank": 2,
    "multi_letter": "B",
    "multi_score": "0.32",
    "multi_score_change": -1,
    "scale_txt_name": "Large",
    "style_txt_name": "Blend",
    "report_period_txt": "Rating based on Fiscal Year 2026 s.a.",
    "ratings_json": "[]"
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [StockRatingsResponse](#StockRatingsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### StockRatingsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| industry_name | string | 否 | 行业名称 |
| industry_rank | integer | 否 | 行业内排名 |
| multi_letter | string | 否 | 评级字母等级 |
| multi_score | string | 否 | 综合评分 |
| multi_score_change | integer | 否 | 评分变化 |
| report_period_txt | string | 否 | 报告期描述 |
| scale_txt_name | string | 否 | 评级量表名称 |
| style_txt_name | string | 否 | 评级风格名称 |
| ratings_json | string | 否 | 原始评级详情 JSON |

#### 1.26 股东持仓详情

- **Python SDK**：`FundamentalContext.shareholder_detail(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[股东持仓详情](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/shareholder-detail)

获取单个股东的持仓历史及交易明细。`object_id` 来自 `shareholder_top` 返回结果。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |
| object_id | integer | 是 | 股东 ID，来自 `shareholder_top` 的 `object_id` 字段 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.shareholder_detail("AAPL.US", 19463)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.shareholder_detail("AAPL.US", 19463)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "name": "The Vanguard Group, Inc.",
    "title": "",
    "avatar": "",
    "owner_source": "Institution",
    "holding_periods": [],
    "holding_details": [],
    "holding_summary": [],
    "trading_periods": ["Past 1 Month", "Past 3 Months", "Past 1 Year", "Past 3 Years"],
    "tradings": [
      {
        "period": "Past 1 Month",
        "accum_buy": "8500000.00",
        "accum_sell": "2687264.00",
        "net_buy": "5812736.00",
        "trading_details": [
          {
            "trading_date": "2025-12-18",
            "trading_shares": "5200000",
            "trading_price": "248.12",
            "trading_type": "Buy"
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ShareholderDetailResponse](#ShareholderDetailResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ShareholderDetailResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| name | string | false | 股东名称 |
| title | string | false | 股东头衔 / 类型 |
| avatar | string | false | 头像 URL |
| owner_source | string | false | 股东类型：`Company`、`Institution`、`Person`、`Insider` |
| holding_periods | string[] | false | 可用的持仓报告期列表 |
| holding_details | object[] | false | 持仓明细记录 |
| holding_summary | object[] | false | 持仓汇总记录 |
| trading_periods | string[] | false | 可用的交易统计区间（如 `Past 1 Month`、`Past 3 Months`） |
| tradings | object[] | false | 各区间交易汇总 |
| ∟ period | string | false | 区间标签（如 `Past 1 Month`） |
| ∟ accum_buy | string | false | 该区间累计买入股数 |
| ∟ accum_sell | string | false | 该区间累计卖出股数 |
| ∟ net_buy | string | false | 该区间净买入股数（买入减卖出） |
| ∟ trading_details | object[] | false | 该区间内的具体交易记录 |
| ∟ ∟ trading_date | string | false | 交易日期 |
| ∟ ∟ trading_shares | string | false | 交易股数 |
| ∟ ∟ trading_price | string | false | 交易价格 |
| ∟ ∟ trading_type | string | false | 交易方向：`Buy` 或 `Sell` |

> 说明：部分字段在数据不可用时返回空字符串或空数组。

#### 1.27 大股东排行

- **Python SDK**：`FundamentalContext.shareholder_top(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[大股东排行](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/shareholder-top)

获取上市公司前 20 大股东（机构、个人、内部人）的持股数据，支持多报告期对比。`object_id` 可传入 `shareholder_detail` 查看详情。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.shareholder_top("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.shareholder_top("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "info": [
      {
        "period": "Latest",
        "share_holders": [
          {
            "object_id": "148057",
            "name": "The Vanguard Group, Inc.",
            "title": "",
            "shares_held": "1426283914.00",
            "percent_shares_held": "9.71%",
            "percent_shares_changed": "0.01%",
            "shares_changed": "0.00",
            "period": "Latest",
            "filing_date": "2025/12/31"
          },
          {
            "object_id": "452583",
            "name": "BlackRock, Inc.",
            "title": "",
            "shares_held": "1138572603.00",
            "percent_shares_held": "7.75%",
            "percent_shares_changed": "-0.06%",
            "shares_changed": "-10565359.00",
            "period": "Latest",
            "filing_date": "2026/03/31"
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ShareholderTopResponse](#ShareholderTopResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ShareholderTopResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| info | object[] | false | 各报告期的股东数据 |
| ∟ period | string | false | 报告期标签（如 `Latest`） |
| ∟ share_holders | object[] | false | 股东列表（最多 20 条） |
| ∟ ∟ object_id | string | false | 股东唯一 ID，可传入 `shareholder_detail` |
| ∟ ∟ name | string | false | 股东名称 |
| ∟ ∟ title | string | false | 股东类型（机构 / 个人 / 内部人） |
| ∟ ∟ shares_held | string | false | 持股数量 |
| ∟ ∟ percent_shares_held | string | false | 持股比例，含 `%` 符号（如 `9.71%`） |
| ∟ ∟ percent_shares_changed | string | false | 持股比例变动，含 `%` 符号 |
| ∟ ∟ shares_changed | string | false | 持股变动数量（正增负减） |
| ∟ ∟ period | string | false | 该条目的报告期标签 |
| ∟ ∟ filing_date | string | false | 申报日期 |

#### 1.28 主要股东

- **Python SDK**：`FundamentalContext.shareholders(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[主要股东](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/shareholders)

获取公司主要机构股东和个人股东信息。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.shareholders("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.shareholders("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "forward_url": "",
    "total": 33,
    "shareholder_list": [
      {
        "shareholder_name": "Timothy D. Cook",
        "percent_of_shares": "2.84",
        "institution_type": "",
        "report_date": "2026-04-21",
        "shareholder_id": "0",
        "shares_changed": "0",
        "stocks": []
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [ShareholderResponse](#ShareholderResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### ShareholderResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| shareholder_list | object[] | 是 | 股东列表， |
| ∟ shareholder_name | string | 是 | 股东名称 |
| ∟ percent_of_shares | string | 是 | 持股比例 |
| ∟ institution_type | string | 否 | 机构类型 |
| ∟ report_date | string | 否 | 报告日期 |
| ∟ shareholder_id | string | 否 | 股东 ID |
| ∟ shares_changed | string | 否 | 持股变动 |
| ∟ stocks | object[] | 否 | 关联标的 |
| forward_url | string | 否 | 完整股东页面链接 |
| total | integer | 是 | 股东总数 |

#### 1.29 美股分析师一致预期

- **Python SDK**：`FundamentalContext.us_analyst_consensus(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[美股分析师一致预期](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_analyst_consensus)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股分析师一致预期——营收、EPS 预测及买入/持有/卖出评级。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | 股票代码，如 `AAPL.US` |
| report | string | 否 | 报告周期：`af`（年报）、`saf`（半年报）、`qf`（季报）、`q1`（Q1）、`3q`（Q3）|

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)
resp = ctx.us_analyst_consensus("AAPL.US", "af")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)
    resp = await ctx.us_analyst_consensus("AAPL.US", "af")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "ai_summary": "Analysts remain broadly bullish on AAPL with 35 Buy ratings...",
  "aichat_data": {
    "agent_id": "analyst_aapl",
    "handoff_agent_id": "",
    "symbol": "AAPL.US",
    "text": "Analyst consensus summary for AAPL",
    "type": "consensus",
    "workflow_type": "analyst"
  },
  "currency": "USD",
  "report": "af",
  "list": [
    {
      "fiscal_year": 2025,
      "report_txt": "FY2025",
      "revenue": {"actual": "391035000000", "estimate": "388000000000"},
      "eps": {"actual": "6.42", "estimate": "6.29"},
      "ebit": {"actual": "125820000000", "estimate": "122000000000"}
    }
  ],
  "opt_reports": ["af", "qf"],
  "h5_data": null
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [UsAnalystConsensus](#UsAnalystConsensus) |
| 400    | 请求错误 | None   |

#### Schemas

##### UsAnalystConsensus

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| ai_summary | string | 是 | AI 生成的分析师一致预期摘要 |
| aichat_data | USAIChatData | 是 | AI 对话上下文数据 |
| currency | string | 是 | 货币代码，如 `USD` |
| report | string | 是 | 报告周期类型 |
| list | USConsensusItem[] | 是 | 按财年排列的一致预期数据 |
| opt_reports | string[] | 否 | 可选的报告期列表 |
| h5_data | any | 否 | H5 展示数据 |

##### USConsensusItem

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| fiscal_year | int | 财年 |
| report_txt | string | 报告期标签（如 `FY2024`） |
| revenue | USConsensusEstimate | 营收一致预期 |
| eps | USConsensusEstimate | EPS 一致预期 |
| ebit | USConsensusEstimate | EBIT 一致预期 |

##### USConsensusEstimate

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| actual | string | 实际公布值 |
| estimate | string | 分析师一致预期值 |

##### USAIChatData

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| agent_id | string | AI Agent 标识 |
| handoff_agent_id | string | 转交 Agent 标识 |
| symbol | string | 股票代码 |
| text | string | 对话上下文文本 |
| type | string | 对话类型 |
| workflow_type | string | 工作流类型 |

#### 1.30 美股公司分红

- **Python SDK**：`FundamentalContext.us_company_dividends(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[美股公司分红](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_company_dividends)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股股票分红历史——TTM 股息率、派息次数及逐笔分红记录。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | 股票代码，如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)
resp = ctx.us_company_dividends("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)
    resp = await ctx.us_company_dividends("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "recent_dividends": {
    "dividend_ttm": "1.00",
    "dividend_yield_ttm": "0.0053",
    "payouts": "4",
    "currency": "USD"
  },
  "dividend_history": [
    {
      "fiscal_year": "2024",
      "fiscal_year_range": "2024-01-01 ~ 2024-12-31",
      "dividend": "1.00",
      "dividend_yield": "0.0053",
      "dividend_growth_rate": "0.0408",
      "dividend_payout_ratio": "0.1497",
      "total_shareholder_yield": "0.0163",
      "currency": "USD"
    }
  ],
  "payout_ratios": [
    {
      "fiscal_year": "2024",
      "fiscal_year_range": "2024-01-01 ~ 2024-12-31",
      "dividend_payout_ratio": "0.1497",
      "currency": "USD"
    }
  ],
  "dividend_payout_history": [
    {
      "dividend": "0.25",
      "dividend_type": "Cash",
      "currency": "USD",
      "ex_date": "2024-11-08",
      "payment_date": "2024-11-14",
      "record_date": "2024-11-11",
      "title": "Q4 FY2024 Dividend",
      "start_time_unix": "1730000000"
    }
  ]
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [UsCompanyDividends](#UsCompanyDividends) |
| 400    | 请求错误 | None   |

#### Schemas

##### UsCompanyDividends

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| recent_dividends | USRecentDividend | 是 | 近期分红摘要 |
| dividend_history | USDividendHistoryItem[] | 否 | 历年分红历史 |
| payout_ratios | USDividendHistoryItem[] | 否 | 派息率历史 |
| dividend_payout_history | USDividendPayoutRecord[] | 否 | 逐笔分红派发记录 |

##### USRecentDividend

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| dividend_ttm | string | 过去 12 个月每股股息 |
| dividend_yield_ttm | string | TTM 股息率（%） |
| payouts | string | 过去一年派息次数 |
| currency | string | 货币代码 |

##### USDividendHistoryItem

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| fiscal_year | string | 财年 |
| fiscal_year_range | string | 财年日期范围 |
| dividend | string | 每股总股息 |
| dividend_yield | string | 股息率 |
| dividend_growth_rate | string | 股息同比增长率 |
| dividend_payout_ratio | string | 派息率 |
| dividend_to_cashflow_ratio | string | 股息与现金流比率 |
| total_shareholder_yield | string | 股东总回报率 |
| net_buyback | string | 净回购金额 |
| net_buyback_yield | string | 净回购收益率 |
| net_buyback_growth_rate | string | 净回购增长率 |
| net_buyback_payout_ratio | string | 净回购派出率 |
| net_buyback_to_cashflow_ratio | string | 净回购与现金流比率 |
| currency | string | 货币代码 |

#### 1.31 美股公司概览

- **Python SDK**：`FundamentalContext.us_company_overview(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[美股公司概览](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_company_overview)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股公司概览信息——简介、市值、排名标签和详情链接。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | 股票代码，如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)
resp = ctx.us_company_overview("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)
    resp = await ctx.us_company_overview("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "intro": "Apple Inc. designs, manufactures, and markets smartphones, personal computers...",
  "market_cap": "3150000000000",
  "ccy_symbol": "USD",
  "top_rank_tags": [
    {
      "key": "sp500",
      "title": "S&P 500",
      "text": "S&P 500",
      "rank_type": 1
    }
  ],
  "detail_url": "https://longbridge.com/stocks/AAPL.US",
  "sharelist": []
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [UsCompanyOverview](#UsCompanyOverview) |
| 400    | 请求错误 | None   |

#### Schemas

##### UsCompanyOverview

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| intro | string | 是 | 公司简介 |
| market_cap | string | 是 | 市值 |
| ccy_symbol | string | 是 | 货币符号 |
| top_rank_tags | USRankTag[] | 否 | 排名标签列表 |
| detail_url | string | 否 | 公司详情页链接 |
| sharelist | USSharelistItem[] | 否 | 相关自选列表 |

##### USRankTag

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| key | string | 标签标识 |
| title | string | 标签标题 |
| text | string | 标签显示文本 |
| rank_type | int | 排名类型 |
| highlight_text | string | 高亮显示文本 |

##### USSharelistItem

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| id | string | 自选列表 ID |
| name | string | 自选列表名称 |
| chg | string | 变动值 |

#### 1.32 美股 ETF 分红信息

- **Python SDK**：`FundamentalContext.us_etf_dividend_info(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[美股 ETF 分红信息](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_etf_dividend_info)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股 ETF 分红信息——TTM 股息率、派息频率及财年明细。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | ETF 代码，如 `IVV.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)
resp = ctx.us_etf_dividend_info("IVV.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)
    resp = await ctx.us_etf_dividend_info("IVV.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "dividend_ttm": "6.84",
  "dividend_yield_ttm": "0.0134",
  "dividend_frequency": "Quarterly",
  "currency": "USD",
  "fiscal_year_info": [
    {
      "fiscal_year": "2025",
      "fiscal_year_range": "2025-01-01 ~ 2025-12-31",
      "dividend": "6.52",
      "dividend_yield": "0.0134",
      "currency": "USD"
    }
  ]
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [UsETFDividendInfo](#UsETFDividendInfo) |
| 400    | 请求错误 | None   |

#### Schemas

##### UsETFDividendInfo

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| dividend_ttm | string | 是 | 过去 12 个月每股股息 |
| dividend_yield_ttm | string | 是 | TTM 股息率（%） |
| dividend_frequency | string | 是 | 派息频率（如 `Quarterly`） |
| currency | string | 是 | 货币代码，如 `USD` |
| fiscal_year_info | USFiscalYearDividend[] | 否 | 按财年分列的年度分红明细 |

##### USFiscalYearDividend

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| fiscal_year | string | 财年 |
| fiscal_year_range | string | 财年日期范围 |
| dividend | string | 年度总股息 |
| dividend_yield | string | 年度股息率 |
| currency | string | 货币代码 |

#### 1.33 美股 ETF 文件

- **Python SDK**：`FundamentalContext.us_etf_files(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[美股 ETF 文件](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_etf_files)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

列出美股 ETF 的监管文件——招股书、事实说明书和年报。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | ETF 代码，如 `IVV.US` |
| size | int | 否 | 最大返回文件数，不填则返回全部 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)
resp = ctx.us_etf_files("IVV.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)
    resp = await ctx.us_etf_files("IVV.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "files": [
    {
      "file_name": "iShares Core S&P 500 ETF Prospectus",
      "file_path": "https://www.iShares.com/content/dam/iShares/prospectus/en/IVV.pdf",
      "update_date": "2024-01-15",
      "code": "IVV_PROSPECTUS",
      "format": "pdf"
    },
    {
      "file_name": "iShares Core S&P 500 ETF Annual Report",
      "file_path": "https://www.iShares.com/content/dam/iShares/reports/en/IVV_AR.pdf",
      "update_date": "2024-02-01",
      "code": "IVV_ANNUAL",
      "format": "pdf"
    }
  ]
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [UsETFFileList](#UsETFFileList) |
| 400    | 请求错误 | None   |

#### Schemas

##### UsETFFilesResponse

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| files | USETFFile[] | 是 | ETF 监管文件列表 |

##### USETFFile

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| file_name | string | 文件名称 |
| file_path | string | 文件路径或 URL |
| update_date | string | 最后更新日期 |
| code | string | 文件代码 |
| format | string | 文件格式（如 `pdf`） |

#### 1.34 美股财务概览

- **Python SDK**：`FundamentalContext.us_financial_overview(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[美股财务概览](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_financial_overview)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

按报告周期获取美股财务概览——损益、资产负债和现金流摘要。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | 股票代码，如 `AAPL.US` |
| report | string | 是 | 报告周期：`annual` 或 `quarterly`（默认：annual）|

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)
resp = ctx.us_financial_overview("AAPL.US", report="annual")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)
    resp = await ctx.us_financial_overview("AAPL.US", report="annual")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "ccy_symbol": "USD",
  "report_type": "annual",
  "is_list": [
    {
      "revenue": "391035000000",
      "net_income": "93736000000",
      "net_margin": "0.2397",
      "report": {
        "start_date": "2023-10-01",
        "end_date": "2024-09-28",
        "report_txt": "FY2024"
      }
    }
  ],
  "bs_list": [
    {
      "debt_assets_ratio": "0.8193",
      "total_assets": "364840000000",
      "total_liabilities": "308927000000",
      "report": {
        "start_date": "2023-10-01",
        "end_date": "2024-09-28",
        "report_txt": "FY2024"
      }
    }
  ],
  "cf_list": [
    {
      "operating": "118254000000",
      "investing": "-21013000000",
      "financing": "-89831000000",
      "report": {
        "start_date": "2023-10-01",
        "end_date": "2024-09-28",
        "report_txt": "FY2024"
      }
    }
  ]
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [UsFinancialOverview](#UsFinancialOverview) |
| 400    | 请求错误 | None   |

#### Schemas

##### UsFinancialOverview

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| ccy_symbol | string | 是 | 货币符号 |
| report_type | string | 是 | 报告类型（如 `annual`、`quarterly`） |
| is_list | USFinancialISItem[] | 是 | 损益表条目列表 |
| bs_list | USFinancialBSItem[] | 是 | 资产负债表条目列表 |
| cf_list | USFinancialCFItem[] | 是 | 现金流量表条目列表 |

##### USFinancialISItem

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| revenue | string | 是 | 总营收 |
| net_income | string | 是 | 净利润 |
| net_margin | string | 是 | 净利润率 |
| report | USReportPeriod | 是 | 报告期信息 |

##### USFinancialBSItem

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| debt_assets_ratio | string | 是 | 资产负债率 |
| total_assets | string | 是 | 总资产 |
| total_liabilities | string | 是 | 总负债 |
| report | USReportPeriod | 是 | 报告期信息 |

##### USFinancialCFItem

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| operating | string | 是 | 经营活动现金流 |
| investing | string | 是 | 投资活动现金流 |
| financing | string | 是 | 筹资活动现金流 |
| report | USReportPeriod | 是 | 报告期信息 |

##### USReportPeriod

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| start_date | string | 是 | 报告期开始日期 |
| end_date | string | 是 | 报告期结束日期 |
| report_txt | string | 是 | 报告期标签（如 `FY2024`、`Q1 2024`） |

#### 1.35 美股财务报表

- **Python SDK**：`FundamentalContext.us_financial_statement(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[美股财务报表](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_financial_statement)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股指定财务报表（损益表、资产负债表或现金流量表）。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | 股票代码，如 `AAPL.US` |
| kind | string | 是 | 报表类型：`IS`（损益表）、`BS`（资产负债表）、`CF`（现金流量表）|
| report | string | 否 | 报告周期 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)
resp = ctx.us_financial_statement("AAPL.US", "IS", "af")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)
    resp = await ctx.us_financial_statement("AAPL.US", "IS", "af")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "currency": "USD",
  "report": "af",
  "empty_fields": [],
  "list": [
    {
      "ff_period": "A",
      "ff_year": 2024,
      "fp_end": "2024-09-28",
      "report_txt": "FY2024",
      "rpt_date": "2024-11-01",
      "fields": [
        {
          "id": "revenue",
          "name": "总营收",
          "value": "391035000000",
          "yoy": "0.0198",
          "level": 1,
          "display_order": 1,
          "field": "revenue",
          "value_type": "amount"
        }
      ]
    }
  ]
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [UsFinancialStatement](#UsFinancialStatement) |
| 400    | 请求错误 | None   |

#### Schemas

##### UsFinancialStatement

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| currency | string | 是 | 货币代码，如 `USD` |
| report | string | 是 | 报告周期类型（如 `annual`、`quarterly`） |
| empty_fields | string[] | 否 | 本期无数据的字段列表 |
| list | USFinancialStatementPeriod[] | 是 | 按报告期排列的报表数据 |

##### USFinancialStatementPeriod

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| ff_period | string | 是 | 报告周期代码（如 `A`=年报、`Q`=季报） |
| ff_year | int | 是 | 财年 |
| fp_end | string | 是 | 报告期结束日期 |
| report_txt | string | 是 | 报告期标签（如 `FY2024`） |
| rpt_date | string | 是 | 财报发布日期 |
| fields | USFinancialStatementField[] | 是 | 财务行项目列表 |

##### USFinancialStatementField

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| id | string | 是 | 字段标识 |
| name | string | 是 | 字段显示名称 |
| value | string | 是 | 字段值 |
| yoy | string | 否 | 同比变动率 |
| level | int | 是 | 层级（1=顶层） |
| display_order | int | 是 | 显示顺序 |
| field | string | 是 | 字段键名 |
| value_type | string | 是 | 值类型（如 `amount`、`ratio`） |

#### 1.36 美股关键财务指标

- **Python SDK**：`FundamentalContext.us_key_financial_metrics(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[美股关键财务指标](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_key_financial_metrics)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股关键财务指标——营收、净利润、EPS、利润率和增长率。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | 股票代码，如 `AAPL.US` |
| report | string | 否 | 报告周期：`af`（年报）、`saf`（半年报）、`qf`（季报）、`q1`（Q1）、`3q`（Q3）|

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)
resp = ctx.us_key_financial_metrics("AAPL.US", "af")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)
    resp = await ctx.us_key_financial_metrics("AAPL.US", "af")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "currency": "USD",
  "report": "af",
  "empty_fields": [],
  "list": [
    {
      "ff_period": "A",
      "ff_year": 2024,
      "fp_end": "2024-09-28",
      "report_txt": "FY2024",
      "rpt_date": "2024-11-01",
      "fields": [
        {"key": "revenue", "value": "391035000000"},
        {"key": "gross_margin", "value": "0.4621"},
        {"key": "net_margin", "value": "0.2397"},
        {"key": "eps", "value": "6.07"}
      ]
    }
  ]
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [UsKeyFinancialMetrics](#UsKeyFinancialMetrics) |
| 400    | 请求错误 | None   |

#### Schemas

##### UsKeyFinancialMetrics

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| currency | string | 是 | 货币代码，如 `USD` |
| report | string | 是 | 报告周期类型（如 `annual`、`quarterly`） |
| empty_fields | string[] | 否 | 本期无数据的字段列表 |
| list | USKeyMetricItem[] | 是 | 按报告期排列的关键指标数据 |

##### USKeyMetricItem

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| ff_period | string | 是 | 报告周期代码（如 `A`=年报、`Q`=季报） |
| ff_year | int | 是 | 财年 |
| fp_end | string | 是 | 报告期结束日期 |
| report_txt | string | 是 | 报告期标签（如 `FY2024`） |
| rpt_date | string | 是 | 财报发布日期 |
| fields | object[] | 是 | 关键财务指标（结构因公司而异） |

#### 1.37 美股估值概览

- **Python SDK**：`FundamentalContext.us_valuation_overview(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[美股估值概览](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/us_valuation_overview)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股估值概览——当前估值指标及历史区间。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 是 | 股票代码，如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)
resp = ctx.us_valuation_overview("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)
    resp = await ctx.us_valuation_overview("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "indicator": "PE",
  "metrics": {
    "pe": {
      "circle": "35.2",
      "part": "72",
      "metric": "PE",
      "desc": "Price-to-Earnings ratio",
      "industry_median": "28.4"
    }
  },
  "range": 72,
  "date": "2026-07-01",
  "ccy_symbol": "USD",
  "ai_summary": "Apple's PE ratio is in the 72nd percentile...",
  "aichat_data": {
    "agent_id": "valuation_aapl",
    "handoff_agent_id": "",
    "symbol": "AAPL.US",
    "text": "Valuation overview for AAPL",
    "type": "valuation",
    "workflow_type": "valuation"
  }
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [UsValuationOverview](#UsValuationOverview) |
| 400    | 请求错误 | None   |

#### Schemas

##### UsValuationOverview

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| indicator | string | 是 | 主要估值指标名称（如 `PE`） |
| metrics | map[string, USValuationMetric] | 是 | 以指标名称为键的估值指标字典 |
| range | int | 是 | 历史百分位（0–100） |
| date | string | 是 | 估值日期 |
| ccy_symbol | string | 是 | 货币符号 |
| ai_summary | string | 否 | AI 生成的估值摘要 |
| aichat_data | USAIChatData | 否 | AI 对话上下文数据 |

##### USValuationMetric

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| circle | string | 当前指标数值 |
| part | string | 百分位位置 |
| metric | string | 指标名称 |
| desc | string | 指标描述 |
| industry_median | string | 行业中位数 |

#### 1.38 多股估值对比

- **Python SDK**：`FundamentalContext.valuation_comparison(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[多股估值对比](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/valuation-comparison)

对比多只股票的估值指标（PE/PB/PS/市值/收盘价）。不传对比股票时，服务端自动选取同行业标的。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 主标的证券代码，例如 `AAPL.US` |
| currency | string | 是 | 结果货币：`USD`、`HKD`、`CNY` |
| comparison_symbols | string[] | 否 | 对比股票代码列表；不传时服务端自动选取同行业标的 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

### 自动选取同行业对比
resp = ctx.valuation_comparison("AAPL.US", "USD")
### 指定对比标的
resp = ctx.valuation_comparison("AAPL.US", "USD", ["MSFT.US", "GOOGL.US"])
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.valuation_comparison("AAPL.US", "USD", ["MSFT.US", "GOOGL.US"])
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "counter_id": "ST/US/AAPL",
        "name": "苹果公司",
        "currency": "USD",
        "market_value": "3241500000000",
        "price_close": "213.49",
        "pe": "32.15",
        "pb": "50.21",
        "ps": "8.04",
        "roe": "136.45",
        "eps": "6.43",
        "bps": "4.38",
        "dps": "0.99",
        "div_yld": "0.46",
        "assets": "371082000000",
        "history": [
          { "date": "1622520000", "pe": "37.56", "pb": "30.16", "ps": "6.41" },
          { "date": "1625112000", "pe": "41.49", "pb": "35.64", "ps": "6.60" }
        ]
      },
      {
        "counter_id": "ST/US/MSFT",
        "name": "微软",
        "currency": "USD",
        "market_value": "3085000000000",
        "price_close": "415.32",
        "pe": "35.42",
        "pb": "12.87",
        "ps": "12.61",
        "roe": "38.21",
        "eps": "11.72",
        "bps": "32.28",
        "dps": "3.32",
        "div_yld": "0.80",
        "assets": "512163000000",
        "history": [
          { "date": "1622520000", "pe": "33.12", "pb": "11.94", "ps": "11.84" }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ValuationComparisonResponse](#ValuationComparisonResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ValuationComparisonResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| list | object[] | false | 股票估值对比列表 |
| ∟ counter_id | string | false | Counter ID（如 `ST/US/AAPL`） |
| ∟ name | string | false | 证券名称 |
| ∟ currency | string | false | 数值所用货币 |
| ∟ market_value | string | false | 市值 |
| ∟ price_close | string | false | 最新收盘价 |
| ∟ pe | string | false | 市盈率（TTM） |
| ∟ pb | string | false | 市净率 |
| ∟ ps | string | false | 市销率（TTM） |
| ∟ roe | string | false | 净资产收益率（%） |
| ∟ eps | string | false | 每股收益（TTM） |
| ∟ bps | string | false | 每股净资产 |
| ∟ dps | string | false | 每股派息（TTM） |
| ∟ div_yld | string | false | 股息率（%） |
| ∟ assets | string | false | 总资产 |
| ∟ history | object[] | false | 历史估值时间序列 |
| ∟ ∟ date | string | false | 日期（Unix 时间戳，秒） |
| ∟ ∟ pe | string | false | 历史 PE |
| ∟ ∟ pb | string | false | 历史 PB |
| ∟ ∟ ps | string | false | 历史 PS |

#### 1.39 估值历史

- **Python SDK**：`FundamentalContext.valuation_history(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[估值历史](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/valuation-history)

获取历史估值指标时间序列（市盈率、市净率、市销率、股息率）。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.valuation_history("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.valuation_history("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "history": {
      "metrics": {
        "pe": {
          "desc": "P/E Ratio",
          "high": "35.2",
          "low": "18.1",
          "median": "26.5",
          "list": [
            {
              "timestamp": "1622520000",
              "value": "28.5"
            }
          ]
        },
        "pb": null,
        "ps": null
      }
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ValuationHistoryResponse](#ValuationHistoryResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ValuationHistoryResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码 |
| list | object[] | 是 | 历史估值数据点列表，见 [ValuationMetric](#ValuationMetric) |
| list[].date | string | 否 | 日期（YYYY-MM-DD） |
| list[].pe | double | 否 | 市盈率（PE） |
| list[].pb | double | 否 | 市净率（PB） |
| list[].ps | double | 否 | 市销率（PS） |
| list[].dividend_yield | double | 否 | 股息率（%） |

#### 1.40 估值指标

- **Python SDK**：`FundamentalContext.valuations(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[估值指标](https://open.longbridge.com/zh-CN/docs/fundamental/fundamental/valuations)

获取当前估值指标（市盈率、市净率、市销率、股息率）及 5 年历史区间数据。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |
| indicator | string | 否 | 指标筛选：`pe`、`pb`、`ps`、`dvd_yld` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import FundamentalContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = FundamentalContext(config)

resp = ctx.valuations("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncFundamentalContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncFundamentalContext.create(config)

    resp = await ctx.valuations("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "metrics": {
      "pe": { "current": "29.5", "high": "35.2", "low": "18.0", "median": "26.0" },
      "pb": { "current": "45.1", "high": "50.0", "low": "30.0", "median": "42.0" }
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [ValuationsResponse](#ValuationsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### ValuationsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| metrics | object | 是 | 估值指标映射 |
| ∟ pe | object | 否 | 市盈率数据 |
| ∟∟ current | string | 是 | 当前值 |
| ∟∟ high | string | 是 | 5 年最高值 |
| ∟∟ low | string | 是 | 5 年最低值 |
| ∟∟ median | string | 是 | 5 年中位值 |

#### 1.41 A/H 溢价

- **Python SDK**：`MarketContext.ah_premium(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[A/H 溢价](https://open.longbridge.com/zh-CN/docs/fundamental/market/ah-premium)

获取 A+H 两地上市股票的 A/H 溢价比率，对比 A 股和 H 股价格。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | A+H 两地上市股票的 H 股代码，例如 `939.HK` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.ah_premium("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.ah_premium("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "klines": [
      {
        "ahpremium_rate": "0.1523",
        "apreclose": "24.80",
        "aprice": "25.10",
        "currency_rate": "0.8920",
        "hpreclose": "19.20",
        "hprice": "19.50",
        "price_spread": "1.23",
        "timestamp": "1778198400"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [AhPremiumResponse](#AhPremiumResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### AhPremiumResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| klines | object[] | true | A/H premium daily kline records |
| ∟ timestamp | string | false | Unix timestamp |
| ∟ ahpremium_rate | string | false | A/H premium rate |
| ∟ aprice | string | false | A-share price (CNY) |
| ∟ apreclose | string | false | A-share previous close (CNY) |
| ∟ hprice | string | false | H-share price (HKD) |
| ∟ hpreclose | string | false | H-share previous close (HKD) |
| ∟ currency_rate | string | false | CNH/HKD exchange rate |
| ∟ price_spread | string | false | Price spread |

#### 1.42 A/H 溢价盘中数据

- **Python SDK**：`MarketContext.ah_premium_intraday(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[A/H 溢价盘中数据](https://open.longbridge.com/zh-CN/docs/fundamental/market/ah-premium-intraday)

获取两地上市证券的盘中 A/H 溢价时间序列数据。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 两地上市股票的港股代码，例如 `939.HK` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.ah_premium_intraday("939.HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.ah_premium_intraday("939.HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "klines": [
      {
        "ahpremium_rate": "0.1523",
        "apreclose": "24.80",
        "aprice": "25.10",
        "currency_rate": "0.8920",
        "hpreclose": "19.20",
        "hprice": "19.50",
        "price_spread": "1.23",
        "timestamp": "1778198400"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [AhPremiumIntradayResponse](#AhPremiumIntradayResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### AhPremiumIntradayResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| klines | object[] | true | Intraday A/H premium kline data, see [AhPremiumKline](#AhPremiumKline) |
| ∟ timestamp | string | false | Unix 时间戳 |
| ∟ ahpremium_rate | string | false | A/H premium rate |
| ∟ aprice | string | false | A-share price (CNY) |
| ∟ apreclose | string | false | A-share previous close (CNY) |
| ∟ hprice | string | false | H-share price (HKD) |
| ∟ hpreclose | string | false | H-share previous close (HKD) |
| ∟ currency_rate | string | false | CNH/HKD exchange rate |
| ∟ price_spread | string | false | Price spread |

#### 1.43 经纪商每日持仓历史

- **Python SDK**：`MarketContext.broker_holding_daily(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[经纪商每日持仓历史](https://open.longbridge.com/zh-CN/docs/fundamental/market/broker-holding-daily)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可查询任意标的，包括美股。
:::

获取某一经纪商在港股上市证券中的每日持仓历史记录。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 港股代码，例如 `700.HK` |
| broker_id | string | 是 | 经纪商参与者 ID，例如 `B01224` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.broker_holding_daily("700.HK", "B01224")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.broker_holding_daily("700.HK", "B01224")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "date": "2026.05.13",
        "holding": "22903430",
        "chg": "7029132.0000",
        "ratio": "0.0025"
      },
      {
        "date": "2026.05.12",
        "holding": "15874298",
        "chg": "-2150000.0000",
        "ratio": "0.0017"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [BrokerHoldingDailyResponse](#BrokerHoldingDailyResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### BrokerHoldingDailyHistoryResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| list | object[] | true | 每日持仓历史记录， |
| ∟ date | string | true | 日期（如 `2026.05.13`） |
| ∟ holding | string | false | 总持股数 |
| ∟ chg | string | false | 日变动量 |
| ∟ ratio | string | false | 持仓比率 |

#### 1.44 经纪商持仓详情

- **Python SDK**：`MarketContext.broker_holding_detail(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[经纪商持仓详情](https://open.longbridge.com/zh-CN/docs/fundamental/market/broker-holding-detail)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可查询任意标的，包括美股。
:::

获取港股上市证券的完整经纪商持仓详情列表（所有经纪商及其持仓数量）。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 港股代码，例如 `700.HK` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.broker_holding_detail("700.HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.broker_holding_detail("700.HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "updated_at": "2026.05.13",
    "list": [
      {
        "parti_number": "B01224",
        "name": "HSBC Securities",
        "strong": false,
        "shares": {
          "value": "25100",
          "chg_1": "4000.0000",
          "chg_5": "6100.0000",
          "chg_20": "12600.0000",
          "chg_60": "8800.0000"
        },
        "ratio": {
          "value": "0.0025",
          "chg_1": "0.0004",
          "chg_5": "0.0006",
          "chg_20": "0.0012",
          "chg_60": "0.0009"
        }
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [BrokerHoldingDetailResponse](#BrokerHoldingDetailResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### BrokerHoldingDetailResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| updated_at | string | false | 最后更新日期 |
| list | object[] | true | 经纪商持仓明细，见 [BrokerHoldingItem](#BrokerHoldingItem) |

##### BrokerHoldingItem

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| parti_number | string | true | 经纪商参与者编号 |
| name | string | false | 经纪商名称 |
| strong | boolean | false | 是否为主要持仓者 |
| shares | object | false | 持股数量 |
| shares.value | string | false | 当前持股数 |
| shares.chg_1 | string | false | 1 日变动 |
| shares.chg_5 | string | false | 5 日变动 |
| shares.chg_20 | string | false | 20 日变动 |
| shares.chg_60 | string | false | 60 日变动 |
| ratio | object | false | 持仓比率 |
| ratio.value | string | false | 当前比率 |
| ratio.chg_1 | string | false | 1 日比率变动 |
| ratio.chg_5 | string | false | 5 日比率变动 |
| ratio.chg_20 | string | false | 20 日比率变动 |
| ratio.chg_60 | string | false | 60 日比率变动 |

#### 1.45 经纪商持仓

- **Python SDK**：`MarketContext.broker_positions(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[经纪商持仓](https://open.longbridge.com/zh-CN/docs/fundamental/market/broker-positions)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可查询任意标的，包括美股。
:::

查看港股券商持仓情况，包含主要买卖方和详细持仓列表。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 港股证券代码，例如 `700.HK` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.broker_positions("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.broker_positions("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "buy": [
      {
        "parti_number": "B01224",
        "name": "HSBC",
        "chg": "5000000",
        "strong": true
      }
    ],
    "sell": [
      {
        "parti_number": "B01274",
        "name": "Goldman Sachs HK",
        "chg": "-3000000",
        "strong": false
      }
    ],
    "updated_at": "2026.05.13"
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [BrokerHoldingResponse](#BrokerHoldingResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### BrokerHoldingResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| buy | object[] | 否 | 净买入经纪商列表， |
| ∟ parti_number | string | 是 | 经纪商参与者编号 |
| ∟ name | string | 否 | 经纪商名称 |
| ∟ chg | string | 否 | 持仓变动 |
| ∟ strong | boolean | 否 | 是否为主要持仓者 |
| sell | object[] | 否 | 净卖出经纪商列表， |
| ∟ parti_number | string | 是 | 经纪商参与者编号 |
| ∟ name | string | 否 | 经纪商名称 |
| ∟ chg | string | 否 | 持仓变动 |
| ∟ strong | boolean | 否 | 是否为主要持仓者 |
| updated_at | string | 否 | 最后更新时间 |

#### 1.46 指数成分股

- **Python SDK**：`MarketContext.index_components(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[指数成分股](https://open.longbridge.com/zh-CN/docs/fundamental/market/index-components)

获取指数或 ETF 的成分股列表，支持排序并显示涨跌统计。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 指数或 ETF 代码，例如 `HSI.HK`、`SPY.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.index_components("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.index_components("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "fall_num": 10,
    "flat_num": 3,
    "rise_num": 7,
    "stocks": [
      {
        "symbol": "9988.HK",
        "name": "BABA-W",
        "market": "HK",
        "last_done": "140.90",
        "prev_close": "132.80",
        "chg": "0.0610",
        "amount": "93828577",
        "inflow": "18483450",
        "balance": "13320299492",
        "circulating_shares": "19192403958",
        "total_shares": "19192403958",
        "trade_status": 105,
        "intro": "China's largest e-commerce platform",
        "delay": false,
        "tags": [
          "Top gainers"
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [IndexConstituentsResponse](#IndexConstituentsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### IndexConstituentsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| rise_num | integer | 否 | 上涨数量 |
| fall_num | integer | 否 | 下跌数量 |
| flat_num | integer | 否 | 平盘数量 |
| stocks | object[] | 是 | 成分股列表， |
| ∟ symbol | string | 是 | 证券代码 |
| ∟ name | string | 是 | 证券名称 |
| ∟ market | string | 否 | 市场 |
| ∟ last_done | string | 否 | 最新价 |
| ∟ prev_close | string | 否 | 前收盘价 |
| ∟ chg | string | 否 | 涨跌幅 |
| ∟ amount | string | 否 | 成交额 |
| ∟ inflow | string | 否 | 资金净流入 |
| ∟ circulating_shares | string | 否 | 流通股数 |
| ∟ total_shares | string | 否 | 总股数 |
| ∟ balance | string | 否 | 市值 |
| ∟ trade_status | integer | 否 | 交易状态码 |
| ∟ intro | string | 否 | 简介 |
| ∟ delay | boolean | 否 | 是否为延迟数据 |
| ∟ tags | string[] | 否 | 标签 |

#### 1.47 成交统计

- **Python SDK**：`MarketContext.trading_stats(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[成交统计](https://open.longbridge.com/zh-CN/docs/fundamental/market/trading-stats)

获取指定证券的成交统计数据，展示成交量的价格分布。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `700.HK` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.trading_stats("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.trading_stats("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "statistics": {
      "avgprice": "210.50",
      "buy": "45000000",
      "sell": "38000000",
      "neutral": "12000000",
      "total_amount": "95000000",
      "trades_count": "125000",
      "preclose": "208.20",
      "timestamp": "1778198400",
      "trade_date": [
        "2026-05-13"
      ]
    },
    "trades": [
      {
        "price": "210.00",
        "buy_amount": "5000000",
        "sell_amount": "4000000",
        "neutral_amount": "1000000"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [TradeStatsResponse](#TradeStatsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### TradeStatsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| statistics | object | 是 | 成交统计汇总 |
| statistics.avgprice | string | 否 | 平均成交价 |
| statistics.buy | string | 否 | 总买入成交量 |
| statistics.sell | string | 否 | 总卖出成交量 |
| statistics.neutral | string | 否 | 总中性成交量 |
| statistics.total_amount | string | 否 | 总成交额 |
| statistics.trades_count | string | 否 | 总成交笔数 |
| statistics.preclose | string | 否 | 前收盘价 |
| statistics.timestamp | string | 否 | 统计时间戳 |
| statistics.trade_date | string[] | 否 | 涵盖的交易日期 |
| trades | object[] | 否 | 按价位的成交分布， |
| ∟ price | string | 是 | 价位 |
| ∟ buy_amount | string | 否 | 该价位买入成交额 |
| ∟ sell_amount | string | 否 | 该价位卖出成交额 |
| ∟ neutral_amount | string | 否 | 该价位中性成交额 |


## 8. Market（市场状态与日历）

官方当前开发者文档未标注额外数据卡收费；个别接口可能受数据中心或行情基础权限限制。

### 1. 免费/基础权限

| 接口 | Python SDK | 权限/费用 |
| --- | --- | --- |
| [分红日历](https://open.longbridge.com/zh-CN/docs/market/calendar/dividend-calendar) | CalendarContext.finance_calendar(...) | 免费/基础 |
| [财报日历](https://open.longbridge.com/zh-CN/docs/market/calendar/earnings-calendar) | CalendarContext.finance_calendar(...) | 免费/基础 |
| [IPO 日历](https://open.longbridge.com/zh-CN/docs/market/calendar/ipo-calendar) | CalendarContext.finance_calendar(...) | 免费/基础 |
| [宏观日历](https://open.longbridge.com/zh-CN/docs/market/calendar/macro-calendar) | CalendarContext.finance_calendar(...) | 免费/基础 |
| [拆股日历](https://open.longbridge.com/zh-CN/docs/market/calendar/split-calendar) | CalendarContext.finance_calendar(...) | 免费/基础 |
| [港股 2025 年 Q1 历史温度](https://open.longbridge.com/zh-CN/docs/market/history-market-temperature) | QuoteContext.history_market_temperature(...) | 免费/基础 |
| [港股市场温度](https://open.longbridge.com/zh-CN/docs/market/market-temperature) | QuoteContext.market_temperature(...) | 免费/基础 |
| [市场状态](https://open.longbridge.com/zh-CN/docs/market/market-status) | MarketContext.market_status(...) | 免费/基础 |
| [人气排行分类](https://open.longbridge.com/zh-CN/docs/market/rank-categories) | MarketContext.rank_categories(...) | 免费/基础 |
| [人气排行榜](https://open.longbridge.com/zh-CN/docs/market/rank-list) | MarketContext.rank_list(...) | 免费/基础 |
| [异动股票（Top Movers）](https://open.longbridge.com/zh-CN/docs/market/top-movers) | MarketContext.top_movers(...) | 免费/基础 |
| [交易日历](https://open.longbridge.com/zh-CN/docs/market/trade-days) | QuoteContext.trading_days(...) | 免费/基础 |
| [交易时段](https://open.longbridge.com/zh-CN/docs/market/trade-session) | QuoteContext.trading_session(...) | 免费/基础 |
| [异动行情](https://open.longbridge.com/zh-CN/docs/market/unusual-items) | MarketContext.unusual_items(...) | 免费/基础 |

#### 1.1 分红日历

- **Python SDK**：`CalendarContext.finance_calendar(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[分红日历](https://open.longbridge.com/zh-CN/docs/market/calendar/dividend-calendar)

获取即将到来和历史分红事件，包含除息日、派息日和分红金额。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| start | string | YES | 开始日期，格式 YYYY-MM-DD |
| end | string | YES | 结束日期，格式 YYYY-MM-DD |
| market | string | NO | 市场筛选：US、HK、SH、SZ，不填则返回所有市场 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import CalendarContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = CalendarContext(config)

resp = ctx.dividend_calendar("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncCalendarContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncCalendarContext.create(config)

    resp = await ctx.dividend_calendar("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-04-30",
    "list": [
      {
        "date": "2026-04-30",
        "count": 275,
        "infos": [
          {
            "id": "12345",
            "symbol": "AAPL.US",
            "market": "US",
            "counter_name": "Apple Inc.",
            "event_type": "",
            "activity_type": "",
            "date": "2026-05-14",
            "datetime": "",
            "content": "",
            "star": 0,
            "currency": "",
            "icon": "",
            "chart_uid": "",
            "date_type": "",
            "financial_market_time": "",
            "data_kv": []
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [CalendarEventsResponse](#CalendarEventsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### CalendarEventsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 否 | 响应日期 |
| list | object[] | 是 | 日历日期分组列表，见 [CalendarDateGroup](#CalendarDateGroup) |

##### CalendarDateGroup

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 是 | 日期 |
| count | integer | 否 | 该日期的事件数量 |
| infos | object[] | 是 | 日历事件列表，见 [CalendarEventInfo](#CalendarEventInfo) |

##### CalendarEventInfo

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | 否 | 事件 ID |
| symbol | string | 否 | 证券代码 |
| market | string | 否 | 市场 |
| counter_name | string | 否 | 证券名称 |
| event_type | string | 否 | 事件类型 |
| activity_type | string | 否 | 活动类型 |
| date | string | 否 | 事件日期 |
| datetime | string | 否 | 事件时间 |
| date_type | string | 否 | 日期类型 |
| content | string | 否 | 事件内容描述 |
| currency | string | 否 | 货币 |
| star | integer | 否 | 重要性（1-3 星） |
| icon | string | 否 | 图标链接 |
| chart_uid | string | 否 | 图表标识符 |
| financial_market_time | string | 否 | 金融市场时间 |
| data_kv | object[] | 否 | 键值数据对 |

#### 1.2 财报日历

- **Python SDK**：`CalendarContext.finance_calendar(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[财报日历](https://open.longbridge.com/zh-CN/docs/market/calendar/earnings-calendar)

浏览即将发布的财报及近期业绩，包含 EPS 和营收预期。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| start | string | YES | 开始日期，格式 YYYY-MM-DD |
| end | string | YES | 结束日期，格式 YYYY-MM-DD |
| market | string | NO | 市场筛选：US、HK、SH、SZ，不填则返回所有市场 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import CalendarContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = CalendarContext(config)

resp = ctx.earnings_calendar("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncCalendarContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncCalendarContext.create(config)

    resp = await ctx.earnings_calendar("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-04-30",
    "list": [
      {
        "date": "2026-04-30",
        "count": 2228,
        "infos": [
          {
            "id": "12345",
            "symbol": "AAPL.US",
            "market": "US",
            "counter_name": "Apple Inc.",
            "event_type": "",
            "activity_type": "",
            "date": "2026-05-14",
            "datetime": "",
            "content": "",
            "star": 0,
            "currency": "",
            "icon": "",
            "chart_uid": "",
            "date_type": "",
            "financial_market_time": "",
            "data_kv": []
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [CalendarEventsResponse](#CalendarEventsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### CalendarEventsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 否 | 响应日期 |
| list | object[] | 是 | 日历日期分组列表，见 [CalendarDateGroup](#CalendarDateGroup) |

##### CalendarDateGroup

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 是 | 日期 |
| count | integer | 否 | 该日期的事件数量 |
| infos | object[] | 是 | 日历事件列表，见 [CalendarEventInfo](#CalendarEventInfo) |

##### CalendarEventInfo

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | 否 | 事件 ID |
| symbol | string | 否 | 证券代码 |
| market | string | 否 | 市场 |
| counter_name | string | 否 | 证券名称 |
| event_type | string | 否 | 事件类型 |
| activity_type | string | 否 | 活动类型 |
| date | string | 否 | 事件日期 |
| datetime | string | 否 | 事件时间 |
| date_type | string | 否 | 日期类型 |
| content | string | 否 | 事件内容描述 |
| currency | string | 否 | 货币 |
| star | integer | 否 | 重要性（1-3 星） |
| icon | string | 否 | 图标链接 |
| chart_uid | string | 否 | 图表标识符 |
| financial_market_time | string | 否 | 金融市场时间 |
| data_kv | object[] | 否 | 键值数据对 |

#### 1.3 IPO 日历

- **Python SDK**：`CalendarContext.finance_calendar(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[IPO 日历](https://open.longbridge.com/zh-CN/docs/market/calendar/ipo-calendar)

获取即将上市和近期 IPO 信息，包含预计发行价和上市日期。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| start | string | YES | 开始日期，格式 YYYY-MM-DD |
| end | string | YES | 结束日期，格式 YYYY-MM-DD |
| market | string | NO | 市场筛选：US、HK、SH、SZ，不填则返回所有市场 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import CalendarContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = CalendarContext(config)

resp = ctx.ipo_calendar("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncCalendarContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncCalendarContext.create(config)

    resp = await ctx.ipo_calendar("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-04-30",
    "list": [
      {
        "date": "2026-05-05",
        "count": 1,
        "infos": [
          {
            "id": "12345",
            "symbol": "AAPL.US",
            "market": "US",
            "counter_name": "Apple Inc.",
            "event_type": "",
            "activity_type": "",
            "date": "2026-05-14",
            "datetime": "",
            "content": "",
            "star": 0,
            "currency": "",
            "icon": "",
            "chart_uid": "",
            "date_type": "",
            "financial_market_time": "",
            "data_kv": []
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [CalendarEventsResponse](#CalendarEventsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### CalendarEventsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 否 | 响应日期 |
| list | object[] | 是 | 日历日期分组列表，见 [CalendarDateGroup](#CalendarDateGroup) |

##### CalendarDateGroup

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 是 | 日期 |
| count | integer | 否 | 该日期的事件数量 |
| infos | object[] | 是 | 日历事件列表，见 [CalendarEventInfo](#CalendarEventInfo) |

##### CalendarEventInfo

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | 否 | 事件 ID |
| symbol | string | 否 | 证券代码 |
| market | string | 否 | 市场 |
| counter_name | string | 否 | 证券名称 |
| event_type | string | 否 | 事件类型 |
| activity_type | string | 否 | 活动类型 |
| date | string | 否 | 事件日期 |
| datetime | string | 否 | 事件时间 |
| date_type | string | 否 | 日期类型 |
| content | string | 否 | 事件内容描述 |
| currency | string | 否 | 货币 |
| star | integer | 否 | 重要性（1-3 星） |
| icon | string | 否 | 图标链接 |
| chart_uid | string | 否 | 图表标识符 |
| financial_market_time | string | 否 | 金融市场时间 |
| data_kv | object[] | 否 | 键值数据对 |

#### 1.4 宏观日历

- **Python SDK**：`CalendarContext.finance_calendar(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[宏观日历](https://open.longbridge.com/zh-CN/docs/market/calendar/macro-calendar)

获取即将发布的[宏观经济数据](https://longbridge.com/calendar/macrodata)，如 CPI、GDP 和美联储会议等。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| start | string | YES | 开始日期，格式 YYYY-MM-DD |
| end | string | YES | 结束日期，格式 YYYY-MM-DD |
| market | string | NO | 市场筛选：US、HK、SH、SZ，不填则返回所有市场 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import CalendarContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = CalendarContext(config)

resp = ctx.macro_calendar("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncCalendarContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncCalendarContext.create(config)

    resp = await ctx.macro_calendar("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-04-30",
    "list": [
      {
        "date": "2026-05-02",
        "count": 0,
        "infos": [
          {
            "id": "12345",
            "symbol": "AAPL.US",
            "market": "US",
            "counter_name": "Apple Inc.",
            "event_type": "",
            "activity_type": "",
            "date": "2026-05-14",
            "datetime": "",
            "content": "",
            "star": 0,
            "currency": "",
            "icon": "",
            "chart_uid": "",
            "date_type": "",
            "financial_market_time": "",
            "data_kv": []
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [CalendarEventsResponse](#CalendarEventsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### CalendarEventsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 否 | 响应日期 |
| list | object[] | 是 | 日历日期分组列表，见 [CalendarDateGroup](#CalendarDateGroup) |

##### CalendarDateGroup

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 是 | 日期 |
| count | integer | 否 | 该日期的事件数量 |
| infos | object[] | 是 | 日历事件列表，见 [CalendarEventInfo](#CalendarEventInfo) |

##### CalendarEventInfo

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | 否 | 事件 ID |
| symbol | string | 否 | 证券代码 |
| market | string | 否 | 市场 |
| counter_name | string | 否 | 证券名称 |
| event_type | string | 否 | 事件类型 |
| activity_type | string | 否 | 活动类型 |
| date | string | 否 | 事件日期 |
| datetime | string | 否 | 事件时间 |
| date_type | string | 否 | 日期类型 |
| content | string | 否 | 事件内容描述 |
| currency | string | 否 | 货币 |
| star | integer | 否 | 重要性（1-3 星） |
| icon | string | 否 | 图标链接 |
| chart_uid | string | 否 | 图表标识符 |
| financial_market_time | string | 否 | 金融市场时间 |
| data_kv | object[] | 否 | 键值数据对 |

#### 1.5 拆股日历

- **Python SDK**：`CalendarContext.finance_calendar(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[拆股日历](https://open.longbridge.com/zh-CN/docs/market/calendar/split-calendar)

获取即将到来和历史拆股及合股事件。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| start | string | YES | 开始日期，格式 YYYY-MM-DD |
| end | string | YES | 结束日期，格式 YYYY-MM-DD |
| market | string | NO | 市场筛选：US、HK、SH、SZ，不填则返回所有市场 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import CalendarContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = CalendarContext(config)

resp = ctx.split_calendar("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncCalendarContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncCalendarContext.create(config)

    resp = await ctx.split_calendar("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-04-30",
    "list": [
      {
        "date": "2026-04-30",
        "count": 2228,
        "infos": [
          {
            "id": "12345",
            "symbol": "AAPL.US",
            "market": "US",
            "counter_name": "Apple Inc.",
            "event_type": "",
            "activity_type": "",
            "date": "2026-05-14",
            "datetime": "",
            "content": "",
            "star": 0,
            "currency": "",
            "icon": "",
            "chart_uid": "",
            "date_type": "",
            "financial_market_time": "",
            "data_kv": []
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [CalendarEventsResponse](#CalendarEventsResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### CalendarEventsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 否 | 响应日期 |
| list | object[] | 是 | 日历日期分组列表，见 [CalendarDateGroup](#CalendarDateGroup) |

##### CalendarDateGroup

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| date | string | 是 | 日期 |
| count | integer | 否 | 该日期的事件数量 |
| infos | object[] | 是 | 日历事件列表，见 [CalendarEventInfo](#CalendarEventInfo) |

##### CalendarEventInfo

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | 否 | 事件 ID |
| symbol | string | 否 | 证券代码 |
| market | string | 否 | 市场 |
| counter_name | string | 否 | 证券名称 |
| event_type | string | 否 | 事件类型 |
| activity_type | string | 否 | 活动类型 |
| date | string | 否 | 事件日期 |
| datetime | string | 否 | 事件时间 |
| date_type | string | 否 | 日期类型 |
| content | string | 否 | 事件内容描述 |
| currency | string | 否 | 货币 |
| star | integer | 否 | 重要性（1-3 星） |
| icon | string | 否 | 图标链接 |
| chart_uid | string | 否 | 图表标识符 |
| financial_market_time | string | 否 | 金融市场时间 |
| data_kv | object[] | 否 | 键值数据对 |

#### 1.6 港股 2025 年 Q1 历史温度

- **Python SDK**：`QuoteContext.history_market_temperature(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[港股 2025 年 Q1 历史温度](https://open.longbridge.com/zh-CN/docs/market/history-market-temperature)
- **HTTP**：`GET /v1/quote/history_market_temperature`

﻿---
title: 历史市场温度
slug: /market/history-market-temperature
sidebar_position: 3
---

该接口用于获取历史市场温度。

#### Request

##### Parameters

| Name       | Type   | Required | Description                              |
| ---------- | ------ | -------- | ---------------------------------------- |
| market     | string | YES      | 市场，目前支持 US、HK、SG、CN            |
| start_date | string | YES      | 开始日期，最小到 2016 年，比如：20240101 |
| end_date   | string | YES      | 结束日期，比如：20250101                 |

##### Request Example

###### Python 示例

```python
import datetime
from longbridge.openapi import QuoteContext, Config, Market, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
resp = ctx.history_market_temperature(Market.US, datetime.date(2024, 1, 1), datetime.date(2025, 1, 1))
print(resp)
```

###### Python 异步示例

```python
import asyncio
import datetime
from longbridge.openapi import AsyncQuoteContext, Config, Market, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)
    resp = await ctx.history_market_temperature(Market.US, datetime.date(2024, 1, 1), datetime.date(2025, 1, 1))
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "data": {
    "type": "month",
    "list": [
      {
        "timestamp": 1580486400,
        "temperature": 36,
        "valuation": 12,
        "sentiment": 46
      },
      {
        "timestamp": 1582992000,
        "temperature": 46,
        "valuation": 12,
        "sentiment": 46
      }
    ]
  }
}
```

###### Response Status

| Status | Description | Schema                                                                   |
| ------ | ----------- | ------------------------------------------------------------------------ |
| 200    | 返回成功    | [HistoryMarketTemperatureResponse](#history_market_temperature_response) |
| 400    | 参数错误    | None                                                                     |

<aside className="success">
</aside>

#### Schemas

##### HistoryMarketTemperatureResponse

| Name         | Type     | Required | Description                                 |
| ------------ | -------- | -------- | ------------------------------------------- |
| list         | object[] | true     | 历史温度列表                                |
| ∟timestamp   | integer  | true     | 时间戳                                      |
| ∟temperature | integer  | true     | 温度值                                      |
| ∟valuation   | integer  | true     | 估值值                                      |
| ∟sentiment   | integer  | true     | 情绪值                                      |
| type         | string   | true     | 数据颗粒度 <br />day: 日;week: 周;month: 月 |

#### 错误码

| 业务错误码 | 描述           | 排查建议                 |
| ---------- | -------------- | ------------------------ |
| 2601500    | 服务端内部错误 | 请重试或联系技术人员处理 |

#### 1.7 港股市场温度

- **Python SDK**：`QuoteContext.market_temperature(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[港股市场温度](https://open.longbridge.com/zh-CN/docs/market/market-temperature)
- **HTTP**：`GET /v1/quote/market_temperature`

﻿---
title: 市场温度
slug: /market/market-temperature
sidebar_position: 2
---

获取当前市场温度

#### Request

##### Parameters

| Name   | Type   | Required | Description                   |
| ------ | ------ | -------- | ----------------------------- |
| market | string | YES      | 市场，目前支持 US、HK、SG、CN |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, Market, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)
resp = ctx.market_temperature(Market.US)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, Market, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)
    resp = await ctx.market_temperature(Market.US)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "data": {
    "temperature": 50,
    "description": "温度适宜，保持平稳",
    "valuation": 23,
    "sentiment": 78,
    "updated_at": 1744616612
  }
}
```

###### Response Status

| Status | Description | Schema                                                    |
| ------ | ----------- | --------------------------------------------------------- |
| 200    | 返回成功    | [MarketTemperatureResponse](#market_temperature_response) |
| 400    | 参数错误    | None                                                      |

<aside className="success">
</aside>

#### Schemas

##### MarketTemperatureResponse

| Name        | Type    | Required | Description |
| ----------- | ------- | -------- | ----------- |
| temperature | integer | true     | 温度值      |
| description | string  | true     | 温度描述    |
| valuation   | integer | true     | 市场估值    |
| sentiment   | integer | true     | 市场情绪    |
| updated_at  | integer | true     | 更新时间    |

#### 错误码

| 业务错误码 | 描述           | 排查建议                 |
| ---------- | -------------- | ------------------------ |
| 2601500    | 服务端内部错误 | 请重试或联系技术人员处理 |

#### 1.8 市场状态

- **Python SDK**：`MarketContext.market_status(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[市场状态](https://open.longbridge.com/zh-CN/docs/market/market-status)

获取各交易所当前的开市/休市状态。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| market | string | 否 | 市场代码：`US`、`HK`、`SH`、`SZ`、`SG`。不填则返回全部市场。 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.market_status("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.market_status("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "market_time": [
      {
        "market": "US",
        "delay_sub_status": 0,
        "delay_timestamp": "0",
        "delay_trade_status": 0
      },
      {
        "market": "HK",
        "delay_sub_status": 0,
        "delay_timestamp": "0",
        "delay_trade_status": 0
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [MarketStatusResponse](#MarketStatusResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### MarketStatusResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| market_time | object[] | 是 | 市场状态列表， |
| ∟ market | string | 是 | 市场：`US`、`HK`、`CN`、`SG`、`Crypto` |
| ∟ delay_sub_status | integer | 否 | 延迟订阅状态 |
| ∟ delay_timestamp | string | 否 | 延迟时间戳 |
| ∟ delay_trade_status | integer | 否 | 延迟交易状态 |

#### 1.9 人气排行分类

- **Python SDK**：`MarketContext.rank_categories(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[人气排行分类](https://open.longbridge.com/zh-CN/docs/market/rank-categories)

获取人气排行榜的标签分类配置，`second_tags[].key` 可传入 `rank_list`。

#### Parameters

> **SDK 方法参数。**

此方法无参数。

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.rank_categories()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.rank_categories()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "first_tags": [
      {
        "key": "ib_hot",
        "name": "热度排行",
        "second_tags": [
          { "key": "ib_hot_all-us", "name": "美股总热度", "market": "US" },
          { "key": "ib_hot_all-hk", "name": "港股总热度", "market": "HK" },
          { "key": "ib_hot_all-cn", "name": "A 股总热度", "market": "CN" }
        ]
      },
      {
        "key": "ib_change",
        "name": "涨跌排行",
        "second_tags": [
          { "key": "ib_change_top-us", "name": "美股涨幅榜", "market": "US" },
          { "key": "ib_change_top-hk", "name": "港股涨幅榜", "market": "HK" }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [RankCategoriesResponse](#RankCategoriesResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### RankCategoriesResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| first_tags | object[] | false | 一级分类列表 |
| ∟ key | string | false | 一级分类键值 |
| ∟ name | string | false | 一级分类名称 |
| ∟ second_tags | object[] | false | 二级分类列表 |
| ∟ ∟ key | string | false | 二级分类键值，可传入 `rank_list` 的 `key` 参数 |
| ∟ ∟ name | string | false | 二级分类名称 |
| ∟ ∟ market | string | false | 所属市场：`US`、`HK`、`CN`、`SG` |

#### 1.10 人气排行榜

- **Python SDK**：`MarketContext.rank_list(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[人气排行榜](https://open.longbridge.com/zh-CN/docs/market/rank-list)

根据排行榜标签 key 获取股票排行。key 来自 `rank_categories` 的 `second_tags[].key`，例如 `hot_all-us`（美股总热度）。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| key | string | 是 | 排行榜标签键值，来自 `rank_categories` 的 `second_tags[].key` |
| need_article | boolean | 否 | 是否返回关联文章，默认 `false` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.rank_list("hot_all-us")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.rank_list("hot_all-us", need_article=False)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "bmp": false,
    "lists": [
      {
        "code": "MU",
        "symbol": "MU.US",
        "name": "美光科技",
        "last_done": "698.740",
        "chg": "0.0252",
        "change": "17.200",
        "inflow": "-347041642",
        "market_cap": "787992890796",
        "industry": "半导体厂商",
        "pre_post_price": "726.600",
        "pre_post_chg": "0.0399",
        "amplitude": "0.1082",
        "five_day_chg": "-0.0885",
        "turnover_rate": "0.0550",
        "volume_rate": "1.11",
        "pb_ttm": "32.68"
      }
    ]
  }
}
```

> 说明：响应中包含更多附加字段，上述为主要字段。

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [RankListResponse](#RankListResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### RankListResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| bmp | boolean | false | 是否为盘前预览数据 |
| lists | object[] | false | 排行榜股票列表 |
| ∟ code | string | false | 股票代码（如 `MU`） |
| ∟ symbol | string | false | 标的代码，格式为 `代码.市场`（如 `MU.US`） |
| ∟ name | string | false | 证券名称 |
| ∟ last_done | string | false | 最新成交价 |
| ∟ chg | string | false | 涨跌幅（小数比率，如 `0.0252` 表示 2.52%） |
| ∟ change | string | false | 价格涨跌额（如 `17.200`） |
| ∟ inflow | string | false | 净流入资金（单位：所属市场货币） |
| ∟ market_cap | string | false | 市值 |
| ∟ industry | string | false | 行业分类 |
| ∟ pre_post_price | string | false | 盘前/盘后价格 |
| ∟ pre_post_chg | string | false | 盘前/盘后涨跌幅（小数比率） |
| ∟ amplitude | string | false | 振幅（小数比率） |
| ∟ five_day_chg | string | false | 5 日涨跌幅（小数比率） |
| ∟ turnover_rate | string | false | 换手率（小数比率） |
| ∟ volume_rate | string | false | 量比 |
| ∟ pb_ttm | string | false | 市净率（TTM） |

> 说明：响应中包含更多附加字段，上述为主要字段。

#### 1.11 异动股票（Top Movers）

- **Python SDK**：`MarketContext.top_movers(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[异动股票（Top Movers）](https://open.longbridge.com/zh-CN/docs/market/top-movers)

获取价格波动超过近 20 个交易日标准差的异动股票，系统自动关联相关新闻解读异动原因。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| markets | string[] | 否 | 市场列表：`HK`、`US`、`CN`、`SG`；不传返回所有市场 |
| sort | integer | 否 | 排序方式：`0`=时间（最新优先），`1`=涨跌幅，`2`=热度（默认） |
| date | string | 否 | 指定日期，格式 `YYYY-MM-DD`；不传返回最新数据 |
| limit | integer | 否 | 返回条数，默认 20 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.top_movers(markets=["HK", "US"], sort=2, limit=20)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.top_movers(markets=["HK", "US"], sort=2, limit=20)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "events": [
      {
        "stock": {
          "code": "TSLA",
          "counter_id": "ST/US/TSLA",
          "name": "特斯拉",
          "change": "-0.0388",
          "last_done": "404.110",
          "market": "US",
          "labels": ["汽车制造商"],
          "logo": "https://assets.lbkrs.com/ticker/ST/US/TSLA.png",
          "trade_status": 0
        },
        "timestamp": "1779202097",
        "alert_reason": "波动超 20 日均值",
        "alert_type": 11,
        "post": null
      }
    ],
    "next_params": {
      "visited": ["11098290", "11098478", "11099705"]
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [TopMoversResponse](#TopMoversResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### TopMoversResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| events | object[] | false | 异动股票列表 |
| ∟ stock | object | false | 股票基本信息 |
| ∟ ∟ code | string | false | 股票代码（如 `TSLA`） |
| ∟ ∟ counter_id | string | false | Counter ID（如 `ST/US/TSLA`） |
| ∟ ∟ name | string | false | 证券名称 |
| ∟ ∟ change | string | false | 涨跌幅（如 `-0.0388`） |
| ∟ ∟ last_done | string | false | 最新成交价 |
| ∟ ∟ market | string | false | 市场：`US`、`HK`、`CN`、`SG` |
| ∟ ∟ labels | string[] | false | 行业 / 主题标签 |
| ∟ ∟ logo | string | false | Logo 图片 URL |
| ∟ ∟ trade_status | integer | false | 交易状态码 |
| ∟ timestamp | string | false | 异动时间（Unix 秒，字符串格式） |
| ∟ alert_reason | string | false | 异动原因描述 |
| ∟ alert_type | integer | false | 异动类型代码 |
| ∟ post | object | false | 关联新闻文章（复杂对象，包含 `title`、`description_html`、`published_at` 等字段；无关联新闻时为 `null`） |
| next_params | object | false | 翻页参数对象，传入下次请求以获取下一页 |

#### 1.12 交易日历

- **Python SDK**：`QuoteContext.trading_days(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[交易日历](https://open.longbridge.com/zh-CN/docs/market/trade-days)

该接口用于获取市场的交易日信息。

:::info

[业务指令](../../socket/biz_command)：`9`

:::

#### Request

##### Parameters

| Name    | Type   | Required | Description                                                                                                                                              |
| ------- | ------ | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| market  | string | 是       | 市场 <br /><br />**可选值：**<br/>`US` - 美股市场<br/>`HK` - 港股市场<br/>`CN` - A 股市场<br/>`SG` - 新加坡市场                                          |
| beg_day | string | 是       | 开始时间，使用 `YYMMDD` 格式，例如：`20220401`                                                                                                           |
| end_day | string | 是       | 结束时间，使用 `YYMMDD` 格式，例如：`20220420` <br/><br/>**校验规则：**<br/> `开始时间` 和 `结束时间`，间隔不能大于一个月 <br/> 仅支持查询最近一年的数据 |

##### Protobuf

```protobuf
message MarketTradeDayRequest {
  string market = 1;
  string beg_day = 2;
  string end_day = 3;
}
```

##### Request Example

###### Python 示例

```python
from datetime import date
from longbridge.openapi import QuoteContext, Config, Market, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.trading_days(Market.HK, date(2022, 1, 1), date(2022, 2, 1))
print(resp)
```

###### Python 异步示例

```python
import asyncio
from datetime import date
from longbridge.openapi import AsyncQuoteContext, Config, Market, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.trading_days(Market.HK, date(2022, 1, 1), date(2022, 2, 1))
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name           | Type     | Description                |
| -------------- | -------- | -------------------------- |
| trade_day      | string[] | 交易日，使用 `YYMMDD` 格式 |
| half_trade_day | string[] | 半日市，使用 `YYMMDD` 格式 |

##### Protobuf

```protobuf
message MarketTradeDayResponse {
  repeated string trade_day = 1;
  repeated string half_trade_day = 2;
}
```

##### Response JSON Example

```json
{
  "trade_day": [
    "20220120",
    "20220121",
    "20220124",
    "20220125",
    "20220126",
    "20220127",
    "20220128",
    "20220204",
    "20220207",
    "20220208",
    "20220209",
    "20220210"
  ],
  "half_trade_day": ["20220131"]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                             |
| ---------- | ---------- | -------------- | ------------------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败               |
| 3          | 301606     | 限流           | 降低请求频次                         |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理             |
| 7          | 301600     | 请求数据非法   | 检查请求的市场，日期是否在正确范围内 |

#### 1.13 交易时段

- **Python SDK**：`QuoteContext.trading_session(...)`
- **权限/费用**：开通 OpenAPI 后自动获得，无需额外购买
- **官方页面**：[交易时段](https://open.longbridge.com/zh-CN/docs/market/trade-session)

该接口用于获取各市场当日交易时段。

:::info

[业务指令](../../socket/biz_command)：`8`

:::

#### Request

##### Request Example

###### Python 示例

```python
from longbridge.openapi import QuoteContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = QuoteContext(config)

resp = ctx.trading_session()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncQuoteContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncQuoteContext.create(config)

    resp = await ctx.trading_session()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Properties

| Name                 | Type     | Description                                                                                 |
| -------------------- | -------- | ------------------------------------------------------------------------------------------- |
| market_trade_session | object[] | 市场交易时段                                                                                |
| ∟ market             | string   | 市场<br/><br/>`US` - 美股市场<br/>`HK` - 港股市场<br/>`CN` - A 股市场<br/>`SG` - 新加坡市场 |
| ∟ trade_session      | object[] | 交易时段                                                                                    |
| ∟∟ beg_time          | int32    | 交易开始时间，格式：`hhmm` 例如：`900`                                                      |
| ∟∟ end_time          | int32    | 交易结束时间，格式：`hhmm` 例如：`1400`                                                     |
| ∟∟ trade_session     | int32    | 交易时段，详见 [TradeSession](../objects#tradesession---交易时段)                           |

##### Protobuf

```protobuf
message MarketTradePeriodResponse {
  repeated MarketTradePeriod market_trade_session = 1;
}

message MarketTradePeriod {
  string market = 1;
  repeated TradePeriod trade_session = 2;
}

message TradePeriod {
  int32 beg_time = 1;
  int32 end_time = 2;
  TradeSession trade_session = 3;
}
```

##### Response JSON Example

```json
{
  "market_trade_session": [
    {
      "market": "US",
      "trade_session": [
        {
          "beg_time": 930,
          "end_time": 1600
        },
        {
          "beg_time": 400,
          "end_time": 930,
          "trade_session": 1
        },
        {
          "beg_time": 1600,
          "end_time": 2000,
          "trade_session": 2
        }
      ]
    },
    {
      "market": "HK",
      "trade_session": [
        {
          "beg_time": 930,
          "end_time": 1200
        },
        {
          "beg_time": 1300,
          "end_time": 1600
        }
      ]
    },
    {
      "market": "CN",
      "trade_session": [
        {
          "beg_time": 930,
          "end_time": 1130
        },
        {
          "beg_time": 1300,
          "end_time": 1457
        }
      ]
    },
    {
      "market": "SG",
      "trade_session": [
        {
          "beg_time": 900,
          "end_time": 1200
        },
        {
          "beg_time": 1300,
          "end_time": 1700
        }
      ]
    }
  ]
}
```

#### 错误码

| 协议错误码 | 业务错误码 | 描述           | 排查建议                 |
| ---------- | ---------- | -------------- | ------------------------ |
| 3          | 301600     | 无效的请求     | 请求参数有误或解包失败   |
| 3          | 301606     | 限流           | 降低请求频次             |
| 7          | 301602     | 服务端内部错误 | 请重试或联系技术人员处理 |

#### 1.14 异动行情

- **Python SDK**：`MarketContext.unusual_items(...)`
- **权限/费用**：官方页面未标注额外行情卡收费，仍需 OpenAPI 权限
- **官方页面**：[异动行情](https://open.longbridge.com/zh-CN/docs/market/unusual-items)

识别市场异动，包括价格异常波动、成交量激增等非正常交易行为。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| market | string | 是 | 市场代码：`US`、`HK`、`SH`、`SZ`、`SG` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import MarketContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = MarketContext(config)

resp = ctx.unusual_items("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncMarketContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncMarketContext.create(config)

    resp = await ctx.unusual_items("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "all_off": false,
    "changes": [
      {
        "symbol": "TSLA.US",
        "name": "Tesla Inc.",
        "alert_name": "大宗交易",
        "alert_time": 1778198400000,
        "emotion": 1,
        "change_values": [
          "+5.2%"
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功     | [AnomalyResponse](#AnomalyResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### AnomalyResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| all_off | boolean | false | 是否全局关闭异动提醒 |
| changes | object[] | false | 市场异动事件列表， |
| ∟ symbol | string | true | 证券代码 |
| ∟ name | string | false | 证券名称 |
| ∟ alert_name | string | false | 异动类型名称 |
| ∟ alert_time | integer | false | 异动时间（Unix 时间戳，毫秒） |
| ∟ emotion | integer | false | 情绪方向：`1`=正面/上涨，`2`=负面/下跌 |
| ∟ change_values | string[] | false | 变化数值字符串列表 |


## 9. News & Contents（资讯、社区与股单）

官方当前开发者文档未标注额外数据卡收费；创建讨论/回复有接口级频率限制。

### 1. 免费/基础权限

| 接口 | Python SDK | 权限/费用 |
| --- | --- | --- |
| [个股资讯](https://open.longbridge.com/zh-CN/docs/content/news/news) | ContentContext.news(...) | 免费/基础 |
| [添加标的到股单](https://open.longbridge.com/zh-CN/docs/content/sharelist/add-securities) | SharelistContext.add_securities(...) | 免费/基础 |
| [创建股单](https://open.longbridge.com/zh-CN/docs/content/sharelist/create-sharelist) | SharelistContext.create_sharelist(...) | 免费/基础 |
| [删除股单](https://open.longbridge.com/zh-CN/docs/content/sharelist/delete-sharelist) | SharelistContext.delete_sharelist(...) | 免费/基础 |
| [股单列表](https://open.longbridge.com/zh-CN/docs/content/sharelist/list-sharelist) | SharelistContext.list_sharelist(...) | 免费/基础 |
| [热门股单](https://open.longbridge.com/zh-CN/docs/content/sharelist/popular-sharelist) | SharelistContext.popular(...) | 免费/基础 |
| [从股单移除标的](https://open.longbridge.com/zh-CN/docs/content/sharelist/remove-securities) | SharelistContext.remove_securities(...) | 免费/基础 |
| [股单详情](https://open.longbridge.com/zh-CN/docs/content/sharelist/sharelist-detail) | SharelistContext.detail(...) | 免费/基础 |
| [股单标的排序](https://open.longbridge.com/zh-CN/docs/content/sharelist/sort-securities) | SharelistContext.sort_securities(...) | 免费/基础 |
| [更新股单](https://open.longbridge.com/zh-CN/docs/content/sharelist/update-sharelist) | SharelistContext.update_sharelist(...) | 免费/基础 |
| [创建讨论](https://open.longbridge.com/zh-CN/docs/content/topics/create-topic) | ContentContext.create_topic(...) | 免费/基础 |
| [创建讨论回复](https://open.longbridge.com/zh-CN/docs/content/topics/create-topic-reply) | ContentContext.create_topic_reply(...) | 免费/基础 |
| [我的讨论](https://open.longbridge.com/zh-CN/docs/content/topics/my-topics) | ContentContext.topics_mine(...) | 免费/基础 |
| [讨论详情](https://open.longbridge.com/zh-CN/docs/content/topics/topic-detail) | ContentContext.topic_detail(...) | 免费/基础 |
| [讨论回复](https://open.longbridge.com/zh-CN/docs/content/topics/topic-replies) | ContentContext.list_topic_replies(...) | 免费/基础 |
| [标的社区讨论](https://open.longbridge.com/zh-CN/docs/content/topics/topics) | ContentContext.topics(...) | 免费/基础 |

#### 1.1 个股资讯

- **Python SDK**：`ContentContext.news(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[个股资讯](https://open.longbridge.com/zh-CN/docs/content/news/news)
- **HTTP**：`GET /v1/content/{symbol}/news`

获取指定股票的资讯列表。完整资讯流可访问 [资讯](https://longbridge.com/news)。

#### Request

##### Path Parameters

| Name   | Type   | Required | Description                                    |
| ------ | ------ | -------- | ---------------------------------------------- |
| symbol | string | YES      | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US` |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import ContentContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ContentContext(config)

resp = ctx.news("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncContentContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncContentContext.create(config)

    resp = await ctx.news("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "279528757",
        "title": "Beats 跨界联动耐克破圈！苹果欲再掀可穿戴消费热潮 耐克押注 "运动科技" 叙事",
        "description": "苹果公司旗下的 Beats 与耐克合作推出限量版 Powerbeats Pro 2 耳机，耳机上印有耐克的 Swoosh 标志。该耳机将于 3 月 20 日在线及部分 Apple Store 发售，售价为 250 美元。这是 Beats 首次与外部运动品牌合作，标志着两家公司在品牌和产品生态上的进一步协同。耳机具备实时心率追踪功能，续航时间最长可达 45 小时。",
        "url": "https://longbridge.com/news/279528757",
        "published_at": "1773805586",
        "comments_count": 0,
        "likes_count": 0,
        "shares_count": 0
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                                    |
| ------ | ----------- | ----------------------------------------- |
| 200    | 返回成功    | [news_response](#schemanews_response)     |
| 500    | 内部错误    | None                                      |

#### Schemas

##### news_response

| Name               | Type      | Required | Description                   |
| ------------------ | --------- | -------- | ----------------------------- |
| items              | object[]  | true     | 资讯列表                      |
| ∟ id               | string    | true     | 资讯 ID                       |
| ∟ title            | string    | true     | 标题                          |
| ∟ description      | string    | true     | 摘要/描述                     |
| ∟ url              | string    | true     | 资讯详情链接                  |
| ∟ published_at     | string    | true     | 发布时间，Unix 时间戳（秒）   |
| ∟ comments_count   | int32     | true     | 评论数                        |
| ∟ likes_count      | int32     | true     | 点赞数                        |
| ∟ shares_count     | int32     | true     | 分享数                        |

#### 1.2 添加标的到股单

- **Python SDK**：`SharelistContext.add_securities(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[添加标的到股单](https://open.longbridge.com/zh-CN/docs/content/sharelist/add-securities)

向股单中添加一个或多个标的。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | integer | 是 | 股单 ID |
| symbols | string[] | 是 | 待添加的标的代码 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import SharelistContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = SharelistContext(config)

ctx.add_securities(123, ["TSLA.US", "AAPL.US"])
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncSharelistContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncSharelistContext.create(config)

    await ctx.add_securities(123, ["TSLA.US", "AAPL.US"])

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success"
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | None   |
| 400    | 请求错误    | None   |

#### 1.3 创建股单

- **Python SDK**：`SharelistContext.create_sharelist(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[创建股单](https://open.longbridge.com/zh-CN/docs/content/sharelist/create-sharelist)

创建新的社区自选股列表，可选择预设初始证券。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| name | string | 是 | 股单名称 |
| description | string | 否 | 描述 |
| securities | string[] | 否 | 初始证券代码列表，例如 `["AAPL.US", "NVDA.US"]` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import SharelistContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = SharelistContext(config)

resp = ctx.create_sharelist(name="AI Picks", description="Top AI infrastructure stocks")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncSharelistContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncSharelistContext.create(config)

    resp = await ctx.create_sharelist(name="AI Picks", description="Top AI infrastructure stocks")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 15922
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [CreateSharelistResponse](#CreateSharelistResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### CreateSharelistResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | int64 | true | 新创建股单的 ID |

#### 1.4 删除股单

- **Python SDK**：`SharelistContext.delete_sharelist(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[删除股单](https://open.longbridge.com/zh-CN/docs/content/sharelist/delete-sharelist)

永久删除您创建的自选股列表，此操作不可撤销。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | int64 | 是 | 股单 ID（路径参数） |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import SharelistContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = SharelistContext(config)

resp = ctx.delete_sharelist(15921)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncSharelistContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncSharelistContext.create(config)

    resp = await ctx.delete_sharelist(15921)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [DeleteSharelistResponse](#DeleteSharelistResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### DeleteSharelistResponse

无响应体字段。

#### 1.5 股单列表

- **Python SDK**：`SharelistContext.list_sharelist(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[股单列表](https://open.longbridge.com/zh-CN/docs/content/sharelist/list-sharelist)

获取当前用户创建的或订阅的所有社区自选股列表。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| type | string | 否 | 筛选：`mine`（我创建的）或 `subscribed`（我订阅的），不传则返回两者 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import SharelistContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = SharelistContext(config)

resp = ctx.list_sharelist()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncSharelistContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncSharelistContext.create(config)

    resp = await ctx.list_sharelist()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "mine": [
      {
        "id": 15921,
        "name": "AI Picks",
        "type": "Regular",
        "day_change": "-0.40",
        "ytd_change": "6.64",
        "subscribers": 500
      }
    ],
    "subscribed": []
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [SharelistListResponse](#SharelistListResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### SharelistListResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| sharelists | object[] | false | 用户自建股单列表，见 [SharelistInfo](#SharelistInfo) |
| subscribed_sharelists | object[] | false | 已订阅股单列表，见 [SharelistInfo](#SharelistInfo) |
| tail_mark | string | false | 已订阅列表的分页游标 |

##### SharelistInfo

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | integer | true | 股单 ID |
| name | string | false | 股单名称 |
| description | string | false | 描述 |
| cover | string | false | 封面图片 URL |
| subscribers_count | integer | false | 订阅人数 |
| chg | string | false | 日涨跌幅 |
| this_year_chg | string | false | 今年以来涨跌幅 |
| subscribed | boolean | false | 当前用户是否已订阅 |
| sharelist_type | integer | false | 类型：`0`=普通，`3`=官方，`4`=行业 |
| industry_code | string | false | 行业代码（行业股单适用） |
| stocks | object[] | false | 成份股列表，见 [SharelistStock](#SharelistStock) |

##### SharelistStock

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | true | 证券代码 |
| code | string | false | 股票代码 |
| name | string | false | 证券名称 |
| market | string | false | 市场 |
| intro | string | false | 简介 |
| last_done | string | false | 最新价格 |
| change | string | false | 日涨跌幅 |
| trade_status | integer | false | 交易状态码 |
| latency | boolean | false | 是否为延迟行情数据 |
| unread_change_log_category | string | false | 未读变更日志分类 |

#### 1.6 热门股单

- **Python SDK**：`SharelistContext.popular(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[热门股单](https://open.longbridge.com/zh-CN/docs/content/sharelist/popular-sharelist)

获取社区热门股单列表。

#### Parameters

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| count | integer | 否 | 返回数量上限，默认 20 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import SharelistContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = SharelistContext(config)

resp = ctx.popular(10)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncSharelistContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncSharelistContext.create(config)

    resp = await ctx.popular(10)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      { "id": 123, "name": "AI Picks", "description": "Top AI infrastructure stocks" },
      { "id": 456, "name": "EV Leaders", "description": "Electric vehicle sector leaders" }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [SharelistListResponse](#SharelistListResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### SharelistListResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| sharelists | object[] | false | 用户自建股单列表，见 [SharelistInfo](#SharelistInfo) |
| subscribed_sharelists | object[] | false | 已订阅股单列表，见 [SharelistInfo](#SharelistInfo) |
| tail_mark | string | false | 已订阅列表的分页游标 |

##### SharelistInfo

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | integer | true | 股单 ID |
| name | string | false | 股单名称 |
| description | string | false | 描述 |
| cover | string | false | 封面图片 URL |
| subscribers_count | integer | false | 订阅人数 |
| chg | string | false | 日涨跌幅 |
| this_year_chg | string | false | 今年以来涨跌幅 |
| subscribed | boolean | false | 当前用户是否已订阅 |
| sharelist_type | integer | false | 类型：`0`=普通，`3`=官方，`4`=行业 |
| industry_code | string | false | 行业代码（行业股单适用） |
| stocks | object[] | false | 成份股列表，见 [SharelistStock](#SharelistStock) |

##### SharelistStock

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | true | 证券代码 |
| code | string | false | 股票代码 |
| name | string | false | 证券名称 |
| market | string | false | 市场 |
| intro | string | false | 简介 |
| last_done | string | false | 最新价格 |
| change | string | false | 日涨跌幅 |
| trade_status | integer | false | 交易状态码 |
| latency | boolean | false | 是否为延迟行情数据 |
| unread_change_log_category | string | false | 未读变更日志分类 |

#### 1.7 从股单移除标的

- **Python SDK**：`SharelistContext.remove_securities(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[从股单移除标的](https://open.longbridge.com/zh-CN/docs/content/sharelist/remove-securities)

从股单中移除一个或多个标的。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | integer | 是 | 股单 ID |
| symbols | string[] | 是 | 待移除的标的代码 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import SharelistContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = SharelistContext(config)

ctx.remove_securities(123, ["TSLA.US"])
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncSharelistContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncSharelistContext.create(config)

    await ctx.remove_securities(123, ["TSLA.US"])

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success"
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | None   |
| 400    | 请求错误    | None   |

#### 1.8 股单详情

- **Python SDK**：`SharelistContext.detail(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[股单详情](https://open.longbridge.com/zh-CN/docs/content/sharelist/sharelist-detail)

获取股单详情，包括名称、描述及成分股列表。

#### Parameters

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | integer | 是 | 股单 ID |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import SharelistContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = SharelistContext(config)

resp = ctx.detail(123)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncSharelistContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncSharelistContext.create(config)

    resp = await ctx.detail(123)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 123,
    "name": "AI Picks",
    "description": "Top AI infrastructure stocks",
    "securities": ["AAPL.US", "NVDA.US"]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [SharelistDetail](#SharelistDetail) |
| 400    | 请求错误    | None   |

#### Schemas

##### SharelistDetailResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| sharelist | object | true | 股单详情 |
| scopes | object | false | 订阅权限信息 |

##### SharelistInfo

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | integer | true | 股单 ID |
| name | string | false | 名称 |
| description | string | false | 描述 |
| cover | string | false | 封面图 URL |
| subscribers_count | integer | false | 订阅人数 |
| chg | string | false | 当日涨跌幅 |
| this_year_chg | string | false | 年初至今涨跌幅 |
| subscribed | boolean | false | 是否已订阅 |
| sharelist_type | integer | false | 类型：`0`=普通，`3`=官方，`4`=行业 |
| industry_code | string | false | 行业代码 |
| stocks | object[] | false | 成分股列表，见 [SharelistStock](#SharelistStock) |

##### SharelistScopes

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| is_self | boolean | false | 是否为创建者 |
| subscription | boolean | false | 是否已订阅 |

#### 1.9 股单标的排序

- **Python SDK**：`SharelistContext.sort_securities(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[股单标的排序](https://open.longbridge.com/zh-CN/docs/content/sharelist/sort-securities)

对股单中的标的重新排序。传入的标的代码列表即为新顺序。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | integer | 是 | 股单 ID |
| symbols | string[] | 是 | 按期望顺序排列的标的代码 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import SharelistContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = SharelistContext(config)

ctx.sort_securities(123, ["TSLA.US", "AAPL.US", "700.HK"])
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncSharelistContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncSharelistContext.create(config)

    await ctx.sort_securities(123, ["TSLA.US", "AAPL.US", "700.HK"])

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success"
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | None   |
| 400    | 请求错误    | None   |

#### 1.10 更新股单

- **Python SDK**：`SharelistContext.update_sharelist(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[更新股单](https://open.longbridge.com/zh-CN/docs/content/sharelist/update-sharelist)

在自选股列表中添加、移除或重排证券，或对列表重命名。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | int64 | 是 | 股单 ID（路径参数） |
| name | string | 否 | 新名称，不传则保持原名 |
| mode | string | 否 | 证券操作模式：`add`（添加）、`remove`（移除）或 `replace`（替换） |
| securities | string[] | 否 | 受操作影响的证券代码列表 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import SharelistContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = SharelistContext(config)

resp = ctx.update_sharelist(15921, mode="add", securities=["TSLA.US", "NVDA.US"])
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncSharelistContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncSharelistContext.create(config)

    resp = await ctx.update_sharelist(15921, mode="add", securities=["TSLA.US", "NVDA.US"])
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [UpdateSharelistResponse](#UpdateSharelistResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### UpdateSharelistResponse

无响应体字段。

#### 1.11 创建讨论

- **Python SDK**：`ContentContext.create_topic(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[创建讨论](https://open.longbridge.com/zh-CN/docs/content/topics/create-topic)
- **HTTP**：`POST /v1/content/topics`

在 [社区](https://longbridge.com/topics)创建一篇新讨论。支持两种内容类型：

| 类型 | `title` | `body` 格式 | 说明 |
|------|---------|-------------|------|
| `post`（默认） | 可选 | 纯文本 | Markdown 语法（如 `**加粗**`、`# 标题`）**不会渲染**，将作为字面字符显示，类似发推文。 |
| `article` | **必填** | Markdown | 服务端将 Markdown 转为 HTML 展示，支持标题、表格、加粗、代码块等。 |

仅限 **Longbridge 开户且持有资产** 的用户才允许通过 Longbridge Developers 的 API 或 CLI 发布社区讨论和回复。否则返回 `403`。

正文中提到的标的代码（如 `700.HK`、`TSLA.US`）会被平台自动识别并关联为相关标的。`tickers` 字段用于补充正文中未显式提及的标的。

> ⚠️ 请勿滥用此功能关联与内容无关的标的，否则后台内容运营可能会限制发布，甚至有可能禁言。

**频率限制：** 同一用户每分钟最多创建 3 篇，24 小时内最多 10 篇，超出返回 `429`。

> ⚠️ 以上频率限制规则仅供参考，平台可能随时进行内部调整。

#### Request

##### Request Body

| Name        | Type     | Required              | Description                                                                                           |
| ----------- | -------- | --------------------- | ----------------------------------------------------------------------------------------------------- |
| title       | string   | 是（article 类型必填） | 标题。`topic_type` 为 `article` 时必填，`post` 时可省略。                                              |
| body        | string   | YES                   | 正文。`post` 类型为纯文本，Markdown 不渲染；`article` 类型支持 Markdown。                              |
| topic_type  | string   | NO                    | 内容类型：`post`（纯文本，默认）或 `article`（Markdown）                                               |
| tickers     | string[] | NO                    | 关联标的代码，格式 `{symbol}.{market}`，如 `["AAPL.US", "700.HK"]`，最多 10 个。**注意：** 正文中提到的标的代码（如 `700.HK`、`TSLA.US`）会被平台自动识别并关联，`tickers` 用于补充正文中未显式提及的标的。 |
| hashtags    | string[] | NO                    | 讨论标签名称列表，如 `["earnings", "fed"]`，最多 1 个                                                  |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import ContentContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ContentContext(config)

### 短帖（纯文本）
resp = ctx.create_topic(
    title="",
    body="今天看好 700.HK",
    topic_type="post",
    tickers=["700.HK"],
)
print(resp)

### 长文（Markdown，标题必填）
resp = ctx.create_topic(
    title="我的分析",
    body="**看好** 700.HK，因为...",
    topic_type="article",
    tickers=["700.HK"],
    license=1,
)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncContentContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncContentContext.create(config)

    resp = await ctx.create_topic(
        title="我的分析",
        body="**看好** 700.HK，因为...",
        topic_type="article",
        tickers=["700.HK"],
    )
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "item": {
      "id": "39304657",
      "title": "我对苹果的看法",
      "topic_type": "article",
      "tickers": ["AAPL.US"],
      "hashtags": ["earnings"],
      "created_at": "1742000000"
    }
  }
}
```

##### Response Status

| Status | Description | Schema                                                |
| ------ | ----------- | ----------------------------------------------------- |
| 200    | 返回成功    | [create_topic_response](#schemacreate_topic_response) |
| 403    | 权限不足    | 用户未开户或无资产                                    |
| 429    | 频率超限    | 超过每分钟或每日创建上限，请稍后重试                  |
| 500    | 内部错误    | None                                                  |

#### Schemas

##### create_topic_response

| Name                | Type     | Required | Description                          |
| ------------------- | -------- | -------- | ------------------------------------ |
| item                | object   | true     | 新建讨论详情                         |
| ∟ id                | string   | true     | 讨论 ID                              |
| ∟ title             | string   | false    | 标题                                 |
| ∟ description       | string   | false    | 纯文本摘要（由正文自动截取）         |
| ∟ body              | string   | false    | 完整正文（`article` 类型为 Markdown）|
| ∟ topic_type        | string   | false    | 内容类型，`article` 或 `post`        |
| ∟ tickers           | string[] | false    | 关联标的代码                         |
| ∟ hashtags          | string[] | false    | 讨论标签名称列表                     |
| ∟ images            | object[] | false    | 附图列表                             |
| ∟∟ url              | string   | false    | 原始图片 URL                         |
| ∟∟ sm               | string   | false    | 小缩略图 URL                         |
| ∟∟ lg               | string   | false    | 大缩略图 URL                         |
| ∟ likes_count       | int32    | false    | 点赞数                               |
| ∟ comments_count    | int32    | false    | 回复数                               |
| ∟ views_count       | int32    | false    | 浏览数                               |
| ∟ shares_count      | int32    | false    | 分享数                               |
| ∟ detail_url        | string   | false    | 讨论页面直链                         |
| ∟ author            | object   | false    | 作者信息                             |
| ∟∟ member_id        | string   | false    | 作者 member ID                       |
| ∟∟ name             | string   | false    | 作者昵称                             |
| ∟∟ avatar           | string   | false    | 作者头像 URL                         |
| ∟ created_at        | string   | true     | 创建时间，Unix 时间戳（秒）          |
| ∟ updated_at        | string   | false    | 最近更新时间，Unix 时间戳（秒）      |

#### 1.12 创建讨论回复

- **Python SDK**：`ContentContext.create_topic_reply(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[创建讨论回复](https://open.longbridge.com/zh-CN/docs/content/topics/create-topic-reply)
- **HTTP**：`POST /v1/content/topics/:topic_id/comments`

在指定讨论下发布回复，支持嵌套回复已有回复。完整社区讨论可访问 [社区](https://longbridge.com/topics)。

仅限 **[Longbridge 开户](https://longbridge.com/hk/download)且持有资产** 的用户才允许通过 Longbridge Developers 的 API 或 CLI 发布社区讨论和回复。否则返回 `403`。

**正文格式：** 仅支持纯文本，不支持 HTML 或 Markdown。

正文中提到的标的代码（如 `700.HK`、`TSLA.US`）会被平台自动识别并关联为相关标的。

⚠️ 请勿滥用此功能关联与内容无关的标的，否则后台内容运营可能会限制发布，甚至有可能禁言。

**频率限制：** 同一用户在同一讨论下，前 3 条无间隔限制；此后每条须与上一条保持递增间隔（3 s → 5 s → 8 s → 13 s → 21 s → 34 s → 55 s 封顶），超出限制返回 `429`。

> ⚠️ 以上频率限制规则仅供参考，平台可能随时进行内部调整。

#### Request

##### Path Parameters

| Name     | Type   | Required | Description                       |
| -------- | ------ | -------- | --------------------------------- |
| topic_id | string | YES      | 讨论 ID，如 `6993508780031016960` |

##### Request Body

| Name        | Type   | Required | Description                                                                    |
| ----------- | ------ | -------- | ------------------------------------------------------------------------------ |
| body        | string | YES      | 回复正文，仅支持纯文本。正文中提到的标的代码会被平台自动识别并关联。           |
| reply_to_id | string | NO       | 被回复的回复 ID；不填或填 `"0"` 表示发顶层回复，填入有效 ID 则嵌套在该回复下。 |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import ContentContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ContentContext(config)

### 顶层回复
reply = ctx.create_topic_reply("6993508780031016960", body="分析得很好！")
print(reply.id)

### 嵌套回复
nested = ctx.create_topic_reply(
    "6993508780031016960",
    body="同意你的观点。",
    reply_to_id="7001234567890123456",
)
print(nested.id)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncContentContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncContentContext.create(config)

    reply = await ctx.create_topic_reply("6993508780031016960", body="分析得很好！")
    print(reply.id)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "item": {
      "id": "7001234567890123460",
      "topic_id": "6993508780031016960",
      "body": "分析得很好！",
      "reply_to_id": "0",
      "author": {
        "member_id": "10086",
        "name": "张三",
        "avatar": "https://example.com/avatar.jpg"
      },
      "images": [],
      "likes_count": 0,
      "comments_count": 0,
      "created_at": "1742002000"
    }
  }
}
```

##### Response Status

| Status | Description | Schema                                                |
| ------ | ----------- | ----------------------------------------------------- |
| 200    | 返回成功    | [create_reply_response](#schemacreate_reply_response) |
| 403    | 权限不足    | 用户未开户或无资产                                    |
| 429    | 频率超限    | 超过同讨论下的发帖频率限制，请等待后重试              |
| 500    | 内部错误    | None                                                  |

#### Schemas

##### create_reply_response

| Name             | Type     | Required | Description                   |
| ---------------- | -------- | -------- | ----------------------------- |
| item             | object   | true     | 新建回复详情                  |
| ∟ id             | string   | true     | 回复 ID                       |
| ∟ topic_id       | string   | true     | 所属讨论 ID                   |
| ∟ body           | string   | false    | 回复正文（纯文本）            |
| ∟ reply_to_id    | string   | false    | 父回复 ID，`"0"` 表示顶层回复 |
| ∟ author         | object   | false    | 作者信息                      |
| ∟∟ member_id     | string   | false    | 作者 member ID                |
| ∟∟ name          | string   | false    | 作者昵称                      |
| ∟∟ avatar        | string   | false    | 作者头像 URL                  |
| ∟ images         | object[] | false    | 附图列表                      |
| ∟∟ url           | string   | false    | 原始图片 URL                  |
| ∟∟ sm            | string   | false    | 小缩略图 URL                  |
| ∟∟ lg            | string   | false    | 大缩略图 URL                  |
| ∟ likes_count    | int32    | false    | 点赞数                        |
| ∟ comments_count | int32    | false    | 嵌套回复数                    |
| ∟ created_at     | string   | true     | 创建时间，Unix 时间戳（秒）   |

#### 1.13 我的讨论

- **Python SDK**：`ContentContext.topics_mine(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[我的讨论](https://open.longbridge.com/zh-CN/docs/content/topics/my-topics)
- **HTTP**：`GET /v1/content/topics/mine`

获取当前登录用户发布的讨论列表，支持分页与类型过滤。可在 [社区](https://longbridge.com/topics)查看。

#### Request

##### Query Parameters

| Name        | Type   | Required | Description                                                                    |
| ----------- | ------ | -------- | ------------------------------------------------------------------------------ |
| page        | int32  | NO       | 页码，默认 1                                                                   |
| size        | int32  | NO       | 每页数量，范围 1~500，默认 50                                                  |
| topic_type  | string | NO       | 类型过滤，可选 `article`（长文）、`post`（短帖），不传返回全部                  |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import ContentContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ContentContext(config)

resp = ctx.topics_mine(page=1, size=50, topic_type="article")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncContentContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncContentContext.create(config)

    resp = await ctx.topics_mine(page=1, size=50, topic_type="article")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "39304657",
        "title": "我对苹果的分析",
        "description": "文章摘要...",
        "body": "Markdown 正文内容...",
        "topic_type": "article",
        "tickers": ["AAPL.US"],
        "hashtags": ["earnings"],
        "images": [],
        "likes_count": 12,
        "comments_count": 3,
        "views_count": 200,
        "shares_count": 1,
        "license": 1,
        "detail_url": "https://longbridge.com/topics/39304657",
        "author": {
          "member_id": "10086",
          "name": "张三",
          "avatar": "https://example.com/avatar.jpg"
        },
        "created_at": "1742000000",
        "updated_at": "1742000000"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                                            |
| ------ | ----------- | ------------------------------------------------- |
| 200    | 返回成功    | [my_topics_response](#schemamy_topics_response)   |
| 500    | 内部错误    | None                                              |

#### Schemas

##### my_topics_response

| Name                | Type     | Required | Description                                                       |
| ------------------- | -------- | -------- | ----------------------------------------------------------------- |
| items               | object[] | true     | 讨论列表                                                          |
| ∟ id                | string   | true     | 讨论 ID                                                           |
| ∟ title             | string   | false    | 标题（短帖可能为空）                                              |
| ∟ description       | string   | false    | 纯文本摘要                                                        |
| ∟ body              | string   | false    | Markdown 格式正文                                                 |
| ∟ topic_type        | string   | true     | 内容类型，`article`（长文）或 `post`（短帖）                       |
| ∟ tickers           | string[] | false    | 关联标的代码，如 `["AAPL.US", "700.HK"]`                         |
| ∟ hashtags          | string[] | false    | 讨论标签名称列表                                                  |
| ∟ images            | object[] | false    | 附图列表                                                          |
| ∟∟ url              | string   | false    | 原始图片 URL                                                      |
| ∟∟ sm               | string   | false    | 小缩略图 URL                                                      |
| ∟∟ lg               | string   | false    | 大缩略图 URL                                                      |
| ∟ likes_count       | int32    | false    | 点赞数                                                            |
| ∟ comments_count    | int32    | false    | 评论数                                                            |
| ∟ views_count       | int32    | false    | 浏览数                                                            |
| ∟ shares_count      | int32    | false    | 分享数                                                            |
| ∟ license           | int32    | false    | 版权声明，`0`=无声明，`1`=原创，`2`=非原创                        |
| ∟ detail_url        | string   | false    | 讨论详情页链接                                                    |
| ∟ author            | object   | false    | 作者信息                                                          |
| ∟∟ member_id        | string   | false    | 作者 member ID                                                    |
| ∟∟ name             | string   | false    | 作者昵称                                                          |
| ∟∟ avatar           | string   | false    | 作者头像 URL                                                      |
| ∟ created_at        | string   | true     | 创建时间，Unix 时间戳（秒）                                       |
| ∟ updated_at        | string   | false    | 最后更新时间，Unix 时间戳（秒）                                   |

#### 1.14 讨论详情

- **Python SDK**：`ContentContext.topic_detail(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[讨论详情](https://open.longbridge.com/zh-CN/docs/content/topics/topic-detail)
- **HTTP**：`GET /v1/content/topics/:id`

根据讨论 ID 获取完整详情，包含正文（Markdown）、作者信息、关联标的与标签、互动数据及详情页链接。可在 [社区](https://longbridge.com/topics)查看。

#### Request

##### Path Parameters

| Name | Type   | Required | Description                       |
| ---- | ------ | -------- | --------------------------------- |
| id   | string | YES      | 讨论 ID，如 `6993508780031016960` |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import ContentContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ContentContext(config)

topic = ctx.topic_detail("6993508780031016960")
print(topic)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncContentContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncContentContext.create(config)

    topic = await ctx.topic_detail("6993508780031016960")
    print(topic)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "item": {
      "id": "6993508780031016960",
      "title": "我对苹果的分析",
      "description": "文章摘要...",
      "body": "**看多** AAPL，因为...",
      "topic_type": "article",
      "tickers": ["AAPL.US"],
      "hashtags": ["earnings"],
      "images": [
        {
          "url": "https://cdn.longbridge.com/img/abc.jpg",
          "sm": "https://cdn.longbridge.com/img/abc_sm.jpg",
          "lg": "https://cdn.longbridge.com/img/abc_lg.jpg"
        }
      ],
      "likes_count": 42,
      "comments_count": 7,
      "views_count": 1500,
      "shares_count": 3,
      "detail_url": "https://longbridge.com/topics/6993508780031016960",
      "author": {
        "member_id": "10086",
        "name": "张三",
        "avatar": "https://example.com/avatar.jpg"
      },
      "created_at": "1742000000",
      "updated_at": "1742001000"
    }
  }
}
```

##### Response Status

| Status | Description | Schema                                                |
| ------ | ----------- | ----------------------------------------------------- |
| 200    | 返回成功    | [topic_detail_response](#schematopic_detail_response) |
| 500    | 内部错误    | None                                                  |

#### Schemas

##### topic_detail_response

| Name             | Type     | Required | Description                                  |
| ---------------- | -------- | -------- | -------------------------------------------- |
| item             | object   | true     | 讨论详情                                     |
| ∟ id             | string   | true     | 讨论 ID                                      |
| ∟ title          | string   | false    | 标题（短帖可能为空）                         |
| ∟ description    | string   | false    | 纯文本摘要                                   |
| ∟ body           | string   | false    | Markdown 格式正文                            |
| ∟ topic_type     | string   | true     | 内容类型，`article`（长文）或 `post`（短帖） |
| ∟ tickers        | string[] | false    | 关联标的代码，如 `["AAPL.US", "700.HK"]`     |
| ∟ hashtags       | string[] | false    | 讨论标签名称列表                             |
| ∟ images         | object[] | false    | 附图列表                                     |
| ∟∟ url           | string   | false    | 原始图片 URL                                 |
| ∟∟ sm            | string   | false    | 小缩略图 URL                                 |
| ∟∟ lg            | string   | false    | 大缩略图 URL                                 |
| ∟ likes_count    | int32    | false    | 点赞数                                       |
| ∟ comments_count | int32    | false    | 回复数                                       |
| ∟ views_count    | int32    | false    | 浏览数                                       |
| ∟ shares_count   | int32    | false    | 分享数                                       |
| ∟ detail_url     | string   | false    | 讨论详情页链接                               |
| ∟ author         | object   | false    | 作者信息                                     |
| ∟∟ member_id     | string   | false    | 作者 member ID                               |
| ∟∟ name          | string   | false    | 作者昵称                                     |
| ∟∟ avatar        | string   | false    | 作者头像 URL                                 |
| ∟ created_at     | string   | true     | 创建时间，Unix 时间戳（秒）                  |
| ∟ updated_at     | string   | false    | 最后更新时间，Unix 时间戳（秒）              |

#### 1.15 讨论回复

- **Python SDK**：`ContentContext.list_topic_replies(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[讨论回复](https://open.longbridge.com/zh-CN/docs/content/topics/topic-replies)
- **HTTP**：`GET /v1/content/topics/:topic_id/comments`

获取指定讨论下的回复列表，支持分页。完整社区讨论可访问 [社区](https://longbridge.com/topics)。

每条回复包含作者信息、正文（纯文本）、互动数据及 `reply_to_id` 字段：`"0"` 表示顶层回复，其他值表示对指定回复的嵌套回复。

#### Request

##### Path Parameters

| Name     | Type   | Required | Description                       |
| -------- | ------ | -------- | --------------------------------- |
| topic_id | string | YES      | 讨论 ID，如 `6993508780031016960` |

##### Query Parameters

| Name | Type  | Required | Description                  |
| ---- | ----- | -------- | ---------------------------- |
| page | int32 | NO       | 页码，默认 1                 |
| size | int32 | NO       | 每页数量，范围 1~50，默认 20 |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import ContentContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ContentContext(config)

replies = ctx.list_topic_replies("6993508780031016960", page=1, size=20)
for r in replies:
    print(r.author.name, r.body)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncContentContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncContentContext.create(config)

    replies = await ctx.list_topic_replies("6993508780031016960", page=1, size=20)
    for r in replies:
        print(r.author.name, r.body)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "7001234567890123456",
        "topic_id": "6993508780031016960",
        "body": "分析得很到位！",
        "reply_to_id": "0",
        "author": {
          "member_id": "10087",
          "name": "李四",
          "avatar": "https://example.com/avatar2.jpg"
        },
        "images": [],
        "likes_count": 5,
        "comments_count": 2,
        "created_at": "1742001500"
      },
      {
        "id": "7001234567890123457",
        "topic_id": "6993508780031016960",
        "body": "估值部分我有不同看法。",
        "reply_to_id": "7001234567890123456",
        "author": {
          "member_id": "10088",
          "name": "王五",
          "avatar": "https://example.com/avatar3.jpg"
        },
        "images": [],
        "likes_count": 1,
        "comments_count": 0,
        "created_at": "1742001800"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                                                  |
| ------ | ----------- | ------------------------------------------------------- |
| 200    | 返回成功    | [topic_replies_response](#schematopic_replies_response) |
| 500    | 内部错误    | None                                                    |

#### Schemas

##### topic_replies_response

| Name             | Type     | Required | Description                   |
| ---------------- | -------- | -------- | ----------------------------- |
| items            | object[] | true     | 回复列表                      |
| ∟ id             | string   | true     | 回复 ID                       |
| ∟ topic_id       | string   | true     | 所属讨论 ID                   |
| ∟ body           | string   | false    | 回复正文（纯文本）            |
| ∟ reply_to_id    | string   | false    | 父回复 ID，`"0"` 表示顶层回复 |
| ∟ author         | object   | false    | 作者信息                      |
| ∟∟ member_id     | string   | false    | 作者 member ID                |
| ∟∟ name          | string   | false    | 作者昵称                      |
| ∟∟ avatar        | string   | false    | 作者头像 URL                  |
| ∟ images         | object[] | false    | 附图列表                      |
| ∟∟ url           | string   | false    | 原始图片 URL                  |
| ∟∟ sm            | string   | false    | 小缩略图 URL                  |
| ∟∟ lg            | string   | false    | 大缩略图 URL                  |
| ∟ likes_count    | int32    | false    | 点赞数                        |
| ∟ comments_count | int32    | false    | 嵌套回复数                    |
| ∟ created_at     | string   | true     | 创建时间，Unix 时间戳（秒）   |

#### 1.16 标的社区讨论

- **Python SDK**：`ContentContext.topics(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[标的社区讨论](https://open.longbridge.com/zh-CN/docs/content/topics/topics)
- **HTTP**：`GET /v1/content/{symbol}/topics`

获取指定股票的讨论列表。完整社区讨论可访问 [社区](https://longbridge.com/topics)。

#### Request

##### Path Parameters

| Name   | Type   | Required | Description                                    |
| ------ | ------ | -------- | ---------------------------------------------- |
| symbol | string | YES      | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US` |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import ContentContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ContentContext(config)

resp = ctx.topics("AAPL.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncContentContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncContentContext.create(config)

    resp = await ctx.topics("AAPL.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "39304657",
        "title": "英伟达 GTC 备受关注；阿里 "Token 战略" 再加码｜今日重要消息回顾",
        "description": "0317 ｜海豚君重点关注：🐬 个股 1、[st]ST/US/NVDA#英伟达.US[/st] 英伟达 GTC 2026 大会正式开幕，英伟达创始人兼 CEO 黄仁勋发表了主题演讲。宣布，其下一代 Vera Rubin 架构将推出专为空间轨道数据中心设计的 Vera Rubin Space Module，性能比 H100 提升 25 倍。同时宣布与 Groq 合作开发新型 LPU 芯片...",
        "url": "https://longbridge.com/topics/39304657",
        "published_at": "1773736144",
        "comments_count": 1,
        "likes_count": 7,
        "shares_count": 4
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                                        |
| ------ | ----------- | --------------------------------------------- |
| 200    | 返回成功    | [topics_response](#schematopics_response)     |
| 500    | 内部错误    | None                                          |

#### Schemas

##### topics_response

| Name               | Type      | Required | Description                   |
| ------------------ | --------- | -------- | ----------------------------- |
| items              | object[]  | true     | 讨论列表                      |
| ∟ id               | string    | true     | 讨论 ID                       |
| ∟ title            | string    | true     | 标题                          |
| ∟ description      | string    | true     | 摘要/描述                     |
| ∟ url              | string    | true     | 讨论详情链接                  |
| ∟ published_at     | string    | true     | 发布时间，Unix 时间戳（秒）   |
| ∟ comments_count   | int32     | true     | 评论数                        |
| ∟ likes_count      | int32     | true     | 点赞数                        |
| ∟ shares_count     | int32     | true     | 分享数                        |


## 10. Screener（选股器）

官方当前开发者文档未标注额外数据卡收费；策略与筛选能力受账户可见范围影响。

### 1. 免费/基础权限

| 接口 | Python SDK | 权限/费用 |
| --- | --- | --- |
| [选股指标](https://open.longbridge.com/zh-CN/docs/screener/screener-indicators) | ScreenerContext.screener_indicators(...) | 免费/基础 |
| [预设选股策略](https://open.longbridge.com/zh-CN/docs/screener/screener-recommend-strategies) | ScreenerContext.screener_recommend_strategies(...) | 免费/基础 |
| [选股筛选](https://open.longbridge.com/zh-CN/docs/screener/screener-search) | ScreenerContext.screener_search(...) | 免费/基础 |
| [选股策略详情](https://open.longbridge.com/zh-CN/docs/screener/screener-strategy) | ScreenerContext.screener_strategy(...) | 免费/基础 |
| [我的选股策略](https://open.longbridge.com/zh-CN/docs/screener/screener-user-strategies) | ScreenerContext.screener_user_strategies(...) | 免费/基础 |

#### 1.1 选股指标

- **Python SDK**：`ScreenerContext.screener_indicators(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[选股指标](https://open.longbridge.com/zh-CN/docs/screener/screener-indicators)

获取[选股器](https://longbridge.com/screener)支持的所有指标定义，包含键值、名称、单位和可用范围，可用于构建自定义筛选条件。

接口：`GET /v1/quote/ai/screener/indicators`

> **SDK 响应：** `data` 字段为分组结构 `{"groups": [{...}]}`。CLI `screener indicators --format json` 会将其展平为扁平数组以方便使用。

#### Parameters

> **SDK 方法参数。**

此方法无参数。

#### Request Example

###### Python 示例

```python
from longbridge.openapi import ScreenerContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ScreenerContext(config)

resp = ctx.screener_indicators()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncScreenerContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncScreenerContext.create(config)

    resp = await ctx.screener_indicators()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "groups": [
      {
        "group_name": "公司规模与财务",
        "indicators": [
          { "id": "1", "key": "marketcap", "name": "市值", "unit": "亿", "min": null, "max": null }
        ]
      }
    ]
  }
}
```

> 所有 `key` 值已去除 `filter_` 前缀，`id` 字段为字符串类型。

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ScreenerIndicatorsResponse](#ScreenerIndicatorsResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ScreenerIndicatorsResponse

SDK 响应 `data` 为分组结构，CLI `--format json` 输出会将其展平为扁平数组。所有 `key` 值已去除 `filter_` 前缀。

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| groups | object[] | false | 指标分组 |
| ∟ group_name | string | false | 分组名称 |
| ∟ indicators | object[] | false | 该分组下的指标 |
| ∟ ∟ id | string | false | 指标 ID（字符串类型） |
| ∟ ∟ key | string | false | 指标键值，用于构建筛选条件（不含 `filter_` 前缀） |
| ∟ ∟ name | string | false | 指标显示名称 |
| ∟ ∟ unit | string | false | 单位（如 `%`、`亿`） |
| ∟ ∟ min | string | false | 指标全局下限；null 表示无下限 |
| ∟ ∟ max | string | false | 指标全局上限；null 表示无上限 |

#### 1.2 预设选股策略

- **Python SDK**：`ScreenerContext.screener_recommend_strategies(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[预设选股策略](https://open.longbridge.com/zh-CN/docs/screener/screener-recommend-strategies)

获取平台预设的选股策略列表，含近期平均日涨跌幅和策略内股票。

接口：`GET /v1/quote/ai/screener/strategies/recommend`

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| market | string | 否 | 市场筛选：`US`、`HK`、`CN`、`SG`，默认 `US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import ScreenerContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ScreenerContext(config)

resp = ctx.screener_recommend_strategies()
print(resp)

### 港股市场
resp = ctx.screener_recommend_strategies(market="HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncScreenerContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncScreenerContext.create(config)

    resp = await ctx.screener_recommend_strategies(market="HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "strategys": [
      { "id": 19, "name": "今日大涨股票", "type": "platform", "market": "US" },
      { "id": 20, "name": "今年增长冠军", "type": "platform", "market": "US" }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ScreenerStrategiesResponse](#ScreenerStrategiesResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ScreenerStrategiesResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| strategys | object[] | false | 策略列表 |
| ∟ id | integer | false | 策略 ID（传入 `screener_strategy` 或 `screener_search`） |
| ∟ name | string | false | 策略名称 |
| ∟ type | string | false | `"platform"` 表示平台预设策略 |
| ∟ market | string | false | 目标市场（如 `"US"`、`"HK"`） |

#### 1.3 选股筛选

- **Python SDK**：`ScreenerContext.screener_search(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[选股筛选](https://open.longbridge.com/zh-CN/docs/screener/screener-search)

按策略 ID 或自定义指标条件筛选股票，支持分页。

接口：`POST /v1/quote/ai/screener/search`

> **JSON 输出格式说明：** 响应使用扁平的 `items[]` 数组（非 `stocks[]`），所有数值字段为 JSON 数字类型（非字符串），指标键名不含 `filter_` 前缀。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| market | string | 是 | 市场：`US`、`HK`、`CN`、`SG` |
| strategy_id | integer | 否 | 策略 ID；与自定义条件二选一，或同时使用 |
| conditions | ScreenerCondition[] | 否 | 自定义筛选条件（模式 B，不传 strategy_id 时使用） |
| show | string[] | 否 | 额外需要返回的指标键名，在默认 7 列之外追加 |
| page | integer | 否 | 页码，从 0 开始，默认 0 |
| size | integer | 否 | 每页条数，默认 20 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import ScreenerContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ScreenerContext(config)

### 按策略 ID 筛选
resp = ctx.screener_search("US", strategy_id=42)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncScreenerContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncScreenerContext.create(config)

    resp = await ctx.screener_search("US", strategy_id=42, page=1, size=20)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 88,
    "page": 0,
    "market": "US",
    "items": [
      {
        "symbol": "AAPL.US",
        "name": "苹果公司",
        "prevchg": 0.62,
        "marketcap": 3241500000000,
        "pettm": 32.15,
        "pbmrq": 50.21,
        "salesgrowthyoy": 8.04
      },
      {
        "symbol": "MSFT.US",
        "name": "微软",
        "prevchg": 1.05,
        "marketcap": 3085000000000,
        "pettm": 35.42,
        "pbmrq": 12.87,
        "salesgrowthyoy": 12.61
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ScreenerSearchResponse](#ScreenerSearchResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ScreenerSearchResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| total | integer | false | 满足条件的股票总数 |
| page | integer | false | 当前页码（从零开始） |
| market | string | false | 结果集的市场 |
| items | object[] | false | 筛选结果股票列表 |
| ∟ symbol | string | false | 证券代码 |
| ∟ name | string | false | 证券名称 |
| ∟ prevchg | number | false | 昨日涨跌幅（如 `1.24` 表示 1.24%） |
| ∟ marketcap | number | false | 市值（数字类型） |
| ∟ pettm | number | false | 市盈率 TTM（数字类型） |
| ∟ pbmrq | number | false | 市净率 MRQ（数字类型） |
| ∟ salesgrowthyoy | number | false | 营收同比增速（%） |
| ∟ industry | string | false | 行业分类 |

> 所有数值指标字段均为 JSON 数字类型。具体返回字段取决于所用策略或筛选条件。指标键名不含 `filter_` 前缀。

#### 1.4 选股策略详情

- **Python SDK**：`ScreenerContext.screener_strategy(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[选股策略详情](https://open.longbridge.com/zh-CN/docs/screener/screener-strategy)

根据策略 ID 获取单个选股策略的完整配置，包含所有指标分组和各指标的筛选范围。

接口：`GET /v1/quote/ai/screener/strategy/{id}`（策略 ID 为路径参数）

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | integer | 是 | 策略 ID，来自 `screener_recommend_strategies` 或 `screener_user_strategies` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import ScreenerContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ScreenerContext(config)

resp = ctx.screener_strategy(42)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncScreenerContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncScreenerContext.create(config)

    resp = await ctx.screener_strategy(42)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 19,
    "name": "今日大涨股票",
    "market": "US",
    "type": "platform",
    "filter": {
      "filters": [
        { "key": "prevchg", "min": "2", "max": "", "tech_values": {} }
      ]
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ScreenerStrategyDetail](#ScreenerStrategyDetail) |
| 400    | 请求错误    | None   |

#### Schemas

##### ScreenerStrategyDetail

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | integer | false | 策略 ID |
| name | string | false | 策略名称 |
| market | string | false | 目标市场 |
| type | string | false | 策略类型 |
| filter | object | false | 筛选配置 |
| ∟ filters | object[] | false | 筛选条件列表 |
| ∟ ∟ key | string | false | 指标键值（不含 `filter_` 前缀） |
| ∟ ∟ min | string | false | 下限 |
| ∟ ∟ max | string | false | 上限 |
| ∟ ∟ tech_values | object | false | 技术指标参数 |

#### 1.5 我的选股策略

- **Python SDK**：`ScreenerContext.screener_user_strategies(...)`
- **权限/费用**：官方文档未标注额外数据卡收费
- **官方页面**：[我的选股策略](https://open.longbridge.com/zh-CN/docs/screener/screener-user-strategies)

获取当前登录用户创建的自定义选股策略列表。

接口：`GET /v1/quote/ai/screener/strategies/mine`

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| market | string | 否 | 市场筛选：`US`、`HK`、`CN`、`SG`，默认 `US` |

需要登录。

#### Request Example

###### Python 示例

```python
from longbridge.openapi import ScreenerContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = ScreenerContext(config)

resp = ctx.screener_user_strategies()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncScreenerContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncScreenerContext.create(config)

    resp = await ctx.screener_user_strategies()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "strategys": [
      { "id": 42, "name": "我的成长股策略", "type": "user", "market": "US" }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ScreenerStrategiesResponse](#ScreenerStrategiesResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ScreenerStrategiesResponse

响应结构与 [screener_recommend_strategies](./screener_recommend_strategies) 相同，请参阅该文档中的 Schema 定义。


## 11. Trade（交易与资产）

不属于行情卡收费分类；交易、资产与账户能力需要相应账户/交易授权，真实下单会产生券商交易费用。

### 1. 账户/交易权限

| 接口 | Python SDK | 权限/费用 |
| --- | --- | --- |
| [账户资金](https://open.longbridge.com/zh-CN/docs/trade/asset/account) | TradeContext.account_balance(...) | 账户权限 |
| [资金流水](https://open.longbridge.com/zh-CN/docs/trade/asset/cashflow) | TradeContext.cash_flow(...) | 账户权限 |
| [基金持仓](https://open.longbridge.com/zh-CN/docs/trade/asset/fund) | TradeContext.fund_positions(...) | 账户权限 |
| [margin_ratio](https://open.longbridge.com/zh-CN/docs/trade/asset/margin_ratio) | TradeContext.margin_ratio(...) | 账户权限 |
| [股票持仓](https://open.longbridge.com/zh-CN/docs/trade/asset/stock) | TradeContext.stock_positions(...) | 账户权限 |
| [美股资产概览](https://open.longbridge.com/zh-CN/docs/trade/asset/us_asset_overview) | TradeContext.us_asset_overview(...) | 账户权限 |
| [美股已实现盈亏](https://open.longbridge.com/zh-CN/docs/trade/asset/us_realized_pl) | TradeContext.us_realized_pl(...) | 账户权限 |
| [history_executions](https://open.longbridge.com/zh-CN/docs/trade/execution/history_executions) | TradeContext.history_executions(...) | 账户权限 |
| [today_executions](https://open.longbridge.com/zh-CN/docs/trade/execution/today_executions) | TradeContext.today_executions(...) | 账户权限 |
| [estimate_available_buy_limit](https://open.longbridge.com/zh-CN/docs/trade/order/estimate_available_buy_limit) | TradeContext.estimate_max_purchase_quantity(...) | 账户权限 |
| [history_orders](https://open.longbridge.com/zh-CN/docs/trade/order/history_orders) | TradeContext.history_orders(...) | 账户权限 |
| [将下方订单 ID 替换为实际的订单 ID](https://open.longbridge.com/zh-CN/docs/trade/order/order_detail) | TradeContext.order_detail(...) | 账户权限 |
| [将下方订单 ID 替换为实际的订单 ID](https://open.longbridge.com/zh-CN/docs/trade/order/replace) | TradeContext.replace_order(...) | 账户权限 |
| [委托下单](https://open.longbridge.com/zh-CN/docs/trade/order/submit) | TradeContext.submit_order(...) | 账户权限 |
| [today_orders](https://open.longbridge.com/zh-CN/docs/trade/order/today_orders) | TradeContext.today_orders(...) | 账户权限 |
| [美股委托详情](https://open.longbridge.com/zh-CN/docs/trade/order/us_order_detail) | TradeContext.us_order_detail(...) | 账户权限 |
| [美股历史委托](https://open.longbridge.com/zh-CN/docs/trade/order/us_query_orders) | TradeContext.us_query_orders(...) | 账户权限 |
| [将下方订单 ID 替换为实际的订单 ID](https://open.longbridge.com/zh-CN/docs/trade/order/withdraw) | TradeContext.cancel_order(...) | 账户权限 |
| [交易推送](https://open.longbridge.com/zh-CN/docs/trade/trade-push) | TradeContext.subscribe(...)；TradeContext.unsubscribe(...)；TradeContext.set_on_order_changed(...) | 账户权限 |

#### 1.1 账户资金

- **Python SDK**：`TradeContext.account_balance(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[账户资金](https://open.longbridge.com/zh-CN/docs/trade/asset/account)
- **HTTP**：`GET /v1/asset/account`

该接口用于获取用户每个币种可用、可取、冻结、待结算金额、在途资金 (基金申购赎回) 信息。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name     | Type   | Required | Description           |
| -------- | ------ | -------- | --------------------- |
| currency | string | NO       | 币种（HKD、USD、CNH） |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)
resp = ctx.account_balance()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)
    resp = await ctx.account_balance()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "total_cash": "1759070010.72",
        "max_finance_amount": "977582000",
        "remaining_finance_amount": "0",
        "risk_level": "1",
        "margin_call": "2598051051.50",
        "currency": "HKD",
        "net_assets": "24145.90",
        "init_margin": "1540.09",
        "maintenance_margin": "1540.09",
        "buy_power": "1759070.12",
        "cash_infos": [
          {
            "withdraw_cash": "97592.30",
            "available_cash": "195902464.37",
            "frozen_cash": "11579339.13",
            "settling_cash": "207288537.81",
            "currency": "HKD"
          },
          {
            "withdraw_cash": "199893416.74",
            "available_cash": "199893416.74",
            "frozen_cash": "28723.76",
            "settling_cash": "-276806.51",
            "currency": "USD"
          }
        ],
        "frozen_transaction_fees": [
          {
            "currency": "USD",
            "frozen_transaction_fee": "6.51"
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                                    |
| ------ | ----------- | ----------------------------------------- |
| 200    | 返回成功    | [accountcash_rsp](#schemaaccountcash_rsp) |
| 400    | 内部错误    | None                                      |

<aside className="success">
</aside>

#### Schemas

##### accountcash_rsp

| Name                       | Type     | Required | Description                                                                                            |
| -------------------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------ |
| list                       | object[] | false    | 账户资金信息                                                                                           |
| ∟ total_cash               | string   | true     | 现金总额                                                                                               |
| ∟ max_finance_amount       | string   | true     | 最大融资金额                                                                                           |
| ∟ remaining_finance_amount | string   | true     | 剩余融资金额                                                                                           |
| ∟ risk_level               | string   | true     | 风控等级 <br/> <br/> <b>可选值:</b><br/> `0` - 安全 <br/> `1` - 中风险<br/> `2` - 预警<br/> `3` - 危险 |
| ∟ margin_call              | string   | true     | 追缴保证金                                                                                             |
| ∟ net_assets               | string   | true     | 净资产                                                                                                 |
| ∟ init_margin              | string   | true     | 初始保证金                                                                                             |
| ∟ maintenance_margin       | string   | true     | 维持保证金                                                                                             |
| ∟ currency                 | string   | true     | 币种                                                                                                   |
| ∟ market                   | string   | false    | 市场                                                                                                   |
| ∟ buy_power                | string   | true     | 购买力                                                                                                 |
| ∟ cash_infos               | object[] | false    | 现金详情                                                                                               |
| ∟∟ withdraw_cash           | string   | true     | 可提现金                                                                                               |
| ∟∟ available_cash          | string   | true     | 可用现金                                                                                               |
| ∟∟ frozen_cash             | string   | true     | 冻结现金                                                                                               |
| ∟∟ settling_cash           | string   | true     | 待结算现金                                                                                             |
| ∟∟ currency                | string   | true     | 币种                                                                                                   |
| ∟ frozen_transaction_fees  | object[] | false    | 冻结费用                                                                                               |
| ∟∟ currency                | string   | false    | 币种                                                                                                   |
| ∟∟ frozen_transaction_fee  | string   | false    | 费用金额                                                                                               |

#### 1.2 资金流水

- **Python SDK**：`TradeContext.cash_flow(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[资金流水](https://open.longbridge.com/zh-CN/docs/trade/asset/cashflow)
- **HTTP**：`GET /v1/asset/cashflow`

该接口用于获取资金流入/流出方向、资金类别、资金金额、发生时间、关联股票代码和资金流水说明信息。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name          | Type   | Required | Description                                                                               |
| ------------- | ------ | -------- | ----------------------------------------------------------------------------------------- |
| start_time    | string | YES      | 开始时间，时间戳，以 `秒` 为单位，例如：`1650037563`                                      |
| end_time      | string | YES      | 结束时间，时间戳，以 `秒` 为单位，例如：`1650747581`                                      |
| business_type | string | NO       | 资金类型 <br/><br/> <b>可选值:</b> <br/>`1` - 现金 <br/>`2` - 股票<br/> `3` - 基金        |
| symbol        | string | NO       | 标的代码，例如：`AAPL.US`                                                                 |
| page          | string | NO       | 起始页 <br/><br/><b>默认值:</b> `1` <br/><b>数据校验规则:</b><br/> <b>取值范围:</b> `>=1` |
| size          | string | NO       | 每页大小 <br/><br/><b>默认值:</b> `50` <br/><b>数据校验规则:</b> `1~10000`                |

##### Request Example

###### Python 示例

```python
from datetime import datetime
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)
resp = ctx.cash_flow(
    start_at = datetime(2022, 5, 9),
    end_at = datetime(2022, 5, 12),
)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from datetime import datetime
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)
    resp = await ctx.cash_flow(
        start_at = datetime(2022, 5, 9),
        end_at = datetime(2022, 5, 12),
    )
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "transaction_flow_name": "股票买入成交",
        "direction": 1,
        "balance": "-248.60",
        "currency": "USD",
        "business_time": "1621507957",
        "symbol": "AAPL.US",
        "description": "AAPL"
      },
      {
        "transaction_flow_name": "股票买入成交",
        "direction": 1,
        "balance": "-125.16",
        "currency": "USD",
        "business_time": "1621504824",
        "symbol": "AAPL.US",
        "description": "AAPL"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                              |
| ------ | ----------- | ----------------------------------- |
| 200    | 返回成功    | [cashflow_rsp](#schemacashflow_rsp) |
| 400    | 内部错误    | None                                |

<aside className="success">
</aside>

#### Schemas

##### cashflow_rsp

| Name                    | Type     | Required | Description                                                                         |
| ----------------------- | -------- | -------- | ----------------------------------------------------------------------------------- |
| list                    | object[] | false    | 流水信息                                                                            |
| ∟ transaction_flow_name | string   | true     | 流水名称                                                                            |
| ∟ direction             | string   | true     | 流出方向 <br/><br/><b>可选值:</b> <br/>`1` - 流出 <br/> `2` - 流入                  |
| ∟ business_type         | string   | true     | 资金类别 <br/><br/><b>可选值:</b> <br/>`1` - 现金 <br/> `2` - 股票 <br/> `3` - 基金 |
| ∟ balance               | string   | true     | 资金金额                                                                            |
| ∟ currency              | string   | true     | 资金币种                                                                            |
| ∟ business_time         | string   | true     | 业务时间                                                                            |
| ∟ symbol                | string   | false    | 关联股票代码信息                                                                    |
| ∟ description           | string   | false    | 资金流水说明                                                                        |

#### 1.3 基金持仓

- **Python SDK**：`TradeContext.fund_positions(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[基金持仓](https://open.longbridge.com/zh-CN/docs/trade/asset/fund)
- **HTTP**：`GET /v1/asset/fund`

该接口用于获取包括账户、基金代码、持有份额、成本净值、当前净值、币种在内的基金持仓信息。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name   | Type     | Required | Description                                                                                                                                           |
| ------ | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| symbol | string[] | NO       | 基金代码，使用 `ISIN` 格式，例如：`HK0000676327` <a href="https://en.wikipedia.org/wiki/International_Securities_Identification_Number">ISIN 解释</a> |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)
resp = ctx.fund_positions()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)
    resp = await ctx.fund_positions()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "account_channel": "lb",
        "fund_info": [
          {
            "symbol": "HK0000447943",
            "symbol_name": "高腾亚洲收益基金",
            "currency": "USD",
            "holding_units": "5.000",
            "current_net_asset_value": "0",
            "cost_net_asset_value": "0.00",
            "net_asset_value_day": "1649865600"
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                      |
| ------ | ----------- | --------------------------- |
| 200    | 返回成功    | [fund_rsp](#schemafund_rsp) |
| 400    | 内部错误    | None                        |

<aside className="success">
</aside>

#### Schemas

##### fund_rsp

| Name                       | Type     | Required | Description    |
| -------------------------- | -------- | -------- | -------------- |
| list                       | object[] | false    | 股票持仓信息   |
| ∟ account_channel          | string   | true     | 账户类型       |
| ∟ fund_info                | object[] | false    | 基金详情       |
| ∟∟ symbol                  | string   | true     | 基金 ISIN 代码 |
| ∟∟ current_net_asset_value | string   | true     | 当前净值       |
| ∟∟ net_asset_value_day     | string   | true     | 当前净值时间   |
| ∟∟ symbol_name             | string   | true     | 基金名称       |
| ∟∟ currency                | string   | true     | 币种           |
| ∟∟ cost_net_asset_value    | string   | true     | 成本净值       |

#### 1.4 margin_ratio

- **Python SDK**：`TradeContext.margin_ratio(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[margin_ratio](https://open.longbridge.com/zh-CN/docs/trade/asset/margin_ratio)
- **HTTP**：`GET /v1/risk/margin-ratio`

﻿---
slug: margin_ratio
title: 保证金比例
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

该接口用于获取股票初始保证金比例、维持保证金比例、强平保证金比例。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name   | Type   | Required | Description                                          |
| ------ | ------ | -------- | ---------------------------------------------------- |
| symbol | string | YES      | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US` |

##### Request Example

###### Python 示例

```python
from datetime import datetime
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)
resp = ctx.margin_ratio("700.HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from datetime import datetime
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)
    resp = await ctx.margin_ratio("700.HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "data": {
    "im_factor": "0.1",
    "mm_factor": "0.1",
    "fm_factor": "0.1"
  }
}
```

##### Response Status

| Status | Description | Schema                                      |
| ------ | ----------- | ------------------------------------------- |
| 200    | 返回成功    | [margin_ratio_rsp](#schemamargin_ratio_rsp) |
| 400    | 内部错误    | None                                        |

<aside className="success">
</aside>

#### Schemas

##### margin_ratio_rsp

| Name      | Type   | Required | Description    |
| --------- | ------ | -------- | -------------- |
| im_factor | string | true     | 初始保证金比例 |
| mm_factor | string | true     | 维持保证金比例 |
| fm_factor | string | true     | 强平保证金比例 |

#### 1.5 股票持仓

- **Python SDK**：`TradeContext.stock_positions(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[股票持仓](https://open.longbridge.com/zh-CN/docs/trade/asset/stock)
- **HTTP**：`GET /v1/asset/stock`

该接口用于获取包括账户、股票代码、持仓股数、可用股数、持仓均价（按账户设置计算均价方式）、币种在内的股票持仓信息。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name   | Type     | Required | Description                                          |
| ------ | -------- | -------- | ---------------------------------------------------- |
| symbol | string[] | NO       | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US` |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)
resp = ctx.stock_positions()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)
    resp = await ctx.stock_positions()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "account_channel": "lb",
        "stock_info": [
          {
            "symbol": "700.HK",
            "symbol_name": "腾讯控股",
            "currency": "HKD",
            "quantity": "650",
            "market": "HK",
            "available_quantity": "-450",
            "cost_price": "457.53",
            "init_quantity": "214"
          },
          {
            "symbol": "9991.HK",
            "symbol_name": "宝尊电商-SW",
            "currency": "HKD",
            "market": "HK",
            "quantity": "200",
            "available_quantity": "0",
            "cost_price": "32.25",
            "init_quantity": "214"
          },
          {
            "symbol": "TCEHY.US",
            "symbol_name": "腾讯控股 (ADR)",
            "currency": "USD",
            "market": "US",
            "quantity": "10",
            "available_quantity": "10",
            "init_quantity": "18"
          },
          {
            "symbol": "2628.HK",
            "symbol_name": "中国人寿",
            "currency": "HKD",
            "market": "HK",
            "quantity": "9000",
            "available_quantity": "0",
            "init_quantity": "8000"
          },
          {
            "symbol": "5.HK",
            "symbol_name": "汇丰控股",
            "currency": "HKD",
            "market": "HK",
            "quantity": "2400",
            "available_quantity": "2000",
            "init_quantity": "2000"
          },
          {
            "symbol": "BABA.US",
            "symbol_name": "阿里巴巴",
            "currency": "USD",
            "market": "US",
            "quantity": "2000209",
            "available_quantity": "2000209",
            "init_quantity": "214"
          },
          {
            "symbol": "2.HK",
            "symbol_name": "中电控股",
            "currency": "HKD",
            "market": "HK",
            "quantity": "2000",
            "available_quantity": "2000",
            "init_quantity": "2000"
          },
          {
            "symbol": "NOK.US",
            "symbol_name": "诺基亚",
            "currency": "USD",
            "market": "US",
            "quantity": "1",
            "available_quantity": "0",
            "init_quantity": "1"
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                        |
| ------ | ----------- | ----------------------------- |
| 200    | 返回成功    | [stock_rsp](#schemastock_rsp) |
| 400    | 内部错误    | None                          |

<aside className="success">
</aside>

#### Schemas

##### stock_rsp

| Name                  | Type     | Required | Description                                       |
| --------------------- | -------- | -------- | ------------------------------------------------- |
| list                  | object[] | false    | 股票持仓信息                                      |
| ∟ account_channel     | string   | true     | 账户类型                                          |
| ∟ stock_info          | object[] | false    | 股票列表                                          |
| ∟∟ symbol             | string   | true     | 股票代码                                          |
| ∟∟ symbol_name        | string   | true     | 股票名称                                          |
| ∟∟ quantity           | string   | true     | 持仓股数                                          |
| ∟∟ available_quantity | string   | false    | 可用股数                                          |
| ∟∟ currency           | string   | true     | 币种                                              |
| ∟∟ market             | string   | true     | 市场                                              |
| ∟∟ cost_price         | string   | true     | 成本价格 (具体根据客户端选择平均买入还是摊薄成本) |
| ∟∟ init_quantity      | string   | false    | 开盘前初始持仓                                    |

#### 1.6 美股资产概览

- **Python SDK**：`TradeContext.us_asset_overview(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[美股资产概览](https://open.longbridge.com/zh-CN/docs/trade/asset/us_asset_overview)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股账户资产概览——买入力、现金、股票、期权和加密货币。

#### Parameters

> **SDK 方法参数。**

无需参数。

#### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)
resp = ctx.us_asset_overview()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)
    resp = await ctx.us_asset_overview()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "account_type": "US",
  "asset_timestamp": 1751866334,
  "cash_buy_power": "12500.00",
  "overnight_buy_power": "10000.00",
  "currency": "USD",
  "cash_list": [
    {
      "currency": "USD",
      "total_cash": "12500.00",
      "settled_cash": "12000.00",
      "total_amount": "12500.00",
      "outstanding": "500.00",
      "frozen_buy_cash": "0.00"
    }
  ],
  "stock_list": [
    {
      "symbol": "AAPL.US",
      "quantity": "10",
      "currency": "USD",
      "average_cost": "180.00",
      "last_done": "185.00",
      "prev_close": "183.00",
      "asset_type": "stock",
      "trade_status": "Normal"
    }
  ],
  "crypto_list": [
    {
      "symbol": "BTCUSD.BKKT",
      "average_cost": "50000.00",
      "currency": "USD",
      "asset_type": "crypto",
      "industry_name": "Cryptocurrency"
    }
  ]
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [USAssetOverview](#USAssetOverview) |
| 400    | 请求错误 | None   |

#### Schemas

##### USAssetOverview

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| account_type | string | 是 | 账户类型标识 |
| asset_timestamp | int64 | 是 | 资产数据快照时间（Unix 秒） |
| cash_buy_power | string | 是 | 可用买入力（现金） |
| overnight_buy_power | string | 是 | 隔夜买入力 |
| currency | string | 是 | 基础货币 |
| cash_list | USCashEntry[] | 否 | 按货币分列的现金余额 |
| stock_list | USStockEntry[] | 否 | 股票持仓 |
| option_list | object[] | 否 | 期权持仓 |
| crypto_list | USCryptoEntry[] | 否 | 加密货币持仓 |

##### USCashEntry

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| currency | string | 货币代码 |
| total_cash | string | 总现金 |
| settled_cash | string | 已结算现金 |
| total_amount | string | 含未结算的总金额 |
| outstanding | string | 未结算金额 |
| frozen_buy_cash | string | 待成交买单冻结金额 |

##### USStockEntry

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| symbol | string | 股票代码（如 `AAPL`） |
| full_symbol | string | 完整代码（如 `AAPL.US`） |
| asset_type | string | 资产类型 |
| quantity | string | 持有数量 |
| currency | string | 货币代码 |
| average_cost | string | 平均持仓成本价 |
| market | string | 市场标识 |
| trade_status | string | 交易状态 |
| prev_close | string | 上一收盘价 |
| last_done | string | 最新成交价 |
| market_price | string | 当前市场价格 |
| today_pl | string | 当日盈亏 |
| name | string | 证券名称 |
| position_side | string | 持仓方向（多/空） |
| industry_name | string | 行业/板块名称 |

##### USCryptoEntry

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| symbol | string | 加密货币交易对代码，如 `BTCUSD.BKKT` |
| average_cost | string | 平均持仓成本价 |
| currency | string | 计价货币 |
| asset_type | string | 资产类型 |
| industry_name | string | 行业/分类名称 |

#### 1.7 美股已实现盈亏

- **Python SDK**：`TradeContext.us_realized_pl(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[美股已实现盈亏](https://open.longbridge.com/zh-CN/docs/trade/asset/us_realized_pl)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股账户已实现盈亏，按资产类别（股票/期权/加密货币）分组。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| currency | string | 是 | 结算货币，例如 `USD` |
| category | string | 否 | 资产类别：`ALL` \| `STOCK` \| `OPTION` \| `CRYPTO`（默认：`ALL`） |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)
resp = ctx.us_realized_pl("USD", category="STOCK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)
    resp = await ctx.us_realized_pl("USD", category="STOCK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "realized_pl_list": [
    {
      "category": 1,
      "currency": "USD",
      "metrics": [
        {"amount": "1250.50", "period": 1, "rate": "0.0312"}
      ]
    },
    {
      "category": 3,
      "currency": "USD",
      "metrics": [
        {"amount": "-85.20", "period": 1, "rate": "-0.0215"}
      ]
    }
  ]
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [USRealizedPL](#USRealizedPL) |
| 400    | 请求错误 | None   |

#### Schemas

##### USRealizedPL

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| realized_pl_list | USRealizedPLEntry[] | 是 | 按资产类别分列的盈亏明细 |

##### USRealizedPLEntry

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| category | int | 是 | 资产类别：`1`=股票，`2`=期权，`3`=加密货币 |
| currency | string | 是 | 货币代码，如 `USD` |
| metrics | USRealizedPLMetric[] | 是 | 按时期分列的盈亏指标 |

##### USRealizedPLMetric

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| amount | string | 是 | 已实现盈亏金额 |
| period | int | 是 | 时间周期 |
| rate | string | 是 | 收益率（%） |

#### 1.8 history_executions

- **Python SDK**：`TradeContext.history_executions(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[history_executions](https://open.longbridge.com/zh-CN/docs/trade/execution/history_executions)
- **HTTP**：`GET /v1/trade/execution/history`

﻿---
slug: history_executions
sidebar_position: 1
title: 历史成交明细
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

该接口用于获取历史订单的成交明细，包括买入和卖出的成交记录，不支持当日成交明细查询。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name     | Type   | Required | Description                                                                                                   |
| -------- | ------ | -------- | ------------------------------------------------------------------------------------------------------------- |
| symbol   | string | NO       | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US`                                                          |
| start_at | string | NO       | 开始时间，格式为时间戳 (秒)，例如：`1650410999`。<br/><br/>开始时间为空时，默认为结束时间或当前时间前九十天。 |
| end_at   | string | NO       | 结束时间，格式为时间戳 (秒)，例如：`1650410999`。<br/><br/>结束时间为空时，默认为开始时间后九十天或当前时间。 |

##### Request Example

###### Python 示例

```python
from datetime import datetime
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)

resp = ctx.history_executions(
    symbol = "700.HK",
    start_at = datetime(2022, 5, 9),
    end_at = datetime(2022, 5, 12),
)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from datetime import datetime
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)

    resp = await ctx.history_executions(
        symbol = "700.HK",
        start_at = datetime(2022, 5, 9),
        end_at = datetime(2022, 5, 12),
    )
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "has_more": false,
    "trades": [
      {
        "order_id": "693664675163312128",
        "price": "388",
        "quantity": "100",
        "symbol": "700.HK",
        "trade_done_at": "1648611351",
        "trade_id": "693664675163312128-1648611351433741210"
      }
    ]
  }
}
```

##### Response Status

| Status | Description              | Schema                                                  |
| ------ | ------------------------ | ------------------------------------------------------- |
| 200    | 查询成功                 | [history_executions_rsp](#schemahistory_executions_rsp) |
| 400    | 查询失败，请求参数错误。 | None                                                    |

<aside className="success">
</aside>

#### Schemas

##### history_executions_rsp

| Name            | Type     | Required | Description                                                                                                   |
| --------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------- |
| has_more        | boolean  | true     | 是否还有更多数据。<br/><br/>每次查询最大订单数量为 1000，如果查询结果数量超过 1000，那么 has_more 就会为 true |
| trades          | object[] | false    | 成交明细信息                                                                                                  |
| ∟ order_id      | string   | true     | 订单 ID                                                                                                       |
| ∟ trade_id      | string   | true     | 成交 ID                                                                                                       |
| ∟ symbol        | string   | true     | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US`                                                          |
| ∟ trade_done_at | string   | true     | 成交时间，格式为时间戳 (秒)                                                                                   |
| ∟ quantity      | string   | true     | 成交数量                                                                                                      |
| ∟ price         | string   | true     | 成交价格                                                                                                      |

#### 1.9 today_executions

- **Python SDK**：`TradeContext.today_executions(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[today_executions](https://open.longbridge.com/zh-CN/docs/trade/execution/today_executions)
- **HTTP**：`GET /v1/trade/execution/today`

﻿---
slug: today_executions
sidebar_position: 2
title: 当日成交明细
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

该接口用于获取当日订单的成交明细。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name     | Type   | Required | Description                                               |
| -------- | ------ | -------- | --------------------------------------------------------- |
| symbol   | string | NO       | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US`      |
| order_id | string | NO       | 订单 ID，用于指定订单 ID 查询，例如：`701276261045858304` |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)

resp = ctx.today_executions(symbol = "700.HK")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)

    resp = await ctx.today_executions(symbol = "700.HK")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "trades": [
      {
        "order_id": "693664675163312128",
        "price": "388",
        "quantity": "100",
        "symbol": "700.HK",
        "trade_done_at": "1648611351",
        "trade_id": "693664675163312128-1648611351433741210"
      }
    ]
  }
}
```

##### Response Status

| Status | Description              | Schema |
| ------ | ------------------------ | ------ |
| 200    | 查询成功                 | None   |
| 400    | 查询失败，请求参数错误。 | None   |

##### Response Schema

<aside className="success">
</aside>

#### Schemas

##### today_executions_rsp

| Name            | Type     | Required | Description                                          |
| --------------- | -------- | -------- | ---------------------------------------------------- |
| trades          | object[] | false    | 成交明细信息                                         |
| ∟ order_id      | string   | true     | 订单 ID                                              |
| ∟ trade_id      | string   | true     | 成交 ID                                              |
| ∟ symbol        | string   | true     | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US` |
| ∟ trade_done_at | string   | true     | 成交时间，格式为时间戳 (秒)                          |
| ∟ quantity      | string   | true     | 成交数量                                             |
| ∟ price         | string   | true     | 成交价格                                             |

#### 1.10 estimate_available_buy_limit

- **Python SDK**：`TradeContext.estimate_max_purchase_quantity(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[estimate_available_buy_limit](https://open.longbridge.com/zh-CN/docs/trade/order/estimate_available_buy_limit)
- **HTTP**：`GET /v1/trade/estimate/buy_limit`

﻿---
slug: estimate_available_buy_limit
sidebar_position: 7
title: 预估最大购买数量
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

该接口用于港美股，窝轮，期权的预估最大购买数量。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name       | Type   | Required | Description                                                                                 |
| ---------- | ------ | -------- | ------------------------------------------------------------------------------------------- |
| symbol     | string | YES      | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US`                                        |
| order_type | string | YES      | [订单类型](../trade-definition#ordertype)                                                   |
| price      | string | NO       | 预估下单价格，例如：`388.5`                                                                 |
| side       | string | YES      | 买卖方向<br/><br/> **可选值：**<br/> `Buy` - 买入<br/> `Sell` - 卖出 卖出只支持美股卖空查询 |
| currency   | string | NO       | 结算货币                                                                                    |
| order_id   | string | NO       | 订单 ID，获取改单预估最大购买数量时必填                                                     |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OrderType, OrderSide, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)

resp = ctx.estimate_max_purchase_quantity(
    symbol = "700.HK",
    order_type = OrderType.LO,
    side = OrderSide.Buy,
)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OrderType, OrderSide, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)

    resp = await ctx.estimate_max_purchase_quantity(
        symbol = "700.HK",
        order_type = OrderType.LO,
        side = OrderSide.Buy,
    )
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "cash_max_qty": "100",
    "margin_max_qty": "100"
  }
}
```

##### Response Status

| Status | Description              | Schema                                                                      |
| ------ | ------------------------ | --------------------------------------------------------------------------- |
| 200    | 获取预估最大购买数量     | [estimate_available_buy_limit_rsp](#schemaestimate_available_buy_limit_rsp) |
| 400    | 查询失败，请求参数错误。 | None                                                                        |

<aside className="success">
</aside>

#### Schemas

##### estimate_available_buy_limit_rsp

预估最大购买数量

| Name           | Type   | Required | Description                  |
| -------------- | ------ | -------- | ---------------------------- |
| cash_max_qty   | string | true     | 现金可买数量，默认为空字符串 |
| margin_max_qty | string | true     | 融资可买数量，默认为空字符串 |

#### 1.11 history_orders

- **Python SDK**：`TradeContext.history_orders(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[history_orders](https://open.longbridge.com/zh-CN/docs/trade/order/history_orders)
- **HTTP**：`GET /v1/trade/order/history`

﻿---
slug: history_orders
sidebar_position: 3
title: 历史订单
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

该接口用于获取历史订单。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name     | Type     | Required | Description                                                                                                   |
| -------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------- |
| symbol   | string   | NO       | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US`                                                          |
| status   | string[] | NO       | [订单状态](../trade-definition#orderstatus)<br/><br/>例如：`status=FilledStatus&status=NewStatus`             |
| side     | string   | NO       | 买卖方向<br/><br/> **可选值：**<br/> `Buy` - 买入<br/> `Sell` - 卖出                                          |
| market   | string   | NO       | 市场<br/><br/> **可选值：**<br/> `US` - 美股<br/> `HK` - 港股                                                 |
| start_at | string   | NO       | 开始时间，格式为时间戳 (秒)，例如：`1650410999`。<br/><br/>开始时间为空时，默认为结束时间或当前时间前九十天。 |
| end_at   | string   | NO       | 结束时间，格式为时间戳 (秒)，例如：`1650410999`。<br/><br/>结束时间为空时，默认为开始时间后九十天或当前时间。 |

##### Request Example

###### Python 示例

```python
from datetime import datetime
from longbridge.openapi import TradeContext, Config, OrderStatus, OrderSide, Market, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)

resp = ctx.history_orders(
    symbol = "700.HK",
    status = [OrderStatus.Filled, OrderStatus.New],
    side = OrderSide.Buy,
    market = Market.HK,
    start_at = datetime(2022, 5, 9),
    end_at = datetime(2022, 5, 12),
)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from datetime import datetime
from longbridge.openapi import AsyncTradeContext, Config, OrderStatus, OrderSide, Market, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)

    resp = await ctx.history_orders(
        symbol = "700.HK",
        status = [OrderStatus.Filled, OrderStatus.New],
        side = OrderSide.Buy,
        market = Market.HK,
        start_at = datetime(2022, 5, 9),
        end_at = datetime(2022, 5, 12),
    )
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "orders": [
      {
        "currency": "HKD",
        "executed_price": "0.000",
        "executed_quantity": "0",
        "expire_date": "",
        "last_done": "",
        "limit_offset": "",
        "msg": "",
        "order_id": "706388312699592704",
        "order_type": "ELO",
        "outside_rth": "UnknownOutsideRth",
        "price": "11.900",
        "quantity": "200",
        "side": "Buy",
        "status": "RejectedStatus",
        "stock_name": "东亚银行",
        "submitted_at": "1651644897",
        "symbol": "23.HK",
        "tag": "Normal",
        "time_in_force": "Day",
        "trailing_amount": "",
        "trailing_percent": "",
        "trigger_at": "0",
        "trigger_price": "",
        "trigger_status": "NOT_USED",
        "updated_at": "1651644898",
        "remark": "",
        "limit_depth_level": 0,
        "monitor_price": "",
        "trigger_count": 1,
        "attached_orders": [
          {
            "order_id": "706388312699592705",
            "attached_type_display": 2,
            "trigger_price": "10.500",
            "quantity": "200",
            "executed_qty": "0",
            "status": "NewStatus",
            "updated_at": "1651644898",
            "withdrawn": false,
            "gtd": "",
            "time_in_force": "Day",
            "counter_id": "",
            "trigger_status": 0,
            "executed_amount": "0",
            "tag": 0,
            "submitted_at": "1651644897",
            "executed_price": "0.000",
            "force_only_rth": "RTH_ONLY",
            "reviewed": false,
            "activate_order_type": "MIT",
            "activate_rth": "RTH_ONLY",
            "submit_price": ""
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description              | Schema                                          |
| ------ | ------------------------ | ----------------------------------------------- |
| 200    | 历史订单查询成功         | [history_orders_rsp](#schemahistory_orders_rsp) |
| 400    | 查询失败，请求参数错误。 | None                                            |

<aside className="success">
</aside>

#### Schemas

##### history_orders_rsp

| Name                | Type     | Required | Description                                                                                                                                                                         |
| ------------------- | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| has_more            | boolean  | true     | 是否还有更多数据。<br/><br/>每次查询最大订单数量为 1000，如果查询结果数量超过 1000，那么 has_more 就会为 true                                                                       |
| orders              | object[] | false    | 订单信息                                                                                                                                                                            |
| ∟ order_id          | string   | true     | 订单 ID                                                                                                                                                                             |
| ∟ status            | string   | true     | [订单状态](../trade-definition#orderstatus)                                                                                                                                         |
| ∟ stock_name        | string   | true     | 股票名称                                                                                                                                                                            |
| ∟ quantity          | string   | true     | 下单数量                                                                                                                                                                            |
| ∟ executed_quantity | string   | true     | 成交数量。<br/><br/>当订单未成交时为 0                                                                                                                                              |
| ∟ price             | string   | true     | 下单价格。<br/><br/>当市价条件单未触发时为空字符串                                                                                                                                  |
| ∟ executed_price    | string   | true     | 成交价。<br/><br/>当订单未成交时为 0                                                                                                                                                |
| ∟ submitted_at      | string   | true     | 下单时间                                                                                                                                                                            |
| ∟ side              | string   | true     | 买卖方向<br/><br/> **可选值：**<br/> `Buy` - 买入<br/> `Sell` - 卖出                                                                                                                |
| ∟ symbol            | string   | true     | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US`                                                                                                                                |
| ∟ order_type        | string   | true     | [订单类型](../trade-definition#ordertype)                                                                                                                                           |
| ∟ last_done         | string   | true     | 最近成交价格。<br/><br/>当订单未成交时为空字符串                                                                                                                                    |
| ∟ trigger_price     | string   | true     | `LIT` / `MIT` 订单触发价格。<br/><br/>当订单不是 `LIT` / `MIT` 订单为空字符串                                                                                                       |
| ∟ msg               | string   | true     | 拒绝信息或备注，默认为空字符串。                                                                                                                                                    |
| ∟ tag               | string   | true     | 订单标记<br/><br/> **可选值：**<br/> `Normal` - 普通订单<br/> `Gtc` - 长期单<br/> `Grey` - 暗盘单                                                                                   |
| ∟ time_in_force     | string   | true     | 订单有效期类型<br/><br/> **可选值：**<br/> `Day` - 当日有效<br/> `GTC` - 撤单前有效<br/> `GTD` - 到期前有效                                                                         |
| ∟ expire_date       | string   | true     | 长期单过期时间，格式为 `YYYY-MM-DD`, 例如：`2022-12-05。<br/><br/>不是长期单时，默认为空字符串。`                                                                                   |
| ∟ updated_at        | string   | true     | 最近更新时间，格式为时间戳 (秒)，默认为 0。                                                                                                                                         |
| ∟ trigger_at        | string   | true     | 条件单触发时间，格式为时间戳 (秒)，默认为 0。                                                                                                                                       |
| ∟ trailing_amount   | string   | true     | `TSLPAMT` 订单跟踪金额。<br/><br/>当订单不是 `TSLPAMT` 订单时为空字符串。                                                                                                           |
| ∟ trailing_percent  | string   | true     | `TSLPPCT` 订单跟踪涨跌幅。<br/><br/>当订单不是 `TSLPPCT` 订单时为空字符串。                                                                                                         |
| ∟ limit_offset      | string   | true     | `TSLPAMT` / `TSLPPCT` 订单指定价差。<br/><br/>当订单不是 `TSLPAMT` / `TSLPPCT` 订单时为空字符串。                                                                                   |
| ∟ trigger_status    | string   | true     | 条件单触发状态<br/> 当订单不是条件单或条件单未触发时，触发状态为 NOT_USED<br/><br/> **可选值：**<br/> `NOT_USED` - 未激活 `DEACTIVE` - 已失效 `ACTIVE` - 已激活 `RELEASED` - 已触发 |
| ∟ currency          | string   | true     | 结算货币                                                                                                                                                                            |
| ∟ outside_rth       | string   | true     | 是否允许盘前盘后<br/> 当订单不是美股时，默认为 UnknownOutsideRth<br/><br/> **可选值：**<br/> `RTH_ONLY` - 不允许盘前盘后<br/> `ANY_TIME` - 允许盘前盘后<br/> `OVERNIGHT` - 夜盘"    |
| ∟ remark            | string   | true     | 备注                                                                                                                                                                                |
| ∟ limit_depth_level | int32    | true     | 指定买卖档位        |
| ∟ monitor_price     | string   | true     | 监控价格            |
| ∟ trigger_count     | int32    | true     | 触发次数            |
| ∟ attached_orders           | object[] | false    | 附加订单详情列表 |
| ∟∟ order_id                 | string   | true     | 附加订单 ID |
| ∟∟ attached_type_display    | int32    | true     | 附加订单类型。**可选值：** `1` - 止盈 `2` - 止损 |
| ∟∟ trigger_price            | string   | true     | 触发价格 |
| ∟∟ quantity                 | string   | true     | 下单数量 |
| ∟∟ executed_qty             | string   | true     | 成交数量 |
| ∟∟ status                   | string   | true     | 订单状态 |
| ∟∟ updated_at               | string   | true     | 最近更新时间，格式为时间戳 (秒) |
| ∟∟ withdrawn                | boolean  | true     | 是否已撤销 |
| ∟∟ gtd                      | string   | true     | GTD 到期日期，格式为 `YYYY-MM-DD` |
| ∟∟ time_in_force            | string   | true     | 订单有效期类型<br/><br/> **可选值：**<br/> `Day` - 当日有效<br/> `GTC` - 撤单前有效<br/> `GTD` - 到期前有效 |
| ∟∟ counter_id               | string   | true     | 对应单 ID |
| ∟∟ trigger_status           | int32    | true     | 附加单激活后的条件单触发状态。<br/>`0` - 未激活 <br/>`1` - 监控中 <br/>`2` - 已撤单 <br/>`4` - 已触发 |
| ∟∟ executed_amount          | string   | true     | 成交金额 |
| ∟∟ tag                      | int32    | true     | 订单标记 |
| ∟∟ submitted_at             | string   | true     | 下单时间，格式为时间戳 (秒) |
| ∟∟ executed_price           | string   | true     | 成交价格 |
| ∟∟ force_only_rth           | string   | true     | 是否仅正常交易时段执行。 |
| ∟∟ reviewed                 | boolean  | true     | 是否已审核 |
| ∟∟ activate_order_type      | string   | true     | 触发后提交的订单类型，例如 `LIT`（限价单）或 `MIT`（市价单） |
| ∟∟ activate_rth             | string   | true     | 触发后提交订单是否允许盘前盘后。|
| ∟∟ submit_price             | string   | true     | 委托价格 |

#### 1.12 将下方订单 ID 替换为实际的订单 ID

- **Python SDK**：`TradeContext.order_detail(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[将下方订单 ID 替换为实际的订单 ID](https://open.longbridge.com/zh-CN/docs/trade/order/order_detail)
- **HTTP**：`GET /v1/trade/order`

﻿---
slug: order_detail
sidebar_position: 4
title: 订单详情
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

该接口用于订单详情查询。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name     | Type   | Required | Description                                               |
| -------- | ------ | -------- | --------------------------------------------------------- |
| order_id | string | YES      | 订单 ID，用于指定订单 ID 查询，例如：`701276261045858304` |
| is_attached | bool   | NO       | order_id 是否为附加单  |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)

resp = ctx.order_detail(
    order_id = "701276261045858304",
    is_attached = False,
)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)

    resp = await ctx.order_detail(
        order_id = "701276261045858304",
        is_attached = False,
    )
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "order_id": "828940451093708800",
    "status": "FilledStatus",
    "stock_name": "苹果",
    "quantity": "10",
    "executed_quantity": "10",
    "price": "200.000",
    "executed_price": "164.660",
    "submitted_at": "1680863604",
    "side": "Buy",
    "symbol": "AAPL.US",
    "order_type": "LO",
    "last_done": "164.660",
    "trigger_price": "0.0000",
    "msg": "",
    "tag": "Normal",
    "time_in_force": "Day",
    "expire_date": "2023-04-10",
    "updated_at": "1681113000",
    "trigger_at": "0",
    "trailing_amount": "",
    "trailing_percent": "",
    "limit_offset": "",
    "limit_depth_level": 0,
    "monitor_price": "",
    "trigger_count": 1,
    "trigger_status": "NOT_USED",
    "outside_rth": "ANY_TIME",
    "currency": "USD",
    "remark": "1680863603.927165",
    "free_status": "None",
    "free_amount": "",
    "free_currency": "",
    "deductions_status": "NONE",
    "deductions_amount": "",
    "deductions_currency": "",
    "platform_deducted_status": "NONE",
    "platform_deducted_amount": "",
    "platform_deducted_currency": "",
    "history": [
      {
        "price": "164.6600",
        "quantity": "10",
        "status": "FilledStatus",
        "msg": "Execution of 10",
        "time": "1681113000"
      },
      {
        "price": "200.0000",
        "quantity": "10",
        "status": "NewStatus",
        "msg": "",
        "time": "1681113000"
      }
    ],
    "charge_detail": {
      "items": [
        {
          "code": "BROKER_FEES",
          "name": "收费明细",
          "fees": []
        },
        {
          "code": "THIRD_FEES",
          "name": "第三方收费明细",
          "fees": []
        }
      ],
      "total_amount": "0",
      "currency": "USD"
    },
    "attached_orders": [
      {
        "order_id": "706388312699592705",
        "attached_type_display": 2,
        "trigger_price": "10.500",
        "quantity": "200",
        "executed_qty": "0",
        "status": "NewStatus",
        "updated_at": "1651644898",
        "withdrawn": false,
        "gtd": "",
        "time_in_force": "Day",
        "counter_id": "",
        "trigger_status": 0,
        "executed_amount": "0",
        "tag": 0,
        "submitted_at": "1651644897",
        "executed_price": "0.000",
        "force_only_rth": "RTH_ONLY",
        "reviewed": false,
        "activate_order_type": "MIT",
        "activate_rth": "RTH_ONLY",
        "submit_price": ""
      }
    ]
  }
}
```

##### Response Status

| Status | Description              | Schema                                      |
| ------ | ------------------------ | ------------------------------------------- |
| 200    | 订单详情查询成功         | [order_detail_rsp](#schemaorder_detail_rsp) |
| 400    | 查询失败，请求参数错误。 | None                                        |

<aside className="success">
</aside>

#### Schemas

##### order_detail_rsp

订单信息

| Name                       | Type     | Required | Description                                                                                                                                                                                        |
| -------------------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| order_id                   | string   | true     | 订单 ID                                                                                                                                                                                            |
| status                     | string   | true     | [订单状态](../trade-definition#orderstatus)                                                                                                                                                        |
| stock_name                 | string   | true     | 股票名称                                                                                                                                                                                           |
| quantity                   | string   | true     | 下单数量                                                                                                                                                                                           |
| executed_quantity          | string   | true     | 成交数量。<br/><br/>当订单未成交时为 0                                                                                                                                                             |
| price                      | string   | true     | 下单价格。<br/><br/>当市价条件单未触发时为空字符串                                                                                                                                                 |
| executed_price             | string   | true     | 成交价。<br/><br/>当订单未成交时为 0                                                                                                                                                               |
| submitted_at               | string   | true     | 下单时间                                                                                                                                                                                           |
| side                       | string   | true     | 买卖方向<br/><br/> **可选值：**<br/> `Buy` - 买入<br/> `Sell` - 卖出                                                                                                                               |
| symbol                     | string   | true     | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US`                                                                                                                                               |
| order_type                 | string   | true     | [订单类型](../trade-definition#ordertype)                                                                                                                                                          |
| last_done                  | string   | true     | 最近成交价格。<br/><br/>当订单未成交时为空字符串                                                                                                                                                   |
| trigger_price              | string   | true     | `LIT` / `MIT` 订单触发价格。<br/><br/>当订单不是 `LIT` / `MIT` 订单为空字符串                                                                                                                      |
| msg                        | string   | true     | 拒绝信息或备注，默认为空字符串。                                                                                                                                                                   |
| tag                        | string   | true     | 订单标记<br/><br/> **可选值：**<br/> `Normal` - 普通订单<br/> `Gtc` - 长期单<br/> `Grey` - 暗盘单                                                                                                  |
| time_in_force              | string   | true     | 订单有效期类型<br/><br/> **可选值：**<br/> `Day` - 当日有效<br/> `GTC` - 撤单前有效<br/> `GTD` - 到期前有效                                                                                        |
| expire_date                | string   | true     | 长期单过期时间，格式为 `YYYY-MM-DD`, 例如：`2022-12-05。<br/><br/> 不是长期单时，默认为空字符串。                                                                                                  |
| updated_at                 | string   | true     | 最近更新时间，格式为时间戳 (秒)，默认为 0。                                                                                                                                                        |
| trigger_at                 | string   | true     | 条件单触发时间，格式为时间戳 (秒)，默认为 0。                                                                                                                                                      |
| trailing_amount            | string   | true     | `TSLPAMT` 订单跟踪金额。<br/><br/>当订单不是 `TSLPAMT` 订单时为空字符串。                                                                                                                          |
| trailing_percent           | string   | true     | `TSLPPCT` 订单跟踪涨跌幅。<br/><br/>当订单不是 `TSLPPCT` 订单时为空字符串。                                                                                                                        |
| limit_offset               | string   | true     | `TSLPAMT` / `TSLPPCT` 订单指定价差。<br/><br/>当订单不是 `TSLPAMT` / `TSLPPCT` 订单时为空字符串。                                                                                                  |
| trigger_status             | string   | true     | 条件单触发状态<br/> 当订单不是条件单或条件单未触发时，触发状态为 NOT_USED<br/><br/> **可选值：**<br/> `NOT_USED` - 未激活<br/> `DEACTIVE` - 已失效<br/> `ACTIVE` - 已激活<br/> `RELEASED` - 已触发 |
| currency                   | string   | true     | 结算货币                                                                                                                                                                                           |
| outside_rth                | string   | true     | 是否允许盘前盘后<br/> 当订单不是美股时，默认为 UnknownOutsideRth<br/><br/> **可选值：**<br/> `RTH_ONLY` - 不允许盘前盘后<br/> `ANY_TIME` - 允许盘前盘后<br/> `OVERNIGHT` - 夜盘"                   |
| remark                     | string   | true     | 备注                                                                                                                                                                                               |
| free_status                | string   | true     | 免佣状态，默认为 None<br/><br/> **可选值：**<br/> `None` - 无<br/> `Calculated` - 免佣额待计算<br/> `Pending` - 待免佣<br/> `Ready` - 已免佣                                                       |
| free_amount                | string   | true     | 免佣金额，默认为空字符串                                                                                                                                                                           |
| free_currency              | string   | true     | 免佣货币，默认为空字符串                                                                                                                                                                           |
| deductions_status          | string   | true     | 抵扣状态/返现状态，默认为 NONE<br/><br/> **可选值：**<br/> `NONE` - 待结算 <br/> `NO_DATA` - 已结算无数据<br/> `PENDING` - 已结算待发放<br/> `DONE` - 已结算已发放                                 |
| deductions_amount          | string   | true     | 抵扣金额，默认为空字符串                                                                                                                                                                           |
| deductions_currency        | string   | true     | 抵扣货币，默认为空字符串                                                                                                                                                                           |
| platform_deducted_status   | string   | true     | 平台费抵扣状态/返现状态，默认为 NONE<br/><br/> **可选值：**<br/> `NONE` - 待结算 <br/> `NO_DATA` - 已结算无数据<br/> `PENDING` - 已结算待发放<br/> `DONE` - 已结算已发放                           |
| platform_deducted_amount   | string   | true     | 平台费抵扣金额，默认为空字符串                                                                                                                                                                     |
| platform_deducted_currency | string   | true     | 平台费抵扣货币，默认为空字符串                                                                                                                                                                     |
| history                    | object[] | true     | 订单历史明细                                                                                                                                                                                       |
| ∟ price                    | string   | true     | 成交展示成交价格，过期、撤单、拒绝等状态展示提交价格                                                                                                                                               |
| ∟ quantity                 | string   | true     | 成交展示成交数量，过期、撤单、拒绝等状态展示剩余数量                                                                                                                                               |
| ∟ status                   | string   | true     | 订单状态                                                                                                                                                                                           |
| ∟ msg                      | string   | true     | 成交或错误信息                                                                                                                                                                                     |
| ∟ time                     | string   | true     | 发生时间                                                                                                                                                                                           |
| charge_detail              | object   | true     | 订单费用                                                                                                                                                                                           |
| ∟ total_amount             | string   | true     | 全部费用                                                                                                                                                                                           |
| ∟ currency                 | string   | true     | 结算货币                                                                                                                                                                                           |
| ∟ items                    | object[] | true     | 订单费用明细                                                                                                                                                                                       |
| ∟∟ code                    | string   | true     | 收费类别代码<br/><br/> **可选值：**<br/> `UNKNOWN`<br/> `BROKER_FEES`<br/> `THIRD_FEES`                                                                                                            |
| ∟∟ name                    | string   | true     | 收费类别名称                                                                                                                                                                                       |
| ∟∟ fees                    | object[] | true     | 收费明细                                                                                                                                                                                           |
| ∟∟∟ code                   | string   | true     | 收费代码                                                                                                                                                                                           |
| ∟∟∟ name                   | string   | true     | 收费名称                                                                                                                                                                                           |
| ∟∟∟ amount                 | string   | true     | 单项收费金额                                                                                                                                                                                       |
| ∟∟∟ currency               | string   | true     | 收费货币                                                                                                                                                                                           |
| ∟ limit_depth_level        | int32    | true     | 指定买卖档位 |
| ∟ monitor_price            | string   | true     | 监控价格 |
| ∟ trigger_count            | int32    | true     | 触发次数 |
| ∟ attached_orders          | object[] | false    | 附加订单详情列表 |
| ∟∟ order_id                | string   | true     | 附加订单 ID |
| ∟∟ attached_type_display   | int32    | true     | 附加订单类型。**可选值：** `1` - 止盈 `2` - 止损 |
| ∟∟ trigger_price           | string   | true     | 触发价格 |
| ∟∟ quantity                | string   | true     | 下单数量 |
| ∟∟ executed_qty            | string   | true     | 成交数量 |
| ∟∟ status                  | string   | true     | 订单状态 |
| ∟∟ updated_at              | string   | true     | 最近更新时间，格式为时间戳 (秒) |
| ∟∟ withdrawn               | boolean  | true     | 是否已撤销 |
| ∟∟ gtd                     | string   | true     | GTD 到期日期，格式为 `YYYY-MM-DD` |
| ∟∟ time_in_force           | string   | true     | 订单有效期类型<br/><br/> **可选值：**<br/> `Day` - 当日有效<br/> `GTC` - 撤单前有效<br/> `GTD` - 到期前有效 |
| ∟∟ counter_id              | string   | true     | 对应单 ID |
| ∟∟ trigger_status          | int32    | true     | 附加单激活后的条件单触发状态。<br/>`0` - 未激活 <br/>`1` - 监控中 <br/>`2` - 已撤单 <br/>`4` - 已触发 |
| ∟∟ executed_amount         | string   | true     | 成交金额 |
| ∟∟ tag                     | int32    | true     | 订单标记 |
| ∟∟ submitted_at            | string   | true     | 下单时间，格式为时间戳 (秒) |
| ∟∟ executed_price          | string   | true     | 成交价格 |
| ∟∟ force_only_rth          | string   | true     | 是否仅正常交易时段执行。 |
| ∟∟ reviewed                | boolean  | true     | 是否已审核 |
| ∟∟ activate_order_type     | string   | true     | 触发后提交的订单类型，例如 `LIT`（限价单）或 `MIT`（市价单） |
| ∟∟ activate_rth            | string   | true     | 触发后提交订单是否允许盘前盘后。 |
| ∟∟ submit_price            | string   | true     | 委托价格 |

#### 1.13 将下方订单 ID 替换为实际的订单 ID

- **Python SDK**：`TradeContext.replace_order(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[将下方订单 ID 替换为实际的订单 ID](https://open.longbridge.com/zh-CN/docs/trade/order/replace)
- **HTTP**：`PUT /v1/trade/order`

﻿---
slug: replace
sidebar_position: 5
title: 修改订单
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

该接口用于修改订单的价格，数量。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name             | Type   | Required | Description                                                                     |
| ---------------- | ------ | -------- | ------------------------------------------------------------------------------- |
| order_id         | string | YES      | 订单 ID                                                                         |
| quantity         | string | YES      | 改单数量，例如：`200`                                                           |
| price            | string | NO       | 改单价格，例如：`388.5`<br/><br/> `LO` / `ELO` / `ALO` / `ODD` / `LIT` 订单必填 |
| trigger_price    | string | NO       | 触发价格，例如：`388.5`<br/><br/> `LIT` / `MIT` 订单必填                        |
| limit_offset     | string | NO       | 指定价差<br/><br/> `TSLPAMT` / `TSLPPCT` 订单在 `limit_depth_level` 为 0 时必填  |
| trailing_amount  | string | NO       | 跟踪金额<br/><br/> `TSLPAMT` 订单必填                                           |
| trailing_percent | string | NO       | 跟踪涨跌幅<br/><br/> `TSLPPCT` 订单必填                                         |
| remark           | string | NO       | 备注 (最大 64 字符)                                                             |
| limit_depth_level | int32 | NO       | 指定买卖档位，`TSLPAMT` / `TSLPPCT` 订单必填                                      |
| monitor_price     | string| NO       | 监控价格，`TSLPAMT` / `TSLPPCT` 订单必填                                         |
| trigger_count     | int32 | NO       | 触发次数，`LIT` / `MIT` / `TSLPAMT` / `TSLPPCT` 订单必填                         |
| attached_params   | object | NO      | 附加单参数（止盈止损） |
| attached_params.attached_order_type | string | NO | 附加单订单类型<br/><br/>**可选值：**<br/>`PROFIT_TAKER` - 止盈<br/>`STOP_LOSS` - 止损<br/>`BRACKET` - 括号单 |
| attached_params.profit_taker_price | string | NO | 止盈触发价格 |
| attached_params.stop_loss_price | string | NO | 止损触发价格 |
| attached_params.time_in_force | string | NO | 附加单有效期类型<br/><br/>**可选值：**<br/>`Day` - 当日有效<br/> `GTC` - 撤单前有效<br/> `GTD` - 到期前有效（此时继承主单 expire_date） |
| attached_params.expire_time | int64 | NO | 到期时间（Unix 时间戳，单位秒） |
| attached_params.profit_taker_id | int64 | NO | 止盈单 ID，修改现有止盈单时填写 |
| attached_params.stop_loss_id | int64 | NO | 止损单 ID，修改现有止损单时填写 |
| attached_params.cancel_all_attached | bool | NO | 是否取消所有附加单 |
| attached_params.main_id | int64 | NO | 主单 ID |
| attached_params.quantity | string | NO | 附加单数量 |
| attached_params.market_price | string | NO | 市价 |
| attached_params.activate_order_type | string | NO | 触发后提交的订单类型，例如 `LIT`（限价单）或 `MIT`（市价单） |
| attached_params.profit_taker_submit_price | string | NO | 止盈限价委托价格，`activate_order_type` 为 `LIT` 时必填 |
| attached_params.stop_loss_submit_price | string | NO | 止损限价委托价格，`activate_order_type` 为 `LIT` 时必填 |
| attached_params.activate_rth | string | NO | 触发后提交的订单是否允许盘前盘后<br/><br/>**可选值：**<br/> `RTH_ONLY` - 不允许盘前盘后<br/> `ANY_TIME` - 允许盘前盘后 |

##### Request Example

###### Python 示例

```python
from decimal import Decimal
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)

ctx.replace_order(
    order_id = "709043056541253632",
    quantity = Decimal(100),
    price = Decimal(50),
)
```

###### Python 异步示例

```python
import asyncio
from decimal import Decimal
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)

    ctx.replace_order(
        order_id = "709043056541253632",
        quantity = Decimal(100),
        price = Decimal(50),
    )

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

##### Response Status

| Status | Description                | Schema |
| ------ | -------------------------- | ------ |
| 200    | 提交成功，订单已委托。     | None   |
| 400    | 下单被拒绝，请求参数错误。 | None   |

<aside className="success">
</aside>

#### 1.14 委托下单

- **Python SDK**：`TradeContext.submit_order(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[委托下单](https://open.longbridge.com/zh-CN/docs/trade/order/submit)
- **HTTP**：`POST /v1/trade/order`

该接口用于港美股，窝轮，期权的委托下单。

#### Request

#### Parameters

> Content-Type: application/json; charset=utf-8

| Name               | Type   | Required | Description                                                                                                                               |
| ------------------ | ------ | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| symbol             | string | YES      | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US`                                                                                      |
| order_type         | string | YES      | [订单类型](../trade-definition#ordertype)                                                                                                 |
| submitted_price    | string | NO       | 下单价格，例如：`388.5`<br/><br/> `LO` / `ELO` / `ALO` / `ODD` / `LIT` 订单必填                                                           |
| submitted_quantity | string | YES      | 下单数量，例如：`100`                                                                                                                     |
| trigger_price      | string | NO       | 触发价格，例如：`388.5`<br/><br/> `LIT` / `MIT` 订单必填                                                                                  |
| limit_offset       | string | NO       | 指定价差，例如 "1.2" 表示价差 1.2 USD (如果是美股)<br/><br/> `TSLPAMT` / `TSLPPCT` 订单在 `limit_depth_level` 为 0 时必填 |
| trailing_amount    | string | NO       | 跟踪金额<br/><br/> `TSLPAMT` 订单必填                                                                                                     |
| trailing_percent   | string | NO       | 跟踪涨跌幅，单位为百分比，例如 "2.5" 表示 "2.5%"<br/><br/> `TSLPPCT` 订单必填                                                             |
| expire_date        | string | NO       | 长期单过期时间，格式为 `YYYY-MM-DD`, 例如：`2022-12-05`<br/><br/> time_in_force 为 `GTD` 时必填                                           |
| side               | string | YES      | 买卖方向<br/><br/> **可选值：**<br/> `Buy` - 买入<br/> `Sell` - 卖出                                                                      |
| outside_rth        | string | NO       | 是否允许盘前盘后，美股必填<br/><br/> **可选值：**<br/> `RTH_ONLY` - 不允许盘前盘后<br/> `ANY_TIME` - 允许盘前盘后<br/> `OVERNIGHT` - 夜盘 |
| time_in_force      | string | YES      | 订单有效期类型<br/><br/> **可选值：**<br/> `Day` - 当日有效<br/> `GTC` - 撤单前有效<br/> `GTD` - 到期前有效                               |
| remark             | string | NO       | 备注 (最大 64 字符)                                                                                                                       |
| limit_depth_level  | int32  | NO       | 指定买卖档位，取值范围为 -5 ～ 0 ～ 5，负数代表买盘档位（如 -1 表示买一），<br/>正数代表卖盘档位（如 1 表示卖一），为 0 时 limit_offset 参数生效<br/>`TSLPAMT` / `TSLPPCT` 订单有效 |
| monitor_price      | string |  NO      | 监控价格，需要达到该价格才会开始监控，更新参考价<br/>`TSLPAMT` / `TSLPPCT` 订单有效 |
| trigger_count      | int32  |  NO      | 触发次数，取值范围 0 ~ 3, 表示在 1 分钟内触发多次才会触发订单<br/>`LIT` / `MIT` / `TSLPAMT` / `TSLPPCT` 订单有效 |
| client_request_id  | string | NO       | 幂等性请求 ID，用于防止重复下单。服务器会缓存该请求 ID 10 分钟。在此期间内如果收到相同 ID 的请求，将返回原始响应而不创建重复订单。必须是唯一标识符（如 UUID）。 |
| attached_params    | object |  NO      | 附加单参数（止盈止损） |
| attached_params.attached_order_type | string | NO | 附加单订单类型<br/><br/>**可选值：**<br/>`PROFIT_TAKER` - 止盈<br/>`STOP_LOSS` - 止损<br/>`BRACKET` - 括号单 |
| attached_params.profit_taker_price | string | NO | 止盈触发价格 |
| attached_params.stop_loss_price | string | NO | 止损触发价格 |
| attached_params.time_in_force | string | NO | 附加单有效期类型<br/><br/>**可选值：**<br/>`Day` - 当日有效<br/> `GTC` - 撤单前有效<br/> `GTD` - 到期前有效（此时继承主单 expire_date） |
| attached_params.expire_time | int64 | NO | 到期时间（Unix 时间戳，单位秒） |
| attached_params.activate_order_type | string | NO | 触发后提交的订单类型，例如 `LIT`（限价单）或 `MIT`（市价单） |
| attached_params.profit_taker_submit_price | string | NO | 止盈限价委托价格，`activate_order_type` 为 `LIT` 时必填 |
| attached_params.stop_loss_submit_price | string | NO | 止损限价委托价格，`activate_order_type` 为 `LIT` 时必填 |
| attached_params.activate_rth | string | NO | 触发后提交的订单是否允许盘前盘后 <br/><br/>**可选值：**<br/> `RTH_ONLY` - 不允许盘前盘后<br/> `ANY_TIME` - 允许盘前盘后 |

#### 幂等性

为了防止由于网络重试或客户端故障而导致订单重复，您可以使用 `client_request_id` 参数：

- **用途**：防止相同请求重试时创建重复订单
- **缓存时长**：10 分钟（服务器端）
- **格式**：每个请求需要一个唯一字符串（如 UUID 或自定义标识符）
- **行为**：如果在 10 分钟内收到相同的 `client_request_id`，服务器将返回原始请求的缓存响应，而不创建新订单

###### 幂等性示例

```
首次请求：client_request_id="abc123-uuid-request" → 创建订单，ID 为 12345
重试请求（10 分钟内，相同 ID）：client_request_id="abc123-uuid-request" → 返回现有订单 ID 12345（无重复）
新请求：client_request_id="xyz789-uuid-request" → 创建新订单
```

###### 不传 client_request_id 的情况

如果不提供 `client_request_id`（或传空值），请求仍会正常成功并创建订单。但是**幂等拦截将被跳过**，这意味着：

- 每个请求（即使内容完全相同）都会创建单独的订单
- 网络重试或意外重复请求可能导致订单重复
- 服务器不会对该请求进行缓存

强烈建议在关键下单操作中始终提供唯一的 `client_request_id`，以防止意外的重复订单。

#### Examples

为了方便理解，我们下面以 Python 作为示例，介绍如何实现一些场景的下单操作。

##### 建仓买入

我们期望以 380 HKD 价格，买入 100 股 `700.HK`，并设定“订单当日有效”。

```py
from decimal import Decimal
from longbridge.openapi import TradeContext, Config, OrderType, OrderSide, TimeInForceType, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)

### Create a context for trade APIs
ctx = TradeContext(config)

resp = ctx.submit_order(
    "700.HK",
    OrderType.LO,
    OrderSide.Buy,
    Decimal(100),
    TimeInForceType.Day,
    submitted_price=Decimal(380),
    remark="Hello from Python SDK",
)
```

其中：

- `OrderSide.Buy` - 表示买入
- `OrderType.LO` - 表示挂单为**限价单**，当为限价单时，我们需要传递 `submitted_price` 参数
- `TimeInForceType.Day` - 表示订单当日有效

##### 平仓卖出

提交市价单，卖出 100 股 `700.HK`，并设定“订单当日有效”。

```py
ctx.submit_order(
    "700.HK",
    OrderType.MO,
    OrderSide.Sell,
    Decimal(100),
    TimeInForceType.Day,
    remark="Hello from Python SDK",
)
```

- `OrderType.MO` - 表示挂单为**市价单**
- `OrderSide.Sell` - 表示卖出

##### 到价止盈止损

> 对应我们客户端下单界面上的“到价买入”和“到价卖出”订单类型。

假定我们在持有 100 股 `NVDA.US` 前提下，监控市价在跌破 1000.00 USD 价格时，以 999.00 限价单平仓，并设定**订单撤销前有效**。

:::tip
**订单撤销前有效** - 是指订单在达到条件后，会一直有效直到被成交或者被撤销。
:::

```py
ctx.submit_order(
    "NVDA.US",
    OrderType.LIT,
    OrderSide.Sell,
    Decimal(100),
    TimeInForceType.GoodTilCanceled,
    Decimal("999.00"),
    trigger_price=Decimal("1000.00"),
    remark="Hello from Python SDK",
)
```

- `OrderType.LIT` - 表示挂单为**触价限价单**
- `TimeInForceType.GoodTilCanceled` - 表示订单撤销前有效
- `trigger_price` - 参数用于设定触发价格，当行情价格达到触发价格时，订单会被提交

##### 跟踪止盈止损

> 对应我们客户端下单界面上的“反弹买入”和“回落卖出”订单类型。

我们有时候需要设定一个跟踪止盈止损，以保护我们的盈利或者减少损失。

假定我们持有 100 股 `NVDA.US`，提交一个条件单，监控 `NVDA.US` 的行情变化，当市价在下单后的**最高点回落** 0.5% 时，按照触发时的市价，减少 1.2 USD，挂出一个限价单，订单在 6 月 30 日前有效。

可以用下面的代码实现：

```py
ctx.submit_order(
    "NVDA.US",
    OrderType.TSLPPCT,
    OrderSide.Sell,
    Decimal(100),
    TimeInForceType.GoodTilDate,
    expire_date=datetime.date(2024, 6, 30),
    trailing_percent=Decimal("0.5"),
    limit_offset=Decimal("1.2"),
    remark="Hello from Python SDK",
)
```

- `OrderType.TSLPPCT` - 表示挂单为**跟踪止损限价单 (跟踪涨跌幅)**，这里如果你想要使用**跟踪金额**，可以使用 `TSLPAMT`
- `TimeInForceType.GoodTilDate` - 表示订单到期前有效，当传递此类型参数是，我们也需要传递 `expire_date` 参数
- `expire_date` - 参数用于设定订单到期时间
- `trailing_percent` - 参数用于设定跟踪涨跌幅，如 `0.5` 表示 0.5%
- `limit_offset` - 参数用于设定指定价差，这里 `1.2` 表示 1.2 USD。如果你不需要指定价差，可以传递 `0` 或不传。

当我们挂出这么一个条件单以后，如果 `NVDA.US` 的市价在下单后的最高点回落 0.5% 时，比如最高点为 `1,100 USD`，回落 0.5% 就是 `1,094.5 USD`，那么我们的订单会以 `1,094.5 USD - 1.2 = 1,093.3 USD` 的价格挂出限价单。

#### 1.15 today_orders

- **Python SDK**：`TradeContext.today_orders(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[today_orders](https://open.longbridge.com/zh-CN/docs/trade/order/today_orders)
- **HTTP**：`GET /v1/trade/order/today`

﻿---
slug: today_orders
sidebar_position: 2
title: 当日订单
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

该接口用于获取当日订单和订单查询。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name     | Type     | Required | Description                                                                                       |
| -------- | -------- | -------- | ------------------------------------------------------------------------------------------------- |
| symbol   | string   | NO       | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US`                                              |
| status   | string[] | NO       | [订单状态](../trade-definition#orderstatus)<br/><br/>例如：`status=FilledStatus&status=NewStatus` |
| side     | string   | NO       | 买卖方向<br/><br/> **可选值：**<br/> `Buy` - 买入<br/> `Sell` - 卖出                              |
| market   | string   | NO       | 市场<br/><br/> **可选值：**<br/> `US` - 美股<br/> `HK` - 港股                                     |
| order_id | string   | NO       | 订单 ID，用于指定订单 ID 查询，例如：`701276261045858304`                                         |
| is_attached | bool | NO        | order_id 是否为附加单，为 true 时返回附加单订单信息                                                |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OrderStatus, OrderSide, Market, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)

resp = ctx.today_orders(
    symbol = "700.HK",
    status = [OrderStatus.Filled, OrderStatus.New],
    side = OrderSide.Buy,
    market = Market.HK,
)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OrderStatus, OrderSide, Market, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)

    resp = await ctx.today_orders(
        symbol = "700.HK",
        status = [OrderStatus.Filled, OrderStatus.New],
        side = OrderSide.Buy,
        market = Market.HK,
    )
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "orders": [
      {
        "currency": "HKD",
        "executed_price": "0.000",
        "executed_quantity": "0",
        "expire_date": "",
        "last_done": "",
        "limit_offset": "",
        "msg": "",
        "order_id": "706388312699592704",
        "order_type": "ELO",
        "outside_rth": "UnknownOutsideRth",
        "price": "11.900",
        "quantity": "200",
        "side": "Buy",
        "status": "RejectedStatus",
        "stock_name": "东亚银行",
        "submitted_at": "1651644897",
        "symbol": "23.HK",
        "tag": "Normal",
        "time_in_force": "Day",
        "trailing_amount": "",
        "trailing_percent": "",
        "trigger_at": "0",
        "trigger_price": "",
        "trigger_status": "NOT_USED",
        "updated_at": "1651644898",
        "remark": "",
        "limit_depth_level": 0,
        "monitor_price": "",
        "trigger_count": 1,
        "attached_orders": [
          {
            "order_id": "706388312699592705",
            "attached_type_display": 2,
            "trigger_price": "10.500",
            "quantity": "200",
            "executed_qty": "0",
            "status": "NewStatus",
            "updated_at": "1651644898",
            "withdrawn": false,
            "gtd": "",
            "time_in_force": "Day",
            "counter_id": "",
            "trigger_status": 0,
            "executed_amount": "0",
            "tag": 0,
            "submitted_at": "1651644897",
            "executed_price": "0.000",
            "force_only_rth": "RTH_ONLY",
            "reviewed": false,
            "activate_order_type": "MIT",
            "activate_rth": "RTH_ONLY",
            "submit_price": ""
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description              | Schema                                      |
| ------ | ------------------------ | ------------------------------------------- |
| 200    | 当日订单查询成功         | [today_orders_rsp](#schematoday_orders_rsp) |
| 400    | 查询失败，请求参数错误。 | None                                        |

<aside className="success">
</aside>

#### Schemas

##### today_orders_rsp

| Name                | Type     | Required | Description                                                                                                                                                                         |
| ------------------- | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| orders              | object[] | false    | 订单信息                                                                                                                                                                            |
| ∟ order_id          | string   | true     | 订单 ID                                                                                                                                                                             |
| ∟ status            | string   | true     | [订单状态](../trade-definition#orderstatus)                                                                                                                                         |
| ∟ stock_name        | string   | true     | 股票名称                                                                                                                                                                            |
| ∟ quantity          | string   | true     | 下单数量                                                                                                                                                                            |
| ∟ executed_quantity | string   | true     | 成交数量。<br/><br/>当订单未成交时为 0                                                                                                                                              |
| ∟ price             | string   | true     | 下单价格。<br/><br/>当市价条件单未触发时为空字符串                                                                                                                                  |
| ∟ executed_price    | string   | true     | 成交价。<br/><br/>当订单未成交时为 0                                                                                                                                                |
| ∟ submitted_at      | string   | true     | 下单时间                                                                                                                                                                            |
| ∟ side              | string   | true     | 买卖方向<br/><br/> **可选值：**<br/> `Buy` - 买入<br/> `Sell` - 卖出                                                                                                                |
| ∟ symbol            | string   | true     | 股票代码，使用 `ticker.region` 格式，例如：`AAPL.US`                                                                                                                                |
| ∟ order_type        | string   | true     | [订单类型](../trade-definition#ordertype)                                                                                                                                           |
| ∟ last_done         | string   | true     | 最近成交价格。<br/><br/>当订单未成交时为空字符串                                                                                                                                    |
| ∟ trigger_price     | string   | true     | `LIT` / `MIT` 订单触发价格。<br/><br/>当订单不是 `LIT` / `MIT` 订单为空字符串                                                                                                       |
| ∟ msg               | string   | true     | 拒绝信息或备注，默认为空字符串。                                                                                                                                                    |
| ∟ tag               | string   | true     | 订单标记<br/><br/> **可选值：**<br/> `Normal` - 普通订单<br/> `Gtc` - 长期单<br/> `Grey` - 暗盘单                                                                                   |
| ∟ time_in_force     | string   | true     | 订单有效期类型<br/><br/> **可选值：**<br/> `Day` - 当日有效<br/> `GTC` - 撤单前有效<br/> `GTD` - 到期前有效                                                                         |
| ∟ expire_date       | string   | true     | 长期单过期时间，格式为 `YYYY-MM-DD`, 例如：`2022-12-05。<br/><br/>不是长期单时，默认为空字符串。`                                                                                   |
| ∟ updated_at        | string   | true     | 最近更新时间，格式为时间戳 (秒)，默认为 0。                                                                                                                                         |
| ∟ trigger_at        | string   | true     | 条件单触发时间，格式为时间戳 (秒)，默认为 0。                                                                                                                                       |
| ∟ trailing_amount   | string   | true     | `TSLPAMT` 订单跟踪金额。<br/><br/>当订单不是 `TSLPAMT` 订单时为空字符串。                                                                                                           |
| ∟ trailing_percent  | string   | true     | `TSLPPCT` 订单跟踪涨跌幅。<br/><br/>当订单不是 `TSLPPCT` 订单时为空字符串。                                                                                                         |
| ∟ limit_offset      | string   | true     | `TSLPAMT` / `TSLPPCT` 订单指定价差。<br/><br/>当订单不是 `TSLPAMT` / `TSLPPCT` 订单时为空字符串。                                                                                   |
| ∟ trigger_status    | string   | true     | 条件单触发状态<br/> 当订单不是条件单或条件单未触发时，触发状态为 NOT_USED<br/><br/> **可选值：**<br/> `NOT_USED` - 未激活 `DEACTIVE` - 已失效 `ACTIVE` - 已激活 `RELEASED` - 已触发 |
| ∟ currency          | string   | true     | 结算货币                                                                                                                                                                            |
| ∟ outside_rth       | string   | true     | 是否允许盘前盘后<br/> 当订单不是美股时，默认为 UnknownOutsideRth<br/><br/> **可选值：**<br/> `RTH_ONLY` - 不允许盘前盘后<br/> `ANY_TIME` - 允许盘前盘后<br/> `OVERNIGHT` - 夜盘"    |
| ∟ remark            | string   | true     | 备注                                                                                                                                                                                |
| ∟ limit_depth_level | int32    | true     | 指定买卖档位         |
| ∟ trigger_count     | int32    | true     | 触发次数            |
| ∟ monitor_price     | string   | true     | 监控价格            |
| ∟ attached_orders           | object[] | false    | 附加订单详情列表 |
| ∟∟ order_id                 | string   | true     | 附加订单 ID |
| ∟∟ attached_type_display    | int32    | true     | 附加订单类型。**可选值：** `1` - 止盈 `2` - 止损 |
| ∟∟ trigger_price            | string   | true     | 触发价格 |
| ∟∟ quantity                 | string   | true     | 下单数量 |
| ∟∟ executed_qty             | string   | true     | 成交数量 |
| ∟∟ status                   | string   | true     | 订单状态 |
| ∟∟ updated_at               | string   | true     | 最近更新时间，格式为时间戳 (秒) |
| ∟∟ withdrawn                | boolean  | true     | 是否已撤销 |
| ∟∟ gtd                      | string   | true     | GTD 到期日期，格式为 `YYYY-MM-DD` |
| ∟∟ time_in_force            | string   | true     | 订单有效期类型<br/><br/> **可选值：**<br/> `Day` - 当日有效<br/> `GTC` - 撤单前有效<br/> `GTD` - 到期前有效 |
| ∟∟ counter_id               | string   | true     | 对应单 ID |
| ∟∟ trigger_status           | int32    | true     | 附加单激活后的条件单触发状态。<br/>`0` - 未激活 <br/>`1` - 监控中 <br/>`2` - 已撤单 <br/>`4` - 已触发 |
| ∟∟ executed_amount          | string   | true     | 成交金额 |
| ∟∟ tag                      | int32    | true     | 订单标记 |
| ∟∟ submitted_at             | string   | true     | 下单时间，格式为时间戳 (秒) |
| ∟∟ executed_price           | string   | true     | 成交价格 |
| ∟∟ force_only_rth           | string   | true     | 是否仅正常交易时段执行。 |
| ∟∟ reviewed                 | boolean  | true     | 是否已审核 |
| ∟∟ activate_order_type      | string   | true     | 触发后提交的订单类型，例如 `LIT`（限价单）或 `MIT`（市价单） |
| ∟∟ activate_rth             | string   | true     | 触发后提交订单是否允许盘前盘后。|
| ∟∟ submit_price             | string   | true     | 委托价格 |

#### 1.16 美股委托详情

- **Python SDK**：`TradeContext.us_order_detail(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[美股委托详情](https://open.longbridge.com/zh-CN/docs/trade/order/us_order_detail)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

获取美股指定委托的详情，包括成交历史，可选获取关联子委托。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| order_id | string | 是 | 委托 ID |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)
resp = ctx.us_order_detail("701276261045858304")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)
    resp = await ctx.us_order_detail("701276261045858304")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "order": {
    "id": "701276261045858304",
    "symbol": "AAPL.US",
    "action": "Buy",
    "order_type": "LO",
    "status": "Filled",
    "price": "185.00",
    "quantity": "10",
    "executed_qty": "10",
    "executed_price": "184.95",
    "executed_amount": "1849.50",
    "currency": "USD",
    "submitted_at": "1751866334",
    "done_at": "1751866400",
    "time_in_force": 0,
    "msg": ""
  },
  "current_attached_order": null,
  "current_millisecond": "1751866400000"
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [USOrderDetailResponse](#USOrderDetailResponse) |
| 400    | 请求错误 | None   |

##### USOrderDetailResponse

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| order | USOrderDetail \| null | 是 | 完整委托详情，未找到时为 null |
| current_attached_order | USOrderDetail \| null | 否 | 关联子委托（括号单/OCO） |
| current_millisecond | string | 否 | 服务器时间戳（毫秒） |

##### USOrderDetail

核心字段（完整响应包含 50+ 个字段，涵盖费用、触发条件和结算详情）：

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| id | string | 委托 ID |
| symbol | string | 交易标的，如 `AAPL.US` |
| action | int | 方向：1=买入，2=卖出 |
| order_type | string | 委托类型 |
| status | string | 委托状态 |
| price | string | 委托价格 |
| quantity | string | 委托数量 |
| executed_qty | string | 已成交数量 |
| executed_price | string | 平均成交价格 |
| executed_amount | string | 成交总金额 |
| currency | string | 货币代码 |
| submitted_at | string | 提交时间 |
| done_at | string | 完成时间 |
| time_in_force | int | 有效期类型 |
| trigger_price | string | 触发价格（止损/止盈单） |
| msg | string | 状态消息 |
| order_histories | USOrderHistory[] | 委托状态变更历史 |
| attached_orders | USAttachedOrder[] | 关联子委托列表 |
| button_control | USButtonControl | 可用操作按钮状态 |
| charge_detail | USChargeDetail \| null | 费用明细 |

##### USOrderHistory

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| exec_type | int | 执行类型 |
| status | string | 当前节点委托状态 |
| price | string | 价格 |
| qty | string | 数量 |
| time | string | 时间戳 |
| msg | string | 消息 |

#### 1.17 美股历史委托

- **Python SDK**：`TradeContext.us_query_orders(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[美股历史委托](https://open.longbridge.com/zh-CN/docs/trade/order/us_query_orders)

:::warning Longbridge US 账户
此方法仅适用于美国数据中心账户。
:::

查询美股账户的历史委托和待成交委托，支持分页和筛选。

#### Parameters

> **SDK 方法参数。**

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| symbol | string | 否 | 按标的筛选，例如 `AAPL.US` |
| action | int | 否 | 方向筛选：`0`=全部，`1`=买入，`2`=卖出（默认：`0`） |
| start_at | int64 | 否 | 开始时间（Unix 秒）；`0` = 最近 90 天 |
| end_at | int64 | 否 | 结束时间（Unix 秒）；`0` = 当前时间 |
| query_type | int32 | 否 | 0=全部，1=待成交，2=已成交（默认：0） |
| page | int32 | 否 | 页码，从 1 开始（默认：1） |
| limit | int32 | 否 | 每页数量（默认：20） |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("请访问：", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)
### 查询全部委托（使用默认参数）
resp = ctx.us_query_orders()
### 筛选 AAPL.US 买入委托
resp = ctx.us_query_orders(symbol="AAPL.US", action=1)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("请访问：", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)
    resp = await ctx.us_query_orders()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "orders": [
    {
      "id": "701276261045858304",
      "symbol": "AAPL.US",
      "action": "Buy",
      "order_type": "LO",
      "status": "Filled",
      "price": "185.00",
      "quantity": "10",
      "submitted_at": 1751866334,
      "updated_at": 1751866400
    }
  ],
  "total_count": 1
}
```

##### Response Status

| 状态码 | 描述 | 结构 |
| ------ | ---- | ---- |
| 200    | 成功 | [QueryUSOrdersResponse](#QueryUSOrdersResponse) |
| 400    | 请求错误 | None   |

#### Schemas

##### QueryUSOrdersResponse

| 名称 | 类型 | 必填 | 描述 |
| ---- | ---- | ---- | ---- |
| orders | USOrder[] | 是 | 符合筛选条件的委托列表 |
| total_count | int | 是 | 满足条件的委托总数 |

##### USOrder

| 名称 | 类型 | 描述 |
| ---- | ---- | ---- |
| id | string | 委托 ID |
| symbol | string | 交易标的，如 `AAPL.US` |
| action | string | 方向：`Buy` 或 `Sell` |
| order_type | string | 委托类型 |
| status | string | 委托状态 |
| price | string | 委托价格 |
| quantity | string | 委托数量 |
| submitted_at | int64 | 提交时间（Unix 秒） |
| updated_at | int64 | 最后更新时间（Unix 秒） |

#### 1.18 将下方订单 ID 替换为实际的订单 ID

- **Python SDK**：`TradeContext.cancel_order(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[将下方订单 ID 替换为实际的订单 ID](https://open.longbridge.com/zh-CN/docs/trade/order/withdraw)
- **HTTP**：`DELETE /v1/trade/order`

﻿---
slug: withdraw
sidebar_position: 6
title: 撤销订单
language_tabs: false
toc_footers: []
includes: []
search: true
highlight_theme: ''
headingLevel: 2
---

该接口用于订单撤销。

#### Request

##### Parameters

> Content-Type: application/json; charset=utf-8

| Name     | Type   | Required | Description |
| -------- | ------ | -------- | ----------- |
| order_id | string | YES      | 订单 ID     |
| is_attached | bool | NO      | order_id 是否为附加单 |

##### Request Example

###### Python 示例

```python
from longbridge.openapi import TradeContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)

ctx.cancel_order("709043056541253632")
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncTradeContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncTradeContext.create(config)

    ctx.cancel_order("709043056541253632")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

##### Response Status

| Status | Description                | Schema |
| ------ | -------------------------- | ------ |
| 200    | 提交成功，订单已委托。     | None   |
| 400    | 撤单被拒绝，请求参数错误。 | None   |

<aside className="success">
</aside>

#### 1.19 交易推送

- **Python SDK**：`TradeContext.subscribe(...)；TradeContext.unsubscribe(...)；TradeContext.set_on_order_changed(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[交易推送](https://open.longbridge.com/zh-CN/docs/trade/trade-push)

客户端可以通过交易长连接网关获取到交易和资产的变更通知。

#### Example

```python
from time import sleep
from decimal import Decimal
from longbridge.openapi import TradeContext, Config, OrderSide, OrderType, TimeInForceType, PushOrderChanged, TopicType, OAuthBuilder

def on_order_changed(event: PushOrderChanged):
    print(event)

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = TradeContext(config)
ctx.set_on_order_changed(on_order_changed)
ctx.subscribe([TopicType.Private])

resp = ctx.submit_order(
    side=OrderSide.Buy,
    symbol="700.HK",
    order_type=OrderType.LO,
    submitted_price=Decimal(50),
    submitted_quantity=Decimal(200),
    time_in_force=TimeInForceType.Day,
    remark="Hello from Python SDK",
)
print(resp)
sleep(5)  # waiting for push event

### Finally, unsubscribe
ctx.unsubscribe([TopicType.Private])
```

#### 订阅

:::info
指令：`16`
:::

我们可以通过 `subscribe` 方法订阅交易推送，订阅成功后，服务端会将相应的推送消息推送给客户端，SDK 的 `set_on_order_changed` 可以设置推送消息的回调函数，当收到交易推送消息时，会调用该回调函数。

Protobuf 定义如下：

```protobuf
// Sub is Sub command content, command is 16
message Sub {
  repeated string topics = 1;
}

// SubResponse is response of Sub Request
message SubResponse {
  message Fail {
    string topic = 1;
    string reason = 2;
  }
  repeated string success = 1; // 订阅成功
  repeated Fail fail = 2; // 订阅失败
  repeated string current = 3;  // 当前订阅
}
```

目前支持的 topic：

- private - 交易和资产类的私有通知

#### 取消订阅

取消订阅用于取消订阅信息，如前面 `subscribe` 订阅成功后，可以通过 `unsubscribe` 函数来取消订阅。

:::info
指令：`17`
:::

Protobuf 定义如下：

```protobuf
// Unsub is Unsub command content, command is 17
message Unsub {
  repeated string topics = 1;
}

// UnsubResponse is response of Unsub request
message UnsubResponse {
  repeated string current = 3; // 当前订阅
}
```

#### 注册通知推送

我们可以通过 `set_on_order_changed` 方法（Go 里面为 `OnTrade`）设置推送消息的回调函数，当收到交易推送消息时，会调用该回调函数。

:::info
指令：`18`
:::

Protobuf 定义如下：

```protobuf
// Dispatch type
enum DispatchType {
  DISPATCH_UNDEFINED = 0;
  DISPATCH_DIRECT = 1;
  DISPATCH_BROADCAST = 2;
}

enum ContentType {
  CONTENT_UNDEFINED = 0;
  CONTENT_JSON = 1;
  CONTENT_PROTO = 2;
}

// Notification is push message, command is 18
message Notification {
  string topic = 1;
  ContentType content_type = 2;
  DispatchType dispatch_type = 3;
  bytes data = 4;
}
```


## 12. Account（账户、组合与定投）

不属于行情卡收费分类；组合、提醒和定投接口需要账户授权，是否产生产品费用以账户条款为准。

### 1. 账户/交易权限

| 接口 | Python SDK | 权限/费用 |
| --- | --- | --- |
| [创建股价提醒](https://open.longbridge.com/zh-CN/docs/account/alert/create-alert) | AlertContext.create_alert(...) | 账户权限 |
| [删除股价提醒](https://open.longbridge.com/zh-CN/docs/account/alert/delete-alert) | AlertContext.delete_alert(...) | 账户权限 |
| [获取股价提醒列表](https://open.longbridge.com/zh-CN/docs/account/alert/list-alerts) | AlertContext.list_alerts(...) | 账户权限 |
| [更新股价提醒](https://open.longbridge.com/zh-CN/docs/account/alert/update-alert) | AlertContext.enable(...) | 账户权限 |
| [计算定投日期](https://open.longbridge.com/zh-CN/docs/account/dca/calc-date) | DCAContext.calc_date(...) | 账户权限 |
| [检查定投支持](https://open.longbridge.com/zh-CN/docs/account/dca/check-support) | DCAContext.check_support(...) | 账户权限 |
| [创建定投](https://open.longbridge.com/zh-CN/docs/account/dca/create-dca) | DCAContext.create(...) | 账户权限 |
| [定投交易历史](https://open.longbridge.com/zh-CN/docs/account/dca/dca-history) | DCAContext.history(...) | 账户权限 |
| [定投统计](https://open.longbridge.com/zh-CN/docs/account/dca/dca-stats) | DCAContext.stats(...) | 账户权限 |
| [获取定投列表](https://open.longbridge.com/zh-CN/docs/account/dca/list-dca) | DCAContext.list(...) | 账户权限 |
| [暂停定投](https://open.longbridge.com/zh-CN/docs/account/dca/pause-dca) | DCAContext.pause(...) | 账户权限 |
| [恢复定投](https://open.longbridge.com/zh-CN/docs/account/dca/resume-dca) | DCAContext.resume(...) | 账户权限 |
| [设置定投提醒](https://open.longbridge.com/zh-CN/docs/account/dca/set-reminder) | DCAContext.set_reminder(...) | 账户权限 |
| [终止定投](https://open.longbridge.com/zh-CN/docs/account/dca/stop-dca) | DCAContext.stop(...) | 账户权限 |
| [更新定投](https://open.longbridge.com/zh-CN/docs/account/dca/update-dca) | DCAContext.update(...) | 账户权限 |
| [汇率](https://open.longbridge.com/zh-CN/docs/account/portfolio/exchange-rates) | PortfolioContext.exchange_rates(...) | 账户权限 |
| [按市场盈亏分析](https://open.longbridge.com/zh-CN/docs/account/portfolio/profit-analysis-by-market) | PortfolioContext.profit_analysis_by_market(...) | 账户权限 |
| [盈亏分析明细](https://open.longbridge.com/zh-CN/docs/account/portfolio/profit-analysis-detail) | PortfolioContext.profit_analysis_detail(...) | 账户权限 |
| [盈亏流水](https://open.longbridge.com/zh-CN/docs/account/portfolio/profit-analysis-flows) | PortfolioContext.profit_analysis_flows(...) | 账户权限 |
| [盈亏分析汇总](https://open.longbridge.com/zh-CN/docs/account/portfolio/profit-analysis-summary) | PortfolioContext.profit_analysis_summary(...) | 账户权限 |

#### 1.1 创建股价提醒

- **Python SDK**：`AlertContext.create_alert(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[创建股价提醒](https://open.longbridge.com/zh-CN/docs/account/alert/create-alert)

为指定证券创建股价提醒，当价格高于或低于目标价时触发通知。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `TSLA.US` |
| price | string | 是 | 目标价格 |
| direction | string | 是 | 提醒方向：`rise`（上涨）或 `fall`（下跌） |
| frequency | string | 否 | 触发频率：`once`（仅一次，默认）或 `every`（每次） |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import AlertContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = AlertContext(config)

resp = ctx.create_alert()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncAlertContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncAlertContext.create(config)

    resp = await ctx.create_alert()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 486469
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [CreateAlertResponse](#CreateAlertResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### CreateAlertResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | int64 | true | 新创建提醒的 ID |

#### 1.2 删除股价提醒

- **Python SDK**：`AlertContext.delete_alert(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[删除股价提醒](https://open.longbridge.com/zh-CN/docs/account/alert/delete-alert)

根据 ID 删除指定的股价提醒。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | int64 | 是 | 提醒 ID（路径参数） |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import AlertContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = AlertContext(config)

resp = ctx.delete_alert("486469")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncAlertContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncAlertContext.create(config)

    resp = await ctx.delete_alert("486469")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [DeleteAlertResponse](#DeleteAlertResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### DeleteAlertResponse

无响应体字段。

#### 1.3 获取股价提醒列表

- **Python SDK**：`AlertContext.list_alerts(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[获取股价提醒列表](https://open.longbridge.com/zh-CN/docs/account/alert/list-alerts)

获取当前用户的所有股价提醒，支持按标的筛选。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 否 | 按证券代码筛选，例如 `TSLA.US` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import AlertContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = AlertContext(config)

resp = ctx.list_alerts()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncAlertContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncAlertContext.create(config)

    resp = await ctx.list_alerts()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "lists": [
      {
        "symbol": "AAPL.US",
        "code": "AAPL",
        "market": "US",
        "name": "Apple",
        "price": "298.87",
        "chg": "4.07",
        "p_chg": "1.38",
        "product": "stock",
        "indicators": [
          {
            "id": "514050",
            "indicator_id": "1",
            "enabled": true,
            "frequency": 2,
            "scope": 0,
            "text": "价格涨到 400",
            "state": [
              1
            ],
            "value_map": {
              "price": "400"
            }
          }
        ]
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [AlertListResponse](#AlertListResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### AlertListResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| lists | object[] | true | 按标的分组的提醒列表，见 [AlertSymbolGroup](#AlertSymbolGroup) |

##### AlertSymbolGroup

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | true | 证券代码 |
| code | string | false | 股票代码 |
| market | string | false | 市场 |
| name | string | false | 证券名称 |
| price | string | false | 最新价 |
| chg | string | false | 当日涨跌额 |
| p_chg | string | false | 当日涨跌幅 |
| product | string | false | 产品类型 |
| indicators | object[] | false | 股价提醒列表，见 [AlertItem](#AlertItem) |

##### AlertItem

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | true | 提醒 ID |
| indicator_id | string | false | 条件：`1`=价格上涨，`2`=价格下跌，`3`=涨幅，`4`=跌幅 |
| enabled | boolean | false | 是否启用 |
| frequency | integer | false | 触发频率：`1`=每日，`2`=每次，`3`=一次 |
| scope | integer | false | 范围 |
| text | string | false | 显示文本 |
| state | integer[] | false | 触发状态标志 |
| value_map | object | false | 触发值（如 `{"price":"400"}` 或 `{"chg":"5"}`） |

#### 1.4 更新股价提醒

- **Python SDK**：`AlertContext.enable(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[更新股价提醒](https://open.longbridge.com/zh-CN/docs/account/alert/update-alert)

启用或禁用已有的股价提醒。先通过 `list` 获取完整的 `AlertItem`，修改 `item.enabled` 后调用 `update(item)`。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | int64 | 是 | 提醒 ID（路径参数） |
| enabled | bool | 是 | 设为 `true` 启用，`false` 禁用 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import AlertContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = AlertContext(config)

resp = ctx.update_alert("112326", enabled=True)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncAlertContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncAlertContext.create(config)

    resp = await ctx.update_alert("112326", enabled=True)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [UpdateAlertResponse](#UpdateAlertResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### UpdateAlertResponse

无响应体字段。

#### 1.5 计算定投日期

- **Python SDK**：`DCAContext.calc_date(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[计算定投日期](https://open.longbridge.com/zh-CN/docs/account/dca/calc-date)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

根据给定的定投计划参数，计算下一次预计交易日期。

#### Parameters

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 标的代码 |
| frequency | string | 是 | 定投频率：`daily`、`weekly`、`fortnightly`、`monthly` |
| day_of_week | string | 否 | 每周计划的执行星期：`mon`–`fri` |
| day_of_month | integer | 否 | 每月/每两周计划的执行日期：1–28 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder, DCAFrequency

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

resp = ctx.calc_date("AAPL.US", DCAFrequency.Monthly, day_of_month=15)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder, DCAFrequency

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    resp = await ctx.calc_date("AAPL.US", DCAFrequency.Monthly, day_of_month=15)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "trade_date": "2024-02-15"
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [DcaCalcDateResult](#DcaCalcDateResult) |
| 400    | 请求错误    | None   |

#### Schemas

##### DcaCalcDateResult

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| trade_date | string | true | 下一次预计交易日期（YYYY-MM-DD） |

#### 1.6 检查定投支持

- **Python SDK**：`DCAContext.check_support(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[检查定投支持](https://open.longbridge.com/zh-CN/docs/account/dca/check-support)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

检查指定标的是否支持定投。

#### Parameters

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbols | string[] | 是 | 待检查的标的代码列表 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

resp = ctx.check_support(["AAPL.US", "700.HK"])
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    resp = await ctx.check_support(["AAPL.US", "700.HK"])
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "infos": [
      {
        "symbol": "AAPL.US",
        "support_regular_saving": true
      },
      {
        "symbol": "700.HK",
        "support_regular_saving": false
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [DcaSupportListResponse](#DcaSupportListResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### DcaSupportListResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| infos | object[] | true | 定投支持情况列表， |
| ∟ symbol | string | true | 证券代码 |
| ∟ support_regular_saving | boolean | true | 是否支持定投 |

#### 1.7 创建定投

- **Python SDK**：`DCAContext.create(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[创建定投](https://open.longbridge.com/zh-CN/docs/account/dca/create-dca)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

为指定证券创建新的定投。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |
| amount | string | 是 | 定投金额 |
| frequency | string | 是 | 频率：`Daily`（每日）、`Weekly`（每周）、`Fortnightly`（每两周）、`Monthly`（每月） |
| day_of_week | string | 否 | 每周/每两周计划的执行星期：`mon`–`fri` |
| day_of_month | integer | 否 | 每月计划的执行日期（1–28） |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

resp = ctx.create_dca("AAPL.US", amount="500", frequency="Monthly", day_of_month=15)
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    resp = await ctx.create_dca("AAPL.US", amount="500", frequency="Monthly", day_of_month=15)
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "1225781523156889601"
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [CreateDcaResponse](#CreateDcaResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### CreateDcaResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | true | 新创建计划的 ID |

#### 1.8 定投交易历史

- **Python SDK**：`DCAContext.history(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[定投交易历史](https://open.longbridge.com/zh-CN/docs/account/dca/dca-history)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

获取指定定投的执行历史，包含交易日期、金额和价格。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | 是 | 计划 ID（路径参数） |
| page | integer | 否 | 页码（从 1 开始，默认：1） |
| size | integer | 否 | 每页数量（默认：20） |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

resp = ctx.dca_history("1225781523156889600")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    resp = await ctx.dca_history("1225781523156889600")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "has_more": false,
    "records": [
      {
        "symbol": "AAPL.US",
        "order_id": "123456",
        "status": "Filled",
        "action": "Buy",
        "order_type": "Market",
        "executed_qty": "1",
        "executed_price": "180.50",
        "executed_amount": "180.50",
        "created_at": "1763769600",
        "rejected_reason": ""
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [DcaHistoryResponse](#DcaHistoryResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### DcaHistoryResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| records | object[] | true | 执行记录列表， |
| ∟ symbol | string | true | 证券代码 |
| ∟ order_id | string | false | 关联订单 ID |
| ∟ status | string | false | 执行状态 |
| ∟ action | string | false | 操作类型 |
| ∟ order_type | string | false | 订单类型 |
| ∟ executed_qty | string | false | 成交数量 |
| ∟ executed_price | string | false | 成交价格 |
| ∟ executed_amount | string | false | 成交金额 |
| ∟ rejected_reason | string | false | 拒绝原因（如有） |
| ∟ created_at | string | false | 执行时间 |
| ∟ created_at | string | false | 执行时间 |
| ∟ rejected_reason | string | false | 拒绝原因（如有） |
| has_more | boolean | false | 是否有更多记录 |

#### 1.9 定投统计

- **Python SDK**：`DCAContext.stats(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[定投统计](https://open.longbridge.com/zh-CN/docs/account/dca/dca-stats)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

获取定投统计汇总信息，包括总投入金额和盈亏情况。

#### Parameters

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 否 | 按标的过滤 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

resp = ctx.stats()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    resp = await ctx.stats()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "active_count": "2",
    "finished_count": "1",
    "suspended_count": "0",
    "rest_days": "3",
    "total_amount": "5400",
    "total_profit": "120.50",
    "nearest_plans": [
      {
        "plan_id": "1239402174908207104",
        "symbol": "AAPL.US",
        "stock_name": "Apple Inc.",
        "market": "US",
        "status": "Active",
        "per_invest_amount": "100",
        "invest_frequency": "Monthly",
        "invest_day_of_month": "15",
        "next_trd_date": "1778853600",
        "cum_amount": "0",
        "cum_profit": "0"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [DcaStats](#DcaStats) |
| 400    | 请求错误    | None   |

#### Schemas

##### DcaStatsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| active_count | string | false | 活跃计划数量 |
| finished_count | string | false | 已完成计划数量 |
| suspended_count | string | false | 已暂停计划数量 |
| rest_days | string | false | 距下次扣款天数 |
| total_amount | string | false | 总投入金额 |
| total_profit | string | false | 总盈亏 |
| nearest_plans | object[] | false | 最近即将执行的定投计划（结构与 DcaPlan 一致） |

> `nearest_plans` 的子项结构与 [查看定投计划](./list-dca) 中的 `DcaPlan` 一致。

#### 1.10 获取定投列表

- **Python SDK**：`DCAContext.list(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[获取定投列表](https://open.longbridge.com/zh-CN/docs/account/dca/list-dca)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

获取当前用户的所有定投（DCA）计划。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| status | string | 否 | 按计划状态筛选：`Active`（进行中）、`Suspended`（已暂停）、`Finished`（已结束） |
| symbol | string | 否 | 按证券代码筛选 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

resp = ctx.list_dca()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    resp = await ctx.list_dca()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "plans": [
      {
        "plan_id": "1239402174908207104",
        "symbol": "AAPL.US",
        "stock_name": "Apple Inc.",
        "market": "US",
        "status": "Active",
        "per_invest_amount": "100",
        "invest_frequency": "Monthly",
        "invest_day_of_month": "15",
        "invest_day_of_week": "",
        "next_trd_date": "1778853600",
        "cum_amount": "0",
        "cum_profit": "0",
        "average_cost": "0",
        "allow_margin_finance": false,
        "alter_hours": "6",
        "display_account": "LBPT10065023",
        "member_id": "3162",
        "aaid": "20975338",
        "account_channel": "lb_papertrading",
        "issue_number": 0,
        "created_at": "1778725628",
        "updated_at": "1778725628"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [DcaListResponse](#DcaListResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### DcaListResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| plans | object[] | 是 | 定投计划列表，见 [DcaPlan](#DcaPlan) |

##### DcaPlan

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| plan_id | string | 是 | 定投计划 ID |
| symbol | string | 是 | 证券代码 |
| stock_name | string | 否 | 标的名称 |
| market | string | 否 | 市场 |
| status | string | 否 | 计划状态：`Active`（进行中）、`Suspended`（已暂停）、`Finished`（已结束） |
| per_invest_amount | string | 否 | 每次投入金额 |
| invest_frequency | string | 否 | 投资频率：`Daily`、`Weekly`、`Fortnightly`、`Monthly` |
| invest_day_of_week | string | 否 | 每周扣款日 |
| invest_day_of_month | string | 否 | 每月扣款日 |
| next_trd_date | string | 否 | 下次交易日 |
| cum_amount | string | 否 | 累计投入金额 |
| cum_profit | string | 否 | 累计盈亏 |
| average_cost | string | 否 | 平均持仓成本 |
| allow_margin_finance | boolean | 否 | 是否允许融资 |
| alter_hours | string | 否 | 提前提醒小时数 |
| display_account | string | 否 | 账户显示名称 |
| account_channel | string | 否 | 账户渠道 |
| aaid | string | 否 | 账户资产 ID |
| member_id | string | 否 | 用户 ID |
| issue_number | string | 否 | 已执行次数 |
| created_at | string | 否 | 创建时间 |
| updated_at | string | 否 | 最后更新时间 |

#### 1.11 暂停定投

- **Python SDK**：`DCAContext.pause(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[暂停定投](https://open.longbridge.com/zh-CN/docs/account/dca/pause-dca)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

暂停一个定投计划。计划暂停后可随时恢复。

#### Parameters

| Name    | Type   | Required | Description |
| ------- | ------ | -------- | ----------- |
| plan_id | string | 是       | 定投计划 ID |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

ctx.pause("12345")
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    await ctx.pause("12345")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success"
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | None   |
| 400    | 请求错误    | None   |

#### 1.12 恢复定投

- **Python SDK**：`DCAContext.resume(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[恢复定投](https://open.longbridge.com/zh-CN/docs/account/dca/resume-dca)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

恢复一个已暂停的定投计划。

#### Parameters

| Name    | Type   | Required | Description |
| ------- | ------ | -------- | ----------- |
| plan_id | string | 是       | 定投计划 ID |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

ctx.resume("12345")
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    await ctx.resume("12345")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success"
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | None   |
| 400    | 请求错误    | None   |

#### 1.13 设置定投提醒

- **Python SDK**：`DCAContext.set_reminder(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[设置定投提醒](https://open.longbridge.com/zh-CN/docs/account/dca/set-reminder)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

设置定投计划的提前提醒时间。支持的值：`1`、`6` 或 `12` 小时。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| hours | string | 是 | 提醒提前小时数：`1`、`6` 或 `12` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

ctx.set_reminder("12")
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    await ctx.set_reminder("12")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success"
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | None   |
| 400    | 请求错误    | None   |

#### 1.14 终止定投

- **Python SDK**：`DCAContext.stop(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[终止定投](https://open.longbridge.com/zh-CN/docs/account/dca/stop-dca)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

永久终止一个定投计划。此操作不可撤销。

#### Parameters

| Name    | Type   | Required | Description |
| ------- | ------ | -------- | ----------- |
| plan_id | string | 是       | 定投计划 ID |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

ctx.stop("12345")
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    await ctx.stop("12345")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success"
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | None   |
| 400    | 请求错误    | None   |

#### 1.15 更新定投

- **Python SDK**：`DCAContext.update(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[更新定投](https://open.longbridge.com/zh-CN/docs/account/dca/update-dca)

:::warning Longbridge US 账户不支持
此方法需要 AP 数据中心账户（香港/新加坡）。美股数据中心账户将收到区域限制错误。AP 账户可操作任意标的，包括美股。
:::

暂停或恢复已有的定投。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| id | string | 是 | 计划 ID（路径参数） |
| action | string | 是 | 执行操作：`pause`（暂停）或 `resume`（恢复） |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import DCAContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = DCAContext(config)

resp = ctx.update_dca("1225781523156889600", action="pause")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncDCAContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncDCAContext.create(config)

    resp = await ctx.update_dca("1225781523156889600", action="pause")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [UpdateDcaResponse](#UpdateDcaResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### UpdateDcaResponse

无响应体字段。

#### 1.16 汇率

- **Python SDK**：`PortfolioContext.exchange_rates(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[汇率](https://open.longbridge.com/zh-CN/docs/account/portfolio/exchange-rates)

获取账户中所有货币对的当前外汇汇率。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| base | string | 否 | 基础货币，例如 `USD`，不传则返回所有货币对 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import PortfolioContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = PortfolioContext(config)

resp = ctx.exchange_rates()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncPortfolioContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncPortfolioContext.create(config)

    resp = await ctx.exchange_rates()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "exchanges": [
      {
        "base_currency": "USD",
        "other_currency": "HKD",
        "bid_rate": 7.785,
        "offer_rate": 7.795,
        "average_rate": 7.79
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ExchangeRatesResponse](#ExchangeRatesResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ExchangeRatesResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| exchanges | object[] | true | 汇率列表， |
| ∟ base_currency | string | true | 基准货币 |
| ∟ other_currency | string | true | 报价货币 |
| ∟ bid_rate | number | false | 买入汇率 |
| ∟ offer_rate | number | false | 卖出汇率 |
| ∟ average_rate | number | false | 平均汇率 |

#### 1.17 按市场盈亏分析

- **Python SDK**：`PortfolioContext.profit_analysis_by_market(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[按市场盈亏分析](https://open.longbridge.com/zh-CN/docs/account/portfolio/profit-analysis-by-market)

获取按市场分组的盈亏分析（美股、港股、A 股、新加坡股）。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| start_date | string | 否 | 分析开始日期，格式 `YYYY-MM-DD` |
| end_date | string | 否 | 分析结束日期，格式 `YYYY-MM-DD` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import PortfolioContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = PortfolioContext(config)

resp = ctx.profit_analysis_by_market()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncPortfolioContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncPortfolioContext.create(config)

    resp = await ctx.profit_analysis_by_market()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "has_more": false,
    "profit": "-16325.26",
    "stock_items": [
      {
        "code": "AAPL",
        "market": "US",
        "name": "Apple",
        "profit": "100.00"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ProfitAnalysisByMarketResponse](#ProfitAnalysisByMarketResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ProfitAnalysisByMarketResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| has_more | boolean | false | Whether there are more pages |
| profit | string | false | Total profit/loss |
| stock_items | object[] | false | P&L breakdown by stock |
| ∟ code | string | false | Stock code |
| ∟ market | string | false | 市场代码 |
| ∟ name | string | false | Stock name |
| ∟ profit | string | false | Profit/loss for this stock |

#### 1.18 盈亏分析明细

- **Python SDK**：`PortfolioContext.profit_analysis_detail(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[盈亏分析明细](https://open.longbridge.com/zh-CN/docs/account/portfolio/profit-analysis-detail)

获取指定证券的详细盈亏分析，包含交易流水和成本分解。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | 是 | 证券代码，例如 `AAPL.US` |
| start | string | 否 | 开始日期，格式 `YYYY-MM-DD` |
| end | string | 否 | 结束日期，格式 `YYYY-MM-DD` | 分析结束日期，格式 `YYYY-MM-DD` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import PortfolioContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = PortfolioContext(config)

resp = ctx.profit_analysis_detail("TSLA.US")
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncPortfolioContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncPortfolioContext.create(config)

    resp = await ctx.profit_analysis_detail("TSLA.US")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "name": "Apple",
    "currency": "USD",
    "profit": "100.00",
    "start": "1763769600",
    "end": "1778724973",
    "start_date": "2025-11-22",
    "end_date": "2026-05-14",
    "default_tag": 0,
    "updated_at": "1778724973",
    "updated_date": "2026-05-14",
    "underlying_details": {
      "profit": "100.00",
      "holding_value": "1790.16",
      "holding_value_at_beginning": null,
      "holding_value_at_ending": "1790.16",
      "long_holding_value": "1790.16",
      "short_holding_value": "0.00",
      "cumulative_credited_amount": "0.00",
      "cumulative_debited_amount": "0.00",
      "cumulative_fee_amount": "0.00",
      "credited_details": [],
      "debited_details": [],
      "fee_details": []
    },
    "derivative_pnl_details": {
      "profit": "0.00",
      "holding_value": "0.00",
      "holding_value_at_beginning": null,
      "holding_value_at_ending": "0.00",
      "long_holding_value": "0.00",
      "short_holding_value": "0.00",
      "cumulative_credited_amount": "0.00",
      "cumulative_debited_amount": "0.00",
      "cumulative_fee_amount": "0.00",
      "credited_details": [],
      "debited_details": [],
      "fee_details": []
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ProfitAnalysisDetailResponse](#ProfitAnalysisDetailResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ProfitAnalysisDetailResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| name | string | false | 证券名称 |
| currency | string | false | 货币 |
| profit | string | false | 总盈亏 |
| start | integer | false | 统计期开始 |
| end | integer | false | 统计期结束 |
| start_date | string | false | 开始日期 |
| end_date | string | false | 结束日期 |
| default_tag | integer | false | 默认显示标签 |
| underlying_details | object | false | 正股盈亏明细 |
| updated_at | string | false | 最后更新时间 |
| updated_date | string | false | 最后更新日期 |
| derivative_pnl_details | object | false | 衍生品盈亏明细 |

##### ProfitDetails

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| profit | string | false | 总盈亏 |
| holding_value | string | false | 当前持仓市值 |
| holding_value_at_beginning | string | false | 期初持仓市值 |
| holding_value_at_ending | string | false | 期末持仓市值 |
| long_holding_value | string | false | 多头持仓市值 |
| short_holding_value | string | false | 空头持仓市值 |
| cumulative_credited_amount | string | false | 累计入账金额 |
| cumulative_debited_amount | string | false | 累计出账金额 |
| cumulative_fee_amount | string | false | 累计费用金额 |
| credited_details | object[] | false | 入账明细 |
| debited_details | object[] | false | 出账明细 |
| fee_details | object[] | false | 费用明细 |

#### 1.19 盈亏流水

- **Python SDK**：`PortfolioContext.profit_analysis_flows(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[盈亏流水](https://open.longbridge.com/zh-CN/docs/account/portfolio/profit-analysis-flows)

查询账户资金流水历史，包含入金、出金、分红和结算等。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | YES | 证券代码 |
| page | integer | NO | 页码（默认 1） |
| size | integer | NO | 每页数量（默认 20） |
| derivative | boolean | NO | 是否包含衍生品仓位 |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import PortfolioContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = PortfolioContext(config)

resp = ctx.profit_analysis_flows()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncPortfolioContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncPortfolioContext.create(config)

    resp = await ctx.profit_analysis_flows()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "has_more": false,
    "flows_list": [
      {
        "code": "AAPL",
        "symbol": "AAPL.US",
        "direction": "In",
        "executed_date": "2025-11-22",
        "executed_timestamp": "1763769600",
        "executed_quantity": "10",
        "executed_price": "180.50",
        "executed_cost": "1805.00",
        "describe": "Buy AAPL.US"
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ProfitAnalysisFlowsResponse](#ProfitAnalysisFlowsResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ProfitAnalysisFlowsResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| flows_list | object[] | true | 资金流水列表（分页）， |
| ∟ executed_date | string | true | 执行日期（如 `2024-01-15`） |
| ∟ executed_timestamp | string | false | 执行时间戳 |
| ∟ code | string | false | 证券代码 |
| ∟ direction | string | false | 方向：`In`（买入）或 `Out`（卖出） |
| ∟ executed_quantity | string | false | 成交数量 |
| ∟ executed_price | string | false | 成交价格 |
| ∟ executed_cost | string | false | 成交成本 |
| ∟ describe | string | false | 描述说明 |
| has_more | boolean | false | 是否有更多页 |

#### 1.20 盈亏分析汇总

- **Python SDK**：`PortfolioContext.profit_analysis_summary(...)`
- **权限/费用**：账户/交易授权；非行情卡分类
- **官方页面**：[盈亏分析汇总](https://open.longbridge.com/zh-CN/docs/account/portfolio/profit-analysis-summary)

获取账户盈亏汇总，包含总资产、总盈亏和收益率指标。

#### Parameters

> **SDK 方法参数。**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| start_date | string | 否 | 分析开始日期，格式 `YYYY-MM-DD` |
| end_date | string | 否 | 分析结束日期，格式 `YYYY-MM-DD` |

#### Request Example

###### Python 示例

```python
from longbridge.openapi import PortfolioContext, Config, OAuthBuilder

oauth = OAuthBuilder("your-client-id").build(lambda url: print("Visit:", url))
config = Config.from_oauth(oauth)
ctx = PortfolioContext(config)

resp = ctx.profit_analysis_summary()
print(resp)
```

###### Python 异步示例

```python
import asyncio
from longbridge.openapi import AsyncPortfolioContext, Config, OAuthBuilder

async def main() -> None:
    oauth = await OAuthBuilder("your-client-id").build_async(lambda url: print("Visit:", url))
    config = Config.from_oauth(oauth)
    ctx = AsyncPortfolioContext.create(config)

    resp = await ctx.profit_analysis_summary()
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
```

#### Response

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "summary": {
      "currency": "USD",
      "sum_profit": "62905.97",
      "sum_profit_rate": "0.6128",
      "invest_amount": "102659.74",
      "current_total_asset": "165565.71",
      "initial_asset_value": "0.00",
      "ending_asset_value": "165565.71",
      "is_traded": true,
      "start_date": "2025-10-17",
      "start_time": "1760659200",
      "end_date": "2026-05-14",
      "end_time": "1778731947",
      "profits": {
        "stock": "66370.84",
        "crypto": "0",
        "fund": null,
        "ipo": null,
        "mmf": null,
        "other": null,
        "cumulative_transaction_amount": "1244920.28"
      }
    },
    "sublist": {
      "start": "2025-10-17",
      "start_date": "2025-10-17",
      "end": "2026-05-14",
      "end_date": "2026-05-14",
      "updated_at": "1778731947",
      "updated_date": "2026-05-14",
      "items": [
        {
          "symbol": "AAPL.US",
          "name": "Apple",
          "market": "US",
          "currency": "USD",
          "profit": "100.00",
          "profit_rate": "0.05",
          "holding_period": "180",
          "clearance_times": 0,
          "is_holding": true,
          "item_type": "Stock",
          "isin": "",
          "security_code": "AAPL",
          "underlying_profit": "100.00",
          "derivatives_profit": "0.00",
          "order_profit": null
        }
      ]
    }
  }
}
```

##### Response Status

| Status | Description | Schema |
| ------ | ----------- | ------ |
| 200    | 成功        | [ProfitAnalysisResponse](#ProfitAnalysisResponse) |
| 400    | 请求错误    | None   |

#### Schemas

##### ProfitAnalysisResponse

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| summary | object | true | 总体汇总 |
| sublist | object | false | 逐仓位明细 |

##### ProfitAnalysisSummary

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| currency | string | false | 货币 |
| sum_profit | string | false | 总盈亏 |
| sum_profit_rate | string | false | 总盈亏率 |
| invest_amount | string | false | 总投入金额 |
| current_total_asset | string | false | 当前总资产 |
| initial_asset_value | string | false | 初始资产价值 |
| ending_asset_value | string | false | 期末资产价值 |
| is_traded | boolean | false | 是否有交易记录 |
| start_date | string | false | 统计开始日期 |
| start_time | string | false | 统计开始时间戳 |
| end_date | string | false | 统计结束日期 |
| end_time | string | false | 统计结束时间戳 |
| profits | object | false | 按类型分解的盈亏 |
| profits.stock | string | false | 股票盈亏 |
| profits.crypto | string | false | 加密货币盈亏 |
| profits.fund | string | false | 基金盈亏 |
| profits.ipo | string | false | 打新盈亏 |
| profits.mmf | string | false | 货币基金盈亏 |
| profits.other | string | false | 其他盈亏 |
| profits.cumulative_transaction_amount | string | false | 累计交易金额 |

##### ProfitAnalysisSublist

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| start | string | false | 统计期开始 |
| start_date | string | false | 开始日期 |
| end | string | false | 统计期结束 |
| end_date | string | false | 结束日期 |
| updated_at | string | false | 最后更新时间戳 |
| updated_date | string | false | 最后更新日期 |
| items | object[] | false | 逐仓位盈亏列表，见 [ProfitAnalysisItem](#ProfitAnalysisItem) |

##### ProfitAnalysisItem

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| symbol | string | false | 证券代码 |
| name | string | false | 证券名称 |
| market | string | false | 市场 |
| currency | string | false | 货币 |
| profit | string | false | 盈亏 |
| profit_rate | string | false | 盈亏率 |
| holding_period | string | false | 持仓天数 |
| clearance_times | integer | false | 清仓次数 |
| is_holding | boolean | false | 是否持有中 |
| item_type | string | false | 资产类型：`Stock`、`Fund`、`Crypto` 等 |
| isin | string | false | ISIN 代码 |
| security_code | string | false | 证券代码（短） |
| underlying_profit | string | false | 正股盈亏 |
| derivatives_profit | string | false | 衍生品盈亏 |
| order_profit | string | false | 订单盈亏 |


## 13. AI Agent（Workspace 与对话）

需要加入 Workspace 并拥有 Agent 权限；官方开发者文档未公开统一 AI 计费表。

### 1. 条件/产品权限

| 接口 | Python SDK | 权限/费用 |
| --- | --- | --- |
| [继续对话](https://open.longbridge.com/zh-CN/docs/ai/chat/continue) | AgentContext.continue(...) | 条件权限 |
| [发起对话](https://open.longbridge.com/zh-CN/docs/ai/chat/conversation) | AgentContext.conversation(...) | 条件权限 |
| [Workspace 下的 Agent](https://open.longbridge.com/zh-CN/docs/ai/workspace/agents) | AgentContext.agents(...) | 条件权限 |
| [我的 Workspace](https://open.longbridge.com/zh-CN/docs/ai/workspace/workspaces) | AgentContext.workspaces(...) | 条件权限 |

#### 1.1 继续对话

- **Python SDK**：`AgentContext.continue(...)`
- **权限/费用**：Workspace/Agent 权限；官方未公开统一计费
- **官方页面**：[继续对话](https://open.longbridge.com/zh-CN/docs/ai/chat/continue)
- **HTTP**：`POST /v1/ai/agents/:id/conversations/:chat_uid/messages/:message_id/continue`

当 [发起对话](/zh-CN/docs/ai/chat/conversation) 返回 `status = interrupted` 时，Agent 正等待你补充信息。通过本接口回传答案，暂停的运行会从中断处继续执行，直到成功、再次中断或失败。

同一轮对话可能发生多次中断：若继续后再次返回 `interrupted`，按新的 `interrupt` 重复调用本接口即可。

与发起对话一致，通过请求头 `Accept` 选择阻塞式 / SSE 流式响应。

#### Request

##### Path Parameters

| Name       | Type   | Required | Description                                        |
| ---------- | ------ | -------- | -------------------------------------------------- |
| id         | string | YES      | 目标 Agent 的 UID                                  |
| chat_uid   | string | YES      | 中断所属会话的 `chat_uid`，取自发起对话的响应      |
| message_id | string | YES      | 被中断的消息 ID，取自中断响应的 `message_id`       |

##### Request Body

| Name                 | Type   | Required | Description                                                    |
| -------------------- | ------ | -------- | -------------------------------------------------------------- |
| answers_by_tool_call | object | YES      | 以 `tool_call_id` 为 key 的答案集合，不能为空。value 为「问题文本 → 回答」的键值对 |

`answers_by_tool_call` 的结构为「工具调用 ID → 该次询问的答案」，其中每个答案又是一组「问题 → 回答」：

- 外层 key 对应中断结构里的 `tool_call_id`。
- 内层 key 为中断问题文本，value 为你选择或填写的答案。
- 必须回答该次中断要求的所有问题，否则返回错误。

##### Python 示例

```python
import os
import requests

BASE_URL = os.getenv("LONGBRIDGE_HTTP_URL", "https://openapi.longbridge.com")
token = os.environ["LONGBRIDGE_ACCESS_TOKEN"]
headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
agent_id = "ag_7d3f9b2c"
workspace_id = "1001"
chat_uid = "ct_9f2c1a5b"
message_id = "43"
url = BASE_URL + f"/v1/ai/agents/{agent_id}/conversations/{chat_uid}/messages/{message_id}/continue"
response = requests.request('POST', url, headers=headers, json={"answers_by_tool_call": {"call_abc123": {"你想查询哪个时间区间？": "近一个月"}}}, timeout=60)
response.raise_for_status()
print(response.json())
```

##### Request Example

#### Response

响应结构与 [发起对话](/zh-CN/docs/ai/chat/conversation#schemaconversation_response) 完全一致。

##### Response Headers

- Content-Type: application/json（阻塞式）
- Content-Type: text/event-stream（流式）

##### Response Example

运行成功：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "chat_uid": "ct_9f2c1a5b",
    "message_id": "43",
    "status": "succeeded",
    "answer": "近一个月特斯拉（TSLA.US）……",
    "references": [],
    "elapsed_time": 2.74
  }
}
```

##### Response Status

| Status | Description | Schema                                                |
| ------ | ----------- | ----------------------------------------------------- |
| 200    | 返回成功    | [conversation_response](/zh-CN/docs/ai/chat/conversation#schemaconversation_response) |
| 400    | 参数非法    | `answers_by_tool_call` 为空、消息未处于中断状态、缺少中断所需答案，或会话 / 消息归属不符 |
| 500    | 内部错误    | None                                                  |

##### 归属校验

为防止续跑他人的运行，服务端会校验：`chat_uid` 对应的会话必须属于当前认证成员，且 `message_id` 对应的消息必须属于该会话。任一不满足都会返回 `400`。

#### 1.2 发起对话

- **Python SDK**：`AgentContext.conversation(...)`
- **权限/费用**：Workspace/Agent 权限；官方未公开统一计费
- **官方页面**：[发起对话](https://open.longbridge.com/zh-CN/docs/ai/chat/conversation)
- **HTTP**：`POST /v1/ai/agents/:id/conversations`

向指定 Agent 提问。可以开启一个全新会话，也可以传入已有会话的 `chat_uid` 在同一会话中追加提问。

Agent 会结合行情、账户等能力生成回答。当 Agent 需要你补充信息或确认时，本次运行会**中断**（`status` 为 `interrupted`），此时需通过 [继续对话](/zh-CN/docs/ai/chat/continue) 回传答案后才能继续。

通过请求头 `Accept` 选择响应模式：`text/event-stream` 为 SSE 流式，逐步推送运行过程与回答；其他值为阻塞式，一次性返回聚合后的最终结果。

#### Request

##### Path Parameters

| Name | Type   | Required | Description                              |
| ---- | ------ | -------- | ---------------------------------------- |
| id   | string | YES      | 目标 Agent 的 UID，需为已发布 Agent      |

:::tip 如何获取 Agent 的 UID
除通过 [Workspace 下的 Agent](/zh-CN/docs/ai/workspace/agents) 接口查询外，也可以直接从 Longbridge 网页端获取：打开 Agent 的对话页，URL 形如 `https://longbridge.com/zh-CN/ai/agents/chatbot/chat`，其中 `chatbot` 即为该 Agent 的 UID。
:::

##### Request Body

| Name     | Type   | Required | Description                                        |
| -------- | ------ | -------- | -------------------------------------------------- |
| query    | string | YES      | 用户问题，不能为空                                 |
| chat_uid | string | NO       | 已有会话标识。传入则在该会话中继续提问，不传则新建会话 |

##### Python 示例

```python
import os
import requests

BASE_URL = os.getenv("LONGBRIDGE_HTTP_URL", "https://openapi.longbridge.com")
token = os.environ["LONGBRIDGE_ACCESS_TOKEN"]
headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
agent_id = "ag_7d3f9b2c"
workspace_id = "1001"
chat_uid = "ct_9f2c1a5b"
message_id = "43"
url = BASE_URL + f"/v1/ai/agents/{agent_id}/conversations"
response = requests.request('POST', url, headers=headers, json={"query": "帮我看看特斯拉最近的股价表现"}, timeout=60)
response.raise_for_status()
print(response.json())
```

##### Request Example

#### Response

##### Response Headers

- Content-Type: application/json（阻塞式）
- Content-Type: text/event-stream（流式）

##### Response Example

运行成功：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "chat_uid": "ct_9f2c1a5b",
    "message_id": "42",
    "status": "succeeded",
    "answer": "特斯拉（TSLA.US）最近……",
    "references": [
      { "index": 1, "title": "...", "url": "..." }
    ],
    "elapsed_time": 3.21
  }
}
```

运行中断（Agent 需要你补充信息，运行暂停）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "chat_uid": "ct_9f2c1a5b",
    "message_id": "43",
    "status": "interrupted",
    "answer": "",
    "references": null,
    "elapsed_time": 1.05,
    "interrupt": {
      "node_id": "n_ask_human",
      "tool_call_id": "call_abc123",
      "questions": [
        {
          "question": "你想查询哪个时间区间？",
          "options": [
            { "description": "近一周" },
            { "description": "近一个月" }
          ],
          "multi_select": false
        }
      ],
      "message_id": 43,
      "chat_id": 1001
    }
  }
}
```

流式模式下，服务端以 `event: message` 持续推送运行过程，`data` 中的 `event` 字段标识事件类型：

```
event: message
data: {"event":"chat_started","workflow_run_id":"745910371102313","data":{"chat_uid":"ct_9f2c1a5b","message_id":42}}

event: message
data: {"event":"message","workflow_run_id":"745910371102313","data":{"text":"特斯拉"}}

event: message
data: {"event":"workflow_finished","workflow_run_id":"745910371102313","data":{"status":"succeeded","elapsed_time":3.21,"outputs":{"answer":"..."}}}
```

完整的事件类型列表、负载结构与解析方式见 [SSE 事件](/zh-CN/docs/ai/chat/events)。

##### Response Status

| Status | Description | Schema                                          |
| ------ | ----------- | ----------------------------------------------- |
| 200    | 返回成功    | [conversation_response](#schemaconversation_response) |
| 400    | 参数非法或命中风控 | `query` 为空、请求体错误，或内容风控拦截    |
| 500    | 内部错误    | None                                            |

#### Schemas

##### conversation_response

| Name                 | Type     | Required | Description                                      |
| -------------------- | -------- | -------- | ------------------------------------------------ |
| chat_uid             | string   | true     | 会话标识，追加提问或排查问题时使用               |
| message_id           | string   | true     | 本轮消息 ID（字符串形式）                        |
| status               | string   | true     | 运行终态：`succeeded` / `interrupted` / `failed` / `stopped` |
| answer               | string   | false    | 最终回答文本，`status` 为 `succeeded` 时有效      |
| references           | object[] | false    | 回答引用的资料来源，无引用时为 `null`            |
| elapsed_time         | number   | false    | 运行耗时（秒）                                   |
| interrupt            | object   | false    | 仅当 `status` 为 `interrupted` 时出现            |
| ∟ node_id            | string   | true     | 触发中断的节点 ID                                |
| ∟ tool_call_id       | string   | true     | 本次询问对应的工具调用 ID，继续对话时作为答案的 key |
| ∟ questions          | object[] | true     | 需要你回答的问题列表                             |
| ∟∟ question          | string   | true     | 问题文本                                         |
| ∟∟ options           | object[] | false    | 可选项，为空表示自由作答                         |
| ∟∟∟ description      | string   | false    | 选项文本                                         |
| ∟∟ multi_select      | boolean  | false    | 是否允许多选                                     |
| ∟ message_id         | int64    | false    | 被暂停的消息 ID                                  |
| ∟ chat_id            | int64    | false    | 所属会话 ID                                      |
| error                | object   | false    | 仅当运行出错时出现                               |
| ∟ code               | int32    | false    | 错误码                                           |
| ∟ message            | string   | false    | 错误信息                                         |

#### 1.3 Workspace 下的 Agent

- **Python SDK**：`AgentContext.agents(...)`
- **权限/费用**：Workspace/Agent 权限；官方未公开统一计费
- **官方页面**：[Workspace 下的 Agent](https://open.longbridge.com/zh-CN/docs/ai/workspace/agents)
- **HTTP**：`GET /v1/ai/workspaces/:id/agents`

获取指定 Workspace 下的 Agent 列表。返回的 `uid` 即 [发起对话](/zh-CN/docs/ai/chat/conversation) 接口路径中的 Agent 标识；只有 `is_published` 为 `true` 的 Agent 才能发起对话。

#### Request

##### Path Parameters

| Name | Type   | Required | Description  |
| ---- | ------ | -------- | ------------ |
| id   | string | YES      | Workspace ID |

##### Query Parameters

| Name  | Type   | Required | Description                        |
| ----- | ------ | -------- | ---------------------------------- |
| page  | int32  | NO       | 页码，从 1 开始，默认 1            |
| limit | int32  | NO       | 每页数量，默认 20                  |
| name  | string | NO       | 按 Agent 名称模糊搜索              |

##### Python 示例

```python
import os
import requests

BASE_URL = os.getenv("LONGBRIDGE_HTTP_URL", "https://openapi.longbridge.com")
token = os.environ["LONGBRIDGE_ACCESS_TOKEN"]
headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
agent_id = "ag_7d3f9b2c"
workspace_id = "1001"
chat_uid = "ct_9f2c1a5b"
message_id = "43"
url = BASE_URL + f"/v1/ai/workspaces/{workspace_id}/agents"
response = requests.request('GET', url, headers=headers, json={}, timeout=60)
response.raise_for_status()
print(response.json())
```

##### Request Example

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "agents": [
      {
        "uid": "ag_7d3f9b2c",
        "name": "美股分析助手",
        "description": "结合行情与基本面数据，回答美股相关问题",
        "mode": "chat",
        "icon": "https://cdn.longbridge.com/icons/agent.png",
        "is_published": true,
        "published_at": 1742000000,
        "created_at": 1741000000,
        "updated_at": 1742001000
      }
    ],
    "total": 12
  }
}
```

##### Response Status

| Status | Description | Schema                                    |
| ------ | ----------- | ----------------------------------------- |
| 200    | 返回成功    | [agents_response](#schemaagents_response) |
| 400    | 参数非法    | Workspace 不存在或无权访问                |
| 500    | 内部错误    | None                                      |

#### Schemas

##### agents_response

| Name           | Type     | Required | Description                                          |
| -------------- | -------- | -------- | ---------------------------------------------------- |
| agents         | object[] | true     | Agent 列表                                           |
| ∟ uid          | string   | true     | Agent UID，用于 [发起对话](/zh-CN/docs/ai/chat/conversation) 的路径参数 |
| ∟ name         | string   | true     | Agent 名称                                           |
| ∟ description  | string   | false    | Agent 描述                                           |
| ∟ mode         | string   | true     | Agent 模式，如 `chat`                                |
| ∟ icon         | string   | false    | 图标 URL                                             |
| ∟ is_published | boolean  | true     | 是否已发布，仅已发布的 Agent 可发起对话              |
| ∟ published_at | int64    | false    | 发布时间，Unix 时间戳（秒），未发布为 0              |
| ∟ created_at   | int64    | false    | 创建时间，Unix 时间戳（秒）                          |
| ∟ updated_at   | int64    | false    | 最后更新时间，Unix 时间戳（秒）                      |
| total          | int32    | true     | 符合条件的 Agent 总数                                |

#### 1.4 我的 Workspace

- **Python SDK**：`AgentContext.workspaces(...)`
- **权限/费用**：Workspace/Agent 权限；官方未公开统一计费
- **官方页面**：[我的 Workspace](https://open.longbridge.com/zh-CN/docs/ai/workspace/workspaces)
- **HTTP**：`GET /v1/ai/workspaces`

获取当前账户加入的全部 Workspace 列表。Workspace 是 Agent 的组织单位，先通过本接口找到目标 Workspace，再用 [Workspace 下的 Agent](/zh-CN/docs/ai/workspace/agents) 查询其中可用的 Agent。

#### Request

##### Python 示例

```python
import os
import requests

BASE_URL = os.getenv("LONGBRIDGE_HTTP_URL", "https://openapi.longbridge.com")
token = os.environ["LONGBRIDGE_ACCESS_TOKEN"]
headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
agent_id = "ag_7d3f9b2c"
workspace_id = "1001"
chat_uid = "ct_9f2c1a5b"
message_id = "43"
url = BASE_URL + f"/v1/ai/workspaces"
response = requests.request('GET', url, headers=headers, json={}, timeout=60)
response.raise_for_status()
print(response.json())
```

##### Request Example

#### Response

##### Response Headers

- Content-Type: application/json

##### Response Example

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "workspaces": [
      {
        "id": "1001",
        "name": "我的工作空间",
        "created_at": 1742000000,
        "updated_at": 1742001000
      }
    ]
  }
}
```

##### Response Status

| Status | Description | Schema                                            |
| ------ | ----------- | ------------------------------------------------- |
| 200    | 返回成功    | [workspaces_response](#schemaworkspaces_response) |
| 500    | 内部错误    | None                                              |

#### Schemas

##### workspaces_response

| Name         | Type     | Required | Description                     |
| ------------ | -------- | -------- | ------------------------------- |
| workspaces   | object[] | true     | 当前账户加入的 Workspace 列表   |
| ∟ id         | string   | true     | Workspace ID                    |
| ∟ name       | string   | true     | Workspace 名称                  |
| ∟ created_at | int64    | false    | 创建时间，Unix 时间戳（秒）     |
| ∟ updated_at | int64    | false    | 最后更新时间，Unix 时间戳（秒） |

## 14. 底层 Socket 与实时推送补充

Python SDK 已经封装 Quote WebSocket/Trade WebSocket；如果必须自行实现协议，官方还提供握手、包头、请求包、响应包、推送包、业务指令、端点和 WebSocket/TCP 差异文档。

- [Socket 协议概览](https://open.longbridge.com/zh-CN/docs/socket/protocol/overview)
- [Quote 订阅方式](https://open.longbridge.com/zh-CN/docs/socket/subscribe_quote)
- [Trade 订阅方式](https://open.longbridge.com/zh-CN/docs/socket/subscribe_trade)
- [Socket 接入点](https://open.longbridge.com/zh-CN/docs/socket/hosts)
- [获取 Socket OTP](https://open.longbridge.com/zh-CN/docs/socket-token-api)

自行实现协议时应优先使用官方 Protobuf 定义和 SDK；不要根据示例响应手工猜字段编号。

## 15. 官方来源与校验边界

- [Getting Started（官方）](https://open.longbridge.com/zh-CN/docs/getting-started)
- [Quote API Overview（官方）](https://open.longbridge.com/zh-CN/docs/quote/overview)
- [Fundamental API Overview（官方）](https://open.longbridge.com/zh-CN/docs/fundamental/overview)
- [官方 Developers 文档仓库](https://github.com/longbridge/developers)
- [官方行情权限配置](https://github.com/longbridge/developers/blob/main/quote-permissions.yaml)

价格、行情卡库存、账户区域资格和权限赠送规则可能变化；接入前应以开发者中心和行情商城当前显示为最终依据。本文件的“免费/收费”只复述官方当前文档公开口径，不替代券商费用、产品条款或法律文件。
