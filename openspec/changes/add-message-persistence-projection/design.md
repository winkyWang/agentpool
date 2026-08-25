## Context

历史处理器在模型请求前执行，若用于移除二进制会同时阻止当前轮模型读取附件。持久化投影必须位于事件产生之后、`MessageHistory` 写入之前。

## Decisions

- `MemoryConfig.persistence_processors` 使用导入路径声明单参数处理器。
- 处理器接收并返回 `ChatMessage`，因此能够同时投影 `content` 和内部 Pydantic AI `messages`。
- `BaseAgent` 统一执行处理器；RunHandle 和直接运行入口都复用该能力。
- 内置 `project_multimodal_references` 不保存 URL，仅保留媒体类型和安全标识符。

## Non-goals

- 不修改模型请求、协议事件或默认存储行为。
- 不负责附件文件本身的生命周期和权限。

