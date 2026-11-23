# Stage 2：空间站位母版与子镜头首帧图提示词指南 (`master_blocking_prompt` & `keyframe_prompt`)

所有首帧图像提示词均使用**纯英文**编写，画面必须纯净无任何文字、字幕、边框或水印。

## 1. `master_blocking_prompt`（全场空间拓扑母版图，英文）
- **标准引用符**：使用 `[Scene]` 指代输入环境空镜基准，使用 `[CHR_1]`、`[CHR_2]` 等指代在场角色标准设定图。
- **锁死相对拓扑与唯一 180° 轴线**：
  - 严格还原 `initial_blocking` 定义的左右同侧、相对落座或站立位置、身体朝向夹角、共享台面/器物方位，以及每位角色身后的标志性 `[Scene]` 建筑陈设结构。
  - 明确建立全场唯一且不可逾越的 **180° 视线主轴线（primary 180-degree eyeline axis）** 及摄影机所处轴线同侧机位区（camera stays strictly on one side of the axis）。
- **母版光学与骨相保真**：采用平视自然透视中全景构图（`natural eye-level 35mm-50mm cinematic master shot`），实拍级主辅光比与空间纵深层次清晰；严格还原各 `[CHR_k]` 设定的真实年龄感、面部骨相轮廓与时代服饰细节，全员处于自然沉静的戏剧在场态。

## 2. `keyframe_prompt`（各子镜头静态起幅首帧，英文）
- **严守 180° 轴线、互补视线与跨镜陈设连续**：
  - 严格继承母版的空间方位与摄影机侧：对谈双方正反打切换必须呈现**互补银幕落位与互补视线矢量**（如一方位于画面略偏左、视线朝镜头右侧微偏，则另一方必位于画面略偏右、视线朝镜头左侧微偏），严禁 180° 越轴导致视线同向或背景左右翻转。
  - 持续锚定前景遮挡层与环境几何结构：带过肩关系（`Over-the-shoulder`）或前景层次时，显式写出前景虚化的对谈者肩侧轮廓及固定台面器物；各自背景中的 `[Scene]` 门窗、墙面或器物位置须跨镜恒定，杜绝陈设凭空消失、错位或广角几何分裂畸变。
- **贴视线近正脸大光圈浅景深构图（核心主导准则）**：
  - 说话、心声与反应镜头优先采用**贴近视线轴线（偏离镜头正轴 `10°–20°` 的近正脸视角，`near-frontal 10-to-20-degree angle hugging the eyeline axis`）** 的 `Medium close-up`、`Close-up` 或紧凑 `Over-the-shoulder`（`Medium shot` 仅限空间重锚定或大幅肢体器物交互），摒弃呆板正侧脸（flat 90-degree profile）与疏离远景，确保角色**双眼完整入画**。
  - 显式声明人像定焦浅景深与面部受光：`captured on 85mm portrait prime lens at f/2.0 shallow depth of field, soft sculpted key light on the face, crisp dual catchlights in both eyes, creamy background bokeh separating the subject cleanly from [Scene]`。
- **自然舒展起幅神态与真实年龄骨相保护**：
  - 首帧定格 `0.00s` 蓄势瞬间：**五官肌群必须自然舒展、皮肤质感与骨相紧致贴合 `[CHR_k]` 原始年龄设定**；严禁写入极端皱眉、深沟纹路、面颊凹陷、张大嘴定格或狰狞扭曲等会导致人物显苍老或生硬伪影的描述词。
  - 双唇保持自然轻合或微启待发（`lips gently closed or poised to part`），将 `subtext_intent` 凝练为清澈且富有潜台词张力的起幅眼神焦点。
- **手部触点与器物状态跨镜继承**：
  - 若手部或关键器物入画，写出符合时代与场景逻辑的自然静态支点（如指尖轻搭台面边缘、扶手、衣袖或器物外壁），并严格对齐上一子镜头末尾的手部位置、器物摆放及衣饰状态。
