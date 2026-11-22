# Stage 1：戏剧段落分镜规划指南

将输入的 `8.5s–12.5s` 戏剧段落拆分为 `1` 到 `4` 个连续子镜头（`clips`）：
- 每个子镜头时长 `duration_s` 为整数秒（`2` 到 `12` 秒），所有子镜头总时长与目标段落时长相近，保证每句台词都有充足时间说完。
- 明确标注每个子镜头中实际露面的角色 ID（`visible_role_ids`）与开口说话的角色 ID（`speaking_role_ids`）。
- 若某句属于内心独白（`mode == "inner_os"`），不要放入 `speaking_role_ids`，而是填入该镜头的 `inner_os: {"speaker_id": "...", "text": "...", "start_s": 0.3}`。
- `lcut_audio_hold_over_next_s` 默认填 `0.0`（如需声画交叠可设 `0.0`–`1.2`）。
