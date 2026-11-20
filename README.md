# 东港水产拍卖结算

给水产市场结算员处理双次称重、扣杂计价、结算更正与应付复核。

八个模块：称重采信、货品换算、毛皮配对、扣杂竞价、更正裁决、应付对账、船户归户、结算归档。每个导航页均可重跑同一批数据，隔离行保留编号、原值、行号和原因码。

```sh
docker compose up --build -d
docker compose exec -T app pytest -q
```

浏览器访问 http://localhost:18240 。默认载入现场脏批，包含53条逻辑输入、重复表头、缺列、空值、重复冲突、缺皮重、毛重小于皮重等问题，以及船名与证件尾号可选的归户证据两列。切换“核验清批”或“旧编码批”后重跑。进入“更正裁决”核对票00001：原应付1168.50CNY，更正后1285.35CNY，已付1168.50CNY，仅待付116.85CNY。进入“船户归户”核对现场脏批：13 票并入 9 户可付 15307.39CNY，7 票因同名多证或无证件暂存 8401.52CNY，票级总额 23708.91CNY 与户级总额守恒。

API：各模块 `POST /api/<导航英文名>`；完整运行 `POST /api/runs`，JSON参数可用 `dataset` 或 `csv_text`。查询历史 `GET /api/runs`，复核 `POST /api/runs/{run_id}/review`，传入当前 `revision`。封存下载只有 `GET /api/export/{run_id}` 一个入口。

船户归户：`POST /api/runs/{run_id}/publish` 在一个事务内发布户级结果，`GET /api/runs/{run_id}/publication` 查询发布记录，`GET /api/vouchers` 列原始过磅凭证，`GET /api/vouchers/{sha256}` 下载原始字节。同一证据（run_id/sha256）重发不新增户级行；发布失败整体回滚并保留旧版归属；原始过磅凭证写入后不删除，只增不删。

同输入和规则摘要生成相同批号，不新增重复记录；复核版本改变后旧版本提交返回409。SQLite保存在命名卷。可使用新卷名称重建演示数据，原卷保留。

定义见 `docs/DATA-DICTIONARY.md`，模块与测试映射见 `docs/DEPTH.md`。源码在 `app/`，业务样例在 `sample_data/`，测试在 `tests/`。不连接实际秤台和支付渠道。

采信页支持上传或粘贴CSV。完整源字节与参数随批次持久化，跨页通过run_id读取同一结果。`POST /api/runs/{run_id}/rerun` 读取该批不可变输入快照重新计算，规则未变时批号不变。切换另一示例则创建或复用另一批次。
