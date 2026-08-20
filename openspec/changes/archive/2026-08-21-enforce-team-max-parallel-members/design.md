## Context

`TeamModeBounds.max_parallel_members` 已完成配置校验，但所有成员启动仍直接调用 `SessionPool.send_message()`。`SessionPool` 能可靠表达 Session 是否存在及是否有 `current_run_id`，`FileTeamState` 已用 `state.lock` 保护 `state.json` 的读改写。因此容量约束应落在两者的交界处：SessionPool 提供实时运行事实，FileTeamState 提供跨 Capability 实例的原子预留。

## Goals / Non-Goals

**目标：**

- 所有由 TeamComm 工具与内部通知管理的并发唤醒都不能让同一 Team 的非 Lead 活跃 Run 数超过配置值。
- 向已经活跃的成员发送 steer/queue 不重复占槽。
- 所有终止与失败路径都能释放，陈旧记录可以从 Session 真值对账清理。
- 初始 Team 创建保持整批语义：超限时零 Session 被创建。

**非目标：**

- 不限制 Lead 自身 Run。
- 不改变 `max_members`、`max_member_turns` 或全局 SessionPool 容量语义。
- 不创建调度器、等待队列、业务状态机或第二套 Team 状态服务。

## Decisions

### D1：运行槽属于 Team 持久化状态

`state.json` 新增不可由成员覆盖的 `max_parallel_members` Team 事实和 `active_run_slots` 映射。槽位键为成员名，值记录 `session_id`、当前 `run_id` 与 `pending_reservations`。每个 pending reservation 以 `reservation_id` 绑定 `reserved_at`，允许活跃成员并发接收多个新投递而不丢失“发送尚未建立新 Run”的事实。所有预留、投递确认和释放都在现有 `state.lock` 内完成，原子 API 只读取 Team state 中的上限，不能接受调用方上限参数。该映射是运行协调元数据，不是业务事实；Team 删除时随协调状态一起清理。绕过 TeamComm、直接操作底层 SessionPool 的宿主扩展不属于本变更支持的投递入口。

### D2：SessionPool 是对账真值

`FileTeamState` 在持有 `state.lock` 且读取最新 roster 后，通过同步 resolver 从 `SessionPool` 解析当前非 Lead Session；禁止在锁外生成可能遗漏刚注册成员的快照。占用记录仅在 Session 不存在或 closing，或者 Session 已空闲且没有 pending reservation 时清理。`TeamCommCapability` 是 per-session 实例，实例内的异步锁不能保护不同成员并发，因此“预留后发送前”的临界区必须由持久化 reservation 集合表达，不能依赖进程内 Capability 锁。

空闲成员已经存在未确认 reservation 时，第二个并发唤醒返回“activation in progress”，不能共享 token。活跃成员的后续 steer/queue 会向原槽的 pending 集合增加独立 token。旧 Run 即使在新发送建立 Run 前结束，对账也会因 pending 集合非空而保留槽，因此不能发生旧 Run 清除新 Run 槽的 ABA（先删除再新增）竞态。发送异常或取消由 `finally` 精确移除自身 token；进程终止后的记录由 Session 不存在事实清理，不使用可能误删活跃发送的纯时间超时。

### D3：先预留，再发送，失败即释放

所有非 Lead 成员投递都先在文件锁内取得该成员的 token。发送成功后 RunHandle 已由 `SessionController._route_message()` 同步建立并写入 `current_run_id`，调用方用 reservation token 确认投递并绑定当前 Run；发送失败则 compare-token 释放。向已有 `current_run_id` 的成员换发 token 但复用同一槽，不增加容量计数。

### D4：完成释放由事件驱动清理承担

每次新预留都会启动一个有 Logfire span 的轻量完成监听器。监听当前 RunHandle 的 `complete_event`，处理 chained run 后，在成员真正空闲时释放槽。shutdown、delete、ephemeral cleanup 和发送失败仍显式释放，保证异常路径幂等。

### D5：广播逐成员执行同一容量规则

广播不是绕过容量的特殊路径。已活跃成员直接接收；空闲成员逐个竞争剩余槽位。结果报告成功与因容量未唤醒的数量，避免把部分投递伪装成全量成功。

### D6：Roster identity 在产生副作用前闭合

成员 display name 是 `members` 与 `active_run_slots` 的共同键。`team_create` 在创建目录和 Session 前整批拒绝非字符串、空白、带首尾空白、重复以及与 Lead member name 冲突的名称，禁止字典投影折叠两个运行中的 Session。`team_add_member` 可在原子 claim 前创建未激活 Session，但名称查重、`max_members` 名额和 roster 写入必须在同一个 `state.lock` 临界区完成；claim 失败时关闭尚未激活的 Session。初始激活绑定 claim 得到的 exact Session ID，add 回滚、shutdown 与 ephemeral cleanup 都执行 compare-and-remove，禁止旧调用删除同名替代者。成员 shutdown 即使遇到 Session 关闭异常，也必须删除自己的 roster 与槽位并返回明确的部分失败信息。

## Risks / Trade-offs

- File lock 是同步 I/O；其临界区只包含小型 JSON 读改写和内存 Session 快照判断，不包含 await 或模型调用。
- 进程异常退出会留下槽记录；下一次预留和 `team_status` 都会依据 SessionPool 对账清理。
- 多进程共享同一 Team 目录时，各进程的 SessionPool 只能看到本进程 Session。当前 Dynamic Team Session 由同一 Host 管理；跨 Host Team 不在支持范围内。
