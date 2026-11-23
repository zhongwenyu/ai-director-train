# Stage 2：空间站位母版与光学实拍首帧提示词指南 (`master_blocking_prompt` & `keyframe_prompt`)

所有提示词均使用**英文**编写，通过严格的 180° 轴线几何锚定与电影定焦镜头光学描述，消除切镜空间跳脱、面部骨相偏移与扁平 CG 感：

## 1. `master_blocking_prompt`（全场空间母版图，英文）
- **标准引用占位符**：必须使用 `[Scene]` 指代场景环境基准图，使用 `[CHR_1]`、`[CHR_2]` 等指代在场角色标准设定图。
- **三维拓扑与 180° 轴线锁定**：严格还原 `initial_blocking` 中的相对方位（对面、同侧相邻、前后错位、站姿或坐姿）与身体朝向，确立全场唯一的 **180° 摄影机视线轴线**（明确谁居画面左侧面朝右、谁居画面右侧面朝左）。
- **后景空间地标分配**：清晰写明轴线两侧各自对应的后景建筑结构、门窗或纵深环境陈设锚点（源自 `[Scene]`），为后续正反打切镜提供恒定不变的背景几何参照。
- **实拍光影基调**：确立统一的主光源方向（Key light）、环境漫反射辅光与空间色温层次，呈现真实电影实拍质感，严禁任何文字、字幕、边框或水印。

## 2. `keyframe_prompt`（子镜头起幅首帧，英文）
每个子镜头首帧必须严格继承母版空间坐标，按以下五要素结构化编译：
- **景别、机位与前景呼吸层次**：明确标注景别（`Medium shot`、`Medium close-up`、`Close-up`、`Over-the-shoulder shot`）与机位角度（常态 `Eye-level`）。双人关系正反打优先在过肩镜（`OTS`）中保留前景搭档柔和虚化的肩颈或侧后廓边缘（如 `framed over the softly defocused foreground shoulder of [CHR_2] on the left`），强化双主体空间连接与前景呼吸感；情绪重音特写则采用干净凝聚的单人构图。
- **互补视线矢量与后景几何锚定**：严守 180° 轴线互补法则——若 `[CHR_1]` 在母版居左望右，其正打近景视线必须投向画外右方（`eyeline directed slightly off-camera right`），对应 `[CHR_2]` 反打近景视线必须投向画外左方（`eyeline directed slightly off-camera left`），且各自背后的虚化后景结构必须与母版对应朝向严格一致，杜绝切镜背景跳脱。
- **定焦浅景深与电影光学质感**：写明适配景别的电影定焦镜头光学特性（如中景 `35mm/50mm cinema prime lens`，近景特写 `50mm/85mm prime lens, shallow depth of field`），塑造清晰主体焦点向柔和背景散景的自然过渡（`natural optical bokeh roll-off`）、立体主辅轮廓光比（`dimensional key-to-fill lighting contrast with subtle rim light`）以及真实的皮肤肌理与衣料质感；**严禁全景深扁平化构图、塑料磨皮或高饱和 CG 渲染感**。
- **骨相恒定与生动起幅微神态**：保持 `[CHR_k]` 面部骨相结构、发型与服装细节与设定图高度一致；刻画贴合该镜潜台词（`subtext_intent`）的起幅眼神焦点与真实眉眼情绪张力，双唇处于自然闭合或欲言起势状态（避免首帧定格夸张张嘴残影），同框倾听者亦须呈现专注生动的在场眼神。
- **纯净画幅门禁**：末尾固定约束 `clean cinematic frame, zero text, no subtitles, no watermark`。
