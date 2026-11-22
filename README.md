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

`.github/workflows/nfra-update.yml` 每天北京时间 09:00 运行，也支持在 GitHub Actions 中手动触发。同一时间只允许一个更新任务。列表、正文、备用站、重试及附件下载的请求统一至少间隔 60 秒；定时任务超时设为 360 分钟。程序读取总局目录 4113、派出机构目录 4293，以及仍持续发布公告的旧派出机构目录 4115；按公告 ID 去重，逐篇复查正文。平日回扫最近 30 天，每月 1 日回扫自 2026-11-05 起的增量历史。

本地手动更新：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-nfra.txt
.venv\Scripts\python scripts/nfra_incremental.py
npm run db:seed -- --check
```

正文无可解析处罚表格时，程序自动下载 DOCX、DOC、PDF 附件并使用同一套字段映射和分类流程；同名不同格式按 DOCX、DOC、PDF 顺序回退，避免重复计数。旧版 DOC 需要安装 LibreOffice Writer（`soffice` 在 PATH 中，或设置 `SOFFICE_PATH`）；GitHub Actions 已自动安装。扫描型 PDF 暂不支持 OCR，解析失败仍会阻止写入，避免漏单。

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


## PBOC 总行处罚

PBOC 页签复用 NFRA 的总览、筛选、趋势、地图、明细和报告版式，接口为 `/api/penalties?regulator=pboc`。数据范围仅为人民银行官网总行行政处罚公示目录，按公告发布时间自 2024-01-01 起采集，不代表已覆盖各地分支机构的独立目录。首次采集 48 篇公告、298 条机构或个人记录，最新公告发布日期为 2026-10-16。

官网字段经映射可复用现有 20 个业务字段，但不能完全无损地只用该表头：

| 人民银行字段 | 共用字段或存档位置 |
| --- | --- |
| 当事人名称 | 被处罚单位（公司）/分行/个人，经原有分类流程拆分 |
| 行政处罚决定书文号 | 文号 |
| 违法行为类型 | 违法违规事实 |
| 行政处罚内容 | 处罚决定；罚款金额、处罚类型按共用规则提取 |
| 作出行政处罚决定机关名称 | 处罚机关、机关 |
| 公告发布日期 | 发布时间，区别于决定日期 |
| 决定日期、公示期限、备注 | `seeds/pboc_notice_fields.json` 原文存档 |
| 处罚依据 | 原表未提供时留空，不从违法事实推测 |

`seeds/pboc_penalties.csv` 使用与 NFRA 相同的业务表头和两项技术字段；唯一键使用独立 PBOC 前缀及公告 URL、文号、当事人和处罚对象类别。同一张表被网站拆成多个 HTML 表格时保持表头连续；正文无表格时读取 DOCX/DOC/PDF 附件。扫描型 PDF 仍需 OCR，无法解析会报错并保留既有种子。原始网页缓存在 `work/pboc/`，失败清单写入 `issues.json`。

```bash
python scripts/pboc_incremental.py --since 2024-01-01
node scripts/seed.mjs --regulator=pboc --check
node scripts/seed.mjs --regulator=pboc
```

`004_pboc_penalties.sql` 建立独立 `pboc_penalties` 表。设置 `DATABASE_URL` 后，应用启动在 `SEED_ON_START` 不为 `0` 时依次导入 NFRA、PBOC；按独立校验和跳过未变化文件，按唯一键更新，清理已从 PBOC 种子移除的记录。未配置数据库时，PBOC 接口使用独立种子快照。实际生产导入必须部署新版本并配置 Railway PostgreSQL 服务引用。

`.github/workflows/pboc-update.yml` 每天北京时间 09:30 执行，通常回扫最近 30 天，每月 1 日全量回扫 2024 年起公告；网络请求间隔 60 秒，超时 360 分钟。没有新公告时正常结束；解析失败时不会提交不完整数据。种子提交触发 Railway 已配置的 GitHub 自动部署后，启动程序将自动导入数据库；若未启用自动部署，需要手动部署最新提交。


### 分支机构扩展与历史补采

以人民银行官方分支机构名录（`https://www.pbc.gov.cn/rmyh/105226/105442/index.html`）为准，当前识别到 36 个不同域名。上海总部与上海市分行共用域名，不重复登记。`config/pboc_branches.json` 保留来源、站点、发现的处罚目录及核验状态。目录未找到、页面无法解析或遭遇 403 时会明确记入失败，不能将站点名录视为已完成数据覆盖。

