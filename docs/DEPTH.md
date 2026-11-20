# 深度登记 水产拍卖结算

规模：中型。使用者：水产批发市场结算员。核心规则：先毛皮配对，再扣杂计价，按更正链选择唯一生效版，只支付差额；船户归户以证件尾号为准，船名仅在唯一对应时临时补证，同名多证不并票、进暂存。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 称重采信 | 查看并执行称重采信 | `POST /api/intake` | `app/modules/intake/rules.py` | `tests/test_intake.py` |
| M2 货品换算 | 查看并执行货品换算 | `POST /api/conversion` | `app/modules/conversion/rules.py` | `tests/test_conversion.py` |
| M3 毛皮配对 | 查看并执行毛皮配对 | `POST /api/pairing` | `app/modules/pairing/rules.py` | `tests/test_pairing.py` |
| M4 扣杂竞价 | 查看并执行扣杂竞价 | `POST /api/auction` | `app/modules/auction/rules.py` | `tests/test_auction.py` |
| M5 更正裁决 | 查看并执行更正裁决 | `POST /api/correction` | `app/modules/correction/rules.py` | `tests/test_correction.py` |
| M6 应付对账 | 查看并执行应付对账 | `POST /api/reconcile` | `app/modules/reconcile/rules.py` | `tests/test_reconcile.py` |
| M7 船户归户 | 查看并入票、未并票与证据，发布户级结算 | `POST /api/attribution` | `app/modules/attribution/rules.py` | `tests/test_attribution.py` |
| M8 结算归档 | 查看并执行结算归档 | `POST /api/archive` | `app/modules/archive/rules.py` | `tests/test_archive.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧编码中文票据 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_legacy_encoding` |
| TRAP-02 | BOM表头 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_bom_real` |
| TRAP-04 | 分段表头 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_repeated_header_real` |
| TRAP-05 | 缺列记录 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_bad_columns_real` |
| TRAP-07 | 空值哨兵 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/conversion/rules.py` | `tests/test_conversion.py::test_sentinel_real` |
| TRAP-08 | 前导零票号 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_leading_zero_real` |
| TRAP-14 | 重复编号不同原值 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_duplicate_conflict_real` |
| TRAP-18 | 三类空态 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_empty_states` |
| TRAP-15 | 吨与千克混合 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/conversion/rules.py` | `tests/test_conversion.py::test_tonnes_counterexample` |
| TRAP-06 | 全角千分位 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/conversion/rules.py` | `tests/test_conversion.py::test_fullwidth_thousands` |
| TRAP-10 | 金额半分舍入 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/auction/rules.py` | `tests/test_auction.py::test_half_cent_rounding` |
| TRAP-26 | 陈旧更正分支 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/correction/rules.py` | `tests/test_correction.py::test_stale_branch` |
| TRAP-31 | 船名与证件尾号指向不同户 | 按船名快速并户，导致错付 | 证件尾号优先；同名多证整票不并，进暂存待核实 | `app/modules/attribution/rules.py` | `tests/test_attribution.py::test_document_tail_wins_over_boat` |
| TRAP-32 | 只有船名、无证件尾号 | 永挂不付，真实船户延误收款 | 船名唯一对应某尾号时临时并入并标 `BOAT_NAME_ALIAS` | `app/modules/attribution/rules.py` | `tests/test_attribution.py::test_boat_name_aliases_unique_document` |
| TRAP-33 | 同票毛皮证据不一致 | 随机取一行归户 | 尾号/船名不一致整票不并，证据行保留 | `app/modules/attribution/rules.py` | `tests/test_attribution.py::test_conflicting_documents_in_same_ticket_hold` |
| TRAP-34 | 归户后金额丢分或重复计票 | 户级和票级对不上 | 户级总额=成交票总额=可付+暂存，唯一分配校验 | `app/modules/attribution/rules.py` | `tests/test_attribution.py::test_attribution_amount_conserved` |
| TRAP-35 | 同证据重跑新增户级行 | 重复发布、重复出账 | 发布以 sha256 幂等，重发返回 `reused` 不写行 | `app/settlement.py` | `tests/test_attribution.py::test_rerun_same_evidence_does_not_add_households` |
| TRAP-36 | 发布中途失败 | 半成品户级结果覆盖旧版 | 单事务发布，异常回滚，旧版归属与凭证不动 | `app/settlement.py` | `tests/test_attribution.py::test_failed_publish_keeps_previous_attribution` |
| TRAP-37 | 重发时误删原始过磅凭证 | 事后无法复核 | 凭证按 sha256 只增不删，失败事务同样回滚 | `app/settlement.py` | `tests/test_attribution.py::test_failed_publish_keeps_previous_attribution` |

## 对账规则

输入=采纳原始行+隔离行+空行+同值重复行+重复表头。计价版本总额与生效票总额分别展示，避免把更正前后重复求和。最终应付=已付+待付，负待付为退款。

## 归户规则

每张生效票收集毛重行与皮重行的船名、证件尾号。证件尾号完整且一致时按尾号归户，即使船名相同也拆户；同票尾号不一致整票不并。无尾号时，船名在该批只对应唯一尾号则临时补证（可付，标临时），对应多个或零个尾号则不并、金额进暂存。票级总额必须等于全部户级（可付+暂存）总额，且每票只出现一次；发布前再次与 `balance.amount` 对齐。发布使用单事务，凭证按源字节 sha256 去重只增不删。

## 已知不覆盖

无称重设备实时接入，采用现场导出文件。无支付执行，只生成可复核结算证据。
