# 公众号比价机器人技术设计方案

## 一、核心设计原则

- **无用户系统**：匿名访问，用完即走
- **极简架构**：能不用数据库就不用
- **快速响应**：缓存优先，API兜底
- **可扩展**：后续可加平台、加功能

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────┐
│                  微信公众号                          │
│              （用户发送链接/关键词）                  │
└────────────────────┬────────────────────────────────┘
                     │
                     │ HTTPS POST (XML)
                     │
┌────────────────────▼────────────────────────────────┐
│                FastAPI 服务                          │
│  ┌──────────────────────────────────────────────┐  │
│  │  1. 微信消息处理器 (wechat_handler)            │  │
│  │     - 验证签名                                  │  │
│  │     - 解析 XML 消息                             │  │
│  │     - 提取文本/链接                             │  │
│  └────────────────────┬───────────────────────────┘  │
│                       │                              │
│  ┌────────────────────▼───────────────────────────┐  │
│  │  2. 链接解析器 (link_parser)                    │  │
│  │     - 识别平台（淘宝/京东/拼多多）               │  │
│  │     - 提取商品 ID                               │  │
│  │     - 清洗短链接                                │  │
│  └────────────────────┬───────────────────────────┘  │
│                       │                              │
│  ┌────────────────────▼───────────────────────────┐  │
│  │  3. 价格查询引擎 (price_engine)                 │  │
│  │     - 查缓存 (Redis)                            │  │
│  │     - 调平台 API（淘宝客/京东联盟/多多进宝）      │  │
│  │     - 写入缓存                                  │  │
│  └────────────────────┬───────────────────────────┘  │
│                       │                              │
│  ┌────────────────────▼───────────────────────────┐  │
│  │  4. 转链服务 (link_converter)                   │  │
│  │     - 联盟 API 转链                             │  │
│  │     - 生成带推广代码的链接                       │  │
│  └────────────────────┬───────────────────────────┘  │
│                       │                              │
│  ┌────────────────────▼───────────────────────────┐  │
│  │  5. 消息组装器 (message_builder)                │  │
│  │     - 组装图文回复                              │  │
│  │     - 生成价格对比文案                           │  │
│  └────────────────────┬───────────────────────────┘  │
│                       │                              │
└───────────────────────┼──────────────────────────────┘
                        │
                        │ HTTPS POST (XML)
                        │
┌───────────────────────▼──────────────────────────────┐
│                 微信服务器                            │
│              （推送结果给用户）                        │
└───────────────────────────────────────────────────────┘
```

---

## 三、核心模块设计

### 3.1 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 微信接口 | `api/wechat.py` | 接收/回复微信消息，签名验证 |
| 链接解析 | `services/parser.py` | 识别平台，提取商品ID |
| 价格查询 | `services/price.py` | 对接各平台API查询价格 |
| 转链服务 | `services/converter.py` | 生成推广链接 |
| 消息组装 | `services/message.py` | 生成回复文案 |
| 缓存 | `services/cache.py` | Redis操作 |

---

### 3.2 数据结构设计

#### 商品信息（内存对象）
```python
class ProductInfo:
    platform: str          # "taobao" | "jd" | "pdd"
    item_id: str           # 商品ID
    title: str             # 商品标题
    price: float           # 当前价格
    original_price: float  # 原价
    coupon_amount: float   # 优惠券金额
    final_price: float     # 券后价
    coupon_link: str       # 领券链接
    product_image: str     # 商品图片
    commission_rate: float # 佣金比例
    shop_name: str         # 店铺名
    sales_count: int       # 销量
```

#### 缓存结构（Redis）
```
Key: product:{platform}:{item_id}
Value: JSON(ProductInfo)
TTL: 3600 秒（1小时）

Key: search:{keyword_hash}
Value: JSON(List[ProductInfo])
TTL: 1800 秒（30分钟）
```

---

### 3.3 接口设计

#### 微信回调接口
```
POST /wechat/callback
Content-Type: application/xml

# 接收
<xml>
    <ToUserName>gh_xxx</ToUserName>
    <FromUserName>openid_xxx</FromUserName>
    <CreateTime>123456789</CreateTime>
    <MsgType>text</MsgType>
    <Content>https://item.taobao.com/item.htm?id=123</Content>
    <MsgId>1234567890123456</MsgId>
</xml>

# 返回
<xml>
    <ToUserName>openid_xxx</ToUserName>
    <FromUserName>gh_xxx</FromUserName>
    <CreateTime>123456790</CreateTime>
    <MsgType>news</MsgType>
    <ArticleCount>1</ArticleCount>
    <Articles>
        <item>
            <Title>iPhone 15 Pro - 券后¥8499（省500）</Title>
            <Description>💰原价¥8999 | 🎫优惠¥500 | 💡建议：近期好价...</Description>
            <PicUrl>https://img.xxx.jpg</PicUrl>
            <Url>https://s.click.taobao.com/xxx</Url>
        </item>
    </Articles>
</xml>
```

#### 健康检查
```
GET /health

Response:
{
    "status": "ok",
    "redis": "connected",
    "cache_hit_rate": 0.85
}
```

---

## 四、核心流程

### 4.1 链接查询流程

```
用户发送链接
    │
    ▼
验证微信签名
    │
    ├─ 失败 → 返回 403
    │
    ▼
解析消息类型
    │
    ├─ 非文本消息 → 返回提示"请发送商品链接"
    │
    ▼
提取链接
    │
    ├─ 无链接 → 尝试关键词搜索
    │
    ▼
