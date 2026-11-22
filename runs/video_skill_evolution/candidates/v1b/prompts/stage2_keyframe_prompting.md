# Stage 2：空间站位母版与子镜头锁轴首帧提示词指南 (`master_blocking_prompt` & `keyframe_prompt`)

所有图片提示词均用英文编写，严格保证全场空间拓扑唯一、正反打零越轴、周边陈设稳定及人物骨相自然清晰：

## 1. `master_blocking_prompt`（全场空间站位母版图，英文）
- **标准引用标签**：统一用 `[Scene]` 指代场景空镜图，用 `[CHR_1]`、`[CHR_2]` 等指代在场角色标准设定图。
- **180° 轴线与银幕左右坐标死锁**：严格还原 `initial_blocking` 中的同侧、对坐或对立站位拓扑及身体朝向，将摄影机锁定在唯一轴线侧（严守 180° 轴线定律），明确写出各角色在母版画框中的**银幕左右落位与视线朝向矢量**（例如：`[CHR_1] positioned on the left side of the frame angled toward the right; [CHR_2] positioned on the right side angled toward the left`）。
- **分区背景与中前景锚点固化**：明确写出左区角色身后的专属建筑结构/环境特征、右区角色身后的专属背景结构，以及角色之间或周边的支撑面与关键道具精确摆放位置；采用自然实拍定焦透视（`35mm natural cinema lens, undistorted rectilinear geometry, realistic natural lighting`），画面纯净零文字、零字幕、零水印。

## 2. `keyframe_prompt`（各子镜头静态起幅首帧，英文）
- **严格按出镜名单引用标签**：仅写入本镜 `visible_role_ids` 实际包含的 `[CHR_k]` 与 `[Scene]`，严禁混入画外未出镜角色。
- **正反打银幕矢量与过肩前景死锁（严防越轴与背景翻转）**：
  - **视线与分区背景锁定**：全程继承母版确立的摄影机轴线侧与银幕左右坐标！若母版中 `[CHR_1]` 居左朝右、`[CHR_2]` 居右朝左，则任何拍 `[CHR_1]` 的正打镜头必须保持**人物偏左或居中、面朝画框右侧（`looking toward the right side of the frame`）**并呈现左区专属背景；任何拍 `[CHR_2]` 的反打镜头必须保持**面朝画框左侧（`looking toward the left side of the frame`）**并呈现右区专属背景，**严禁跨镜视线同向或背景左右镜像颠倒**。
  - **过肩镜（`Over-the-shoulder`）前景方位守恒**：反打右方角色时，前景左边缘虚化呈现左方角色的右后肩颈轮廓；正打左方角色时，前景右边缘虚化呈现右方角色的左后肩颈轮廓，前景遮挡人物与方位严禁缺失或左右错换。
- **环境几何透视、前景景深与物理因果状态继承**：
  - **陈设与透视恒定**：保留当前机位视角下对应的前景景深遮挡物、周边器物陈设与平直单一灭点建筑几何（`coherent continuous room geometry, straight architectural lines, consistent foreground and midground props`），严禁背景结构分裂扭曲或陈设凭空消失移位。
  - **跨镜物理状态延续铁律**：若前一子镜已发生肢体触碰、器物取放、递接移位或衣饰姿态改变，本镜首帧必须如实呈现**交互改变后的最新物体状态与手部位置**，严禁退回初始未动状态。
- **主导景别与接地气起幅姿态（防高潮退景 & 防半空悬停）**：
  - **紧凑景别主导**：优先采用 `Medium close-up`、`Close-up`、`Over-the-shoulder` 捕捉眼神与面部张力（仅开篇首镜确需建立多人动作关系时可用 `Medium shot`；情绪转折、无台词反应镜与高潮落点一律锁定 `Medium close-up` 或完整保留下颌双唇的 `Close-up`，严禁退回中远景）。相邻同人镜头须拉开景别级差与至少 `30°` 机位角。
  - **起幅肢体物理落定**：手部与肢体必须处于有真实重力支撑或紧承上镜结尾动势的自然姿态（如搭靠支撑面、稳握器物、自然垂落或抱臂），**严禁把手臂或手掌写成僵硬悬浮在半空的定格动作**；开场微表情自然含蓄，禁绝呆滞直视镜头或挤眉弄眼式假笑。
- **人像柔光美型与清晰唇眼补光（防骨相显老 & 防暗部糊嘴）**：
  - 近景与特写必须配置**柔和立体侧顺主光加正面柔光眼神/唇部补光**（`soft directional key light with gentle wrap-around frontal fill light, clear eye catchlights, distinctly illuminated lip contours, smooth natural skin texture faithful to [CHR_k]'s reference age`）。
  - 哪怕在夜晚、昏暗或冷峻氛围场景中，也必须确保眼周与双唇清晰受光，**严禁生硬顶光、浓重眼袋法令纹黑影导致人物骨相显老，严禁嘴部没入暗部死黑阴影导致口型模糊**；画面干净无任何字幕、UI 或水印。
