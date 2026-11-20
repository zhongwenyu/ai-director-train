#!/usr/bin/env python3
"""
Surgical QA fixes for the 7 items caught during full 21-shot multimodal inspection:
  1. 1-2-13: Strip background piano via Demucs vocals while preserving 100% crisp speech & cloth slap.
  2. 1-3-04: Re-generate 4s male VO clip using f_yexun portrait + v_yexun and mute base [4.7s..9.0s] so zero female voice / zero murmur overlap.
  3. 1-2-07: Re-generate at 15s (seed 12075) so final '牛排五十八一份！' has 1.3s unclipped tail buffer.
  4. 2-1-01: Re-generate at 14s (seed 21018) with unobstructed theatrical frame (zero burned-in text).
  5. 2-1-07: Re-generate at 14s (seed 21078) with unobstructed theatrical frame (zero burned-in text).
  6. 2-2-10: Re-generate at 10s (seed 22108) with unobstructed theatrical frame + zero guitar + male diner shout VO.
  7. 2-3-04: Re-generate at 13s (seed 23048) tapping the single passbook already under his hand in Picture 1 (zero duplicate passbook) + 3.4s male VO cleanly finishing before 4.5s speech!
"""
from __future__ import annotations
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
from build_and_run_ep01_02 import WORK_DIR, CACHE_1K, TAKES_EP1, TAKES_EP2, kf, trim_silence_bounds  # noqa: E402


def fix_1_2_13_demucs():
    sdir = TAKES_EP1 / "1-2-13"
    mp4 = sdir / "video.mp4"
    orig = sdir / "video_with_piano.mp4"
    if not orig.is_file():
        mp4.replace(orig)
    vocals = sdir / "vocals.wav"
    vo_split.demucs_vocals(orig, vocals)
    # Keep cloth-wrap foley in 0..2.1s at 0.35x lowpass, and pure clean vocals + room tone from 2.1s onward
    filt = (
        "[0:a]aresample=48000,volume='if(lt(t,2.1),0.30,0.03)':eval=frame[amb];"
        "[1:a]aresample=48000,volume=1.15[voc];"
        "[amb][voc]amix=inputs=2:duration=first:normalize=0[a]"
    )
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(orig), "-i", str(vocals),
        "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(mp4),
    ], check=True)
    print("[fixed] 1-2-13 piano stripped cleanly via Demucs!", flush=True)


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


def fix_1_3_04_vo(amap: dict):
    sdir = TAKES_EP1 / "1-3-04"
    base_mp4 = sdir / "video_base.mp4"
    vo_mp4 = sdir / "vo_male_368p.mp4"
    final_mp4 = sdir / "video.mp4"
    f_yexun = pika_runner.ensure_1k_image(Path(amap["叶寻"]["front_1k"]), CACHE_1K)
    v_yexun = Path(amap["叶寻"]["voice"])
    gen_dry_vo_4070(vo_mp4, f_yexun, v_yexun, "青梅夏芊芊，前世只有她劝我提防楚南！", 5, 13049)
    ss, se = trim_silence_bounds(vo_mp4)
    # Clamp max VO duration to 3.8s so 5.0 + 3.8 = 8.8s (zero overlap with 9.8s on-screen speech!)
    se = min(se, ss + 3.85)
    # Mute base inside [4.75, 9.20] to silence the faint murmur at 5.2s completely, keeping street ambiance elsewhere
    tmp = final_mp4.with_suffix(".tmp.mp4")
    dur = max(0.1, se - ss)
    filt = (
        f"[0:a]aresample=48000,volume='if(between(t,4.75,9.20),0.02,1.0)':eval=frame[base];"
        f"[1:a]aresample=48000,atrim={ss:.3f}:{se:.3f},asetpts=PTS-STARTPTS,"
        f"afade=t=in:d=0.06,afade=t=out:st={max(0.0, dur - 0.08):.3f}:d=0.08,"
        f"volume=1.65,adelay=5000:all=1[vo];"
        f"[base][vo]amix=inputs=2:duration=first:normalize=0[a]"
    )
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(base_mp4), "-i", str(vo_mp4),
        "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp),
    ], check=True)
    tmp.replace(final_mp4)
    print(f"[fixed] 1-3-04 male VO [{ss}..{se}] placed cleanly at 5.0s!", flush=True)


