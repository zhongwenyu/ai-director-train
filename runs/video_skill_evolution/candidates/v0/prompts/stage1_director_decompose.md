# Stage 1：戏剧段落分镜规划指南

将输入的 `8.5s–12.5s` 戏剧段落拆分为 `2` 到 `5` 个连续子镜头（`clips`）：
- 每个子镜头时长 `duration_s` 为整数秒（`2` 到 `8` 秒），所有子镜头时长之和紧贴 `target_duration_s`，按正常紧凑语速估算每句台词时长，避免前摇发呆与时长注水。
- 明确标注每个子镜头中实际露面的角色 ID（`visible_role_ids`）与画内开口说话的角色 ID（`speaking_role_ids`）。
- 若某句属于内心独白或画外音（`mode == "inner_os"`），不要放入 `speaking_role_ids`，而是填入该镜头的 `inner_os: {"speaker_id": "...", "text": "...", "start_s": 0.2, "mode": "inner_os"}`。
- `lcut_audio_hold_over_next_s` 默认填 `0.0`（仅当下一个子镜头为无台词听话人反应镜头时，可设 `0.3`–`0.8`）。
