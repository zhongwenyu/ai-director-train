# Stage 3：视频动态表演与对白编译指南 (`detailed_action_and_dialogue`)

用英文编写该子镜头的动态画面描述，角色统一用 `<CHR_1>`、`<CHR_2>` 占位符指代（底层编译器会自动绑定 `<Subject k> (Sm)`）：
- 写明摄影机运镜方式（如 `Static camera`、`Subtle push-in`）与贴合角色潜台词（`subtext_intent`）的鲜活真人表情变化、眼神交流与自然手部肢体动作。
- 角色画内开口说话时，从镜头起始 `0.20s` 立即开口，使用标准格式：`<CHR_1> speaks (0.20s-止秒s): <d>[Chinese] 中文台词原文</d>`，要求口型清晰准确贴合每个音节。
- `soundscape` 用英文简述自然环境底噪与动作音效，不写背景音乐乐器。
