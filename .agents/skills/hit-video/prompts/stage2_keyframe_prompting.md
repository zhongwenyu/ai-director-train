# Stage 2：空间站位母版与子镜头首帧图提示词指南 (`master_blocking_prompt` & `keyframe_prompt`)

1. **`master_blocking_prompt`（全场空间座位母版图，英文）**：
   - 使用 `[Scene]` 指代场景空镜，使用 `[CHR_1]`、`[CHR_2]` 等指代在场角色标准图。
   - 严格还原 `initial_blocking` 中的左右同侧、对面落座或站位拓扑与朝向关系，建立全场唯一的 180° 视线轴线，自然实拍光影，零文字零水印。
2. **`keyframe_prompt`（各子镜头起幅首帧，英文）**：
   - 继承空间母版的座位方位与视线方向，描述子镜头景别（`Medium shot`、`Medium close-up`、`Close-up`、`Over-the-shoulder`）、机位角度及开场自然神态，画面干净无字幕。
