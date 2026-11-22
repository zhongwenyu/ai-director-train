# Stage 2：空间站位母版与子镜头首帧图提示词指南 (`master_blocking_prompt` & `keyframe_prompt`)

所有提示词均须采用**具象实拍电影英文（Photorealistic live-action cinema English）**编写，严禁出现任何文字、字幕、UI、分屏拼贴或水印。

## 1. `master_blocking_prompt`（全场空间拓扑与 180° 轴线母版图，英文）
- **标准占位符**：必须使用 `[Scene]` 指代场景空镜，使用 `[CHR_1]`、`[CHR_2]` 等指代全场在场角色标准设定图。
- **相对拓扑与唯一 180° 视线轴线锁死**：
  - 严格依据 `initial_blocking` 还原全员相对落座/站位关系（对坐、并列、错位站坐对峙等）、间距与身体朝向。
  - 将母版摄影机锚定在互动连线单一侧，建立全场唯一不可逾越的 **180° 视线轴线（180-degree camera axis）**：明确限定左侧角色固定居画面左部并朝画面右方注视（`positioned screen-left, torso angled and eyeline directed toward screen-right`），右侧角色固定居画面右部并朝画面左方注视（`positioned screen-right, torso angled and eyeline directed toward screen-left`）。
- **分区陈设锚点与统一透视光影**：
  - 明确写出画面左后方、右后方及角色之间支点台面的标志性固定陈设与建筑几何，锁定单一连贯实拍透视空间（`single unified live-action space, accurate architectural perspective`，杜绝空间折裂畸变）。
  - 锁定全场统一的主光源方向与色温（`consistent directional key light, soft fill, subtle rim separation`），服装形制与关键道具初始状态完整一致。

## 2. `keyframe_prompt`（各子镜头静态起幅首帧，英文）
每个子镜头的 `keyframe_prompt` 仅引用本镜 `visible_role_ids` 对应的 `[CHR_k]` 与 `[Scene]` 对应局部空间，严格遵循以下四项铁律：

### A. 贴视线近正脸大光圈浅景深主导（方向 A 核心构图）
- **摒弃远景与纯正侧脸**：说话镜、反应镜与心声镜严禁采用远景或 90° 正侧面（profile view 会遮蔽远侧眼睛并弱化唇部细节），优先采用**贴近 180° 视线轴线 `10°–20°` 的微斜近正脸（`tight 10-to-20-degree off-axis three-quarter-front angle`）大光圈浅景深 `Medium close-up` 或 `Close-up`**（`85mm prime lens, shallow depth of field, soft background bokeh`）。
- **双眼眼神光与唇齿清晰照明**：双目完整入画且焦点精准锁死瞳孔，呈现清澈眼神光（`crisp catchlights in both eyes`）；主辅光必须清晰照亮鼻梁、双唇与下颌轮廓（`clean balanced lighting across lips and jawline, zero heavy shadow obscuring the mouth`），保障动态口型清晰度。
- **前景遮挡控制**：干净单人 `MCU`/`CU` 保持前景通透无遮挡；若采用 `Over-the-shoulder medium close-up`，仅在画面最侧边柔和虚化对侧 `[CHR_m]` 的肩颈后侧轮廓，增强前中后景景深层次。

### B. 严守 180° 轴线与同机位簇背景复现锁
- **正反打严禁越轴**：
  - 拍母版左侧角色时：人物居画面微偏左，视线投向镜头右侧贴轴方向（`eyeline directed just past camera-right`），虚化后景**仅呈现母版左后方专属陈设**；
  - 拍母版右侧角色时：人物居画面微偏右，视线投向镜头左侧贴轴方向（`eyeline directed just past camera-left`），虚化后景**仅呈现母版右后方专属陈设**；
- **重返机位陈设恒定**：同一段落内重返同一角色的近景/特写机位时，受光面方向、前景遮挡边缘与后景陈设布局必须保持一致复现，严禁正反打背景左右翻转或环境物件凭空消失重现。

### C. 静帧五官松弛舒展与真实骨相保真（防假笑与防显老漂移）
- **自然静息蓄势态**：起幅首帧定格于开口或受激最初的**松弛蓄势瞬间**——面部肌肉自然平滑舒展、双唇轻合或微启蓄气（`relaxed natural facial musculature, poised attentive baseline, lips softly together`）。
- **禁用显老挤压词**：严禁在 `keyframe_prompt` 中使用 `wrinkled`、`deeply creased`、`furrowed`、`contorted`、`grimacing`、`forced grin` 等诱发纹路加深与假笑面具的词汇，严格锁定 `[CHR_k]` 原设定的年轻/真实骨相轮廓与干净皮肤质感（`faithful facial bone structure and smooth natural skin fidelity`），仅以眼神焦点冷暖与身体微倾传递潜台词蓄力感。

### D. 跨镜肢体姿态与受作用表面终态继承
- 第 `N` 镜首帧的身体倾角、手部支点位置、衣袖形态及在场道具/接触表面物理状态，必须严格承接第 `N-1` 镜结尾终态（若前镜已完成俯身、抬手按压、移位或开合操作，本镜起幅必须直接呈现该演进后状态），严禁跨镜手势跳变或物体物理状态凭空复原穿帮。
