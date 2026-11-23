# Stage 2：空间站位母版与子镜头首帧图提示词指南 (`master_blocking_prompt` & `keyframe_prompt`)

## 1. `master_blocking_prompt`（全场空间站位母版图，英文编写）
- **标准引用锚点**：使用 `[Scene]` 指代输入场景环境参考图，使用 `[CHR_1]`、`[CHR_2]` 等严格指代在场各角色标准外观参考图。
- **全场景单一连贯三维空间（杜绝重复/镜像畸变）**：广泛适配室内厅堂陈设、半开放空间、街头巷尾或自然山野旷野等一切题材环境，明确声明单一连贯的真实三维空间拓扑与自然透视逻辑（如 `single coherent 3D spatial layout and natural perspective faithful to [Scene], free of duplicate, mirrored, or phantom background structures and objects`），严防生成违背常理的重复背景构件或对称重影场景。
- **严格锁定 `initial_blocking` 与唯一 180° 轴线**：精准还原 `initial_blocking` 中的左右同侧、隔空/隔物相对落座或站立方位、身体朝向、距离疏密及在场关键器物位置，建立贯穿全段唯一的 **180° 戏剧视线轴线（180-degree line of action）**。
- **实拍光影与纯净画面**：确立全场统一的主光源方向、环境色温与真实摄影景深质感（`cinematic live-action still, natural consistent lighting`），零文字、零字幕、零水印、零拼贴边框。

## 2. `keyframe_prompt`（各子镜头静态起幅首帧，英文编写）
- **严守母版 180° 轴线与正反打方位守恒**：
  - 子镜头景别（`Medium shot`、`Medium close-up`、`Close-up`、`Over-the-shoulder` 等）与机位角度必须置于母版 180° 轴线同侧。
  - 正反打切换时严格锁定左右画框占位与视线对位：若母版中 `[CHR_1]` 居左朝右看、`[CHR_2]` 居右朝左看，则切入单人近景或过肩镜时，`[CHR_1]` 视线必须朝向画框右侧，`[CHR_2]` 视线必须朝向画框左侧，**严禁跨镜视线顺拐或主客方位颠倒**。
- **前景遮挡层次与背景景深连续性（防跳变与防闪回）**：
  - 编写 `Over-the-shoulder` 或带前景层次镜头时，显式交代前景虚化角色肩背所在的画框左/右边缘位置（如 `softly out-of-focus foreground shoulder of [CHR_2] on the right frame edge`）以及后景对应朝向的真实背景环境与景深虚化梯度（`matching background spatial elements from [Scene] with natural shallow depth of field`）。
  - 严禁景别推拉或正反打切镜时背景环境突兀闪回异侧空间，严禁前景遮挡关系或在场关键道具凭空消失。
- **跨镜肢体末态承接**：
  - 同一角色在相邻子镜头中的头颈偏转、躯干重心、手部姿态与随身器物状态，必须顺滑承接上一镜头结尾的动作落点（`seamless continuation of head angle, posture, and hand/prop placement from the preceding clip`），消除跨镜肢体瞬移错位。
- **起幅自然端正稳态原则（防静态崩坏·为动态留白）**：
  - 首帧定格在子镜头起始瞬间的**五官解剖结构端正、神情鲜活蓄势的自然稳态**（`anatomically accurate, poised opening expression matching the dramatic context`），避免将起幅定格在半张大嘴嘶吼或五官过度挤压变形的瞬间，为后续视频动态情绪释放留出自然展开空间。
  - **发声前态区分**：画内即将开口角色呈自然凝视或欲言起势态；**无台词反应镜头与 `inner_os` 心声镜头中的角色必须明确写出双唇自然闭合（`lips naturally closed`）**。画面干净无字幕、无 UI 标记。
