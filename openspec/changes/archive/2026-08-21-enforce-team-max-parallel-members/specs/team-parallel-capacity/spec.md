## ADDED Requirements

### Requirement: Dynamic Team 必须执行非 Lead 并发上限

运行时 SHALL 将 `max_parallel_members` 解释为同一 Team 内正在运行或已取得启动权的非 Lead Session 数量上限。Lead Session 不计入该数量。所有 TeamComm 工具投递与 TeamComm 内部通知 SHALL 服从该限制。

#### Scenario: Agent 配置 overlay 不一致

- **WHEN** Lead 以较小并发上限创建 Team，而成员 Session 的配置 overlay 声明更大上限
- **THEN** 所有成员仍使用 Team 创建时持久化的上限
- **AND** 成员配置不能覆盖该 Team 事实

#### Scenario: 初始成员超过并发上限

- **WHEN** Lead 调用 `team_create`，初始成员数量大于 `max_parallel_members`
- **THEN** 调用返回容量错误
- **AND** 不创建 Team state 或任何成员 Session

#### Scenario: 初始 roster identity 冲突

- **WHEN** 初始成员名不是字符串、为空、带首尾空白、重复或与 Lead member name 相同
- **THEN** 调用返回 roster identity 错误
- **AND** 不创建 Team state 或任何成员 Session

#### Scenario: 并发动态加员原子 claim roster

- **WHEN** 两个 `team_add_member` 调用并发尝试占用相同 display name，或并发尝试占用最后一个 `max_members` 名额
- **THEN** 名称查重、成员数量检查与 roster 写入在同一个 Team 状态锁内完成
- **AND** 仅一个调用成功，失败调用关闭尚未激活的 Session
- **AND** 不得存在未计入 roster 或运行槽的活跃成员 Session

#### Scenario: 迟到清理不能删除同名替代者

- **WHEN** 旧成员激活或清理仍在进行，而该 roster identity 已被新 Session 重新 claim
- **THEN** 旧激活不得把初始消息投递给新 Session
- **AND** 旧回滚、shutdown 或 ephemeral cleanup 只能 compare-and-remove 自己的 exact Session ID
- **AND** 新 Session 的 roster 与运行槽保持不变

#### Scenario: 并发唤醒空闲成员

- **WHEN** 多个调用并发向不同空闲成员发送会启动 Run 的消息
- **THEN** 只有不超过剩余容量的调用能原子取得运行槽
- **AND** 其他调用返回明确容量错误且不启动目标成员 Run

#### Scenario: 同一成员并发投递

- **WHEN** 不同 Team Session 同时向同一个成员投递消息
- **THEN** 第一个空闲成员唤醒持有可原子确认的 reservation token
- **AND** 第二个唤醒在首个 token 尚未绑定 Run 时返回 activation-in-progress
- **AND** 该成员只计算为一个运行槽

#### Scenario: 向活跃成员发送消息

- **WHEN** 目标成员已经持有运行槽且 Session 有活跃 Run
- **THEN** steer 或 queue 消息正常投递
- **AND** 不新增运行槽占用

### Requirement: 运行槽必须在所有终止路径释放

运行槽 SHALL 在 Run 完成、失败、取消、Session 创建或消息发送失败、成员 shutdown、Team delete 和 ephemeral cleanup 后幂等释放。

#### Scenario: Run 正常完成

- **WHEN** 持槽成员的最后一个 chained Run 完成且 Session 进入 idle
- **THEN** 对应运行槽被释放
- **AND** 后续空闲成员可以取得该容量

#### Scenario: 占用记录陈旧

- **WHEN** 占用记录指向不存在、closing 或已经 idle 的 Session
- **THEN** 下一次容量预留或 `team_status` 查询会清理该记录
- **AND** 清理动作产生 telemetry 事件

#### Scenario: 活跃成员旧 Run 在新投递期间结束

- **WHEN** 活跃成员已取得一个新投递 reservation，但旧 Run 在新消息建立 Run 前结束
- **THEN** 对账保留该成员运行槽直到该 reservation 完成或取消
- **AND** 其他空闲成员不能在该窗口取得同一容量

#### Scenario: shutdown 的 Session 关闭失败

- **WHEN** Lead shutdown 成员时底层 Session 关闭抛出异常
- **THEN** roster 与对应运行槽仍被清理
- **AND** 工具结果明确报告 Session 关闭失败

### Requirement: Team 状态必须报告并发使用量

`team_status` SHALL 报告当前有效非 Lead 运行槽数量与 `max_parallel_members` 上限。

#### Scenario: 查询 Team 状态

- **WHEN** Team 成员调用 `team_status`
- **THEN** 返回结果包含 `active/max_parallel_members` 容量信息
- **AND** 数量来自对 SessionPool 对账后的 Team state

### Requirement: Team capability 必须按 Session 所属关系暴露

Team member 工具和协议 SHALL 只对带有 `team_id` 的成员 Session 可见。Lead Session 在创建 Team 前 SHALL 只获得 `team_create`。

#### Scenario: member-eligible Agent 独立运行

- **WHEN** 一个配置为 `member_eligible` 的 Agent 以不带 `team_id` 的独立 Session 运行
- **THEN** 不注入 Team 协议说明
- **AND** 不暴露 Team 工具

#### Scenario: Lead 尚未创建 Team

- **WHEN** Lead Session 尚不包含 `team_id`
- **THEN** 只暴露 `team_create`
- **AND** 创建成功后才暴露其余 Team 工具

#### Scenario: Lead 删除 Team

- **WHEN** Lead 成功删除当前 Team
- **THEN** Session metadata 中的 Team 归属被清除
- **AND** Lead 再次只看到 `team_create`
