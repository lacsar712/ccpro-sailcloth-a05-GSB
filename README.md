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

布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。

按帆布间维护**树脂浴浓度带**（`ResinBand`：帆布间、下限百分、上限百分、是否启用、配置人）：

- 登记浸渍时，树脂百分比必须落在该间**现行启用带**的上下限之间（含边界）；出带或该间无启用带，均以中文错误挡住，且不产生半插入记录。
- 同一帆布间启用中的浓度带**最多一条**（数据库部分唯一约束兜底，并发启停也只留一版）。
- 下限必须小于上限，二者都须为正。
- 仅管理员可新建/改上下限/启停浓度带；操作工可登记浸渍但改不了带。
- 标「已固化」与改卷态不看浓度带；固化时长 ≥ 12 小时的旧规则照旧。

规则实现：`backend/core/rules.py`

种子数据：帆布间「北岸帆布间」+ 启用中浓度带 20%–30%（配置人 admin）+ 架上原布一卷（R-01）。

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

- **登录** → 进入主工作面
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`）；点击打开右侧面板登记 `DipRun`（面板显示该间启用浓度带，出带中文挡住）、切换固化状态；架下为浸渍流水次要信息流
- **`/bands` 树脂浴浓度带**：列表、新建、启停、改上下限；写操作仅管理员，操作工只读
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD，侧栏降级为「台账」入口，非主路径

API 契约不变（JWT、`/api/lofts|rolls|dips|bands|dashboard/`）。

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