def rerun_5_shots(amap: dict):
    v_yexun = amap["叶寻"]["voice"]
    v_lin = amap["林双双"]["voice"]
    v_chu = amap["楚南"]["voice"]
    v_xia = amap["夏建国"]["voice"]
    v_wang = amap["老王"]["voice"]
    v_shout = amap["_diner_shout_voice"]

    f_yexun = amap["叶寻"]["front_1k"]
    f_qian = amap["夏芊芊"]["front_1k"]
    f_lin = amap["林双双"]["front_1k"]
    f_chu = amap["楚南"]["front_1k"]
    f_xia = amap["夏建国"]["front_1k"]
    f_wang = amap["老王"]["front_1k"]
    f_diner = amap["中年食客"]["front_1k"]

    specs = [
        # 1. 1-2-07 (15s unclipped)
        (TAKES_EP1, {
            "id": "1-2-07",
            "duration": 15,
            "seed": 12075,
            "ref_images": [kf("1-2-07"), f_chu, f_lin, f_yexun],
            "ref_audios": [v_chu, v_lin],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man twirling dorm keys in the center of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2> (S2): The young woman on the right of <Picture 1>, matching <Picture 3>. Voice matches Audio 2.\n"
                "- <Subject 3>: The young man seated calmly on the left of <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.8s) Medium three-shot framed from <Picture 1>.\n"
                "- [Shot 2] (6.8s-15.0s) Closer medium two-shot on <Subject 1> and <Subject 2> exchanging eager looks.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-6.6s): Jingling his dorm key ring, <Subject 1> (S1) gestures grandly across the dining room while <Subject 3> watches silently, speaking briskly and smugly: <d>[Chinese] 老叶，外语系女生约会谁吃油烟土火锅？拿两万五铺白桌布改法式西餐厅，剩一万五搞开业促销！</d>\n"
                "- [Shot 2] (6.9s-8.4s): <Subject 2>'s (S2) eyes light up eagerly as she asks: <d>[Chinese] 那主厨呢？</d>\n"
                "- [Shot 2] (8.5s-13.5s): <Subject 1> (S1) pats his chest boastfully and answers clearly: <d>[Chinese] 我表哥赵帆在深圳大酒店当西餐副厨，我替你请好了，牛排五十八一份！</d>\n"
                "- [Shot 2] (13.5s-15.0s): <Subject 2> smiles brightly with admiration while <Subject 1> grins.\n"
                "[Environment]\n"
                "- 2005 Chongqing small restaurant interior at dusk.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema frame with completely clean unobstructed lower frame, natural eye lines and lip-sync.\n"
                "[Audio]\n"
                "- Subtle jingle of keys, brisk natural two-speaker Mandarin dialogue finishing cleanly by 13.5s, quiet room tone, zero music."
            ),
        }),
        # 2. 2-1-01 (14s, zero burned-in text)
        (TAKES_EP2, {
            "id": "2-1-01",
            "duration": 14,
            "seed": 21019,
            "ref_images": [kf("2-1-01"), f_xia, f_wang],
            "ref_audios": [v_wang, v_xia],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S2): The man with the white wrist bandage leaning on the wooden counter on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 2.\n"
                "- <Subject 2> (S1): The stocky cook resting his hand near the upright cleaver on the right pass counter in <Picture 1>, matching <Picture 3>. Voice matches Audio 1.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-7.6s) Medium confrontation shot framed from <Picture 1> inside the small eatery.\n"
                "- [Shot 2] (7.6s-14.0s) Medium close-up on <Subject 1> bracing his uninjured left hand on the wooden counter.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-7.4s): Pointing aggressively across the counter above the scattered porcelain shards on the floor, <Subject 2> (S1) glares at <Subject 1> and speaks loudly: <d>[Chinese] 老夏，少打感情牌！你五天前颠勺拉裂手腕筋，现在晚市三桌单子都下了，不签三千块长约、预支九千块，老子立马走人！</d>\n"
                "- [Shot 2] (7.8s-13.0s): Cradling his bandaged right forearm against his chest, <Subject 1> (S2) slaps the wooden counter with his left hand and protests indignantly: <d>[Chinese] 老王！上周说好六十块一天顶班，你趁上客坐地起价，让我上哪儿掏九千块？！</d>\n"
                "- [Shot 2] (13.0s-14.0s): <Subject 2> sneers coldly.\n"
                "[Environment]\n"
                "- Warm tungsten-lit 2005 Chongqing small stir-fry eatery front counter.\n"
                "[Camera & Visuals]\n"
                "- Raw realistic 35mm theatrical film look, completely clean unobstructed image across the entire frame.\n"
                "[Audio]\n"
                "- Palm slap on wood, loud extortionate cook voice and indignant fatherly voice, natural room ambiance, zero music."
            ),
        }),
        # 3. 2-1-07 (14s, zero burned-in text)
        (TAKES_EP2, {
            "id": "2-1-07",
            "duration": 14,
            "seed": 21079,
            "ref_images": [kf("2-1-07"), f_yexun, f_diner, f_qian, f_wang, f_xia],
            "ref_audios": [v_yexun, v_xia, v_wang],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man stepping in on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The diner seated at the square wooden table in <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The young woman standing by the counter in <Picture 1>, matching <Picture 4>.\n"
                "- <Subject 4> (S3): The stocky cook with crossed arms on the right of <Picture 1>, matching <Picture 5>. Voice matches Audio 3.\n"
                "- <Subject 5> (S2): The man with the bandaged right wrist behind the counter in <Picture 1>, matching <Picture 6>. Voice matches Audio 2.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-6.6s) Medium group shot framed from <Picture 1> as <Subject 1> reassures the room.\n"
                "- [Shot 2] (6.6s-14.0s) Closer medium shot as <Subject 4> scoffs and <Subject 1> calmly instructs <Subject 3> to pay him off.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.5s): Gesturing warmly toward <Subject 2>'s table, <Subject 1> (S1) speaks with steady confidence: <d>[Chinese] 叔，坐下喝口茶。十分钟热菜不上桌，今晚三桌全免单，算我的！</d>\n"
                "- [Shot 1] (4.7s-6.5s): Behind the counter, <Subject 5> (S2) looks up in joyful surprise: <d>[Chinese] 寻娃子？你怎么过来了！</d>\n"
                "- [Shot 2] (6.7s-10.3s): Keeping his arms crossed, <Subject 4> (S3) jeers loudly at <Subject 1>: <d>[Chinese] 案板上就剩副腥猪肝和鸭杂，你个穷学生拿嘴炒啊？</d>\n"
                "- [Shot 2] (10.5s-13.1s): Ignoring <Subject 4> completely, <Subject 1> (S1) turns calmly to <Subject 3>: <d>[Chinese] 芊芊姐，结他六十块日工钱，请他腾地方。</d>\n"
                "- [Shot 2] (13.1s-14.0s): <Subject 3> slaps banknotes decisively onto the wooden counter.\n"
                "[Environment]\n"
                "- Warm incandescent 2005 neighborhood eatery front hall.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography, completely clean unobstructed image from top to bottom.\n"
                "[Audio]\n"
                "- Natural four-turn room dialogue, crisp banknote slap on wood, zero music."
            ),
        }),
        # 4. 2-2-10 (10s, zero burned-in text, zero guitar, male diner shout VO)
        (TAKES_EP2, {
            "id": "2-2-10",
            "duration": 10,
            "seed": 22109,
            "ref_images": [kf("2-2-10"), f_xia, f_wang],
            "ref_audios": [v_xia],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The man with the bandaged right wrist behind the wooden counter on the left of <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The stocky cook standing awkwardly by the doorframe on the right of <Picture 1>, matching <Picture 3>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-5.2s) Medium two-shot framed from <Picture 1> as <Subject 1> crumples the red flyers.\n"
                "- [Shot 2] (5.2s-10.0s) Medium shot as <Subject 1> waves <Subject 2> out the doorway.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-5.2s): Smiling proudly with his lips closed, <Subject 1> crumples the red paper flyers with his left hand and tosses the paper ball into the wastebasket beside the counter.\n"
                "- [Shot 2] (5.4s-8.2s): Turning toward the doorway where <Subject 2> stands red-faced, <Subject 1> (S1) waves his left hand briskly and speaks aloud: <d>[Chinese] 王师傅，好走不送！</d>\n"
                "- [Shot 2] (8.2s-10.0s): <Subject 2> lowers his head in embarrassment and hurries out into the night.\n"
                "[Environment]\n"
                "- Lively 2005 neighborhood eatery front counter at night.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema photography, completely clean unobstructed image, <Subject 1>'s lips closed from 0s to 5.3s.\n"
                "[Audio]\n"
                "- Crisp paper crumpling, subtle clink of dishes in dining room, proud male send-off line at 5.4s, footsteps, strictly zero guitar, zero music."
            ),
            "vo_custom": {
                "face": f_chu,
                "voice": v_shout,
                "duration": 5,
                "text": "老夏，我们也加份泡椒猪肝和爆鸭杂，再拿四瓶啤酒！",
                "dst_start": 0.3,
                "max_len": 4.7,
            },
        }),
        # 5. 2-3-04 (13s, single passbook already under hand, zero VO overlap)
        (TAKES_EP2, {
            "id": "2-3-04",
            "duration": 13,
            "seed": 23049,
            "ref_images": [kf("2-3-04"), f_yexun, f_qian, f_xia],
            "ref_audios": [v_yexun],
            "prompt": (
                "[Subject]\n"
                "- <Subject 1> (S1): The young man standing on the left with his right hand resting on the red passbook on the wooden table in <Picture 1>, matching <Picture 2>. Voice matches Audio 1.\n"
                "- <Subject 2>: The young woman seated on the right of <Picture 1>, matching <Picture 3>.\n"
                "- <Subject 3>: The man with the bandaged right wrist seated beside <Subject 2> in <Picture 1>, matching <Picture 4>.\n"
                "[Shot]\n"
                "- [Shot 1] (0s-4.4s) Medium three-shot framed directly from <Picture 1> with <Subject 1>'s hand resting on the single red passbook.\n"
                "- [Shot 2] (4.4s-13.0s) Closer medium shot on <Subject 1> pitching the hotpot partnership with bright conviction.\n"
                "[Timeline]\n"
                "- [Shot 1] (0s-4.4s): Keeping his lips firmly closed in focused resolve, <Subject 1> glances briefly toward the idle iron cauldron in the back corner, then taps his fingers twice firmly on the red passbook already resting under his right hand on the table.\n"
                "- [Shot 2] (4.6s-12.0s): Leaning forward earnestly toward <Subject 3> and <Subject 2>, <Subject 1> (S1) speaks clearly and persuasively: <d>[Chinese] 夏叔，芊芊姐，小炒翻不了身。我拿全部存款和爷爷传下的清润火锅方子入伙，咱们改开老火锅，二十天挣出房租！</d>\n"
                "- [Shot 2] (12.0s-13.0s): <Subject 3> looks up in stunned hope while <Subject 2> gazes intently at the passbook.\n"
                "[Environment]\n"
                "- Quiet half-shuttered 2005 eatery late at night.\n"
                "[Camera & Visuals]\n"
                "- Pure 35mm theatrical cinema frame, single red passbook under <Subject 1>'s hand throughout, lips strictly closed from 0s to 4.5s.\n"
                "[Audio]\n"
                "- Crisp double finger-tap on passbook on wood, earnest confident young male dialogue starting at 4.6s, quiet night room tone, zero music."
            ),
            "vo_custom": {
                "face": f_yexun,
                "voice": v_yexun,
                "duration": 5,
                "text": "百平临街熟铺证照齐全，缺的只是高毛利爆品！",
                "dst_start": 0.25,
                "max_len": 4.0,
            },
        }),
    ]

    for _, sp in specs:
        issues = pika_runner.lint_zero_appearance(sp["prompt"], sp["id"])
        if issues:
            raise ValueError("\n".join(issues))
    print("All 5 re-roll specs passed zero-appearance & <d> purity lint!", flush=True)

    for outdir, sp in specs:
        sid = sp["id"]
        sdir = outdir / sid
        sdir.mkdir(parents=True, exist_ok=True)
        final_mp4 = sdir / "video.mp4"
        final_meta = sdir / "video.json"
        refs_1k = [pika_runner.ensure_1k_image(Path(p), CACHE_1K) for p in sp["ref_images"]]
        audios = [Path(p) for p in sp["ref_audios"]]

        vc = sp.get("vo_custom")
        if not vc:
            pika_runner.run_shot(sp, outdir, CACHE_1K, resolution="480p", force=True)
            continue

        base_mp4 = sdir / "video_base_v2.mp4"
        vo_mp4 = sdir / "vo_v2_368p.mp4"
        face_1k = pika_runner.ensure_1k_image(Path(vc["face"]), CACHE_1K)
        print(f"[rerun+vo] {sid} ({sp['duration']}s 480p + {vc['duration']}s 368p VO)", flush=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_b = pool.submit(
                pika_runner.call_pika_5090,
                base_mp4, sp["prompt"], int(sp["duration"]), int(sp["seed"]), "9:16", "480p", refs_1k, audios,
            )
            fut_v = pool.submit(
                gen_dry_vo_4070, vo_mp4, face_1k, Path(vc["voice"]), vc["text"], int(vc["duration"]), int(sp["seed"]) + 33
            )
            meta = fut_b.result()
            vo_hdr = fut_v.result()

        ss, se = trim_silence_bounds(vo_mp4)
        se = min(se, ss + float(vc["max_len"]))
        # Mute base inside [0, dst_start + (se-ss) + 0.15] so zero base speech/music leaks under VO
        end_mute = float(vc["dst_start"]) + (se - ss) + 0.10
        tmp = final_mp4.with_suffix(".tmp.mp4")
        dur = max(0.1, se - ss)
        filt = (
            f"[0:a]aresample=48000,volume='if(between(t,0,{end_mute:.3f}),0.12,1.0)':eval=frame[base];"
            f"[1:a]aresample=48000,atrim={ss:.3f}:{se:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d=0.06,afade=t=out:st={max(0.0, dur - 0.08):.3f}:d=0.08,"
            f"volume=1.65,adelay={int(round(float(vc['dst_start']) * 1000))}:all=1[vo];"
            f"[base][vo]amix=inputs=2:duration=first:normalize=0[a]"
        )
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-i", str(base_mp4), "-i", str(vo_mp4),
            "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp),
        ], check=True)
        tmp.replace(final_mp4)
        meta["vo_v2_applied"] = {"src": [ss, se], "dst_start": vc["dst_start"], "vo_headers": vo_hdr}
        final_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done rerun+vo] {sid} -> VO [{ss}..{se}] at {vc['dst_start']}s", flush=True)


def main():
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))
    fix_1_2_13_demucs()
    fix_1_3_04_vo(amap)
    rerun_5_shots(amap)
    print("ALL 7 QA FIXES COMPLETED!", flush=True)


if __name__ == "__main__":
    main()
