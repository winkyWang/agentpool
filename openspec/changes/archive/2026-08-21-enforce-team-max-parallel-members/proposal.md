## Why

Dynamic Team 配置已经公开 `max_parallel_members`，但运行时只执行 `max_members` 和成员回合数限制。配置因此会向使用方承诺一个实际不存在的并发上限：多个空闲成员可同时被初始 prompt、成员消息或内部通知唤醒，造成模型请求数、资源占用和外部系统压力超过声明值。

## What Changes

- 将 `max_parallel_members` 定义为同一 Team 内正在运行或已经取得启动权的非 Lead Session 数量上限。
- 在 Team 创建时将并发上限固化到 `state.json`，后续 Agent overlay 不能改变 Team 事实。
- 在 `FileTeamState` 的现有 `state.json` 锁内维护运行槽，保证不同 Session 的并发预留不会超额。
- `team_create` 在创建任何成员 Session 前整批验证初始运行数。
- `team_add_member`、发送给空闲成员的消息、广播及内部唤醒在启动新 Run 前预留槽；向已运行成员的 steer 或 queue 不重复占槽。
- Run 完成、取消、启动/发送失败、成员 shutdown、Team delete 与 ephemeral cleanup 释放槽。
- 每次预留和 `team_status` 前依据 `SessionPool` 清理已不存在或已经空闲的陈旧占用。
- `team_status` 展示当前占用数和配置上限，并为容量拒绝和陈旧占用清理增加 telemetry。
- 修复 Team capability 的 Session 可见性：独立 member-eligible Session 不暴露 Team 协议或工具；Lead 在建 Team 前只暴露 `team_create`。
- 在产生任何副作用前拒绝非字符串、重复、空白、带首尾空白或与 Lead 冲突的初始成员名；动态加员以同一状态锁原子 claim 名称与 `max_members` 名额。

## Capabilities

### New Capabilities

- `team-parallel-capacity`：Dynamic Team 非 Lead Session 运行槽的原子预留、释放、对账与可观测性。

## Impact

- 修改 `FileTeamState` 与 `TeamCommCapability`，不新增第二套 Team Manager。
- 修改 Dynamic Team 配置说明、用户文档与 unreleased changelog。
- 增加 Team Mode 单元测试和组件集成测试；不改变普通 Session 与静态 Team 的执行语义。
