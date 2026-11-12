# RegLens NFRA

国家金融监督管理总局行政处罚分析页面。Node 服务提供页面和 `/api/penalties`。未配置数据库时，API 从仓库内的种子 CSV 提供只读快照；配置 PostgreSQL 后，API 从数据库读取。页面中的银行、保险、其他、日期及分类筛选基于 API 返回的处罚记录。

## 本地运行

需要 Node.js 20+。只查看当前快照时，无需安装 PostgreSQL：

```powershell
npm ci
npm start
```

打开 <http://localhost:4173>。若要连接 PostgreSQL，在启动前设置 `DATABASE_URL`：

```powershell
$env:DATABASE_URL = 'postgresql://user:password@localhost:5432/reglens'
npm run db:migrate
npm start
```

不要提交真实连接串。服务启动时会自动执行尚未应用的 SQL 迁移。`GET /api/health` 报告数据库或种子模式的状态；`GET /api/penalties` 返回前端需要的 20 个业务字段。连接失败时，页面会显示读取错误。

## 数据表和种子数据

- `migrations/001_create_nfra_penalties.sql` 建立 `nfra_penalties` 表及常用查询索引。`source_key` 是逐行唯一键，允许同一处罚书 URL 对应多个当事人。
- `seeds/nfra_penalties.csv` 从 `data/nfra_penalties_3yearsv3.csv` 生成，含 22,054 条记录和原有 20 个业务字段，并增加 `source_key`、`seed_row_number`。日期范围为 2024-01-02 至 2026-11-04。源 CSV 不提交到仓库，种子文件会提交。
- `seeds/nfra_penalties_incremental.csv` 保存官网 2026-11-05 起的增量记录；首次补录至 2026-11-12，27 篇公告对应 121 条机构或个人记录。与历史快照合计 22,175 条。
- `npm run db:seed -- --check` 验证两份种子文件；`npm run db:seed` 分批导入。增量记录以官网公告 ID、表格序号和处罚对象类型生成稳定键；更新时按键覆盖，并清理已从增量种子撤回的记录。`nfra_seed_imports` 记录版本校验和，未变化时跳过导入。
- 如果本地源 CSV 更新，执行 `npm run seed:build` 可重新生成种子文件。唯一键由业务字段内容及同内容记录的出现序号生成；重新分类或修正原文会得到新键，需要在增量采集流程中使用更稳定的来源记录 ID 处理更正。

## 官网增量更新

`.github/workflows/nfra-update.yml` 每天北京时间 09:00 运行，也支持在 GitHub Actions 中手动触发。同一时间只允许一个更新任务。程序读取总局目录 4113、派出机构目录 4293，以及仍持续发布公告的旧派出机构目录 4115；按公告 ID 去重，逐篇复查正文。平日回扫最近 30 天，每月 1 日回扫自 2026-11-05 起的增量历史。

本地手动更新：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-nfra.txt
.venv\Scripts\python scripts/nfra_incremental.py
npm run db:seed -- --check
```

官网请求失败、正文无法解析或出现重复键时，程序报错且不写入增量种子。GitHub Actions 会显示失败，避免把缺口当作完整数据；若 GitHub 的出口地址被官网限制，需要在可访问官网的环境手动运行和核验。分类沿用存量采集规则，并以公告原文拆分机构与个人处罚；未有明确依据的处罚金额保留空值。

## Railway 部署

1. 从 GitHub 仓库 `catxu1224/reglens-nfra` 拉取最新 `main` 部署应用；根目录 `Dockerfile` 会安装 Node 依赖并运行 `npm start`。
2. 在同一 Railway 项目中添加 PostgreSQL 服务。在应用服务的 Variables 中设置 `DATABASE_URL=${{Postgres.DATABASE_URL}}`；若数据库服务名称不是 `Postgres`，将引用中的名称改为实际服务名。确认 `SEED_ON_START` 未设置为 `0`，也可显式设为 `1`。不要把生产连接串提交到 GitHub。
3. 部署启动时先执行 `migrations/001_create_nfra_penalties.sql`、`002_track_seed_import.sql`，再导入历史和增量两份种子文件。第一次导入约 22,175 条；后续部署只在种子校验和变化时写库。用 `/api/health` 确认数据库连接状态为 `ok`，再用 `/api/penalties` 确认 `source` 为 `postgresql` 且 `count` 至少为 22,175。
4. GitHub 定时任务提交新的增量种子后，重新部署最新提交即可同步生产库；若应用已开启 GitHub 自动部署，部署会自动发生。数据库里的非种子记录不会被增量导入删除。

Railway 变量与 PostgreSQL 连接方式见[官方 PostgreSQL 文档](https://docs.railway.com/databases/postgresql)和[变量引用说明](https://docs.railway.com/variables/reference)。

## 页面功能

总览包括处罚条目、金额、机构与个人罚单数、年季月趋势、风险点前 20 词云、省级热力图和风险点 × 机构类型气泡图。处罚明细支持字段模糊搜索及分类筛选。PBOC 和 SAFE 页签目前等待数据接入。

### 智能报告

在筛选栏选择年、季、月及其他条件，点击“模型设置”选择 DeepSeek 或千问（阿里云百炼），填写模型名称和对应 API Key，再点击“智能报告生成”。DeepSeek 默认 `deepseek-flash`；千问默认 `qwen-plus`，并可选择 API Key 所属的北京、新加坡或美国地域。报告按当前筛选的 NFRA 记录生成地区、处罚对象、机构类型、合规风险点图表，展示金额最高的十条处罚记录、法规引用与模型分析。点击“保存为 PDF”，在浏览器打印对话框选择 PDF。每次重新生成都会调用模型，可能产生 API 费用。

API Key 仅保存在当前页面内存，刷新后需重新填写；每次生成经本站 `/api/report-insights` 转发给所选服务商的 Chat Completions API，服务端不保存 Key。发送给模型的是汇总统计、法规依据摘录及匿名化处罚事实，图表数字和十大处罚记录在浏览器本地计算。法规适用观察需通过原处罚书和现行法规核对。服务端只允许 DeepSeek 和阿里云百炼的固定 API 地址，不接受任意自定义服务端点。地域须与千问 API Key 一致。

接口依据：[DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)、[阿里云百炼 OpenAI 兼容接口与地域](https://help.aliyun.com/zh/model-studio/base-url)、[千问结构化输出](https://help.aliyun.com/zh/model-studio/qwen-structured-output)。

本机可执行 `npm test` 检查统计与接口逻辑，执行 `npm run test:browser` 用模拟模型响应检查筛选、报告页面及打印样式；浏览器检查需要本机安装 Chrome。
