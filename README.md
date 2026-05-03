# 公众号比价机器人

支持淘宝、京东、拼多多的微信公众号比价机器人，自动查询优惠券和佣金，帮助用户省钱。

## 功能特性

- 🔍 **链接识别** - 自动识别各平台商品链接
- 💰 **价格查询** - 实时查询商品价格和优惠券
- 🎫 **优惠券** - 自动匹配可用优惠券
- 📊 **智能建议** - 根据折扣力度给出购买建议
- 🔍 **关键词搜索** - 支持关键词搜索商品
- ⚡ **缓存加速** - Redis缓存，响应更快
- 🛡️ **限流保护** - 防止滥用，保护API

## 技术架构

```
用户 -> 微信公众号 -> 后端服务(FastAPI) -> 各平台API
                         ↓
                      Redis缓存
```

### 核心模块

| 模块 | 职责 |
|------|------|
| `platforms/` | 平台适配器（淘宝/京东/拼多多） |
| `services/` | 业务服务（缓存/价格查询/消息组装） |
| `api/` | 微信接口处理 |
| `models/` | 数据模型 |
| `config/` | 配置管理 |

### 设计特点

- **可扩展**：新增平台只需实现适配器接口
- **可维护**：清晰的模块划分，易于维护
- **高性能**：Redis缓存，异步处理
- **易配置**：环境变量配置，无需改代码

## 快速开始

### 1. 环境要求

- Python 3.9+
- Redis 6.0+
- 微信公众号（服务号或订阅号）

### 2. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填写配置
```

### 4. 运行服务

```bash
# 开发模式
python main.py

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 5. 配置微信公众号

1. 登录微信公众平台
2. 开发 -> 基本配置 -> 服务器配置
3. 填写服务器URL: `http://your-domain/wechat/callback`
4. Token填写与.env中WECHAT_TOKEN一致的值
5. 启用服务器配置

## 使用方法

### 查价格

直接发送商品链接：
```
https://item.taobao.com/item.htm?id=123456
```

机器人返回：
```
🍑 iPhone 15 Pro
💰 原价：¥8999
🏷️ 现价：¥8999
🎫 优惠券：满8000减500
✅ 券后价：¥8499
💵 立省：¥500
🔥 折扣：5% off
📈 销量：1.2万

💡 近期好价，可以考虑入手

👇 点击卡片领券购买
```

### 搜商品

发送关键词：
```
iPhone 15
```

机器人返回各平台的比价结果。

### 帮助

发送：
```
帮助
```

查看使用指南。

## 开发文档

### 添加新平台

1. 创建适配器继承 `PlatformAdapter`：

```python
from platforms.base import PlatformAdapter
from models import ProductInfo, PlatformType

class NewPlatformAdapter(PlatformAdapter):
    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.NEW

    async def parse_link(self, link: str) -> Optional[str]:
        # 解析链接提取商品ID
        pass

    async def get_product_info(self, item_id: str) -> ProductInfo:
        # 查询商品信息
        pass

    async def convert_link(self, item_id: str, original_link: str) -> str:
        # 生成推广链接
        pass

    async def search(self, keyword: str, page: int = 1, page_size: int = 10) -> SearchResult:
        # 关键词搜索
        pass
```

2. 注册适配器：

```python
# platforms/__init__.py
from .new_platform import NewPlatformAdapter

ADAPTERS = {
    "taobao": TaobaoAdapter,
    "jd": JDAdapter,
    "pdd": PDDAdapter,
    "new": NewPlatformAdapter,  # 添加新平台
}
```

3. 添加平台配置：

```python
# config/platforms.py
NEW_CONFIG = PlatformConfig(
    name="新平台",
    code="new",
    icon="🆕",
    domains=["newplatform.com"],
    item_id_patterns=[re.compile(r"[?&]id=(\d+)")],
    short_link_domains=["short.np.com"],
)
```

### 调试接口

开发模式下提供调试接口：

- `GET /test/link?link=xxx` - 测试链接解析
- `GET /test/product?platform=taobao&item_id=xxx` - 测试商品查询

## 部署

### Docker部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 云服务器部署

推荐使用：
- 阿里云 ECS / 腾讯云轻量
- 2核2G配置即可
- 搭配Redis云服务

### 监控

- 接口响应时间: 目标 < 2秒
- 缓存命中率: 目标 > 80%
- 错误率: 目标 < 1%

## 申请联盟账号

### 淘宝客
1. 访问 https://pub.alimama.com/
2. 用淘宝账号登录
3. 完成实名认证
4. 创建媒体（网站或APP）
5. 获取App Key和App Secret

### 京东联盟
1. 访问 https://union.jd.com/
2. 注册账号
3. 创建推广位
4. 获取API密钥

### 拼多多
1. 访问 https://open.pinduoduo.com/
2. 注册开发者
3. 创建应用
4. 获取Client ID和Client Secret

## 注意事项

1. **合规使用** - 遵守各平台推广规则
2. **API限流** - 合理控制请求频率
3. **缓存策略** - 适当设置缓存时间，平衡实时性和性能
4. **错误处理** - 做好降级处理，保证服务可用性

## License

MIT

## 联系方式

如有问题，请提Issue或联系开发者。
