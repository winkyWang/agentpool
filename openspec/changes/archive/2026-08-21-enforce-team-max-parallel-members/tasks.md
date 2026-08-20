## 1. Specification

- [x] 1.1 定义 `max_parallel_members` 的运行时语义与边界场景。
- [x] 1.2 验证 OpenSpec proposal、design、tasks 与 spec delta。

## 2. Runtime

- [x] 2.1 在 `FileTeamState` 增加原子运行槽预留、释放与查询。
- [x] 2.2 在 `TeamCommCapability` 集中实现 Session 对账、容量消息和完成监听。
- [x] 2.3 对 `team_create`、`team_add_member`、单播、广播和内部通知执行统一容量约束。
- [x] 2.4 在失败、完成、取消、shutdown、delete 和 ephemeral cleanup 路径释放运行槽。
- [x] 2.5 在 `team_status` 展示当前运行数与配置上限，并增加 telemetry。

## 3. Tests and Documentation

- [x] 3.1 增加 FileTeamState 原子容量单元测试。
- [x] 3.2 增加 TeamCommCapability 初始整批拒绝、并发预留、steer 不重复占槽和释放路径测试。
- [x] 3.3 更新 Team Mode 文档、配置说明与 unreleased changelog。

## 4. Verification and Archive

- [x] 4.1 运行 Team Mode 定向测试、unit、integration、Ruff、format check 与 mypy。
- [x] 4.2 将任务勾选为完成并执行 OpenSpec archive。
