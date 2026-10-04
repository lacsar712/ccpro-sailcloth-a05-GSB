# SailCloth-01 · 帆布浸渍防水台

帆布间布卷与浸渍固化台账基线项目（Django 5 + DRF + Vue 3 SPA）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Django 5 · DRF · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端反代 `/api`） |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01`
- **前端**：http://localhost:3740
- **API**：http://localhost:8740
- **PostgreSQL**：localhost:6140

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。后端 entrypoint 执行 migrate + seed。

## 业务规则

- **固化（旧规则照旧）**：布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。标记固化、改卷态均不检查浓度带。
- **树脂浴浓度带**：按帆布间维护树脂百分比区间（`ResinBand`：帆布间、下限百分、上限百分、是否启用、配置人）。下限须小于上限，二者都须为正。同一帆布间启用中的带最多一条（数据库部分唯一索引兜底并发）。
  - 登记浸渍（`POST /api/dips/`）时读取该间现行启用带，树脂百分比必须落在下限与上限之间（**含边界**）；出带或该间无启用带均返回中文 400，浸渍记录不会落库。
  - 仅**管理员**可新建带、改上下限、启停；操作工可登记浸渍但改不了带（写接口 403）。

规则实现：`backend/core/rules.py`

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

- **登录** → 进入主工作面
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`）；点击打开右侧面板登记 `DipRun`（面板显示该间现行浓度带）、切换固化状态；架下为浸渍流水次要信息流
- **`/bands` 树脂浴浓度带（主）**：浓度带列表、新建、改上下限、启停；仅管理员可写，操作工只读
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD，侧栏降级为「台账」入口，非主路径

API：JWT；`/api/lofts|rolls|dips|resin-bands|dashboard/`。

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
