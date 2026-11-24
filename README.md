# CampusEvent — 校园活动报名系统（实验二）

Python + FastAPI + SQLite 的校园活动报名后端。

实验二 baseline-v1 全部验收通过（C1~C10 + T-S1/T-S2，共 12 条）。
当前另有 4 条补充边界测试，共 23 条 pytest 全部通过。

## 线上访问地址

- 项目 Web 地址：**https://zyq.pythonanywhere.com**
- 健康检查：https://zyq.pythonanywhere.com/health
- API 文档（Swagger）：https://zyq.pythonanywhere.com/docs

> 部署环境：PythonAnywhere 免费实例，Python 3.12 + WSGI 适配器。
> 本地开发使用 Python 3.13，代码同时兼容 3.10+。

---

## 快速开始（本地）

### 1. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate      # macOS / Linux

pip install -r requirements.txt
```

### 2. 初始化数据库

```powershell
python -m project.db
```

默认生成 `campus_event.db`，含 4 张表 + 3 个种子学生（S001 / S002 / S003）。

### 3. 启动开发服务器

```powershell
python -m uvicorn project.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器打开：
- API 文档（Swagger）：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health → `{"status":"ok","app":"CampusEvent"}`

### 4. 跑测试

```powershell
pytest tests/ -v
```

---

## PythonAnywhere 部署（已上线）

线上地址：https://zyq.pythonanywhere.com

部署要点（完整步骤见 [DEPLOY_PYTHONANYWHERE.md](DEPLOY_PYTHONANYWHERE.md)）：

```bash
# PythonAnywhere Bash console
cd /home/ZYQ/24-2-_242806010229_StudyTask
git clone https://github.com/YQ-WCQ/24jike2_242806010229_CampusEvent.git .
git checkout main

# 虚拟环境需与 Web tab 所选 Python 版本一致（此处 3.12）
mkvirtualenv --python=/usr/bin/python3.12 campus-event-env
pip install -r requirements.prod.txt
python -c "from project.db import init_db; init_db()"
```

Web tab 中设置：

| 项 | 值 |
|---|---|
| Source code | `/home/ZYQ/24-2-_242806010229_StudyTask` |
| Working directory | `/home/ZYQ/24-2-_242806010229_StudyTask` |
| Virtualenv | `/home/ZYQ/.virtualenvs/campus-event-env` |
| Python version | 3.12 |

WSGI 配置文件 `/var/www/zyq_pythonanywhere_com_wsgi.py` 内容：

```python
import sys, os

CODE_DIR = '/home/ZYQ/24-2-_242806010229_StudyTask'
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

os.environ['CAMPUS_EVENT_DB'] = os.path.join(CODE_DIR, 'campus_event.db')

from wsgi import application
```

保存后点 **Reload**，访问 `https://zyq.pythonanywhere.com/health` 应返回
`{"status":"ok","app":"CampusEvent"}`。

---

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/activities` | 活动列表（学生端，带剩余名额） |
| `GET` | `/api/activities/{id}` | 活动详情 |
| `POST` | `/api/activities/{id}/registrations` | 学生报名 |
| `GET` | `/api/students/{id}/registrations` | 我的报名 |
| `DELETE` | `/api/students/{sid}/registrations/{rid}` | 取消报名 |
| `GET` | `/api/students/{id}/messages` | 我的通知 |
| `POST` | `/api/admin/activities` | Admin 创建活动 |
| `PUT` | `/api/admin/activities/{id}` | Admin 更新活动 |
| `DELETE` | `/api/admin/activities/{id}` | Admin 删除活动（有报名则拒绝） |
| `GET` | `/api/admin/activities/{id}/stats` | Admin 查看活动统计 |
| `POST` | `/api/admin/registrations/{id}/approve` | Admin 批准报名 |
| `POST` | `/api/admin/registrations/{id}/reject` | Admin 拒绝报名 |

固定演示账号（不入库，内存模拟）：

- 学生：`S001`、`S002`、`S003`（密码无，直接传 student_id）
- 管理员：Admin（内存角色，不登录）

---

## 项目结构

```
project/
  api/           # FastAPI 路由 + schemas + 依赖注入
  domain/        # 领域模型（Activity / Registration / Message）+ 状态机 + 错误
  policies/      # 策略模式：DirectPolicy / AuditPolicy / Factory
  events/        # 进程内事件总线（观察者模式）
  repositories/  # 仓储接口 + SQLite 实现
  services/      # 业务服务（ActivityService / RegistrationService / NotificationService）
  config.py      # 配置（DB 路径等）
  db.py          # DDL + 种子数据
  main.py        # FastAPI app 入口
wsgi.py          # PythonAnywhere WSGI 入口（ASGI→WSGI 适配）
asgi_wsgi_adapter.py  # 手写桥接器（无外部依赖）
tests/           # pytest：C1~C10 + T-S1/T-S2 + 骨架
docs/            # SRS 分析 + 设计说明 + UML 图 + PNG
```

---

## 设计要点

| 决策 | 说明 |
|---|---|
| 策略模式（RegistrationPolicy） | DirectPolicy 自动 APPROVED；AuditPolicy 初始 PENDING。策略工厂按活动类型选择。 |
| 名额检查放服务层 | 两种策略共用的业务规则（B.2.3），策略本身不含名额判断。 |
| 观察者（事件总线） | 报名状态变更发 `RegistrationStatusChangedEvent`，NotificationService 订阅并落库。 |
| 先提交后发布 | 数据库 commit 后再 publish 事件；通知异常只记日志，不回滚业务（B.2.6）。 |
| 服务层查重 | SQLite 不做唯一索引兜底，`find_active` 查 PENDING/APPROVED 联合过滤。 |
| 删除拒绝 | 有任意历史报名（全状态）即拒绝删除；无报名可物理删除。 |
| 内存模拟 Admin | Admin 不入库，无登录注册。 |

---

## Git 标签

| 标签 | 说明 |
|---|---|
| **`baseline-v1`** | 完整业务实现 + 23/23 测试通过，作为初始验收与后续变更基线 |

---

## 实验提交材料清单

| 文件 | 位置 |
|---|---|
| 初始 SRS 分析 | `docs/SRS分析.md` |
| 设计说明（含 UML 类图 + 2 张时序图） | `docs/设计说明V1.md` + `docs/images/` |
| 源代码 | `project/` + `wsgi.py` + `asgi_wsgi_adapter.py` |
| 生产依赖 | `requirements.prod.txt` |
| AI 协作日志 | `AI_DEV_LOG.md` |
| 验收测试用例 | `tests/test_acceptance.py`（C1~C10 + T-S1/T-S2） |
| 运行说明 | 本 README + `DEPLOY_PYTHONANYWHERE.md` |
| 实验报告 | `docs/实验报告.md` |
| Git 标签 | `baseline-v1` |

---

## 后续（等教师发布变更单后）

3.6 规范：不得提前实现变更需求。拿到变更单后：

1. 写变更影响分析（涉及的类、接口、风险、测试范围）
2. 从 `baseline-v1` 创建新分支
3. 实现变更 → 回归测试 → 打 `change-v2` 标签
4. 对比 baseline-v1 vs change-v2，统计新增类 / 修改类 / 回归失败数 / AI 交互轮次
