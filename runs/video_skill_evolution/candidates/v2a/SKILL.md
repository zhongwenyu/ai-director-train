---
name: hit-video
description: 通用 AI 短剧多模态视频生成技能（涵盖空间站位母版、紧凑正反打与反应分镜、动作适配景别首帧、实拍机位与潜台词微表演声画编译）。
---

# 通用短剧视频生成技能 (`hit-video`)

根据输入的戏剧段落任务卡（环境设定、在场站位关系 `initial_blocking`、角色外观、关键道具、对白与心声序列），先确立全场守恒的空间站位母版（`master_blocking_prompt`），再拆解为节奏紧凑、景别适配的子镜头序列（`clips`），依次编译静态起幅首帧（`keyframe_prompt`）与鲜活微表演对白提示词（`detailed_action_and_dialogue`），合成声画合一的戏剧片段。

## 全局导演核心法则（全题材通用）
1. **空间拓扑与 180° 轴线守恒**：以 `master_blocking_prompt` 锁定全员相对方位、朝向与环境锚点；跨机位切镜严格继承左右轴线、视线矢量与同场人物遮挡关系，杜绝角色或周边陈设凭空消失、翻轴错位。
2. **紧凑正反打与反应声桥**：破除单一中远景长镜站桩到底；超过 `3.5s` 的多句或长句交锋主动拆分为 `2s–3s` 正反打切镜，并在情绪落点穿插 `2s` 无声倾听反应近景镜，配合 `lcut_audio_hold_over_next_s` 声桥实现声画交叠。
3. **戏剧动作属性决定景别**：言语交锋点睛、潜台词暗涌与无声反应收紧至 `MCU/CU`（或紧凑 `OTS`）放大眼神层次；涉及跨空间走动离开、拉拽转身、鞠躬逃离等大幅肢体调度或时空意境空镜转场时，必须采用 `MS/WS` 完整呈现肢体轨迹与空间转换，严禁机械套用特写吞没动作。
4. **固定机位主导与极点动机运镜**：常规原地或落座对话与普通反应镜以稳固三脚架固定机位（`Locked-off static camera`）为常态，严禁切镜后习惯性推镜；仅在角色跨空间位移跟拍（`Tracking/Pan`）或全段唯一静默悬念/悲恸凝视极点（`Slow motivated push-in`）启用单次动机运镜。
5. **潜台词微表演与声画同步**：赋予发声与同框倾听双方实时细腻的眉眼递进与呼吸交互；严控台词气口、逐字唇形咬合、禁言闭唇隔离及连贯底噪与心声混响层次。

## 核心工作流
1. **分镜与节奏拆解**：参考 `prompts/stage1_director_decompose.md`，规划紧凑切镜数、整数秒时长（紧贴 `target_duration_s`）、动作适配景别、出镜/发声角色及 `lcut_audio_hold_over_next_s` 声桥。
2. **空间母版与起幅首帧**：参考 `prompts/stage2_keyframe_prompting.md`，编写锁定 180° 轴线的 `master_blocking_prompt` 及景深主次分明、带潜台词微张力的 `keyframe_prompt`。
3. **动态微表演与声画编译**：参考 `prompts/stage3_motion_acting_prompting.md`，编写克制运镜、双人交互微表演、`<d>[Chinese] 台词</d>` 唇形同步（`inner_os` 分离）与连贯 `soundscape`。
