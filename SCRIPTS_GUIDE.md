# 📜 部署脚本使用指南

本项目提供了三个自动化脚本，让部署、监控和清理变得简单快捷。

---

## 🚀 快速开始

### 第一次部署
```bash
# 1. 完整部署
./full-deploy.sh

# 2. 启动仪表盘（新终端）
./start-dashboard.sh

# 3. 连接客户端（新终端）
python3.11 chat_client.py localhost 30080
```

### 清理所有资源
```bash
./cleanup.sh
```

---

## 📋 脚本详解

### 1️⃣ `full-deploy.sh` - 完整部署脚本

**功能：**
- ✅ 检查必需工具（kubectl, helm, docker, python3.11）
- ✅ 自动检测 K8s 环境（Minikube/Docker Desktop）
- ✅ 构建 Docker 镜像
- ✅ 拉取基础镜像（Redis, PostgreSQL）
- ✅ 使用 Helm 部署应用
- ✅ 等待 Pods 就绪
- ✅ 安装 Python 依赖
- ✅ 显示连接信息

**使用方法：**
```bash
./full-deploy.sh
```

**输出示例：**
```
╔══════════════════════════════════════════════════════════════╗
║          FULL DEPLOYMENT - Chat Application                  ║
╚══════════════════════════════════════════════════════════════╝

[1/8] Checking prerequisites...
  ✓ kubectl found
  ✓ helm found
  ✓ docker found
  ✓ python3.11 found
✓ All prerequisites OK

[2/8] Detecting Kubernetes environment...
...
[8/8] Deployment Summary

╔══════════════════════════════════════════════════════════════╗
║                  DEPLOYMENT SUCCESSFUL! 🎉                   ║
╚══════════════════════════════════════════════════════════════╝

Next Steps:
1️⃣  Connect a chat client:
   python3.11 chat_client.py localhost 30080

2️⃣  Start the monitoring dashboard:
   ./start-dashboard.sh
```

**适用场景：**
- 第一次部署应用
- 重新构建并部署
- 更新代码后重新部署

---

### 2️⃣ `start-dashboard.sh` - 启动仪表盘脚本

**功能：**
- ✅ 检查前置条件
- ✅ 验证 K8s 部署存在
- ✅ **自动设置端口转发**（Redis + PostgreSQL）
- ✅ 启动监控仪表盘
- ✅ **Ctrl+C 自动清理端口转发**

**使用方法：**
```bash
./start-dashboard.sh
```

**输出示例：**
```
╔══════════════════════════════════════════════════════════════╗
║           Starting Monitoring Dashboard                     ║
╚══════════════════════════════════════════════════════════════╝

[1/4] Checking prerequisites...
✓ Prerequisites OK

[2/4] Verifying Kubernetes deployment...
✓ Kubernetes deployment verified

[3/4] Setting up port forwarding...
  → Forwarding Redis (localhost:6379 → redis-service:6379)...
  ✓ Redis port forward started (PID: 12345)
  → Forwarding PostgreSQL (localhost:5432 → postgres-service:5432)...
  ✓ PostgreSQL port forward started (PID: 12346)
✓ Port forwarding active

[4/4] Starting dashboard...

📊 Dashboard URL: http://localhost:5000
📡 Health Check:  http://localhost:5000/api/health

Press Ctrl+C to stop the dashboard and cleanup port forwards
```

**重要特性：**
- 🔄 自动端口转发（无需手动操作）
- 🧹 优雅退出（Ctrl+C 自动清理）
- ⚠️ 智能检测端口占用

**适用场景：**
- 查看实时监控数据
- 监控 Pod 状态
- 查看用户统计

---

### 3️⃣ `cleanup.sh` - 清理脚本

**功能：**
- ✅ 停止所有端口转发进程
- ✅ 卸载 Helm release
- ✅ 删除 Kubernetes namespace
- ✅ 可选删除 Docker 镜像
- ✅ 清理临时文件（__pycache__, *.pyc）
- ✅ 验证清理完成

**使用方法：**
```bash
# 基础清理（保留 Docker 镜像）
./cleanup.sh

# 完全清理（包括 Docker 镜像）
./cleanup.sh --images

# 强制清理（跳过确认）
./cleanup.sh --force

# 完全强制清理
./cleanup.sh --images --force
```

**参数说明：**
| 参数 | 说明 |
|------|------|
| `--images` | 同时删除 Docker 镜像 |
| `--force` | 跳过确认提示 |
| `-h, --help` | 显示帮助信息 |

