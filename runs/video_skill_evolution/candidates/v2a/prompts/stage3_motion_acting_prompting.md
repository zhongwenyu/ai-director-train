# Stage 3：视频动态表演与声画同步编译指南 (`detailed_action_and_dialogue` & `soundscape`)

使用地道英文编写动态画面与声场指令，角色统一使用 `<CHR_1>`、`<CHR_2>` 占位符指代（底层编译器自动绑定 `<Subject k> (Sm)`），严禁混入具体角色姓名。

## 1. 个体特征动态延续与克制运镜
- **动态防崩防串脸**：在描述 `<CHR_k>` 动作神态时，自然带出其标志性骨相轮廓、真实肤质光影与发型头饰/衣料随微动产生的真实物理反馈（发丝微颤、头饰轻晃或衣领袖口自然折皱），确保运动全程维持强个体辨识度。
- **呼吸感实拍运镜**：明确标注摄影机运动（如 `Locked-off static camera`、`Imperceptible slow push-in`、`Subtle handheld breathing`、`Smooth rack focus`），运镜须服务于情绪聚焦，保持空间透视与前景遮挡稳定，严禁眩晕式大幅晃动。

## 2. 情境与镜长适配的分级微表演（反面瘫干念·反夸张狰狞）
结合角色潜台词（`subtext_intent`）与题材气质（现代克制、年代厚重、古装仪态、悬疑冷峻），严禁全程单一表情念稿，同时**严禁不分镜长机械堆砌五官乱飞、频繁挥手或大幅摇晃**：
- **短镜法则（`2–3s` 反应镜或短句交锋）——单一鲜明情绪落点**：
  全镜只做**一处高纯度微表情与眼神定格**（例如：听闻对方话语后瞳孔微缩、目光自下而上冷冽抬起、唇线极轻抿紧、下颌微绷，或指尖在器物边缘轻顿停住），以静制动，留白有力。
- **中长镜法则（`4–5s` 核心说话镜）——三拍式自然神态递进**：
  构建从 **“起势眼神蓄力 → 句中潜台词微转折（表里不一的克制笑意、目光短暂游移或眉心暗蹙） → 关键重音眼神锁定与呼吸落点”** 的连贯层次；肢体仅配合心理转折做极自然的重心微调（如上身微倾施压、微偏头审视、指节轻收或轻抚衣袖案沿），过渡柔和真实。

## 3. 台词声学塑形、精确口型同步与闭嘴铁律
- **标准开口格式与防截断时间窗**：
  画内角色开口说话时，从 `0.15s–0.25s` 伴随极轻的自然吸气起音（避免 `0.00s` 切镜硬爆音），结束时间 `end_s` 必须早于该镜 `duration_s` 至少 `0.35s–0.50s` 以留出尾音收束与闭唇余韵，严格采用格式：
  `<CHR_1> speaks (0.20s-3.55s): <d>[Chinese] 中文台词原文</d>`
- **破除朗读腔的声学指导**：
  紧贴 `speaks` 前后用精炼英文写明发声质感、语速节奏、换气气口与潜台词重音（如 `in a low, measured voice, pausing briefly before emphasizing the final words with quiet intensity` 或 `starting calm and detached, voice tightening subtly mid-sentence`），引导生成富有戏剧呼吸转折的真实人声。
- **声画口型隔离铁律**：
  - **说话时段**：显式要求说话者唇舌清晰、自然饱满地贴合每个汉语音节开合（`clear, natural syllable-accurate lip sync`），至 `end_s` 自然合拢收势。
  - **非说话与心声时段**：同镜头内的倾听角色、静默反应镜头角色、以及含 `inner_os` 内心独白的角色，**必须显式写入闭嘴约束**（`keeps lips naturally closed throughout, zero lip movement, communicating purely through eyes and subtle breathing`），彻底杜绝心声漏口型与旁人乱动嘴。

## 4. 连续空间环境声场（`soundscape`）
- 用英文采用**“统一环境底噪床 + 镜头专属微拟音”**结构编写（如 `Consistent quiet indoor room tone with distant muffled air, layered with subtle fabric rustle and a soft breath intake`）。
- **跨镜底噪连续性**：同一场景下所有子镜头的 `soundscape` 必须延续相同质感与声压特征的底层环境底噪（consistent ambient bed），消除正反打切镜时的底噪抽吸与干声断层；**严禁出现任何背景音乐、配乐风格或乐器名称**。
