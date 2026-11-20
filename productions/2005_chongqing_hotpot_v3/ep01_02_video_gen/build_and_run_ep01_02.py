#!/usr/bin/env python3
"""
Compile & execute Episode 1 (9 groups) & Episode 2 (9 groups) hotpot_v3 480p video generation
on local 5090 Pika-H3-Flex + 4070 Ti SUPER 368p short dry VO clips, enforcing:
  - <=1K reference image invariant
  - Zero character appearance/garment tokens + zero <d> speaker-name pollution
  - Pure 35mm theatrical cinema framing + comma/period <d> punctuation (prevents burned-in subtitle hallucinations)
  - Explicit male speaker face_1k for 4070 VO clips + non-overlapping muted base VO windows
"""
from __future__ import annotations
import argparse
import json
import re
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

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v3/ep01_02_video_gen")
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
    v_youcai = amap["林有才"]["voice"]
    v_zhou = amap["周有福"]["voice"]
    v_chen = amap["陈科长"]["voice"]

    f_ye_apron = amap["叶寻 · 渝清记围裙掌勺"]["front_1k"]
    f_ye_clean = amap["叶寻_脱围裙"]["front_1k"]
    f_qian = amap["夏芊芊"]["front_1k"]
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    f_youcai = amap["林有才"]["front_1k"]
    f_zhou = amap["周有福"]["front_1k"]
    f_chen = amap["陈科长"]["front_1k"]

    # ==================== EPISODE 1 (9 SHOTS = 104s) ====================
    ep1 = [
        {
            "id": "1-1-01",
            "episode": 1,
            "duration": 10,
            "seed": 31101,
            "description": "2005年夏夜林记火锅大堂，叶寻端红亮底料上桌，林双双挽着楚南嫌恶掩鼻，把半页汤谱拍在叶寻胸口退婚逼方。",
            "dialogue": "林双双：把你叶家清润汤剩下几味草本补全，咱俩婚约算完了。",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林双双", "楚南"],
            "ref_images": [kf("1-1-01"), f_ye_apron, f_lin, f_chu],
            "ref_audios": [v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man standing on the left beside the wooden table in <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The woman standing in the center-right of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3>: The man standing arm-in-arm beside <Subject 2> on the right of <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-2.6s) Medium three-shot framed from <Picture 1> inside the warm 2005 restaurant hall.\n"
                "- [Shot 2] (2.6s-10.0s) Medium close-up favoring <Subject 2> and <Subject 1> as she slaps the half-sheet paper onto his chest.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-2.4s): Covering her nose disdainfully beside <Subject 3>, <Subject 2> presses the yellowed half-sheet paper hard against <Subject 1>'s chest as <Subject 1> steadies the gleaming pot of red hotpot base on the wooden table.\n"
                "- [Shot 2] (2.6s-8.6s): Lowering her hand from her nose and raising her chin arrogantly beside <Subject 3>'s smug grin, <Subject 2> (S1) speaks in a cold, dismissive tone: <d>[Chinese] 把你叶家清润汤剩下几味草本补全，咱俩婚约算完了。</d>\n"
                "- [Shot 2] (8.6s-10.0s): <Subject 1> takes the half-sheet paper from his chest, staring at her with his jaw tightening.\n"
                "[Environment]\n"
                "- Warm tungsten-lit 2005 Chongqing restaurant hall on a humid summer night.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, natural eye lines and lip-sync.\n"
                "[Audio]\n"
                "- Brass pot set on wood, crisp slap of paper against chest, clear arrogant female Mandarin dialogue, subtle fan hum, zero music."
            ),
        },
        {
            "id": "1-1-02",
            "episode": 1,
            "duration": 12,
            "seed": 31102,
            "description": "叶寻低头看清手背旧烫痕与半页汤谱确认重回2005年，楚南揽着林双双当面羞辱叶寻是满身牛油味的伙夫。",
            "dialogue": "[VO] 叶寻：重回2005年？前世我交出祖传秘方，反被他们榨干赶出老街！\n楚南：双双马上进我楚氏餐饮当主管，能嫁你个满身牛油味的伙夫？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "楚南", "林双双"],
            "ref_images": [kf("1-1-02"), f_ye_apron, f_chu, f_lin],
            "ref_audios": [v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man in the left foreground of <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The man on the right of <Picture 1> with one arm around <Subject 3>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3>: The woman standing beside <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.4s) Close-up on <Subject 1> glancing down at the faint burn mark on his hand and the half-sheet paper.\n"
                "- [Shot 2] (5.4s-12.0s) Medium close-up reverse angle on <Subject 2> and <Subject 3>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.4s): Keeping his lips firmly closed in silent shock and fierce realization, <Subject 1> stares down at his right hand and the yellowed half-sheet paper, then lifts his eyes with ice-cold clarity.\n"
                "- [Shot 2] (5.7s-10.8s): <Subject 2> (S1) pats <Subject 3>'s shoulder and sneers condescendingly at <Subject 1>: <d>[Chinese] 双双马上进我楚氏餐饮当主管，能嫁你个满身牛油味的伙夫。</d>\n"
                "- [Shot 2] (10.8s-12.0s): <Subject 3> looks at <Subject 1> with open contempt.\n"
                "[Environment]\n"
                "- Warm-lit 2005 Chongqing restaurant interior at night.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, <Subject 1>'s lips strictly closed from 0s to 5.5s.\n"
                "[Audio]\n"
                "- Quiet paper rustle from 0s to 5.5s, arrogant male dialogue starting at 5.7s, subtle restaurant room tone, zero music."
            ),
            "vo_custom": {
                "face_1k": f_ye_clean,
                "voice": v_yexun,
                "duration": 6,
                "text": "重回二零零五年，前世我交出祖传秘方，反被他们榨干赶出老街。",
                "dst_start": 0.25,
                "max_len": 5.0,
            },
        },
        {
            "id": "1-1-03",
            "episode": 1,
            "duration": 13,
            "seed": 311035,
            "description": "林有才敲桌逼叶寻留方抵四年白吃之恩，叶寻当场将半页汤谱撕碎扔进桌上凉水壶，林双双气急尖叫。",
            "dialogue": "林有才：白吃我家四年，留张方子抵恩，是你的本分！\n林双双：叶寻你疯了！敢撕我家的方子？",
            "assetNames": ["沙正街林家食府老店大堂", "林有才", "叶寻 · 渝清记围裙掌勺", "林双双"],
            "ref_images": [kf("1-1-03"), f_youcai, f_ye_apron, f_lin],
            "ref_audios": [v_youcai, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The older man holding the lidded teacup on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The man holding the half-sheet paper above the glass water pitcher in the center of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3> (S2): The woman on the right of <Picture 1>, matching <Picture 4>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.6s) Medium three-shot framed from <Picture 1> as <Subject 1> raps his knuckles on the wooden table.\n"
                "- [Shot 2] (4.6s-7.4s) Crisp medium close-up on <Subject 2> ripping the paper sheet in half and dropping the shreds into the glass water pitcher.\n"
                "- [Shot 3] (7.4s-13.0s) Medium close-up on <Subject 3> recoiling in fury.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.4s): Rapping his knuckles heavily on the tabletop, <Subject 1> (S1) glares at <Subject 2> and speaks sternly: <d>[Chinese] 白吃我家四年，留张方子抵恩，是你的本分。</d>\n"
                "- [Shot 2] (4.6s-7.3s): Without a word, <Subject 2> rips the yellowed paper sheet cleanly into shreds with both hands and drops the torn pieces straight into the clear water pitcher on the table.\n"
                "- [Shot 3] (7.6s-11.2s): <Subject 3> (S2) stares at the water pitcher in disbelief and snaps angrily and briskly: <d>[Chinese] 叶寻你疯了，敢撕我家的方子。</d>\n"
                "- [Shot 3] (11.2s-13.0s): <Subject 2> meets her gaze with icy calm.\n"
                "[Environment]\n"
                "- 2005 Chongqing restaurant dining table at night.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, crisp physical paper-tearing action.\n"
                "[Audio]\n"
                "- Knuckle rap on wood, raspy authoritative older male voice, sharp paper rip and splash in pitcher, angry female voice, zero music."
            ),
        },
        {
            "id": "1-1-04",
            "episode": 1,
            "duration": 10,
            "seed": 31104,
            "description": "叶寻拿出掉漆铁盒，将四十八张邮政汇款存根重重拍在桌上打脸四年供读真相，林双双涨红脸慌忙按住单据。",
            "dialogue": "叶寻：我辍学熬四年牛油，四十八张汇款单供你读完大学，两清了！",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻 · 渝清记围裙掌勺", "林双双", "林有才"],
            "ref_images": [kf("1-1-04"), f_ye_apron, f_lin, f_youcai],
            "ref_audios": [v_yexun],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man holding the chipped tin box on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The woman standing on the right of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The older man standing behind <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.4s) Medium close-up framed from <Picture 1> as <Subject 1> slams his hand onto the thick stack of postal money-order stubs on the table.\n"
                "- [Shot 2] (7.4s-10.0s) Close-up on <Subject 2> flushing with shame and pressing her hands over the scattered money-order slips.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-1.2s): Pressing his right palm firmly onto the thick spread of postal remittance slips on the wooden tabletop, <Subject 1> taps the slips sharply so they fan across the wood.\n"
                "- [Shot 1] (1.3s-7.2s): Locking cold, piercing eyes onto <Subject 2>, <Subject 1> (S1) speaks with forceful clarity: <d>[Chinese] 我辍学熬四年牛油，四十八张汇款单供你读完大学，两清了。</d>\n"
                "- [Shot 2] (7.4s-10.0s): <Subject 2>'s face flushes crimson as she reflexively presses her hands over the remittance slips while <Subject 3> looks away stiffly.\n"
                "[Environment]\n"
                "- 2005 Chongqing restaurant wooden table at night.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, crisp facial acting and lip-sync.\n"
                "[Audio]\n"
                "- Heavy slap of paper stack on wood, firm resonant male Mandarin voice, flustered paper rustle, zero music."
            ),
        },
        {
            "id": "1-1-05",
            "episode": 1,
            "duration": 11,
            "seed": 31105,
            "description": "叶寻扯下围裙甩进废纸篓宣布撤火走人，林有才拦门叫嚣离了林记整条街没人敢要他。",
            "dialogue": "叶寻：今晚起火我撤了，看你们拿什么端上桌！\n林有才：忘恩负义的东西！离了林记，这条街谁敢要你？",
            "assetNames": ["沙正街林家食府老店大堂", "叶寻", "林有才", "林双双"],
            "ref_images": [kf("1-1-05"), f_ye_clean, f_youcai, f_lin],
            "ref_audios": [v_yexun, v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man standing near the open doorway on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The older man pointing angrily on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The woman standing frozen by the table in the background of <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.4s) Medium shot framed from <Picture 1> as <Subject 1> flings the crumpled kitchen cloth into the bamboo basket.\n"
                "- [Shot 2] (5.4s-11.0s) Medium shot as <Subject 2> shouts at <Subject 1>'s departing back.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-1.2s): <Subject 1> tosses the crumpled brown kitchen cloth into the bamboo wastebasket beside the doorframe.\n"
                "- [Shot 1] (1.3s-5.2s): Turning half-back with cold resolve, <Subject 1> (S1) declares clearly: <d>[Chinese] 今晚起火我撤了，看你们拿什么端上桌。</d>\n"
                "- [Shot 2] (5.5s-9.8s): <Subject 1> strides out the open doorway into the night street while <Subject 2> (S2) points after him and shouts angrily: <d>[Chinese] 忘恩负义的东西，离了林记，这条街谁敢要你。</d>\n"
                "- [Shot 2] (9.8s-11.0s): <Subject 1> walks straight ahead without looking back.\n"
                "[Environment]\n"
                "- Open wooden doorway of a 2005 Chongqing restaurant leading onto the night street.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, decisive movement and lip-sync.\n"
                "[Audio]\n"
                "- Cloth thudding into bamboo basket, resolute young male voice, furious older male shout, brisk footsteps, zero music."
            ),
        },
        {
            "id": "1-2-01",
            "episode": 1,
            "duration": 13,
            "seed": 312015,
            "description": "叶寻跨进对门桌灶鲜菜备齐的夏记小院立誓护住夏芊芊，夏芊芊抱出账本笔墨无条件信任迎他掌勺。",
            "dialogue": "[VO] 叶寻：前世只有世交芊芊护我到底，这辈子换我撑起夏记！\n夏芊芊：叶爷爷熬汤真传我从小看着！林家瞎了眼，夏记迎你掌勺！",
            "assetNames": ["桂花巷渝清记大堂与天井", "叶寻", "夏芊芊"],
            "ref_images": [kf("1-2-01"), f_ye_clean, f_qian],
            "ref_audios": [v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man standing on the left inside the lantern-lit courtyard in <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The woman holding the ledger book, brush, and inkpad box on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Medium two-shot framed from <Picture 1> inside the warm courtyard lined with wooden hotpot tables and brass pots.\n"
                "- [Shot 2] (4.8s-13.0s) Medium close-up on <Subject 2> setting the ledger and red inkpad onto the wooden table and welcoming <Subject 1> warmly.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.8s): Keeping his lips closed with warm gratitude in his eyes, <Subject 1> takes in the neat wooden tables, brass pots, and baskets of fresh greens as <Subject 2> sets the ledger book and red inkpad onto the wooden table.\n"
                "- [Shot 2] (5.0s-11.2s): Looking brightly at <Subject 1>, <Subject 2> (S1) speaks briskly with warm conviction: <d>[Chinese] 叶爷爷熬汤真传我从小看着，林家瞎了眼，夏记迎你掌勺。</d>\n"
                "- [Shot 2] (11.2s-13.0s): <Subject 1> nods firmly with a slight warm smile.\n"
                "[Environment]\n"
                "- Warm string-lit 2005 Chongqing courtyard hotpot shop at night.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, <Subject 1>'s lips strictly closed throughout.\n"
                "[Audio]\n"
                "- Gentle night courtyard ambiance from 0s to 5.1s, ledger set on wood, crisp warm female Mandarin voice starting at 5.3s, zero music."
            ),
            "vo_custom": {
                "face_1k": f_ye_clean,
                "voice": v_yexun,
                "duration": 6,
                "text": "前世只有世交芊芊护我到底，这辈子换我撑起夏记。",
                "dst_start": 0.25,
                "max_len": 4.6,
            },
        },
        {
            "id": "1-2-02",
            "episode": 1,
            "duration": 10,
            "seed": 31202,
            "description": "夏芊芊立下五五分账合营契书推过印泥，叶寻并排摁下鲜红手印结成同盟。",
            "dialogue": "夏芊芊：五五分账，往后咱俩一口锅里搅马勺！",
            "assetNames": ["桂花巷渝清记大堂与天井", "夏芊芊", "叶寻"],
            "ref_images": [kf("1-2-02"), f_qian, f_ye_clean],
            "ref_audios": [v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The woman on the right of the wooden table in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The man on the left pressing his red-inked thumb onto the contract paper in <Picture 1>, matching <Picture 3>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.6s) Medium close-up over the wooden table framed from <Picture 1> as <Subject 2> presses his red thumbprint beside hers.\n"
                "- [Shot 2] (3.6s-10.0s) Medium two-shot on <Subject 1> and <Subject 2> smiling across the signed partnership sheet.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-3.6s): <Subject 2> presses his red-inked right thumb firmly onto the rice-paper contract right beside <Subject 1>'s red print, then lifts his thumb leaving two bright red prints side by side.\n"
                "- [Shot 2] (3.8s-8.6s): Beaming with crisp camaraderie, <Subject 1> (S1) taps the edge of the contract and speaks cheerfully: <d>[Chinese] 五五分账，往后咱俩一口锅里搅马勺。</d>\n"
                "- [Shot 2] (8.6s-10.0s): <Subject 2> nods firmly in agreement as footsteps approach outside the gate.\n"
                "[Environment]\n"
                "- Warm lantern-lit courtyard wooden table at night.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, clear thumbprint action and natural lip-sync.\n"
                "[Audio]\n"
                "- Firm press on paper, bright spirited female Mandarin voice, approaching footsteps on stone at the end, zero music."
            ),
        },
        {
            "id": "1-2-03",
            "episode": 1,
            "duration": 15,
            "seed": 31203,
            "description": "楚南与林双双堵门嚣张宣布明早断绝夏记全部成品牛油，并亮出红纸定单炫耀已将机械厂十二桌庆功席截胡改签林记。",
            "dialogue": "楚南：夏芊芊，敢收他？明早断你夏记全部成品牛油，看你拿什么交房租！\n林双双：你们备好菜的机械厂十二桌席，周厂长刚改签给林记了！",
            "assetNames": ["重庆老街对门双火锅铺街景", "楚南", "林双双", "夏芊芊", "叶寻"],
            "ref_images": [kf("1-2-03"), f_chu, f_lin, f_qian, f_ye_clean],
            "ref_audios": [v_chu, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man holding the mobile phone on the right outside the doorway in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The woman holding up the red banquet order slip beside <Subject 1> in <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The woman standing on the left inside the threshold in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 4>: The man standing calmly beside <Subject 3> in <Picture 1>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.6s) Medium confrontation shot framed from <Picture 1> at the lantern-lit bluestone doorway.\n"
                "- [Shot 2] (7.6s-15.0s) Closer medium shot on <Subject 2> waving the red order slip triumphantly before <Subject 3> and <Subject 4>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-7.4s): Twirling his mobile phone arrogantly at the gate, <Subject 1> (S1) sneers at <Subject 3> and <Subject 4> and speaks loudly: <d>[Chinese] 夏芊芊，敢收他，明早断你夏记全部成品牛油，看你拿什么交房租。</d>\n"
                "- [Shot 2] (7.7s-13.4s): <Subject 2> (S2) shakes the red paper slip in her hand with a gloating smirk and speaks sharply: <d>[Chinese] 你们备好菜的机械厂十二桌席，周厂长刚改签给林记了。</d>\n"
                "- [Shot 2] (13.4s-15.0s): <Subject 1> laughs smugly and turns away with <Subject 2> while <Subject 3>'s brows furrow.\n"
                "[Environment]\n"
                "- Nighttime lantern-lit 2005 Chongqing bluestone street outside the hotpot shop.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, sharp dramatic eye lines and lip-sync.\n"
                "[Audio]\n"
                "- Arrogant male voice, crisp rustle of paper slip, gloating female voice, quiet night alley ambiance, zero music."
            ),
        },
        {
            "id": "1-2-04",
            "episode": 1,
            "duration": 12,
            "seed": 31204,
            "description": "夏芊芊发愁成品牛油断供，叶寻推出平板三轮车带夏芊芊连夜赶往屠宰场抢头刀鲜牛板油现熬破局。",
            "dialogue": "夏芊芊：成品牛油全断了，明早拿什么开火？\n叶寻：不用陈年老油！坐稳，去屠宰场抢今晚头刀鲜牛板油！\n夏芊芊：走！我跟你去！",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻", "夏芊芊"],
            "ref_images": [kf("1-2-04"), f_ye_clean, f_qian],
            "ref_audios": [v_qian, v_yexun],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The man gripping the handlebars of the flatbed tricycle on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The woman seated on the rear wooden cart of the tricycle on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.6s) Medium two-shot framed from <Picture 1> on the lantern-lit bluestone street.\n"
                "- [Shot 2] (3.6s-12.0s) Dynamic medium shot as <Subject 1> calls back confidently, <Subject 2> grips the cart rail eagerly, and <Subject 1> pedals forward.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-3.5s): Gripping the wooden side rail of the rear tricycle cart with an anxious frown, <Subject 2> (S1) asks urgently: <d>[Chinese] 成品牛油全断了，明早拿什么开火。</d>\n"
                "- [Shot 2] (3.7s-8.6s): Gripping the steel handlebars firmly, <Subject 1> (S2) looks back over his shoulder with fiery confidence and speaks briskly: <d>[Chinese] 不用陈年老油，坐稳，去屠宰场抢今晚头刀鲜牛板油。</d>\n"
                "- [Shot 2] (8.7s-10.4s): <Subject 2>'s eyes light up with excitement as she braces both hands on the cart rail and calls out: <d>[Chinese] 走，我跟你去。</d>\n"
                "- [Shot 2] (10.4s-12.0s): <Subject 1> pushes down hard on the pedals, rolling the tricycle forward into the warm lantern-lit night street.\n"
                "[Environment]\n"
                "- Nighttime 2005 Chongqing bluestone street under warm streetlamps.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, energetic pacing and crisp lip-sync.\n"
                "[Audio]\n"
                "- Urgent female question, confident young male reply, metallic creak of tricycle chain and rolling wheels on stone, zero music."
            ),
        },
    ]

    # ==================== EPISODE 2 (9 SHOTS = 108s) ====================
    ep2 = [
        {
            "id": "2-1-01",
            "episode": 2,
            "duration": 9,
            "seed": 32101,
            "description": "次日清晨老街晨光中，叶寻在夏记门前两口生铁大锅内慢熬雪白鲜牛板油，夏芊芊用细纱布滤出淡竹叶与山栀子清液。",
            "dialogue": "",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻 · 渝清记围裙掌勺", "夏芊芊"],
            "ref_images": [kf("2-1-01"), f_ye_apron, f_qian],
            "ref_audios": [],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man stirring the iron cauldron with a long copper ladle on the left of <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2>: The woman filtering clear herbal liquid through white gauze on the right of <Picture 1>, matching <Picture 3>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.8s) Medium two-shot framed from <Picture 1> in crisp early-morning sunlight outside the hotpot shop.\n"
                "- [Shot 2] (4.8s-9.0s) Appetizing close-up on snowy fresh beef leaf-fat rendering into crystal-golden tallow in the iron cauldron, then tilting up to <Subject 1> and <Subject 2> exchanging a confident nod.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.8s): Morning mist drifts over the bluestone street. <Subject 1> steadily stirs blocks of snowy-white fresh beef fat sizzling gently in the big iron cauldron while <Subject 2> squeezes fine white gauze, filtering pale golden herbal infusion into a ceramic basin.\n"
                "- [Shot 2] (4.8s-9.0s): Clear golden tallow bubbles cleanly around the copper ladle; <Subject 1> and <Subject 2> exchange a silent, assured smile with lips closed.\n"
                "[Environment]\n"
                "- Fresh morning light on a 2005 Chongqing bluestone street outside the shop's brick cauldrons.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, rich culinary texture and rising steam.\n"
                "[Audio]\n"
                "- Rich gentle sizzle of rendering fresh tallow, copper ladle scraping iron pot, soft trickle of filtered liquid, morning birdsong, zero dialogue, zero music."
            ),
        },
        {
            "id": "2-1-02",
            "episode": 2,
            "duration": 13,
            "seed": 32102,
            "description": "对门林记后厨内，林有才照着偷瞄来的半截纸条将干药壳直接丢进发黑高温老油，炸出呛人焦苦黑烟，还嘴硬加糖硬压。",
            "dialogue": "林双双：爸，工友们快入席了，这油味怎么发苦？\n林有才：我偷瞄过十来回，药材下油锅炸准没错！多搁两勺糖压压！",
            "assetNames": ["夏氏小厨后厨猛火炒灶", "林有才", "林双双"],
            "ref_images": [kf("2-1-02"), f_youcai, f_lin],
            "ref_audios": [v_lin, v_youcai],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The older man holding the crumpled paper note beside the smoking iron wok on the right of <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The woman fanning smoke away from her face on the left of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.5s) Medium two-shot framed from <Picture 1> inside the smoky kitchen.\n"
                "- [Shot 2] (4.5s-13.0s) Medium close-up on <Subject 1> stubbornly stirring the darkened oil and scooping white sugar into the wok.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.3s): Greyish-black smoke curls up from the blackened herbs in the hot wok. Coughing slightly and fanning her hand in front of her nose, <Subject 2> (S1) asks anxiously: <d>[Chinese] 爸，工友们快入席了，这油味怎么发苦。</d>\n"
                "- [Shot 2] (4.6s-11.0s): Glancing at his crumpled note, <Subject 1> (S2) waves his ladle stubbornly and replies loudly: <d>[Chinese] 我偷瞄过十来回，药材下油锅炸准没错，多搁两勺糖压压。</d>\n"
                "- [Shot 2] (11.0s-13.0s): <Subject 2> frowns dubiously at the murky dark pot.\n"
                "[Environment]\n"
                "- Dim, smoky 2005 back kitchen with a red-brick iron wok stove.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, realistic burnt smoke and natural lip-sync.\n"
                "[Audio]\n"
                "- Harsh crackle of overheated oil, anxious female voice, stubborn raspy older male voice, clang of iron ladle, zero music."
            ),
        },
        {
            "id": "2-1-03",
            "episode": 2,
            "duration": 13,
            "seed": 32103,
            "description": "正午夏记门前鲜牛油红汤翻滚，叶寻淋入草本清液激起满街奇香，断定林有才干炸药材必成苦炭，夏芊芊备齐冰镇鲜毛肚。",
            "dialogue": "[VO] 叶寻：干药材下高温老油必炸成苦炭。林有才，这十二桌席你咽不下去。\n夏芊芊：太香了！鲜毛肚和配菜全冰镇备齐，随时开席！",
            "assetNames": ["重庆老街对门双火锅铺街景", "叶寻 · 渝清记围裙掌勺", "夏芊芊"],
            "ref_images": [kf("2-1-03"), f_ye_apron, f_qian],
            "ref_audios": [v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1>: The man ladling clear herbal liquid into the bubbling red cauldron on the left of <Picture 1>, matching <Picture 2>.\n"
                "- <Subject 2> (S1): The woman holding the tray of ice-chilled fresh tripe on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.5s) Medium close-up framed from <Picture 1> as fragrant white steam billows from the ruby-red cauldron.\n"
                "- [Shot 2] (5.5s-13.0s) Medium two-shot favoring <Subject 2> smiling brightly with the chilled tripe tray beside <Subject 1>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.5s): Keeping his lips firmly closed in calm mastery, <Subject 1> pours the pale-gold herbal infusion into the bubbling ruby chili tallow, skims the surface smoothly with his copper ladle, and casts a knowing glance across the street.\n"
                "- [Shot 2] (5.8s-11.0s): Inhaling the rich, clean aroma with delight, <Subject 2> (S1) lifts the chilled tripe tray slightly and speaks cheerfully: <d>[Chinese] 太香了，鲜毛肚和配菜全冰镇备齐，随时开席。</d>\n"
                "- [Shot 2] (11.0s-13.0s): <Subject 1> nods confidently.\n"
                "[Environment]\n"
                "- Sunlit noon 2005 Chongqing bluestone street beside two steaming iron cauldrons.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, <Subject 1>'s lips strictly closed throughout.\n"
                "[Audio]\n"
                "- Crisp sizzle of liquid hitting bubbling red oil from 0s to 5.5s, bright enthusiastic female Mandarin voice starting at 5.8s, zero music."
            ),
            "vo_custom": {
                "face_1k": f_ye_clean,
                "voice": v_yexun,
                "duration": 6,
                "text": "干药材下高温老油必炸成苦炭，林有才，这十二桌席你咽不下去。",
                "dst_start": 0.25,
                "max_len": 5.1,
            },
        },
        {
            "id": "2-2-01",
            "episode": 2,
            "duration": 11,
            "seed": 32201,
            "description": "周有福率机械厂工友在林记入席，红锅内黑褐焦渣翻涌，周有福尝了一口当场呛咳吐出质问。",
            "dialogue": "周有福：林老板，又焦又苦还呛嗓子，这就是你吹的清润红汤？",
            "assetNames": ["重庆老街对门双火锅铺街景", "周有福"],
            "ref_images": [kf("2-2-01"), f_zhou],
            "ref_audios": [v_zhou],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The authoritative man seated at the center of the round wooden table in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-3.4s) Medium close-up framed from <Picture 1> at the outdoor banquet table beside the murky dark-dreg hotpot.\n"
                "- [Shot 2] (3.4s-11.0s) Close-up on <Subject 1> slamming down his spoon and questioning indignantly as workers behind him set down their chopsticks.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-3.4s): Dark burnt dregs churn in the pot. <Subject 1> takes half a spoonful of the murky broth, immediately coughs sharply into a paper napkin in disgust, and sets the porcelain spoon down hard on the table.\n"
                "- [Shot 2] (3.6s-9.6s): Frowning heavily in displeasure, <Subject 1> (S1) speaks in a booming, dissatisfied voice: <d>[Chinese] 林老板，又焦又苦还呛嗓子，这就是你吹的清润红汤。</d>\n"
                "- [Shot 2] (9.6s-11.0s): Fellow workers in the background shake their heads and push their bowls away.\n"
                "[Environment]\n"
                "- Daytime 2005 Chongqing bluestone street banquet tables outside Lin's hotpot shop.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, authentic reaction acting and lip-sync.\n"
                "[Audio]\n"
                "- Sharp cough, porcelain spoon clinking hard on wood, booming displeased male voice, murmurs of discontent, zero music."
            ),
        },
        {
            "id": "2-2-02",
            "episode": 2,
            "duration": 13,
            "seed": 32202,
            "description": "林双双慌忙端酸梅汤赔笑硬圆，夏芊芊端着透亮红汤铜锅与执铜勺的叶寻大步走到街心当众叫板。",
            "dialogue": "林双双：周厂长，草本入汤难免带苦，喝口酸梅汤压压就顺了！\n夏芊芊：正宗清润红汤，可不用酸梅汤硬压！",
            "assetNames": ["重庆老街对门双火锅铺街景", "林双双", "夏芊芊", "叶寻 · 渝清记围裙掌勺", "周有福"],
            "ref_images": [kf("2-2-02"), f_lin, f_qian, f_ye_apron, f_zhou],
            "ref_audios": [v_lin, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The woman holding the pitcher of dark plum juice on the right of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The woman carrying the gleaming two-ear brass pot of bright ruby broth on the left of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The man holding the long copper ladle beside <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 4>: The man seated at the table on the far right of <Picture 1>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.0s) Medium shot favoring <Subject 1> offering the plum juice pitcher awkwardly beside <Subject 4>.\n"
                "- [Shot 2] (6.0s-13.0s) Medium two-shot on <Subject 2> and <Subject 3> stepping into the center of the bluestone street with the steaming ruby brass pot.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.8s): Wearing a flustered forced smile, <Subject 1> (S1) leans in with the glass pitcher and speaks hurriedly: <d>[Chinese] 周厂长，草本入汤难免带苦，喝口酸梅汤压压就顺了。</d>\n"
                "- [Shot 2] (6.2s-11.0s): Stepping confidently forward with the steaming pot of crystal-clear ruby broth beside <Subject 3>, <Subject 2> (S2) speaks out loud and clear: <d>[Chinese] 正宗清润红汤，可不用酸梅汤硬压。</d>\n"
                "- [Shot 2] (11.0s-13.0s): <Subject 4> turns his head toward the fragrant ruby pot with immediate curiosity.\n"
                "[Environment]\n"
                "- Bright daytime 2005 Chongqing bluestone street between the two facing hotpot shops.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, crisp staging and lip-sync.\n"
                "[Audio]\n"
                "- Flustered female voice, firm footsteps on stone, clear confident female voice, subtle bubbling broth, zero music."
            ),
        },
        {
            "id": "2-2-03",
            "episode": 2,
            "duration": 15,
            "seed": 322038,
            "description": "林有才嘴硬污蔑夏记没油接席，叶寻当众揭穿林记前四年招牌汤皆出自他手，夏芊芊敞开院门承诺有一丝苦味分文不收。",
            "dialogue": "林有才：别信！夏记连牛油都被断了，拿什么接十二桌大席？\n叶寻：我用头刀鲜板油现熬。林记前四年的招牌汤，本就是我炒的。\n夏芊芊：桌灶鲜菜昨晚就备齐了！周厂长尝一口，有一丝苦味分文不收！",
            "assetNames": ["重庆老街对门双火锅铺街景", "林有才", "叶寻 · 渝清记围裙掌勺", "夏芊芊"],
            "ref_images": [kf("2-2-03"), f_youcai, f_ye_apron, f_qian],
            "ref_audios": [v_youcai, v_yexun, v_qian],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The older man pointing anxiously on the right of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The man holding the copper ladle on the left-center of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3> (S3): The woman standing beside <Subject 2> in front of the open courtyard gate in <Picture 1>, matching <Picture 4>. Voice matches Audio 3.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-15.0s) Continuous medium three-shot framed directly from <Picture 1> camera angle with a subtle steady push-in toward <Subject 2> and <Subject 3> (keeping the exact <Picture 1> background architecture unchanged).\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-3.8s): Pointing in flustered panic on the right, <Subject 1> (S1) shouts briskly: <d>[Chinese] 别信，夏记连牛油都被断了，拿什么接十二桌大席。</d>\n"
                "- [Shot 1] (4.0s-8.6s): Standing calm and upright on the left with his copper ladle, <Subject 2> (S2) answers briskly with rock-solid authority: <d>[Chinese] 我用头刀鲜板油现熬，林记前四年的招牌汤，本就是我炒的。</d>\n"
                "- [Shot 1] (8.8s-13.2s): Beside him, <Subject 3> (S3) gestures openly with her hand and declares briskly and clearly: <d>[Chinese] 桌灶鲜菜早备齐了，周厂长尝一口，有一丝苦味分文不收。</d>\n"
                "- [Shot 1] (13.2s-15.0s): <Subject 1> lowers his pointing hand, speechless.\n"
                "[Environment]\n"
                "- Daytime 2005 Chongqing bluestone street between both facing shops.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, crisp three-speaker exchange.\n"
                "[Audio]\n"
                "- Panicked older male shout, steady authoritative young male voice, crisp confident young female voice, street ambiance, zero music."
            ),
        },
        {
            "id": "2-2-04",
            "episode": 2,
            "duration": 13,
            "seed": 32204,
            "description": "周有福当街试喝红汤再涮鲜毛肚惊艳叫绝，大手一挥当场宣布林记退单，率十二桌工友哄然跨街坐满夏记。",
            "dialogue": "周有福：醇香生津，脆嫩化渣！这才是真手艺！林记退单！工友们，过街坐夏记！",
            "assetNames": ["重庆老街对门双火锅铺街景", "周有福", "夏芊芊", "叶寻 · 渝清记围裙掌勺"],
            "ref_images": [kf("2-2-04"), f_zhou, f_qian, f_ye_apron],
            "ref_audios": [v_zhou],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man holding the small white tasting bowl in the center of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The woman holding the brass pot on the left of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The man standing beside <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.8s) Medium close-up framed from <Picture 1> as <Subject 1> tastes a slice of fresh tripe and sips the bright ruby broth.\n"
                "- [Shot 2] (6.8s-13.0s) Medium shot as <Subject 1> waves his arm grandly and workers cheer and stream across the street toward <Subject 2> and <Subject 3>'s courtyard.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-2.2s): <Subject 1> chews a crisp slice of tripe from the small white bowl, his eyes lighting up in sheer delight.\n"
                "- [Shot 1] (2.3s-6.6s): Giving a hearty thumbs-up toward <Subject 2> and <Subject 3>, <Subject 1> (S1) praises loudly: <d>[Chinese] 醇香生津，脆嫩化渣，这才是真手艺。</d>\n"
                "- [Shot 2] (6.9s-11.2s): Turning back toward the tables behind him, <Subject 1> (S1) waves his right arm commandingly and announces: <d>[Chinese] 林记退单，工友们，过街坐夏记。</d>\n"
                "- [Shot 2] (11.2s-13.0s): Cheering workers rise eagerly in the background and walk toward the open courtyard as <Subject 2> and <Subject 3> smile warmly.\n"
                "[Environment]\n"
                "- Lively sunlit 2005 Chongqing bluestone street outside Xia's courtyard.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, triumphant crowd energy and crisp lip-sync.\n"
                "[Audio]\n"
                "- Booming enthusiastic factory director voice, cheerful crowd applause and footsteps on bluestone, zero music."
            ),
        },
        {
            "id": "2-2-05",
            "episode": 2,
            "duration": 13,
            "seed": 322058,
            "description": "楚南与林双双带卫生科陈科长冲到夏记铁锅前恶人先告状，实名举报夏记偷加违禁药壳，陈科长亮证要求熄火快检。",
            "dialogue": "林双双：陈科长！我实名举报夏记往汤里偷加违禁药壳提香！\n陈科长：接到实名举报，请立刻熄火封样，配合现场快检！",
            "assetNames": ["重庆老街对门双火锅铺街景", "陈科长", "林双双", "楚南", "叶寻 · 渝清记围裙掌勺"],
            "ref_images": [kf("2-2-05"), f_chen, f_lin, f_chu, f_ye_apron],
            "ref_audios": [v_lin, v_chen],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The uniformed inspector holding up the blue credential wallet in the center-right of <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The woman pointing accusingly behind <Subject 1> in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "- <Subject 3>: The man standing beside <Subject 2> with a cold smirk in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 4>: The man standing calmly beside the iron cauldron on the left of <Picture 1>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.4s) Medium confrontation shot framed from <Picture 1> beside the steaming iron cauldrons.\n"
                "- [Shot 2] (5.4s-13.0s) Tight solo close-up on <Subject 1> holding up his blue credential wallet toward <Subject 4> (with <Subject 2> out of frame).\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.2s): Pointing straight at the steaming iron cauldron beside <Subject 4>, <Subject 2> (S1) speaks sharply once and then closes her lips: <d>[Chinese] 陈科长，我实名举报夏记往汤里偷加违禁药壳提香。</d>\n"
                "- [Shot 2] (5.6s-11.0s): In a tight close-up, <Subject 1> (S2) holds up his official blue credential wallet seriously and speaks in a crisp, impartial official tone: <d>[Chinese] 接到实名举报，请立刻熄火封样，配合现场快检。</d>\n"
                "- [Shot 2] (11.0s-13.0s): <Subject 1> lowers the credential wallet seriously.\n"
                "[Environment]\n"
                "- Daytime 2005 Chongqing bluestone street beside Xia's iron cauldrons.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, sharp dramatic tension and lip-sync.\n"
                "[Audio]\n"
                "- Sharp accusing female voice, crisp authoritative male inspector voice, sudden hush over street crowd, zero music."
            ),
        },
        {
            "id": "2-2-06",
            "episode": 2,
            "duration": 12,
            "seed": 32206,
            "description": "楚南趁机煽动食客去对门免单吃楚氏招牌红汤，满院惊疑停筷，叶寻沉稳按住夏芊芊手背，从容关火迎检。",
            "dialogue": "楚南：吃着黑心锅还不跑？楚氏总店刚送来招牌红汤，对门全场免单！",
            "assetNames": ["重庆老街对门双火锅铺街景", "楚南", "叶寻 · 渝清记围裙掌勺", "夏芊芊", "陈科长"],
            "ref_images": [kf("2-2-06"), f_chu, f_ye_apron, f_qian, f_chen],
            "ref_audios": [v_chu],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man gesturing smugly on the right of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The man resting a reassuring hand over <Subject 3>'s wrist beside the cauldron on the left of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The woman standing tense beside the cauldron on the left of <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 4>: The uniformed inspector standing in the mid-ground of <Picture 1>, matching <Picture 5>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.8s) Medium shot favoring <Subject 1> gloating loudly and gesturing back across the street.\n"
                "- [Shot 2] (6.8s-12.0s) High-tension medium close-up on <Subject 2> gently patting <Subject 3>'s hand, turning off the stove valve with a crisp click, and locking fearless eyes onto <Subject 4> and <Subject 1>.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-6.6s): Gesturing grandly across the street with a triumphant sneer, <Subject 1> (S1) calls out loudly to the diners: <d>[Chinese] 吃着黑心锅还不跑，楚氏总店刚送来招牌红汤，对门全场免单。</d>\n"
                "- [Shot 2] (6.8s-12.0s): Keeping his lips closed with rock-steady composure, <Subject 2> presses <Subject 3>'s tense hand reassuringly, clicks off the iron stove valve so the flame dies down, and steps half a pace forward facing <Subject 4> and <Subject 1> with fearless confidence.\n"
                "[Environment]\n"
                "- Daytime 2005 Chongqing bluestone street at Xia's hotpot cauldrons.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography with completely clean unobstructed lower frame, gripping cliffhanger eye-contact.\n"
                "[Audio]\n"
                "- Loud gloating male voice, metallic click of stove valve shutting off, quiet simmering pot, tense hush, zero music."
            ),
        },
    ]

    return ep1, ep2


