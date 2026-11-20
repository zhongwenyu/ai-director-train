#!/usr/bin/env python3
"""
Compile & execute Episode 1 (11 groups) & Episode 2 (10 groups) v2 480p video generation
on local 5090 Pika-H3-Flex + 4070 Ti SUPER 368p short dry VO clips, enforcing:
  - <=1K reference image invariant
  - Zero character appearance/garment tokens + zero <d> speaker-name pollution
  - Dedicated short dry VO placement via place_vo_segments (zero mouth movement during VO)
  - Pre-Impact -> Aftermath physical crash montage in 1-1-07
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
STUDIO_BRIDGE = Path("/home/zhongwenyu/project/playlets-studio/skills/studio-bridge/scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))
sys.path.insert(0, str(STUDIO_BRIDGE))

import pika_runner  # noqa: E402
import vo_split  # noqa: E402

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v2/ep01_02_video_gen")
KF_1K = WORK_DIR / "keyframes_1k"
CACHE_1K = WORK_DIR / "cache_1k"
TAKES_EP1 = WORK_DIR / "takes_ep01"
TAKES_EP2 = WORK_DIR / "takes_ep02"
for d in (CACHE_1K, TAKES_EP1, TAKES_EP2):
    d.mkdir(parents=True, exist_ok=True)


def kf(sid: str) -> str:
    return str(KF_1K / f"{sid}_1k.png")


def build_plans() -> tuple[list, list]:
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))

    v_yexun = amap["叶寻"]["voice"]
    v_qian = amap["夏芊芊"]["voice"]
    v_lin = amap["林双双"]["voice"]
    v_chu = amap["楚南"]["voice"]
    v_xia = amap["夏建国"]["voice"]
    v_wang = amap["老王"]["voice"]
    v_diner = amap["中年食客"]["voice"]
    v_shout = amap["_diner_shout_voice"]

    f_yexun_2020 = amap["叶寻 · 2020研发总厨白服"]["front_1k"]
    f_chu_2020 = amap["楚南 · 海归并购总监西装"]["front_1k"]
    f_lin_2020 = amap["林双双 · 塞纳左岸酒红礼服"]["front_1k"]
    f_yexun = amap["叶寻"]["front_1k"]
    f_qian = amap["夏芊芊"]["front_1k"]
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    f_xia = amap["夏建国"]["front_1k"]
    f_wang = amap["老王"]["front_1k"]
    f_diner = amap["中年食客"]["front_1k"]

    # ==================== EPISODE 1 (11 SHOTS = 123s) ====================
    ep1 = [
        {
            "id": "1-1-01",
            "episode": 1,
            "duration": 11,
            "seed": 1101,
            "description": "2020年林记上市前夜瓢泼大雨，叶寻被保安推出酒店侧铁门摔在泥水里，楚南搂着林双双将叶寻工牌踢进雨水沟羞辱。",
            "dialogue": "楚南：叶大厨，明天集团敲钟，里头全是投行贵客，你一身牛油味往里闯，给双双丢人？",
            "assetNames": ["集团大厦旋转门雨夜街口", "叶寻 · 2020研发总厨白服", "楚南 · 海归并购总监西装", "林双双 · 塞纳左岸酒红礼服"],
            "ref_images": [kf("1-1-01"), f_yexun_2020, f_chu_2020, f_lin_2020],
            "ref_audios": [v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man kneeling on the wet ground in <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The man holding the black umbrella on the steps in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3>: The woman standing beside <Subject 2> under the umbrella in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.2s) Medium-wide high-contrast rainy alley shot framed from <Picture 1>.\n"
                "- [Shot 2] (3.2s-11.0s) Medium two-shot angling slightly upward toward <Subject 2> and <Subject 3> on the hotel steps.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-3.2s): Pouring rain splashes across the wet pavement. <Subject 1> braces one hand in the puddle beside his fallen wooden box as <Subject 2> steps forward and kicks a fallen plastic name badge into the rainwater gutter.\n"
                "- [Shot 2] (3.2s-10.2s): Under the black umbrella, <Subject 2> (S1) keeps one arm around <Subject 3>'s shoulder, looks down with an arrogant sneer, and speaks clearly: <d>[Chinese] 叶大厨，明天集团敲钟，里头全是投行贵客，你一身牛油味往里闯，给双双丢人？</d>\n"
                "- [Shot 2] (10.2s-11.0s): <Subject 3> looks down coldly without a trace of sympathy.\n"
                "[Environment]\n"
                "- Nighttime luxury hotel side gate in heavy pouring rain, cold blue rain reflections mixed with warm golden interior light.\n"
                "[Camera & Visuals]\n"
                "- Crisp realistic cinema photography, dynamic rain streaks, dramatic chiaroscuro lighting.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Heavy rain pelting pavement and umbrella, splash of badge in water, clear close-mic arrogant male dialogue, zero background music."
            ),
        },
        {
            "id": "1-1-04",
            "episode": 1,
            "duration": 14,
            "seed": 11042,
            "description": "叶寻撑着湿滑地面质问林双双十五年过河拆桥，林双双居高临下冷漠撇清。",
            "dialogue": "叶寻：林双双！十五年，我拿爷爷的火锅方子把林记熬到上市，过河就拆桥？！\n林双双：方子是你当年上赶着献的！没楚南留洋回来做资本包装，你熬土火锅也配敲钟？遣散费打你卡上了！",
            "assetNames": ["集团大厦旋转门雨夜街口", "叶寻 · 2020研发总厨白服", "林双双 · 塞纳左岸酒红礼服", "楚南 · 海归并购总监西装"],
            "ref_images": [kf("1-1-04"), f_yexun_2020, f_lin_2020, f_chu_2020],
            "ref_audios": [v_yexun, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The rain-soaked man on the lower left ground in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The woman under the umbrella on the upper right steps in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The man holding the umbrella beside <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.6s) Close-up low-angle shot on <Subject 1> in the pouring rain.\n"
                "- [Shot 2] (5.6s-14.0s) Medium close-up reverse angle on <Subject 2> and <Subject 3> under the black umbrella.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.4s): Rain streams down <Subject 1>'s face as he clutches the wet wooden box to his chest, glares up with raw grief and fury, and speaks forcefully: <d>[Chinese] 林双双！十五年，我拿爷爷的火锅方子把林记熬到上市，过河就拆桥？！</d>\n"
                "- [Shot 2] (5.7s-13.2s): <Subject 2> (S2) tilts her chin coldly beside <Subject 3>'s smug smirk and replies in an icy, dismissive tone: <d>[Chinese] 方子是你当年上赶着献的！没楚南留洋回来做资本包装，你熬土火锅也配敲钟？遣散费打你卡上了！</d>\n"
                "- [Shot 2] (13.2s-14.0s): <Subject 2> turns away coldly under the umbrella.\n"
                "[Environment]\n"
                "- Rain-drenched hotel back steps at night.\n"
                "[Camera & Visuals]\n"
                "- Sharp shot-reverse-shot dramatic tension, glistening rain droplets.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Steady downpour SFX, emotional male voice followed by cold sharp female voice, zero music."
            ),
        },
        {
            "id": "1-1-07",
            "episode": 1,
            "duration": 8,
            "seed": 1107,
            "description": "铁门落锁，叶寻紧抱湿木盒踉跄走上雨夜马路，刺目远光灯与急刹声炸响，叶寻倒在积水血色尾灯余波中。",
            "dialogue": "",
            "assetNames": ["集团大厦旋转门雨夜街口", "叶寻 · 2020研发总厨白服"],
            "ref_images": [kf("1-1-07"), kf("1-1-07_aftermath"), f_yexun_2020],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The rain-soaked man clutching the dark wooden box in <Picture 1> and <Picture 2>, matching <Picture 3>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.4s) Medium tracking shot framed from <Picture 1> as <Subject 1> stumbles onto the dark rainy street.\n"
                "- [Shot 2] (3.4s-5.2s) Extreme close-up on <Subject 1>'s startled face engulfed by blinding white car headlights.\n"
                "- [Shot 3] (5.2s-8.0s) High-angle overhead aftermath shot matching <Picture 2> composition.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-3.4s): Behind <Subject 1>, the heavy iron gate clangs shut. Drenched in pouring rain, <Subject 1> hugs the wooden box tightly against his chest and staggers onto the wet asphalt.\n"
                "- [Shot 2] (3.4s-5.2s): Twin blinding white headlights rush straight toward <Subject 1>'s face as tires screech piercingly on wet pavement, ending in a sudden white flash and heavy dull impact sound!\n"
                "- [Shot 3] (5.2s-8.0s): Matching <Picture 2>, <Subject 1> lies motionless on the rain-lashed wet asphalt with eyes closed, his fingers loosening beside the fallen wooden box as red taillight reflections ripple across the puddle.\n"
                "[Environment]\n"
                "- Dark rain-slicked city street at night.\n"
                "[Camera & Visuals]\n"
                "- Clean three-beat physical montage (pre-impact -> blinding headlight flash -> motionless aftermath), realistic rain physics.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Metallic gate slam, torrential rain, blaring car horn, piercing tire screech, heavy thud, then quiet rain pattering, zero dialogue, zero music."
            ),
        },
        {
            "id": "1-2-01",
            "episode": 1,
            "duration": 10,
            "seed": 1201,
            "description": "叶寻在2005年9月10日傍晚空荡的林记家常馆惊醒，看诺基亚手机确认重生回大三开学，庆幸秘方尚未交出。",
            "dialogue": "[VO] 叶寻：2005年9月10号？大三刚开学……爷爷的清润火锅方子，还没交出去！",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻"],
            "ref_images": [kf("1-2-01"), f_yexun],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man sitting at the wooden table in <Picture 1>, matching <Picture 2>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.0s) Medium close-up framed from <Picture 1> under warm golden dusk sunlight.\n"
                "- [Shot 2] (4.0s-10.0s) Close-up on <Subject 1> picking up the old keypad phone and exhaling with fierce clarity.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.0s): Overhead the vintage ceiling fan turns lazily. <Subject 1> jolts upright from the wooden table, gasping softly with lips parting briefly then closing, staring in disbelief at his smooth young hands.\n"
                "- [Shot 2] (4.0s-10.0s): Keeping his lips firmly closed in silent thought, <Subject 1> picks up the black candybar keypad phone from the table, glances at the glowing screen, and his eyes sharpen with sudden relief and determination.\n"
                "[Environment]\n"
                "- Empty 2005 Chongqing small restaurant dining room bathed in warm orange late-afternoon sunlight.\n"
                "[Camera & Visuals]\n"
                "- Warm nostalgic 2005 film look, crisp focus, natural hand and eye acting, lips strictly closed from 2.0s to 10.0s.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Gentle creak of overhead ceiling fan, soft cloth rustle, quiet street ambiance outside, zero spoken dialogue, zero music."
            ),
            "vo_job": {
                "voice": v_yexun,
                "duration": 7,
                "text": "二零零五年九月十号？大三刚开学……爷爷的清润火锅方子，还没交出去！",
                "dst_start": 2.4,
            },
        },
        {
            "id": "1-2-04",
            "episode": 1,
            "duration": 11,
            "seed": 1204,
            "description": "林双双把发黄旧围裙丢在桌上，抱怨馆子连亏三个月只剩四万块，嫌弃叶寻家土火锅。",
            "dialogue": "林双双：睡迷糊了？到饭点半桌客人都没有，馆子连亏三个月就剩四万块。你昨天说拿你家土火锅救店，算了吧。",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻", "林双双"],
            "ref_images": [kf("1-2-04"), f_yexun, f_lin],
            "ref_audios": [v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man seated at the wooden table in <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The young woman standing beside the table in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-11.0s) Medium two-shot framed from <Picture 1> with subtle push-in.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-1.2s): <Subject 2> slaps a folded yellowed kitchen cloth onto the wooden tabletop in front of <Subject 1> and crosses her arms impatiently.\n"
                "- [Shot 1] (1.2s-10.1s): Frowning in annoyance at the empty dining hall, <Subject 2> (S1) speaks in an impatient, dismissive tone: <d>[Chinese] 睡迷糊了？到饭点半桌客人都没有，馆子连亏三个月就剩四万块。你昨天说拿你家土火锅救店，算了吧。</d>\n"
                "- [Shot 1] (10.1s-11.0s): <Subject 1> leans back calmly, looking at her with cool, detached eyes.\n"
                "[Environment]\n"
                "- Sunlit late-afternoon empty restaurant dining hall.\n"
                "[Camera & Visuals]\n"
                "- Clean steady framing, natural lip-sync and impatient facial expression.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Soft slap of cloth on wood, clear crisp young female dialogue, quiet room tone, zero music."
            ),
        },
        {
            "id": "1-2-07",
            "episode": 1,
            "duration": 14,
            "seed": 1207,
            "description": "室友楚南晃着寝室钥匙串进门，鼓吹两万五改法式西餐厅、请深圳副厨表哥赵帆卖五十八元牛排。",
            "dialogue": "楚南：老叶，外语系女生约会谁吃油烟土火锅？拿两万五铺白桌布改法式西餐厅，剩一万五搞开业促销！\n林双双：那主厨呢？\n楚南：我表哥赵帆在深圳大酒店当西餐副厨，我替你请好了，牛排五十八一份！",
            "assetNames": ["沙正街林家食府老店大堂", "楚南", "林双双", "叶寻"],
            "ref_images": [kf("1-2-07"), f_chu, f_lin, f_yexun],
            "ref_audios": [v_chu, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man twirling dorm keys in the center of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young man seated calmly on the left of <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.3s) Medium three-shot framed from <Picture 1>.\n"
                "- [Shot 2] (7.3s-14.0s) Closer medium two-shot on <Subject 1> and <Subject 2> exchanging eager looks.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-7.1s): Jingling his dorm key ring, <Subject 1> (S1) gestures grandly across the dining room while <Subject 3> watches silently, speaking smugly: <d>[Chinese] 老叶，外语系女生约会谁吃油烟土火锅？拿两万五铺白桌布改法式西餐厅，剩一万五搞开业促销！</d>\n"
                "- [Shot 2] (7.3s-8.9s): <Subject 2>'s (S2) eyes light up eagerly as she asks: <d>[Chinese] 那主厨呢？</d>\n"
                "- [Shot 2] (9.0s-13.3s): <Subject 1> (S1) pats his chest boastfully and answers: <d>[Chinese] 我表哥赵帆在深圳大酒店当西餐副厨，我替你请好了，牛排五十八一份！</d>\n"
                "- [Shot 2] (13.3s-14.0s): <Subject 2> smiles brightly with admiration.\n"
                "[Environment]\n"
                "- 2005 Chongqing small restaurant interior at dusk.\n"
                "[Camera & Visuals]\n"
                "- Crisp multi-character staging, accurate eye lines and lip-sync.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Subtle jingle of keys, natural two-speaker Mandarin dialogue, zero music."
            ),
        },
        {
            "id": "1-2-10",
            "episode": 1,
            "duration": 11,
            "seed": 1210,
            "description": "林双双打发叶寻明天刷后厨油灶打杂，楚南拈起油垢钢丝球递到叶寻面前羞辱。",
            "dialogue": "林双双：还是楚南见过世面！明天停业收拾，叶寻，你留下把后厨油灶刷干净打个杂。\n楚南：接着吧叶大厨，灶刷亮堂点，等我表哥到了赏你口罗宋汤。",
            "assetNames": ["沙正街林家食府老店大堂", "楚南", "林双双", "叶寻"],
            "ref_images": [kf("1-2-10"), f_chu, f_lin, f_yexun],
            "ref_audios": [v_lin, v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young man on the right holding the dark wire scrubber in <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The young woman standing center-right in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3>: The young man standing calmly on the left in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.8s) Medium three-shot framed from <Picture 1>.\n"
                "- [Shot 2] (5.8s-11.0s) Over-the-shoulder close-up as <Subject 1> dangles the greasy wire scrubber in front of <Subject 3>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.6s): <Subject 2> (S1) glances proudly at <Subject 1>, then turns her chin condescendingly toward <Subject 3> and speaks: <d>[Chinese] 还是楚南见过世面！明天停业收拾，叶寻，你留下把后厨油灶刷干净打个杂。</d>\n"
                "- [Shot 2] (5.9s-10.3s): Smirking mockingly, <Subject 1> (S2) holds the dark wire pot scrubber right up toward <Subject 3> and jeers: <d>[Chinese] 接着吧叶大厨，灶刷亮堂点，等我表哥到了赏你口罗宋汤。</d>\n"
                "- [Shot 2] (10.3s-11.0s): <Subject 3> gazes down at the wire scrubber with a faint, icy smile.\n"
                "[Environment]\n"
                "- Warm dusk interior of the small restaurant.\n"
                "[Camera & Visuals]\n"
                "- Sharp dramatic close-ups, clear prop visibility.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Crisp female and male smug dialogue, subtle metallic scrape of wire ball, zero music."
            ),
        },
        {
            "id": "1-2-13",
            "episode": 1,
            "duration": 10,
            "seed": 1213,
            "description": "叶寻用发黄旧围裙裹住钢丝球塞回楚南掌心，当场收回秘方并与林双双彻底断绝关系。",
            "dialogue": "叶寻：五十八的牛排配你们正好。方子收回，油灶你们自己刷。林双双，咱俩到此为止。",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻", "楚南", "林双双"],
            "ref_images": [kf("1-2-13"), f_yexun, f_chu, f_lin],
            "ref_audios": [v_yexun],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man on the left in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The startled young man in the center of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The stunned young woman on the right of <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-10.0s) Medium close-up framed from <Picture 1>, holding steady on <Subject 1>'s decisive counter-move.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-2.0s): <Subject 1> wraps the dark wire scrubber neatly inside the yellowed kitchen cloth and presses the bundle firmly back into <Subject 2>'s open palm.\n"
                "- [Shot 1] (2.0s-9.2s): Looking evenly from <Subject 2> to <Subject 3> with calm, razor-sharp finality, <Subject 1> (S1) speaks clearly: <d>[Chinese] 五十八的牛排配你们正好。方子收回，油灶你们自己刷。林双双，咱俩到此为止。</d>\n"
                "- [Shot 1] (9.2s-10.0s): <Subject 2>'s smile freezes while <Subject 3> stares in disbelief as <Subject 1> turns cleanly toward the exit.\n"
                "[Environment]\n"
                "- Restaurant dining room backlit by golden-orange sunset.\n"
                "[Camera & Visuals]\n"
                "- Satisfying crisp hand action, commanding calm facial acting.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Cloth wrapping wire scrubber, firm pat into palm, calm decisive male dialogue, zero music."
            ),
        },
        {
            "id": "1-2-16",
            "episode": 1,
            "duration": 11,
            "seed": 1216,
            "description": "叶寻大步跨出林记门槛，身后楚南摔围裙讥讽、林双双冷喊威胁，叶寻头也不回走入暮色。",
            "dialogue": "楚南：装什么硬气！掏不出三千块的穷学生，离了双双家店面，攥个破方子去哪儿开锅？\n林双双：叶寻！出了这道门，明天求我也别想再进我家后厨！",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻", "楚南", "林双双"],
            "ref_images": [kf("1-2-16"), f_yexun, f_chu, f_lin],
            "ref_audios": [v_chu, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man striding out through the open doorway in the foreground of <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The young man inside by the wooden table in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3> (S2): The young woman inside shouting toward the door in <Picture 1>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.0s) Medium shot inside looking toward the open doorway as <Subject 2> slams the cloth bundle down.\n"
                "- [Shot 2] (6.0s-11.0s) Exterior tracking shot outside the doorway as <Subject 1> walks resolutely down the sunset street without looking back.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.8s): <Subject 2> (S1) slams the cloth bundle onto the table with a loud scoff while <Subject 1> steps out the doorway: <d>[Chinese] 装什么硬气！掏不出三千块的穷学生，离了双双家店面，攥个破方子去哪儿开锅？</d>\n"
                "- [Shot 2] (6.0s-10.3s): Rushing two steps toward the threshold behind him, <Subject 3> (S2) shouts angrily: <d>[Chinese] 叶寻！出了这道门，明天求我也别想再进我家后厨！</d>\n"
                "- [Shot 2] (10.3s-11.0s): Bathed in warm dusk light, <Subject 1> strides steadily ahead without pausing or turning his head.\n"
                "[Environment]\n"
                "- 2005 Chongqing restaurant threshold opening onto golden-hour street.\n"
                "[Camera & Visuals]\n"
                "- Deep-focus staging transitioning smoothly into sunlit street walk.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Cloth slamming on wood, firm footsteps, mocking male voice and angry female shout fading behind, zero music."
            ),
        },
        {
            "id": "1-3-01",
            "episode": 1,
            "duration": 9,
            "seed": 1301,
            "description": "沙正街亮起晚市灯箱，叶寻在黄葛树下翻看两千八百块暑期工存折，立誓绝不再帮白眼狼。",
            "dialogue": "[VO] 叶寻：两千八暑期工存款，哪怕摆摊，这一世绝不再给白眼狼熬一滴油！",
            "assetNames": ["重庆大学外沙正街黄昏老街", "叶寻"],
            "ref_images": [kf("1-3-01"), f_yexun],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man standing beneath the large banyan tree holding the red passbook in <Picture 1>, matching <Picture 2>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-9.0s) Medium close-up framed from <Picture 1> with gentle push-in under warm dusk streetlamps.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-9.0s): Evening shop signs flicker on along the stone sidewalk. Keeping his lips firmly closed in silent resolve, <Subject 1> opens the folded red savings passbook in his hands, runs his thumb across the printed balance, then folds it neatly into his inner pocket and looks forward with bright, determined eyes.\n"
                "[Environment]\n"
                "- 2005 Chongqing Shazheng Street at dusk beneath old banyan trees and warm shop lightboxes.\n"
                "[Camera & Visuals]\n"
                "- Rich warm twilight atmosphere, lips strictly closed throughout.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Crisp paper rustle of passbook, distant evening street murmur, zero spoken dialogue, zero music."
            ),
            "vo_job": {
                "voice": v_yexun,
                "duration": 6,
                "text": "两千八暑期工存款，哪怕摆摊，这一世绝不再给白眼狼熬一滴油！",
                "dst_start": 1.6,
            },
        },
        {
            "id": "1-3-04",
            "episode": 1,
            "duration": 14,
            "seed": 1304,
            "description": "叶寻偶遇抱会计课本与旺铺急转红纸的青梅夏芊芊，正询问时街尾夏氏小厨突然传出摔盘巨响与叫骂，两人飞奔而去！",
            "dialogue": "夏芊芊：小寻？上晚市了不在街中段林家帮忙，怎么往街尾跑？\n[VO] 叶寻：青梅夏芊芊，财会系学姐，前世只有她劝我提防楚南！\n叶寻：芊芊姐，夏叔出什么事了？",
            "assetNames": ["重庆大学外沙正街黄昏老街", "叶寻", "夏芊芊"],
            "ref_images": [kf("1-3-04"), f_yexun, f_qian],
            "ref_audios": [v_qian, v_yexun],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young man on the left steadying the books in <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The young woman on the right holding textbooks and red flyers in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Medium two-shot framed from <Picture 1> on the dusk sidewalk.\n"
                "- [Shot 2] (4.8s-8.8s) Close-up on <Subject 1> steadying the red flyers in her arms while looking at her warmly with lips closed.\n"
                "- [Shot 3] (8.8s-14.0s) Medium two-shot as <Subject 1> asks a question, porcelain shatters loudly down the street, and both sprint toward the glowing shop ahead!\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.6s): Catching her breath as <Subject 1> steadies her slipping textbooks, <Subject 2> (S1) looks at him in surprise and speaks: <d>[Chinese] 小寻？上晚市了不在街中段林家帮忙，怎么往街尾跑？</d>\n"
                "- [Shot 2] (4.8s-8.8s): Keeping his lips completely closed, <Subject 1> gazes at <Subject 2> with quiet warmth, then glances down at the stack of bright red transfer flyers in her arms.\n"
                "- [Shot 3] (8.9s-11.4s): Looking concerned, <Subject 1> (S2) asks urgently: <d>[Chinese] 芊芊姐，夏叔出什么事了？</d>\n"
                "- [Shot 3] (11.5s-14.0s): Suddenly a loud crash of shattering porcelain erupts from the lit eatery thirty meters down the street! <Subject 2>'s face pales and both bolt forward down the sidewalk toward the eatery!\n"
                "[Environment]\n"
                "- 2005 Chongqing Shazheng Street at dusk with warm eatery lights down the block.\n"
                "[Camera & Visuals]\n"
                "- Crisp acting beats: surprise encounter -> silent warm recognition (4.8s-8.8s lips closed) -> sudden loud crash and urgent sprint cliffhanger.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Clear female and male dialogue, quiet pause from 4.8s to 8.8s, sharp porcelain crash at 11.6s, urgent running footsteps, zero music."
            ),
            "vo_job": {
                "voice": v_yexun,
                "duration": 5,
                "text": "青梅夏芊芊，财会系学姐，前世只有她劝我提防楚南！",
                "dst_start": 4.9,
            },
        },
    ]

    # ==================== EPISODE 2 (10 SHOTS = 115s) ====================
    ep2 = [
        {
            "id": "2-1-01",
            "episode": 2,
            "duration": 13,
            "seed": 2101,
            "description": "夏氏小厨前厅满地碎瓷，临时厨师老王把菜刀剁在传菜木台上，趁夏建国手腕受伤勒索三千月薪并预支九千块。",
            "dialogue": "老王：老夏，少打感情牌！你五天前颠勺拉裂手腕筋，现在晚市三桌单子都下了，不签三千块长约、预支九千块，老子立马走人！\n夏建国：老王！上周说好六十块一天顶班，你趁上客坐地起价，让我上哪儿掏九千块？！",
            "assetNames": ["夏氏小厨前厅与传菜口", "夏建国", "老王"],
            "ref_images": [kf("2-1-01"), f_xia, f_wang],
            "ref_audios": [v_wang, v_xia],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The man with the white wrist bandage leaning on the wooden counter on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The stocky cook gripping the cleaver handle embedded in the pass counter on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.6s) Medium confrontation shot framed from <Picture 1> inside the small eatery.\n"
                "- [Shot 2] (7.6s-13.0s) Closer angle on <Subject 1> bracing his uninjured left hand on the counter in indignation.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-7.4s): Tapping the upright cleaver handle on the wooden pass counter above scattered porcelain shards, <Subject 2> (S1) glares greedily at <Subject 1> and speaks loudly: <d>[Chinese] 老夏，少打感情牌！你五天前颠勺拉裂手腕筋，现在晚市三桌单子都下了，不签三千块长约、预支九千块，老子立马走人！</d>\n"
                "- [Shot 2] (7.7s-12.3s): Breathing heavily and cradling his bandaged right wrist, <Subject 1> (S2) protests angrily: <d>[Chinese] 老王！上周说好六十块一天顶班，你趁上客坐地起价，让我上哪儿掏九千块？！</d>\n"
                "- [Shot 2] (12.3s-13.0s): <Subject 2> sneers with zero remorse.\n"
                "[Environment]\n"
                "- 2005 Chongqing small stir-fry eatery front room under warm incandescent bulbs.\n"
                "[Camera & Visuals]\n"
                "- High-tension realistic street-eatery confrontation, bandaged right wrist preserved accurately.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Thud of palm on wooden counter, loud raspy extortionate cook voice and indignant fatherly voice, zero music."
            ),
        },
        {
            "id": "2-1-04",
            "episode": 2,
            "duration": 12,
            "seed": 2104,
            "description": "夏芊芊冲进店护住父亲，老王摔下围裙煽动街坊散场，戴眼镜中年食客拎包起身准备离开。",
            "dialogue": "夏芊芊：王师傅，菜都点好了你趁火打劫——\n老王：没钱就贴红纸关门！各位街坊趁早换别家吃吧，老夏家今晚断灶了！\n中年食客：老夏，我们专门来捧场，没厨子你早说嘛，饿着肚子干等也不是事啊。",
            "assetNames": ["夏氏小厨前厅与传菜口", "夏芊芊", "夏建国", "老王", "中年食客"],
            "ref_images": [kf("2-1-04"), f_qian, f_xia, f_wang, f_diner],
            "ref_audios": [v_qian, v_wang, v_diner],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman shielding her father by the counter in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The man with the bandaged right wrist behind the counter in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3> (S2): The stocky cook in the center-right of <Picture 1>, matching <Picture 4>. Voice matches Audio 2.\n"
                "- <Subject 4> (S3): The diner holding a dark clutch bag rising from the right wooden table in <Picture 1>, matching <Picture 5>. Voice matches Audio 3.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.4s) Medium-wide front room shot framed from <Picture 1>.\n"
                "- [Shot 2] (7.4s-12.0s) Medium close-up on <Subject 4> standing beside the square wooden table.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-2.6s): Stepping protectively in front of <Subject 2>, <Subject 1> (S1) confronts <Subject 3>: <d>[Chinese] 王师傅，菜都点好了你趁火打劫——</d>\n"
                "- [Shot 1] (2.7s-7.3s): Cutting her off, <Subject 3> (S2) slams his dark kitchen cloth onto the counter and shouts toward the dining tables: <d>[Chinese] 没钱就贴红纸关门！各位街坊趁早换别家吃吧，老夏家今晚断灶了！</d>\n"
                "- [Shot 2] (7.5s-11.4s): Tucking his clutch bag under his arm, <Subject 4> (S3) sighs helplessly toward the counter: <d>[Chinese] 老夏，我们专门来捧场，没厨子你早说嘛，饿着肚子干等也不是事啊。</d>\n"
                "- [Shot 2] (11.4s-12.0s): <Subject 4> turns to step toward the doorway.\n"
                "[Environment]\n"
                "- Warmly lit 2005 neighborhood stir-fry eatery.\n"
                "[Camera & Visuals]\n"
                "- Clear spatial blocking across counter and dining table.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Slap of cloth on counter, wooden bench scrape, clear three-speaker dialogue, zero music."
            ),
        },
        {
            "id": "2-1-07",
            "episode": 2,
            "duration": 13,
            "seed": 2107,
            "description": "叶寻跨门拦住食客立下十分钟免单军令状，无视老王嘲讽，让夏芊芊结清六十块日工钱请老王腾地方。",
            "dialogue": "叶寻：叔，坐下喝口茶。十分钟热菜不上桌，今晚三桌全免单，算我的！\n夏建国：寻娃子？你怎么过来了！\n老王：案板上就剩副腥猪肝和鸭杂，你个穷学生拿嘴炒啊？\n叶寻：芊芊姐，结他六十块日工钱，请他腾地方。",
            "assetNames": ["夏氏小厨前厅与传菜口", "叶寻", "中年食客", "夏芊芊", "老王", "夏建国"],
            "ref_images": [kf("2-1-07"), f_yexun, f_diner, f_qian, f_wang, f_xia],
            "ref_audios": [v_yexun, v_xia, v_wang],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man stepping in on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The diner by the square table in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The young woman by the counter in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 4> (S3): The stocky cook crossing his arms on the right of <Picture 1>, matching <Picture 5>. Voice matches Audio 3.\n"
                "- <Subject 5> (S2): The man with the bandaged right wrist behind the counter in <Picture 1>, matching <Picture 6>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.5s) Medium shot framed from <Picture 1> as <Subject 1> steadies the room.\n"
                "- [Shot 2] (6.5s-13.0s) Medium two-shot as <Subject 4> sneers and <Subject 1> calmly dismisses him while <Subject 3> slaps banknotes on the counter.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.5s): Gesturing warmly toward the table, <Subject 1> (S1) speaks with calm authority: <d>[Chinese] 叔，坐下喝口茶。十分钟热菜不上桌，今晚三桌全免单，算我的！</d>\n"
                "- [Shot 1] (4.6s-6.4s): Behind the counter, <Subject 5> (S2) looks up in surprise: <d>[Chinese] 寻娃子？你怎么过来了！</d>\n"
                "- [Shot 2] (6.6s-10.1s): Folding his arms, <Subject 4> (S3) scoffs derisively at <Subject 1>: <d>[Chinese] 案板上就剩副腥猪肝和鸭杂，你个穷学生拿嘴炒啊？</d>\n"
                "- [Shot 2] (10.2s-12.5s): Without sparing <Subject 4> another glance, <Subject 1> (S1) turns to <Subject 3>: <d>[Chinese] 芊芊姐，结他六十块日工钱，请他腾地方。</d>\n"
                "- [Shot 2] (12.5s-13.0s): <Subject 3> slaps six ten-yuan banknotes onto the wooden counter.\n"
                "[Environment]\n"
                "- 2005 neighborhood eatery front dining hall.\n"
                "[Camera & Visuals]\n"
                "- Crisp pacing, decisive hero entrance, clear banknote slap.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Crisp four-turn dialogue, slap of paper bills on wood, zero music."
            ),
        },
        {
            "id": "2-2-01",
            "episode": 2,
            "duration": 11,
            "seed": 2201,
            "description": "后厨内叶寻握起爷爷十年前留下的旧厨刀，安慰夏建国这口灶凉不了，行云流水切出柳叶猪肝与十字花刀鸭胗。",
            "dialogue": "夏建国：十年前你爷爷教我吊高汤留下的刀。叔这一伤老客跑了一半，撑不过这个月了……\n叶寻：夏叔，有我在，这口灶凉不了。",
            "assetNames": ["夏氏小厨后厨猛火炒灶", "叶寻", "夏建国"],
            "ref_images": [kf("2-2-01"), f_yexun, f_xia],
            "ref_audios": [v_xia, v_yexun],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The young man standing at the wooden chopping block holding the traditional cleaver in <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The man with the white wrist bandage standing by the kitchen doorway on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-8.6s) Medium two-shot inside the traditional back kitchen framed from <Picture 1>.\n"
                "- [Shot 2] (8.6s-11.0s) Crisp close-up on the wooden chopping block as <Subject 1>'s blade slices paper-thin pork liver and cross-hatched duck gizzards.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.7s): Looking wistfully at the copper-ferrule cleaver in <Subject 1>'s hand, <Subject 2> (S1) sighs heavily: <d>[Chinese] 十年前你爷爷教我吊高汤留下的刀。叔这一伤老客跑了一半，撑不过这个月了……</d>\n"
                "- [Shot 1] (5.9s-8.5s): Testing the weight of the blade with steady confidence, <Subject 1> (S2) smiles reassuringly: <d>[Chinese] 夏叔，有我在，这口灶凉不了。</d>\n"
                "- [Shot 2] (8.6s-11.0s): Steel flashes swiftly and rhythmically across the wooden block, slicing fresh pork liver into uniform willow-leaf slices and scoring fine cross-hatch patterns onto duck gizzards.\n"
                "[Environment]\n"
                "- Warm tungsten-lit 2005 Chongqing small eatery back kitchen with brick wok stove and wooden prep table.\n"
                "[Camera & Visuals]\n"
                "- Authentic culinary craftsmanship, rapid precise knife work.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Warm emotional dialogue followed by rapid, crisp rhythmic knife-chopping SFX on wood, zero music."
            ),
        },
        {
            "id": "2-2-04",
            "episode": 2,
            "duration": 8,
            "seed": 2204,
            "description": "猛火宽油下泡椒仔姜，叶寻单手托锅连翻三个大勺，灶火窜起半米高，八分钟内泡椒嫩猪肝与仔姜爆鸭杂油亮出锅！",
            "dialogue": "",
            "assetNames": ["夏氏小厨后厨猛火炒灶", "叶寻"],
            "ref_images": [kf("2-2-04"), f_yexun],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The young man tossing the heavy iron wok over roaring flames in <Picture 1>, matching <Picture 2>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Dynamic medium close-up framed from <Picture 1> on the roaring brick wok range.\n"
                "- [Shot 2] (4.8s-8.0s) Close-up as glossy ruby-red pickled-chili pork liver and stir-fried ginger duck gizzards cascade onto a clean white porcelain plate.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.8s): Red pickled chilies and golden ginger sizzle violently in the seasoned iron wok; <Subject 1> grips the wooden handle single-handedly and tosses the ingredients three times in mid-air as golden-orange wok flames leap half a meter high, illuminating his focused eyes!\n"
                "- [Shot 2] (4.8s-8.0s): With a decisive sweep of the iron ladle, <Subject 1> plates the steaming, glossy, tender pickled-chili pork liver onto a white porcelain dish, rich aromatic steam rising.\n"
                "[Environment]\n"
                "- Traditional brick commercial wok stove in a 2005 Chongqing kitchen.\n"
                "[Camera & Visuals]\n"
                "- Mouth-watering high-contrast food cinematography, vibrant roaring wok-hei flames.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Roaring gas burner, explosive sizzling oil and wok-tossing clangs, ladling onto porcelain, zero dialogue, zero music."
            ),
        },
        {
            "id": "2-2-07",
            "episode": 2,
            "duration": 11,
            "seed": 2207,
            "description": "叶寻与夏芊芊端菜上桌，中年食客闻香夹起猪肝入口，眼睛骤亮大赞半点血腥气没有、比老王强出两条街！",
            "dialogue": "中年食客：半点血腥气没有，又滑又脆！老夏，这小伙子手艺比姓王的强出两条街！",
            "assetNames": ["夏氏小厨前厅与传菜口", "中年食客", "叶寻", "夏芊芊"],
            "ref_images": [kf("2-2-07"), f_diner, f_yexun, f_qian],
            "ref_audios": [v_diner],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The diner seated at the foreground wooden table holding chopsticks in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young man standing beside the table in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The young woman holding a white plate beside <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.6s) Medium close-up framed from <Picture 1> as <Subject 1> tastes the steaming dish.\n"
                "- [Shot 2] (4.6s-11.0s) Close-up on <Subject 1>'s delighted reaction as <Subject 2> and <Subject 3> smile warmly.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.6s): Fragrant white steam rises from the freshly served pickled-chili pork liver and ginger duck offal on the flat wooden table. <Subject 1> inhales the rich aroma, lifts a glossy tender slice with bamboo chopsticks, and takes a bite.\n"
                "- [Shot 2] (4.7s-10.3s): <Subject 1>'s eyes widen with genuine delight as he chews once, gives a thumbs-up toward the counter, and exclaims enthusiastically: <d>[Chinese] 半点血腥气没有，又滑又脆！老夏，这小伙子手艺比姓王的强出两条街！</d>\n"
                "- [Shot 2] (10.3s-11.0s): <Subject 2> and <Subject 3> exchange a relieved smile.\n"
                "[Environment]\n"
                "- Warmly lit 2005 neighborhood eatery front room with flat wooden tables.\n"
                "[Camera & Visuals]\n"
                "- Natural authentic diner reaction, appetizing steam on porcelain dishes.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Chopsticks tapping porcelain, natural chewing beat, enthusiastic authentic male praise, zero music."
            ),
        },
        {
            "id": "2-2-10",
            "episode": 2,
            "duration": 10,
            "seed": 2210,
            "description": "邻桌食客纷纷加点泡椒猪肝鸭杂与山城啤酒，老王脸色铁青，夏建国把转租红纸攥成团扔进废纸篓霸气送客！",
            "dialogue": "邻桌食客（画外）：老夏，我们也加份泡椒猪肝和爆鸭杂，再拿四瓶山城啤酒！\n夏建国：王师傅，好走不送！",
            "assetNames": ["夏氏小厨前厅与传菜口", "夏建国", "老王"],
            "ref_images": [kf("2-2-10"), f_xia, f_wang],
            "ref_audios": [v_xia],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man with the bandaged right wrist standing behind the wooden counter on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The stocky cook standing awkwardly by the doorframe on the right of <Picture 1>, matching <Picture 3>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.2s) Medium two-shot framed from <Picture 1> as <Subject 1> crumples the red transfer flyers.\n"
                "- [Shot 2] (5.2s-10.0s) Medium shot as <Subject 1> waves <Subject 2> out and <Subject 2> slinks away.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.2s): Keeping his lips closed with a proud, beaming smile as lively orders ring out from the dining room, <Subject 1> grabs the stack of red transfer flyers on the counter with his left hand, crumples them into a tight ball, and tosses it straight into the wastebasket!\n"
                "- [Shot 2] (5.5s-8.2s): Turning toward the doorway where <Subject 2>'s face flushes dark red with embarrassment, <Subject 1> (S1) waves his left hand briskly and speaks aloud: <d>[Chinese] 王师傅，好走不送！</d>\n"
                "- [Shot 2] (8.2s-10.0s): <Subject 2> lowers his head and scurries out the door into the night.\n"
                "[Environment]\n"
                "- Lively warm 2005 neighborhood eatery front counter.\n"
                "[Camera & Visuals]\n"
                "- Satisfying paper-crumpling gesture, <Subject 1>'s lips closed from 0s to 5.4s, clear comic-dramatic exit of <Subject 2>.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Crisp paper crumpling, lively restaurant clatter, proud fatherly send-off line at 5.5s, footsteps retreating, zero music."
            ),
            "vo_job": {
                "voice": v_shout,
                "duration": 5,
                "text": "老夏，我们也加份泡椒猪肝和爆鸭杂，再拿四瓶山城啤酒！",
                "dst_start": 0.4,
            },
        },
        {
            "id": "2-3-01",
            "episode": 2,
            "duration": 12,
            "seed": 2301,
            "description": "打烊后卷帘门拉下一半，夏芊芊拨算盘算清账上仅剩六千二，离十月一号一万八季度房租还差一万一千八。",
            "dialogue": "夏芊芊：今晚净落一百一十块，可账上总共只剩六千二。十月一号要交下季度房租一万八，还差一万一千八……剩二十天靠小炒怎么也填不上。",
            "assetNames": ["夏氏小厨前厅与传菜口", "夏芊芊", "夏建国", "叶寻"],
            "ref_images": [kf("2-3-01"), f_qian, f_xia, f_yexun],
            "ref_audios": [v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman seated by the wooden abacus and ledger on the right of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The man with the bandaged right wrist seated in the center of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The young man seated attentively on the left of <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-12.0s) Intimate late-night medium three-shot framed from <Picture 1> under the warm incandescent bulb.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-0.8s): <Subject 1> clicks the last wooden bead on the abacus and rests her hand on the open ledger with a quiet sigh.\n"
                "- [Shot 1] (0.8s-11.2s): Looking up earnestly at <Subject 2> and <Subject 3>, <Subject 1> (S1) speaks in a worried, realistic voice: <d>[Chinese] 今晚净落一百一十块，可账上总共只剩六千二。十月一号要交下季度房租一万八，还差一万一千八……剩二十天靠小炒怎么也填不上。</d>\n"
                "- [Shot 1] (11.2s-12.0s): <Subject 2> lowers his head in heavy silence while <Subject 3>'s eyes turn thoughtfully toward the idle iron cauldron in the corner.\n"
                "[Environment]\n"
                "- Half-shuttered 2005 neighborhood eatery late at night.\n"
                "[Camera & Visuals]\n"
                "- Grounded emotional realism, warm tungsten lighting.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Crisp click of wooden abacus beads, clear worried young female voice, quiet night room tone, zero music."
            ),
        },
        {
            "id": "2-3-04",
            "episode": 2,
            "duration": 12,
            "seed": 2304,
            "description": "叶寻看中百平临街熟铺与生铁大锅，将两千八存折拍在账本旁，提议入伙改开清润老火锅二十天挣出房租！",
            "dialogue": "[VO] 叶寻：一百一十平临街熟铺证照齐全，缺的只是一个高毛利爆品！\n叶寻：夏叔，芊芊姐，小炒翻不了身。我拿全部存款和爷爷传下的清润火锅方子入伙，咱们改开老火锅，二十天挣出房租！",
            "assetNames": ["夏氏小厨前厅与传菜口", "叶寻", "夏芊芊", "夏建国"],
            "ref_images": [kf("2-3-04"), f_yexun, f_qian, f_xia],
            "ref_audios": [v_yexun],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man standing on the left slapping the red passbook onto the table in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young woman seated at the table on the right of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The man with the bandaged right wrist seated beside <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.3s) Medium shot as <Subject 1> glances from the idle iron cauldron in the corner to the table and slaps down his red passbook with lips closed.\n"
                "- [Shot 2] (4.3s-12.0s) Medium close-up framed from <Picture 1> as <Subject 1> pitches the hotpot partnership.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.3s): Keeping his lips firmly closed in sharp calculation, <Subject 1> glances at the large cast-iron cauldron leaning in the back corner, pulls his red passbook from his pocket, and slaps it decisively onto the wooden table beside the ledger.\n"
                "- [Shot 2] (4.5s-11.3s): Leaning forward with bright, unwavering conviction, <Subject 1> (S1) speaks clearly to <Subject 3> and <Subject 2>: <d>[Chinese] 夏叔，芊芊姐，小炒翻不了身。我拿全部存款和爷爷传下的清润火锅方子入伙，咱们改开老火锅，二十天挣出房租！</d>\n"
                "- [Shot 2] (11.3s-12.0s): <Subject 3> looks up in stunned hope.\n"
                "[Environment]\n"
                "- Late-night eatery interior with the idle cast-iron cauldron visible in the background corner.\n"
                "[Camera & Visuals]\n"
                "- Lips strictly closed from 0s to 4.4s, crisp passbook slap, strong persuasive presence.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Firm slap of passbook on wooden table at 3.8s, confident young male dialogue starting at 4.5s, zero music."
            ),
            "vo_job": {
                "voice": v_yexun,
                "duration": 5,
                "text": "一百一十平临街熟铺证照齐全，缺的只是一个高毛利爆品！",
                "dst_start": 0.3,
            },
        },
        {
            "id": "2-3-07",
            "episode": 2,
            "duration": 13,
            "seed": 2307,
            "description": "夏芊芊手指收紧按住账本直视叶寻，犀利质问他是真心合伙还是跟林双双赌气拿父亲救命钱当筏子！",
            "dialogue": "夏芊芊：叶寻，林双双家馆子就在前头一百米，整条街谁不知道你对她百依百顺了两年？你今晚突然拿存折来我家开火锅，到底是真心合伙，还是跟她赌气、拿我爸最后的救命钱当筏子？",
            "assetNames": ["夏氏小厨前厅与传菜口", "夏芊芊", "叶寻", "夏建国"],
            "ref_images": [kf("2-3-07"), f_qian, f_yexun, f_xia],
            "ref_audios": [v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young woman pressing her hand on the ledger on the right of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young man standing across the table on the left of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The man with the bandaged right wrist watching tensely in the center of <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.0s) Medium close-up framed from <Picture 1> tightening on <Subject 1>'s clear, probing gaze.\n"
                "- [Shot 2] (7.0s-13.0s) Tight two-shot holding the razor-sharp eye lock between <Subject 1> and <Subject 2>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-0.6s): <Subject 1>'s fingers tighten firmly on the edge of the paper ledger instead of reaching for the red passbook.\n"
                "- [Shot 1] (0.6s-6.9s): Fixing <Subject 2> straight in the eyes without blinking, <Subject 1> (S1) speaks in a calm, piercing voice: <d>[Chinese] 叶寻，林双双家馆子就在前头一百米，整条街谁不知道你对她百依百顺了两年？</d>\n"
                "- [Shot 2] (7.0s-12.2s): Leaning slightly forward under the warm bulb, <Subject 1> (S1) finishes her sharp question: <d>[Chinese] 你今晚突然拿存折来我家开火锅，到底是真心合伙，还是跟她赌气、拿我爸最后的救命钱当筏子？</d>\n"
                "- [Shot 2] (12.2s-13.0s): Silence hangs taut in the room as <Subject 2> meets her gaze steadily and <Subject 3> holds his breath!\n"
                "[Environment]\n"
                "- Quiet late-night eatery under a single warm incandescent lamp.\n"
                "[Camera & Visuals]\n"
                "- Gripping dramatic cliffhanger close-ups, intelligent clear-headed female lead acting.\n"
                "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n"
                "- Subtle fingers pressing paper ledger, clear sharp probing female dialogue, tense silent beat at end, zero music."
            ),
        },
    ]

    return ep1, ep2


def trim_silence_bounds(wav_or_mp4: Path) -> tuple[float, float]:
    """Find actual speech [start, end] inside a short dry 368p VO clip so we don't slice dead air."""
    probe = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(wav_or_mp4)],
        text=True,
    ))
    dur = float(probe["format"]["duration"])
    proc = subprocess.run(
        ["ffmpeg", "-i", str(wav_or_mp4), "-af", "silencedetect=noise=-36dB:d=0.20", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    import re
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", proc.stderr)]
    s0 = 0.05
    if starts and starts[0] < 0.15 and ends:
        s0 = max(0.0, ends[0] - 0.06)
    e0 = dur - 0.05
    if starts and starts[-1] > s0 + 0.5:
        # Only trim trailing silence if no speech resumes after it
        last_s = starts[-1]
        if not ends or ends[-1] < last_s:
            e0 = min(dur, last_s + 0.12)
    return round(s0, 3), round(max(s0 + 0.4, e0), 3)


def run_one_shot(spec: dict, outdir: Path, force: bool = False):
    sid = spec["id"]
    sdir = outdir / sid
    sdir.mkdir(parents=True, exist_ok=True)
    final_mp4 = sdir / "video.mp4"
    final_meta = sdir / "video.json"
    if final_mp4.is_file() and final_meta.is_file() and not force:
        print(f"[skip] {sid} already exists", flush=True)
        return

    vo_job = spec.get("vo_job")
    if not vo_job:
        pika_runner.run_shot(spec, outdir, CACHE_1K, resolution="480p", force=force)
        return

    # Has vo_job: run 480p base on 5090 AND short 368p dry VO clip on 4070 Ti SUPER in parallel!
    base_mp4 = sdir / "video_base.mp4"
    vo_mp4 = sdir / "vo_short_368p.mp4"
    refs_1k = [pika_runner.ensure_1k_image(Path(p), CACHE_1K) for p in spec["ref_images"]]
    audios = [Path(p) for p in spec.get("ref_audios", [])]
    vo_prompt = (
        "[Subject]\n"
        "- <Subject 1> (S1): The speaker in <Picture 1>. Voice matches Audio 1.\n"
        "[Shot]\n"
        f"- [Shot 1] (0s-{vo_job['duration']}s) Static close-up framed from <Picture 1>.\n"
        "[Timeline]\n"
        f"- [Shot 1] (0.1s-{vo_job['duration'] - 0.2:.1f}s): <Subject 1> (S1) speaks clearly and expressively at a crisp natural pace: <d>[Chinese] {vo_job['text']}</d>\n"
        "[Environment]\n- Quiet dry room.\n[Camera & Visuals]\n- Static.\n"
        "- Clean unsubtitled cinema frame, strictly no on-screen text, captions, or subtitles.\n"                "[Audio]\n- Clean dry close-mic voice matching Audio 1, zero background noise, zero music."
    )
    print(f"[start+vo_job] {sid} ({spec['duration']}s 480p + {vo_job['duration']}s 368p VO)", flush=True)
    old_ckpt = vo_split.LOWRES_CHECKPOINT
    vo_split.LOWRES_CHECKPOINT = ""
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            if base_mp4.is_file() and base_mp4.with_suffix(".json").is_file() and not force:
                fut_base = pool.submit(lambda: json.loads(base_mp4.with_suffix(".json").read_text(encoding="utf-8")))
            else:
                fut_base = pool.submit(
                    pika_runner.call_pika_5090,
                    base_mp4, spec["prompt"], int(spec["duration"]), int(spec["seed"]), "9:16", "480p", refs_1k, audios,
                )
            fut_vo = pool.submit(
                vo_split.h3_lowres,
                vo_mp4, vo_prompt, int(vo_job["duration"]), int(spec["seed"]) + 77, "9:16", "reference", refs_1k[-1:], None, None, [Path(vo_job["voice"])],
            )
            meta = fut_base.result()
            vo_hdr = fut_vo.result()
    finally:
        vo_split.LOWRES_CHECKPOINT = old_ckpt

    ss, se = trim_silence_bounds(vo_mp4)
    pika_runner.place_vo_segments(
        base_mp4=base_mp4,
        vo_mp4=vo_mp4,
        segments=[(ss, se, float(vo_job["dst_start"]))],
        out_mp4=final_mp4,
        base_duck=0.28,
        vo_gain=1.65,
        raw_slice=True,
    )
    meta["vo_job_applied"] = {"src": [ss, se], "dst_start": vo_job["dst_start"], "vo_headers": vo_hdr}
    final_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done+vo_job] {sid} -> VO [{ss}..{se}] placed at {vo_job['dst_start']}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lint-only", action="store_true")
    ap.add_argument("--ep", type=int, choices=[1, 2], default=0, help="0 = both Ep 1 and Ep 2")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    ep1, ep2 = build_plans()
    (WORK_DIR / "ep01_v2_plan.json").write_text(json.dumps(ep1, ensure_ascii=False, indent=2), encoding="utf-8")
    (WORK_DIR / "ep02_v2_plan.json").write_text(json.dumps(ep2, ensure_ascii=False, indent=2), encoding="utf-8")

    all_issues = []
    for s in ep1 + ep2:
        all_issues.extend(pika_runner.lint_zero_appearance(s["prompt"], s["id"]))
    if all_issues:
        print("LINT FAILED:\n" + "\n".join(all_issues), file=sys.stderr)
        sys.exit(2)
    print(f"LINT PASSED: 0 issues across {len(ep1)} Ep1 shots + {len(ep2)} Ep2 shots!", flush=True)
    if args.lint_only:
        return

    targets = []
    if args.ep in (0, 1):
        targets.extend((s, TAKES_EP1) for s in ep1)
    if args.ep in (0, 2):
        targets.extend((s, TAKES_EP2) for s in ep2)
    if args.only:
        only_set = set(args.only)
        targets = [(s, d) for (s, d) in targets if s["id"] in only_set]

    for s, outdir in targets:
        run_one_shot(s, outdir, force=args.force)


if __name__ == "__main__":
    main()
