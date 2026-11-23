# Stage 2：空间站位母版与子镜头首帧图提示词指南 (`master_blocking_prompt` & `keyframe_prompt`)

所有首帧提示词均用**纯英文**编写，通过标准引用标记锁定人物外观、三维空间透视与跨镜接戏连续性。

## 1. `master_blocking_prompt`（全场空间站位母版图，英文）
母版图用于一次性确立整场戏的物理空间坐标系、全员相对拓扑与统一光源方向，供所有子镜头严格继承：
- **标准实体标记**：使用 `[Scene]` 指代输入场景环境设定，使用 `[CHR_1]`、`[CHR_2]` 等精确指代在场全部角色标准设定图（严禁自造英文人名替代标记）。
- **三维拓扑与坐立高度锁定**：严格依据 `initial_blocking`，明确写出每位角色的空间方位（如左右同侧并排、隔空或隔物正对、斜对角站坐组合）、各自姿态高度（明确标注 `seated` 或 `standing`）、身体朝向与视线交互关系，以及核心道具与角色的精确空间归属。
- **180° 安全轴线与实拍光影**：采用客观全景或中全景（`Wide establishing shot` / `Full medium-wide shot`）确立贯穿全场的唯一 **180° 摄影机安全轴线**；锁定主光源方位、冷暖色温与真实光学阴影层次（`natural live-action cinematography, realistic spatial depth`），严禁超现实冗余建筑结构、畸变透视、文字字幕或水印。

## 2. `keyframe_prompt`（各子镜头静态起幅首帧，英文）
每个子镜头的首帧定格该镜第 `0.0s` 的起始瞬间，必须与母版拓扑、相邻镜头状态及本镜 `visible_role_ids` 严密一致：
- **可见角色标记精确对齐**：`keyframe_prompt` 中只能引用 `[Scene]` 及本镜头 `visible_role_ids` 内实际入画的 `[CHR_k]` 标记！纯净单人镜头严禁在文本中写入画外角色的 `[CHR_x]` 标记（画外视线直接写方向如 `gazing intently off-frame right`），防止图像模型误把画外角色塞入单人画面；过肩镜头（OTS）与双人镜头（Two-shot）则准确引用同时入画的双方标记。
- **严守 180° 轴线与正反打视线配对（Eyeline Match）**：
  - 机位始终停留在母版 180° 轴线同一侧，严禁越轴导致人物左右位置颠倒。
  - 正反打切镜严格保持左右留白与视线互补：若母版中甲在左、乙在右，则拍甲时构图偏左、视线朝画面右方（`positioned left of center, looking off-frame right`）；反打拍乙时构图偏右、视线朝画面左方（`positioned right of center, looking off-frame left`），确保切镜视线精准交汇。
- **三层光学景深与跨镜背景地标一致**：
  - 明确写出景别与平视/贴合坐立差别的机位角度：`Medium shot`、`Medium close-up`、`Close-up`、`Over-the-shoulder shot` 或 `Two-shot`。
  - 构建完整的**前景—中景—背景**三层光学空间：
    1. **前景层（Foreground）**：过肩镜头明确描述前景边缘虚化的对手肩颈侧影（如 `framed over the softly blurred right shoulder of [CHR_2] in the foreground`）并保持左右遮挡边一致；单人镜头可利用真实环境前景边缘营造自然浅景深。
    2. **中景主体层（Midground）**：清晰对焦于被摄主体 `[CHR_k]` 的衣着质感、姿态与朝向。
    3. **背景透视层（Background）**：写出 `[Scene]` 在该机位朝向下对应的固定背景建筑/门窗/陈设透视地标与景深虚化光斑；同一机位复切时背景结构必须前后一致，严禁背景凭空消失、突变或生成多手多肢伪影。
- **跨镜姿态与受光接戏连续性**：相邻镜头切换时，同一角色的坐立高度、身体倾角、手部与随身器物接触状态及面部主受光侧必须顺滑衔接，杜绝跨镜站坐瞬移。
- **干净自然的静态起幅基底（零半张嘴扭曲）**：
  - 首帧仅捕捉切镜开启瞬间的自然准备神态（如专注倾听、温和含笑初态、微怔注视等贴合当刻情境的清晰起势）。
  - **唇部静态平衡铁律**：无论该镜后续是否开口说话，首帧静态图中角色双唇必须处于**自然闭合或放松微合的静态平衡态**（`lips naturally closed in a clean, unwarped starting expression`），严禁描写张大嘴发音定格、五官狰狞挤捏或单图堆叠多阶段连续动作；画面纯净无字幕、无 UI、无水印。
