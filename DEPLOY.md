# 部署指南

## 方式一：Docker Compose 部署（推荐）

### 1. 准备服务器
- 阿里云/腾讯云/华为云 轻量应用服务器（2核2G即可）
- 系统：Ubuntu 20.04+ 或 CentOS 7+
- 开放端口：8000（或配置Nginx后开放80/443）

### 2. 服务器环境准备

```bash
# 连接服务器
ssh root@你的服务器IP

# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

### 3. 部署应用

```bash
# 创建应用目录
mkdir -p /opt/price-bot
cd /opt/price-bot

# 从 GitHub 克隆代码（假设你已经上传）
git clone https://github.com/你的用户名/price-compare-bot.git .

# 或者本地上传代码后解压
# unzip price-bot.zip

# 创建环境变量文件
cp .env.example .env
vim .env  # 编辑配置，填写你的微信Token和各平台API密钥

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f app
```

### 4. 配置微信公众号

1. 登录公众号后台：https://mp.weixin.qq.com
2. 开发 → 基本配置 → 服务器配置
3. 填写：
   - URL: `http://你的服务器IP:8000/wechat/callback`
   - Token: 与 `.env` 中的 `WECHAT_TOKEN` 一致
   - EncodingAESKey: 随机生成（或选明文模式不填）
   - 消息加解密方式: 明文模式
4. 点击"提交"验证
5. 启用服务器配置

### 5. 验证部署

```bash
# 测试接口是否通
curl http://你的服务器IP:8000/health

# 应该返回：
# {"status": "healthy", "cache": "connected"}
```

---

## 方式二：直接部署（无Docker）

### 1. 安装依赖

```bash
# Ubuntu/Debian
apt-get update
apt-get install python3-pip python3-venv redis-server nginx

# CentOS/RHEL
yum install python3-pip python3-virtualenv redis nginx
```

### 2. 部署应用

```bash
# 创建目录
mkdir -p /opt/price-bot
cd /opt/price-bot

# 克隆代码
git clone https://github.com/你的用户名/price-compare-bot.git .

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
vim .env  # 编辑配置

# 启动Redis
systemctl start redis
systemctl enable redis

# 启动应用（先用screen/tmux保持运行）
screen -S price-bot
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3. 配置Nginx（可选，推荐用于生产环境）

```bash
# 安装Nginx后，创建配置文件
cat > /etc/nginx/sites-available/price-bot << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 如果有域名

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

# 启用配置
ln -s /etc/nginx/sites-available/price-bot /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

---

## 方式三：云服务器一键部署脚本

保存为 `deploy.sh` 在服务器上运行：

```bash
#!/bin/bash
# 一键部署脚本

set -e

echo "=== 公众号比价机器人一键部署 ==="

# 检查root权限
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 sudo 运行"
    exit 1
fi

# 安装Docker
if ! command -v docker &> /dev/null; then
    echo "正在安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl start docker
    systemctl enable docker
fi

# 安装Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "正在安装 Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# 创建应用目录
APP_DIR="/opt/price-bot"
mkdir -p $APP_DIR
cd $APP_DIR

echo "请确保已将代码上传到 $APP_DIR"
echo "如果没有，请先执行：git clone https://github.com/你的用户名/price-compare-bot.git ."

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "警告：未找到 .env 文件"
    echo "请复制 .env.example 为 .env 并配置你的API密钥"
    cp .env.example .env
fi

# 启动服务
echo "正在启动服务..."
docker-compose down 2>/dev/null || true
docker-compose up -d

# 等待服务启动
sleep 5

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo "✅ 服务启动成功！"
    echo ""
    echo "访问地址: http://$(curl -s ifconfig.me):8000"
    echo "健康检查: http://$(curl -s ifconfig.me):8000/health"
    echo ""
    echo "请在微信公众号后台配置服务器URL："
    echo "URL: http://$(curl -s ifconfig.me):8000/wechat/callback"
    echo ""
    echo "查看日志: docker-compose logs -f app"
else
    echo "❌ 服务启动失败，请检查日志："
    echo "docker-compose logs app"
fi
```

运行：
```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

---

## 常见问题

### 1. 微信验证失败
- 检查服务器8000端口是否开放（安全组/防火墙）
- 确认Token前后没有空格
- 确认URL路径正确 `/wechat/callback`

### 2. 时间戳错误
- 服务器时间不同步：`timedatectl set-ntp true`

### 3. Redis连接失败
- Docker方式：检查redis容器是否启动 `docker-compose ps`
- 直接部署：检查redis服务 `systemctl status redis`

### 4. API调用失败
- 检查 .env 中的API密钥是否正确
- 查看日志 `docker-compose logs -f app`

---

## 更新部署

```bash
cd /opt/price-bot

# 拉取最新代码
git pull origin main

# 重启服务
docker-compose down
docker-compose up -d
```