**输出示例：**
```
╔══════════════════════════════════════════════════════════════╗
║                    CLEANUP SCRIPT                            ║
╚══════════════════════════════════════════════════════════════╝

⚠️  WARNING: This will remove the following:
   • Helm release: my-chat
   • Kubernetes namespace: chat-app
   • All pods, services, and deployments in the namespace
   • All persistent data (PostgreSQL data)

Are you sure you want to continue? [y/N] y

[1/5] Stopping port forwarding processes...
  ✓ Stopped port-forward process (PID: 12345)
  ✓ Stopped port-forward process (PID: 12346)
✓ Port forwarding processes cleaned

[2/5] Uninstalling Helm release...
✓ Helm release 'my-chat' uninstalled

[3/5] Deleting namespace...
  → Waiting for namespace to be fully deleted...
✓ Namespace 'chat-app' deleted

[4/5] Cleaning Docker images...
  → Skipping Docker images cleanup
  → Use --images flag to remove Docker images

[5/5] Cleaning temporary files...
  ✓ Removed __pycache__
  ✓ Removed .pyc files
✓ Temporary files cleaned

╔══════════════════════════════════════════════════════════════╗
║                    CLEANUP COMPLETE! ✨                      ║
╚══════════════════════════════════════════════════════════════╝

📋 Summary:
  ✓ Port forwarding processes stopped
  ✓ Helm release uninstalled
  ✓ Namespace deleted
  ⊘ Docker images preserved
  ✓ Temporary files cleaned

🔄 To redeploy the application, run:
   ./full-deploy.sh
```

**适用场景：**
- 测试完成后清理环境
- 重新开始全新部署
- 释放系统资源
- 遇到问题需要重置

---

## 🔄 常见工作流程

### 工作流 1：日常开发测试
```bash
# 部署（第一次）
./full-deploy.sh

# 启动仪表盘
./start-dashboard.sh  # 终端 1

# 测试客户端
python3.11 chat_client.py localhost 30080  # 终端 2, 3, 4...

# 测试完成后清理
./cleanup.sh
```

### 工作流 2：代码修改后重新部署
```bash
# 清理旧版本（包括镜像）
./cleanup.sh --images

# 重新部署新版本
./full-deploy.sh

# 启动仪表盘
./start-dashboard.sh
```

### 工作流 3：仅重启仪表盘
```bash
# 如果仪表盘崩溃或需要重启
# 先按 Ctrl+C 停止旧的仪表盘

# 重新启动
./start-dashboard.sh
```

### 工作流 4：快速清理（开发环境）
```bash
# 快速清理，不删除镜像，不需要确认
./cleanup.sh --force

# 立即重新部署
./full-deploy.sh
```

---

## 🛠️ 故障排查

### 问题 1：`full-deploy.sh` 失败
```bash
# 检查工具是否安装
kubectl version --client
helm version
docker --version
python3.11 --version

# 检查 Kubernetes 是否运行
kubectl cluster-info
```

### 问题 2：端口转发失败
```bash
# 手动清理端口转发
ps aux | grep "kubectl port-forward" | awk '{print $2}' | xargs kill

# 然后重启仪表盘
./start-dashboard.sh
```

### 问题 3：Pods 一直 Pending
```bash
# 查看 Pod 详情
kubectl get pods -n chat-app
kubectl describe pod <pod-name> -n chat-app

# 查看事件
kubectl get events -n chat-app --sort-by='.lastTimestamp'

# 完全清理并重新部署
./cleanup.sh --images --force
./full-deploy.sh
```

### 问题 4：仪表盘无法连接 Redis/PostgreSQL
```bash
# 检查服务是否存在
kubectl get svc -n chat-app

# 检查端口转发
lsof -i :6379  # Redis
lsof -i :5432  # PostgreSQL

# 如果端口被占用，杀掉进程
kill <PID>

# 重启仪表盘
./start-dashboard.sh
```

---

## 📊 脚本对比

| 功能 | full-deploy.sh | start-dashboard.sh | cleanup.sh |
|------|----------------|-------------------|------------|
| 构建镜像 | ✅ | ❌ | ❌ |
| 部署 K8s | ✅ | ❌ | ❌ |
| 端口转发 | ❌ | ✅ | ❌ |
| 启动仪表盘 | ❌ | ✅ | ❌ |
| 清理资源 | ❌ | ❌ | ✅ |
| 删除镜像 | ❌ | ❌ | ✅ (可选) |
| 安装依赖 | ✅ | ❌ | ❌ |

---

## 💡 最佳实践

### ✅ DO（推荐）
- 第一次使用前仔细阅读脚本输出
- 使用 `./cleanup.sh` 清理测试环境
- 定期使用 `--images` 清理旧镜像
- 遇到问题先查看 Pod 日志

### ❌ DON'T（避免）
- 不要同时运行多个仪表盘实例
- 不要手动删除 namespace（使用 cleanup.sh）
- 不要在生产环境使用 `--force`
- 不要忘记停止仪表盘（会占用端口）

---

## 📞 获取帮助

```bash
# 查看脚本帮助
./cleanup.sh --help

# 查看 K8s 资源
kubectl get all -n chat-app

# 查看日志
kubectl logs -f deployment/chat-server -n chat-app
kubectl logs -f deployment/chat-autoscaler -n chat-app

# 查看仪表盘状态
curl http://localhost:5000/api/health
```

---

## 🎯 总结

| 需求 | 命令 |
|------|------|
| 第一次部署 | `./full-deploy.sh` |
| 启动监控 | `./start-dashboard.sh` |
| 完全清理 | `./cleanup.sh --images` |
| 快速重启 | `./cleanup.sh --force && ./full-deploy.sh` |
| 查看帮助 | `./cleanup.sh --help` |

---

**🎉 现在你可以用一条命令完成所有操作了！**