def trim_silence_bounds(wav_or_mp4: Path) -> tuple[float, float]:
    probe = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(wav_or_mp4)],
        text=True,
    ))
    dur = float(probe["format"]["duration"])
    proc = subprocess.run(
        ["ffmpeg", "-i", str(wav_or_mp4), "-af", "silencedetect=noise=-36dB:d=0.20", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", proc.stderr)]
    s0 = 0.05
    if starts and starts[0] < 0.15 and ends:
        s0 = max(0.0, ends[0] - 0.06)
    e0 = dur - 0.05
    if starts and starts[-1] > s0 + 0.5:
        last_s = starts[-1]
        if not ends or ends[-1] < last_s:
            e0 = min(dur, last_s + 0.12)
    return round(s0, 3), round(max(s0 + 0.4, e0), 3)


def gen_dry_vo_4070(out_mp4: Path, face_1k: Path, voice_wav: Path, text: str, dur: int, seed: int):
    vo_prompt = (
        "[Subject]\n"
        "- <Subject 1> (S1): The speaker in <Picture 1>. Voice matches Audio 1.\n"
        "[Shot]\n"
        f"- [Shot 1] (0s-{dur}s) Static close-up framed from <Picture 1>.\n"
        "[Timeline]\n"
        f"- [Shot 1] (0.1s-{dur - 0.2:.1f}s): <Subject 1> (S1) speaks briskly and clearly: <d>[Chinese] {text}</d>\n"
        "[Environment]\n- Quiet dry room.\n"
        "[Camera & Visuals]\n- Static portrait, pure theatrical frame.\n"
        "[Audio]\n- Clean dry close-mic voice matching Audio 1, zero background noise, zero music."
    )
    old_ckpt = vo_split.LOWRES_CHECKPOINT
    vo_split.LOWRES_CHECKPOINT = ""
    try:
        return vo_split.h3_lowres(
            out_mp4, vo_prompt, dur, seed, "9:16", "reference", [face_1k], None, None, [voice_wav]
        )
    finally:
        vo_split.LOWRES_CHECKPOINT = old_ckpt


def run_one_shot(spec: dict, outdir: Path, force: bool = False):
    sid = spec["id"]
    sdir = outdir / sid
    sdir.mkdir(parents=True, exist_ok=True)
    final_mp4 = sdir / "video.mp4"
    final_meta = sdir / "video.json"
    if final_mp4.is_file() and final_meta.is_file() and not force:
        print(f"[skip] {sid} already exists", flush=True)
        return

    vc = spec.get("vo_custom")
    if not vc:
        pika_runner.run_shot(spec, outdir, CACHE_1K, resolution="480p", force=force)
        return

    base_mp4 = sdir / "video_base.mp4"
    vo_mp4 = sdir / "vo_short_368p.mp4"
    refs_1k = [pika_runner.ensure_1k_image(Path(p), CACHE_1K) for p in spec["ref_images"]]
    audios = [Path(p) for p in spec.get("ref_audios", [])]
    face_1k = pika_runner.ensure_1k_image(Path(vc["face_1k"]), CACHE_1K)

    print(f"[start+vo_custom] {sid} ({spec['duration']}s 480p + {vc['duration']}s 368p male VO)", flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        if base_mp4.is_file() and base_mp4.with_suffix(".json").is_file() and not force:
            fut_b = pool.submit(lambda: json.loads(base_mp4.with_suffix(".json").read_text(encoding="utf-8")))
        else:
            fut_b = pool.submit(
                pika_runner.call_pika_5090,
                base_mp4, spec["prompt"], int(spec["duration"]), int(spec["seed"]), "9:16", "480p", refs_1k, audios,
            )
        fut_v = pool.submit(
            gen_dry_vo_4070, vo_mp4, face_1k, Path(vc["voice"]), vc["text"], int(vc["duration"]), int(spec["seed"]) + 77
        )
        meta = fut_b.result()
        vo_hdr = fut_v.result()

    ss, se = trim_silence_bounds(vo_mp4)
    raw_dur = se - ss
    atempo_str = ""
    if raw_dur > float(vc["max_len"]):
        ratio = min(1.25, raw_dur / float(vc["max_len"]))
        atempo_str = f"atempo={ratio:.3f},"
        eff_dur = raw_dur / ratio
    else:
        eff_dur = raw_dur

    end_mute = float(vc["dst_start"]) + eff_dur + 0.12
    tmp = final_mp4.with_suffix(".tmp.mp4")
    filt = (
        f"[0:a]aresample=48000,volume='if(between(t,0,{end_mute:.3f}),0.08,1.0)':eval=frame[base];"
        f"[1:a]aresample=48000,atrim={ss:.3f}:{se:.3f},asetpts=PTS-STARTPTS,{atempo_str}"
        f"afade=t=in:d=0.06,afade=t=out:st={max(0.0, eff_dur - 0.08):.3f}:d=0.08,"
        f"volume=1.65,adelay={int(round(float(vc['dst_start']) * 1000))}:all=1[vo];"
        f"[base][vo]amix=inputs=2:duration=first:normalize=0[a]"
    )
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(base_mp4), "-i", str(vo_mp4),
        "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp),
    ], check=True)
    tmp.replace(final_mp4)
    meta["vo_custom_applied"] = {"src": [ss, se], "eff_dur": round(eff_dur, 3), "dst_start": vc["dst_start"], "vo_headers": vo_hdr}
    final_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done+vo_custom] {sid} -> VO [{ss}..{se}] (eff {eff_dur:.2f}s) placed at {vc['dst_start']}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lint-only", action="store_true")
    ap.add_argument("--ep", type=int, choices=[1, 2], default=0, help="0 = both Ep 1 and Ep 2")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    ep1, ep2 = build_plans()
    (WORK_DIR / "ep01_v3_plan.json").write_text(json.dumps(ep1, ensure_ascii=False, indent=2), encoding="utf-8")
    (WORK_DIR / "ep02_v3_plan.json").write_text(json.dumps(ep2, ensure_ascii=False, indent=2), encoding="utf-8")

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