识别平台
    │
    ├─ 未知平台 → 返回"暂不支持该平台"
    │
    ▼
提取商品ID
    │
    ▼
查缓存
    │
    ├─ 命中 → 直接返回
    │
    └─ 未命中 → 调平台API
                │
                ├─ API成功 → 写缓存 → 返回
                │
                └─ API失败 → 返回"查询失败，请重试"
```

### 4.2 转链流程

```
获取商品原始链接
    │
    ▼
调联盟转链API
    │
    ├─ 成功 → 获取推广链接
    │
    └─ 失败 → 使用原始链接（无佣金）
    │
    ▼
组装回复消息
```

---

## 五、第三方API对接

### 5.1 淘宝客（阿里妈妈）

**所需API：**
| API | 用途 | 文档 |
|-----|------|------|
| `taobao.tbk.item.info.get` | 获取商品详情 | [链接](https://open.taobao.com/api.htm?docId=24518&docType=2) |
| `taobao.tbk.coupon.get` | 查询优惠券 | [链接](https://open.taobao.com/api.htm?docId=31106&docType=2) |
| `taobao.tbk.sc.material.optional` | 通用搜索 | [链接](https://open.taobao.com/api.htm?docId=35896&docType=2) |
| `taobao.tbk.sc.tpwd.create` | 生成淘口令 | [链接](https://open.taobao.com/api.htm?docId=31102&docType=2) |

**转链方式：**
```
原始链接 → 淘宝客转链API → 生成 s.click.taobao.com 短链
```

### 5.2 京东联盟

**所需API：**
| API | 用途 | 文档 |
|-----|------|------|
| `jd.union.open.goods.promotiongoodsinfo.query` | 查询推广商品 | [链接](https://union.jd.com/openplatform/api/10417) |
| `jd.union.open.promotion.common.get` | 获取推广链接 | [链接](https://union.jd.com/openplatform/api/11725) |

### 5.3 拼多多（多多进宝）

**所需API：**
| API | 用途 | 文档 |
|-----|------|------|
| `pdd.ddk.goods.detail` | 商品详情 | [链接](https://open.pinduoduo.com/application/document/apiTool?scopeName=pdd.ddk.goods.detail) |
| `pdd.ddk.goods.promotion.url.generate` | 生成推广链接 | [链接](https://open.pinduoduo.com/application/document/apiTool?scopeName=pdd.ddk.goods.promotion.url.generate) |

---

## 六、错误处理

### 6.1 错误类型与响应

| 场景 | 用户看到 | 日志记录 |
|------|----------|----------|
| 链接解析失败 | "链接格式不正确，请发送淘宝/京东/拼多多商品链接" | WARN |
| API限流 | "查询太频繁，请稍后再试" | ERROR |
| 商品下架 | "该商品已下架或不可用" | INFO |
| 网络超时 | "查询超时，请重试" | ERROR |
| 系统异常 | "系统繁忙，请稍后再试" | CRITICAL |

### 6.2 降级策略

```python
# 价格查询降级链
1. Redis缓存 → 2. 联盟API → 3. 爬虫（备用）→ 4. 返回原始链接

# 转链降级
1. 联盟转链 → 2. 使用原始链接（提示用户手动领券）
```

---

## 七、安全设计

### 7.1 微信签名验证
```python
def verify_signature(token, signature, timestamp, nonce):
    # 微信签名算法
    tmp_list = [token, timestamp, nonce]
    tmp_list.sort()
    tmp_str = ''.join(tmp_list)
    hashcode = hashlib.sha1(tmp_str.encode()).hexdigest()
    return hashcode == signature
```

### 7.2 防刷限流
```
Redis key: limit:{openid}
Value: 请求次数
TTL: 60秒

限制：单用户每分钟最多 10 次查询
```

### 7.3 敏感信息
- API密钥存环境变量
- 不记录用户对话内容（仅记录匿名统计）

---

## 八、部署方案

### 8.1 资源需求
| 组件 | 配置 | 成本 |
|------|------|------|
| 服务器 | 2核2G | ~50元/月（阿里云/腾讯云） |
| Redis | 256MB | ~20元/月（云服务） |
| 域名 | - | ~50元/年 |

### 8.2 部署架构
```
用户 → 微信服务器 → 你的域名(HTTPS) → Nginx → FastAPI
                                        ↓
                                     Redis
```

### 8.3 监控
- 接口响应时间（目标 < 2秒）
- 缓存命中率（目标 > 80%）
- 错误率（目标 < 1%）

---

## 九、MVP排期

| 阶段 | 任务 | 时间 |
|------|------|------|
| 第1天 | 搭建FastAPI框架，微信消息接收/回复 | 4h |
| 第2天 | 链接解析模块，识别3个平台 | 3h |
| 第3天 | 接入淘宝客API，查询价格+转链 | 6h |
| 第4天 | Redis缓存，消息组装 | 4h |
| 第5天 | 部署上线，测试调试 | 4h |
| - | 合计 | ~21小时 |

---

## 十、后续迭代方向

**Phase 2：**
- [ ] 接入京东、拼多多
- [ ] 价格走势图（保存30天历史）
- [ ] 关键词搜索（不局限于链接）

**Phase 3：**
- [ ] 小程序版本（更好体验）
- [ ] 浏览器插件（PC端）
- [ ] 降价提醒（需用户临时授权）

---

## 需要确认

1. **是否从淘宝单平台开始？**（推荐，最快验证）
2. **是否需要历史价格？**（初期可以不做）
3. **服务器用哪家？**（推荐阿里云ECS或腾讯云轻量）

确认后开始写代码。
