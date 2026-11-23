# Stage 2：空间站位母版与子镜头首帧图提示词指南 (`master_blocking_prompt` & `keyframe_prompt`)

## 1. `master_blocking_prompt`（全场空间座位/站位母版图，英文）
- **标准引用语法**：使用 `[Scene]` 指代场景空镜基准，使用 `[CHR_1]`、`[CHR_2]` 等指代在场角色标准外观图。
- **单一合理建筑结构与三维拓扑**：严格还原 `initial_blocking` 中的左右同侧、对面落座或主次站位拓扑、身体朝向与彼此距离；明确构建单一、符合真实建筑与生活常理的空间透视结构（严禁生成重复对称的克隆门窗、多余重叠桌椅或悬浮错位陈设）。
- **全场唯一 180° 视线轴线**：锁定摄像机主轴线一侧的银幕左右方位（如明确谁居银幕左侧朝右、谁居银幕右侧朝左），采用契合题材年代与昼夜设定的自然实拍光影层次，画面干净无任何文字、字幕或水印。

## 2. `keyframe_prompt`（各子镜头静态起幅首帧，英文）
- **180° 轴线、互补视线与跨镜透视守恒**：
  - 严格继承空间母版的角色落位与视线轴线。正反打与景别切换（`Medium shot`、`Over-the-shoulder`、`Medium close-up`、`Close-up`）必须在轴线同侧完成：银幕左侧角色保持 `looking off-camera right`，银幕右侧角色保持 `looking off-camera left`，严禁无故直视镜头或跨镜视线顺拐。
  - **景深与背景方位一致性**：首帧背景建筑构件、陈设位置及虚化景深必须严格匹配当前机位朝向与焦段（近景/特写自然柔化对应方位背景，严禁把对向背景错贴到反打镜头、背景结构凭空消失或跨镜突兀闪回）。
  - **前景遮挡锚定**：`Over-the-shoulder` 镜头须明确写出前景角色虚化肩背或侧廓遮挡（如 `framed past the softly blurred foreground shoulder of [CHR_other]`），稳固双人空间距离感。
- **破除证件照僵立，构建情境化鲜活起幅与跨镜承接**：
  - 角色起幅必须处于戏剧交流进行中的鲜活状态，身体重心与手部支点贴合人物身份、年代礼仪与当下处境（如古装敛袖凭案/持物、年代或现代自然倚靠、执握随身器物或身体微倾交流），杜绝双臂垂立的呆板证件照摆拍。
  - 面部呈现契合 `subtext_intent` 起势的真实神态（如温润含笑、凝神倾听、微怔错愕、玩味审视或垂眸隐忍），同时保持静态首帧五官自然舒展、零夸张扭曲，为后续动态演进留足弹性。
  - 若相邻镜头连续表现同一在场角色，首帧的头颈角度、手部位置与衣饰状态须与上一镜尾态自然衔接。
- **参数化首帧结构范式（须按实际景别、题材身份与潜台词动态替换槽位，严禁固化单一姿势套路）**：
  `[Shot scale & camera angle on the established 180-degree axis], [optional foreground OTS occlusion of [CHR_other]], [CHR_k] positioned on [screen-left/right] against [angle-matched [Scene] background & natural depth-of-field], [era- and identity-appropriate posture with natural hand/prop fulcrum], looking [off-camera right/left] with [authentic subtext-matched opening expression], natural live-action lighting, clean frame with no text or subtitles.`
