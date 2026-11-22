# Stage 3：视频动态表演与对白编译指南 (`detailed_action_and_dialogue`)

用英文编写该子镜头的动态画面描述，角色统一用 `<CHR_1>`、`<CHR_2>` 占位符指代（底层编译器会自动替换为 `<Subject k> (Sm)`）：
- 写明摄影机运镜方式（如 `Static camera`、`Slow push-in`）与角色在镜头内的动作、神情变化。
- 角色画内开口说话时，使用标准格式：`<CHR_1> speaks (起秒s-止秒s): <d>[Chinese] 中文台词原文</d>`，确保时间窗留出句尾余量，避免截断。
- `soundscape` 用英文简述自然环境底噪与动作音效，不写背景音乐乐器。
