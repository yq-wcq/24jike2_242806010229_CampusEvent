# PythonAnywhere 部署指南（CampusEvent）

> 面向学生账户 `ZYQ`，站点 `https://ZYQ.pythonanywhere.com`
> 代码目录：`/home/ZYQ/24-2-_242806010229_StudyTask`
> **本地已验证通过**：GET `/health` ✅、POST `/api/admin/activities` ✅、19/19 pytest 通过

---

## 架构说明

```
PythonAnywhere WSGI Server
        │
        ▼
wsgi.py  ──►  ASGItoWSGIAdapter  ──►  FastAPI app (ASGI)
                                           │
                                           ▼
                                  SQLite 文件 DB（同目录 campus_event.db）
```

FastAPI 原生是 ASGI，PythonAnywhere Web tab 只暴露 WSGI。
项目里自带 `asgi_wsgi_adapter.py` 手写桥接器（每个请求 `asyncio.run` 一次），
无需额外安装第三方包。

---

## 一、上传代码

### 方式 A：git clone（推荐，如果仓库已 push）

PythonAnywhere Bash console：

```bash
cd ~
git clone <你的 GitHub/GitLab 仓库地址> 24-2-_242806010229_StudyTask
cd 24-2-_242806010229_StudyTask
git checkout baseline-v1
```

### 方式 B：手动 zip 上传

本地把以下内容打包成 zip：

```
wsgi.py                 ← 入口
asgi_wsgi_adapter.py    ← 桥接器
requirements.prod.txt   ← 生产依赖（不是 requirements.txt）
project/                ← 整个目录
```

**不要包含**：`.git/`、`docs/images/`、`tests/`、`.venv/`、`__pycache__/`、`campus_event.db`、本地生成的 `*.pyc`

上传方式：PythonAnywhere → Files → 进入目标目录 → Upload a file。

---

## 二、安装依赖（Bash Console）

```bash
cd /home/ZYQ/24-2-_242806010229_StudyTask

# 创建虚拟环境（推荐，避免影响 PythonAnywhere 全局包）
mkvirtualenv --python=/usr/bin/python3.13 campus-event-env
# 如果没有 3.13，用 3.11 或 3.12 都行（FastAPI 0.115 兼容 3.9+）

# 激活并安装
pip install -r requirements.prod.txt
```

`requirements.prod.txt` 只含 3 个运行时依赖：

```
fastapi>=0.115,<1.0
uvicorn>=0.32,<1.0
pydantic>=2.9,<3.0
```

（不含 pytest、httpx、pillow、markdown——服务器不需要这些）

---

## 三、初始化数据库

```bash
cd /home/ZYQ/24-2-_242806010229_StudyTask
python -c "from project.db import init_db; init_db()"
```

执行后当前目录会生成 `campus_event.db`（含 4 张表 + 3 个种子学生）。

---

## 四、配置 Web tab

PythonAnywhere → Web → Add a new web app：

1. **Configuration**: Manual configuration（不要选 Flask/Django 预设，它们会覆盖我们的 wsgi.py）
2. **Python version**: 选刚才装虚拟环境用的版本（3.11/3.12/3.13）
3. 点 Next

配置完成后，Web tab 页面会显示：

- **Source code**: `/home/ZYQ/24-2-_242806010229_StudyTask` ← 改成这个目录
- **Working directory**: `/home/ZYQ/24-2-_242806010229_StudyTask` ← 同上
- **Virtualenv**: 选刚才创建的 `campus-event-env`
- **WSGI configuration file**: 点进去编辑，把内容全删掉，粘贴：

```python
# /var/www/zyq_pythonanywhere_com_wsgi.py
import sys, os
from pathlib import Path

CODE_DIR = '/home/ZYQ/24-2-_242806010229_StudyTask'
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

os.environ['CAMPUS_EVENT_DB'] = os.path.join(CODE_DIR, 'campus_event.db')

from wsgi import application
```

**注意**：`application` 变量名不能改，PythonAnywhere 找的就是它。

- 保存 → 回 Web tab → 点 **Reload**

---

## 五、验证

浏览器打开 `https://ZYQ.pythonanywhere.com/health`

预期返回：
```json
{"status":"ok","app":"CampusEvent"}
```

如果 502：点 Web tab 里的 **Error log** 看 traceback。

再试创建一个活动：

```bash
curl -X POST https://ZYQ.pythonanywhere.com/api/admin/activities \
  -H "Content-Type: application/json" \
  -d '{"title":"测试活动","category":"体育","start_at":"2026-12-01T10:00:00","location":"操场","capacity":2,"policy_type":"DIRECT"}'
```

预期 201 + `activity_id`。

---

## 六、常用运维命令

```bash
# 查看错误日志
tail -100 /var/log/zyq_pythonanywhere_com.error.log

# 重新初始化 DB（清空所有数据）
python -c "from project.db import init_db; init_db()"

# 清空表保留结构（测试时用）
python -c "from project.db import reset_db; reset_db()"

# Reload Web 服务（改代码后）
# 不用命令，Web tab 点 Reload 按钮

# 备份数据库
cp /home/ZYQ/24-2-_242806010229_StudyTask/campus_event.db /home/ZYQ/24-2-_242806010229_StudyTask/campus_event.db.bak.$(date +%Y%m%d)

# 查看当前 WSGI 入口是否正确
head -5 /var/www/zyq_pythonanywhere_com_wsgi.py
```

---

## 七、PythonAnywhere 免费版限制

| 项目 | 限制 | 对我们的影响 |
|---|---|---|
| 后台长任务 | 不允许 | 我们是请求-响应模型，无后台任务，没问题 |
| 每分钟请求数 | 较低（~50） | 实验演示级别，够用 |
| CPU/内存 | 单进程、低配额 | SQLite + uvicorn adapter 轻量，够用 |
| IPv6 / 自定义域名 | 免费版不支持 | 用默认的 `ZYQ.pythonanywhere.com` 即可 |
| SSH root | 不允许 | 我们不需要 root，虚拟环境够用 |

**如果 Web tab 没有 ASGI 选项**（PythonAnywhere 老界面），继续用上面 Manual configuration + wsgi.py 的方式就行，完全兼容。

---

## 八、升级代码

以后 git push 新版本后：

```bash
cd /home/ZYQ/24-2-_242806010229_StudyTask
git pull
# 如果 requirements.prod.txt 改了：
pip install -r requirements.prod.txt
# 如果 db schema 改了：
python -c "from project.db import init_db; init_db()"
# 然后 Web tab 点 Reload
```

---

## 九、回滚

```bash
cd /home/ZYQ/24-2-_242806010229_StudyTask
git log --oneline -5           # 找 commit hash
git checkout <hash>             # 回退到指定版本
# Web tab 点 Reload
```

---

## 十、附录：本地已验证的适配器行为

| 场景 | 结果 |
|---|---|
| `GET /health` | ✅ 200 `{"status":"ok","app":"CampusEvent"}` |
| `POST /api/admin/activities`（JSON body） | ✅ 201 + activity_id |
| `POST /api/activities/{id}/registrations` | ✅ 201 + PENDING/APPROVED |
| `DELETE /api/admin/activities/{id}`（有报名） | ✅ 400 DELETE_REJECTED |
| 未捕获异常 | ✅ 兜底 500，不崩服务器 |
| 空 response | ✅ 兜底 502，不崩服务器 |
| Content-Length 为 0 | ✅ 正确处理空 body |

适配器代码在 `asgi_wsgi_adapter.py`，约 130 行，纯 Python，无外部依赖。
