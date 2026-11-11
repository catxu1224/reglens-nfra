# RegLens NFRA

国家金融监督管理总局行政处罚分析页面。Node 服务提供页面和 `/api/penalties`。未配置数据库时，API 从仓库内的种子 CSV 提供只读快照；配置 PostgreSQL 后，API 从数据库读取。页面中的银行、保险、其他、日期及分类筛选基于 API 返回的处罚记录。

## 本地运行

需要 Node.js 20+。只查看当前快照时，无需安装 PostgreSQL：

```powershell
npm ci
npm start
```

打开 <http://localhost:4173>。若要连接 PostgreSQL，在启动前设置 `DATABASE_URL` 并导入种子：

```powershell
$env:DATABASE_URL = 'postgresql://user:password@localhost:5432/reglens'
npm run db:migrate
npm run db:seed
npm start
```

不要提交真实连接串。服务启动时会自动执行尚未应用的 SQL 迁移。`GET /api/health` 报告数据库或种子模式的状态；`GET /api/penalties` 返回前端需要的 20 个业务字段。连接失败时，页面会显示读取错误。

## 数据表和种子数据

- `migrations/001_create_nfra_penalties.sql` 建立 `nfra_penalties` 表及常用查询索引。`source_key` 是逐行唯一键，允许同一处罚书 URL 对应多个当事人。
- `seeds/nfra_penalties.csv` 从 `data/nfra_penalties_3yearsv3.csv` 生成，含 22,054 条记录和原有 20 个业务字段，并增加 `source_key`、`seed_row_number`。日期范围为 2024-01-02 至 2026-11-04。源 CSV 不提交到仓库，种子文件会提交。
- `npm run db:seed -- --check` 只验证种子文件；`npm run db:seed` 将其分批写入数据库。重复导入通过 `source_key` 合并，仅更新内容发生变化的记录，不删除库中其他记录。
- 如果本地源 CSV 更新，执行 `npm run seed:build` 可重新生成种子文件。唯一键由业务字段内容及同内容记录的出现序号生成；重新分类或修正原文会得到新键，需要在增量采集流程中使用更稳定的来源记录 ID 处理更正。

当前种子文件是一次性快照；现有本地采集任务维护另一份 CSV，不会自动同步 PostgreSQL。

## Zeabur 部署

1. 在 Zeabur 新建项目，添加 PostgreSQL 服务，并从 GitHub 仓库 `catxu1224/reglens-nfra` 添加应用服务。仓库根目录的 `Dockerfile` 会安装依赖并启动 Node 服务。
2. 在应用服务变量中设置 `DATABASE_URL`。可引用同项目 PostgreSQL 服务暴露的连接串，例如 `${POSTGRES_CONNECTION_STRING}`，具体变量名以该服务的连接信息为准。Zeabur 会提供 `PORT`，应用会监听该端口。连接数据库前，页面仍可使用种子快照。
3. 首次导入数据时，临时设置 `SEED_ON_START=1` 并重新部署。启动时会执行迁移和种子导入；验证 `/api/health`、`/api/penalties` 和页面条数后，移除该变量，避免每次重启重复扫描种子文件。也可以在具有数据库连接的环境运行 `npm run db:seed`。
4. 后续更新数据时，重新生成种子文件并运行导入脚本。生产数据库应按 Zeabur 的 PostgreSQL 备份配置定期备份。

Zeabur 官方说明：[GitHub 集成](https://zeabur.com/docs/en-US/deploy/methods/github-integration)、[环境变量](https://zeabur.com/docs/en-US/deploy/config/environment-variables)、[PostgreSQL 连接示例](https://zeabur.com/en-US/templates/B20CX0)。

## 页面功能

总览包括处罚条目、金额、机构与个人罚单数、年季月趋势、风险点前 20 词云、省级热力图和风险点 × 机构类型气泡图。处罚明细支持字段模糊搜索及分类筛选。PBOC 和 SAFE 页签目前等待数据接入。
