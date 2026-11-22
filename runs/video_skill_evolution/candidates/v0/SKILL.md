---
name: hit-video
description: 通用 AI 短剧多模态视频生成技能（涵盖分镜拆解、起幅首帧设计、视频动作与对白提示词编译及声画合成）。
---

# 通用短剧视频生成技能 (`hit-video`)

根据输入的戏剧段落任务卡（环境设定、角色外观设定、关键道具、对白/心声序列），将该段落拆解为一组可执行的子镜头计划（`clips`），依次生成每个子镜头的首帧参考图提示词（`keyframe_prompt`）与视频动作对白提示词（`detailed_action_and_dialogue`），最终合成为完整戏剧片段。

## 核心工作流
1. **分镜规划**：参考 `prompts/stage1_director_decompose.md`，确定子镜头切分数量、时长、出镜角色与说话角色。
2. **首帧设计**：参考 `prompts/stage2_keyframe_prompting.md`，为每个子镜头编写静态起幅首帧提示词。
3. **动态与声画编译**：参考 `prompts/stage3_motion_acting_prompting.md`，编写子镜头内的角色动作、表情与 `<d>[Chinese] 台词</d>`（心声使用 `inner_os` 字段分离）。