```bash
python scripts/pboc_branches.py --max-requests 280 --max-minutes 280 --retry-failed
```

`pboc_branches.py` 从各站点首页沿“政务公开 / 政府信息公开 / 行政执法”查找处罚目录，兼容旧版表格列表、日期列和下一页链接；从 2024-01-01 起翻页补采。正文可解析时直接取表格，否则尝试 DOCX、DOC、WPS、RTF、XLSX、XLS 和 PDF 附件。旧版 Word/WPS/RTF 转换使用 LibreOffice。扫描图片或不能可靠读取的附件会列入失败清单，等待复核，不会记为已采集。公告来源、处罚机关和决定日期按原文保留。

所有域名、正文、附件、重试和 HTTP 跳转统一经过 `pboc_http.Client`：物理请求至少间隔 60 秒，进度保存在共享时钟文件中，进程重启也不重置限速。403/429 立即停止当前批次；禁止通过 `--interval` 调低间隔。请避免本地任务与云端任务同时采集，以保持跨执行环境的低请求频率。

`seeds/pboc_crawl_state.json` 保存待处理任务、已解析公告、失败原因及逐站覆盖进度。每篇公告解析、分类、去重成功后更新种子并写入检查点。达到请求/时间预算时正常暂停，下一批续采；目录状态 verified 只表示目录已核验，不能等同于历史数据已采完。`historyComplete`、待处理和失败数量用于判断覆盖。网页原文和附件缓存于 `work/pboc/branches/`。

跨网址转载的同一文号、当事人和处罚对象，通过事实、处罚决定和金额核对，避免重复计数；存在冲突时转为失败待复核。原有总行及已采集分行数据均保留，未完成的分行不会导致已采数据被删除。

每日 09:30 的 PBOC GitHub 工作流先回扫总行，再以 280 次请求 / 280 分钟预算推进分行历史任务，并刷新近期公告。缓存与检查点保留到下一次运行；成功采集的记录会发布，失败任务仍使运行明确报错。首次补采会跨多次运行，请以覆盖进度为准。部署启动的 PostgreSQL 导入使用同一 PBOC 种子文件，因此总行和分行共用 PBOC 页面及独立数据库表。


### 连续补齐及全量种子验收

历史补采使用 `workflow_dispatch` 的 `mode=backfill`。每批最多 90 次请求、100 分钟，结束后有待处理任务就自动排入下一批，保留同一个请求时钟；遇到 403/429 当天停止接力。每日 09:30 任务仍保留，用于恢复暂停任务及后续新增公告。解析失败的公告不会标记完成，也不会导致同一天反复抓取同一失败来源。

`pboc_validate_complete.py` 只在官方 36 个分行目录全部核验、历史任务清空、失败归零、记录范围和跨源去重校验通过后，生成 `seeds/pboc_complete_history.json`。清单包含每个分行的记录数、检查日期及统一种子文件 SHA-256；没有清单不能将当前数据称为全量覆盖。

最终仍使用同一个 `seeds/pboc_penalties.csv`（总行加分行），导入同一个 PostgreSQL `pboc_penalties` 表。需要严格验收全量快照时使用：

```bash
python scripts/pboc_validate_complete.py
node scripts/seed.mjs --regulator=pboc --require-complete --check
node scripts/seed.mjs --regulator=pboc --require-complete
```

`--require-complete` 会在数据库写入之前核对 36 分行完成证明、条数和校验和，拒绝没有完成证明或不匹配的种子。
