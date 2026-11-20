#!/usr/bin/env python3
"""
Rebuild spatially discontinuous Scene Master Plates and shot first-frame keyframes across
Episodes 1 and 2 of `2005_chongqing_hotpot_v7` using Spark `MiniMax H3 Image`
(`sol-spark-benchmark`, ComfyUI `127.0.0.1:8338`, `MiniMaxH3ImageConditioning`).

Architecture:
  1. Generate Scene / State Master Plates first (`1-1_master_4p`, `1-3_post_tear_master`,
     `1-3_doorway_master`, `2-1_post_watch_master`) anchored to verified canonical room/street plates.
  2. Derive each shot's `t=0.0s` first frame (and cross-cut `<Picture 2>` auxiliary plates)
     directly from its parent Scene Master Plate (`<Picture 1>`) + character `#front` portraits.
  3. Export both native PNGs in `keyframes_2k/` and `<=1024px` (`1K`) copies in `keyframes_1k/`,
     and render `transition_audit/spark_rebuilt_keyframes_sheet.jpg` for visual verification.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw

SKILL_SCRIPTS = Path("/home/zhongwenyu/project/ai-director-train/.agents/skills/hit-video/scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))

from compress_1k import compress_image_to_1k  # noqa: E402
from spark_h3_image import generate_spark_h3_image  # noqa: E402

WORK_DIR = Path("/home/zhongwenyu/project/ai-director-train/productions/2005_chongqing_hotpot_v7/video_gen")
KF_2K = WORK_DIR / "keyframes_2k"
KF_1K = WORK_DIR / "keyframes_1k"
BACKUP_2K = WORK_DIR / "transition_audit" / "backup_v1_keyframes_2k"
BACKUP_1K = WORK_DIR / "transition_audit" / "backup_v1_keyframes_1k"
AUDIT_DIR = WORK_DIR / "transition_audit"


def backup_existing(stem: str) -> None:
    BACKUP_2K.mkdir(parents=True, exist_ok=True)
    BACKUP_1K.mkdir(parents=True, exist_ok=True)
    p2 = KF_2K / f"{stem}_2k.png"
    p1 = KF_1K / f"{stem}_1k.png"
    if p2.is_file() and not (BACKUP_2K / p2.name).is_file():
        shutil.copy2(p2, BACKUP_2K / p2.name)
    if p1.is_file() and not (BACKUP_1K / p1.name).is_file():
        shutil.copy2(p1, BACKUP_1K / p1.name)


def main() -> int:
    amap = json.loads((WORK_DIR / "asset_map.json").read_text(encoding="utf-8"))

    c_ye_2020 = amap["叶寻 · 2020研发总厨白服"]["front_1k"]
    c_lin_banq = amap["林双双 · 塞纳左岸酒红礼服"]["front_1k"]
    c_chu_exec = amap["楚南 · 海归并购总监西装"]["front_1k"]
    c_zhao = amap["赵帆"]["front_1k"]

    c_ye = amap["叶寻"]["front_1k"]
    c_lin = amap["林双双"]["front_1k"]
    c_chu = amap["楚南"]["front_1k"]
    c_qian = amap["夏芊芊"]["front_1k"]

    # Step 0: Promote already A/B-verified 1-3-09 Spark Master-Plate keyframe
    ab_src = AUDIT_DIR / "ab_master2k_00001_.png"
    if ab_src.is_file():
        backup_existing("1-3-09")
        shutil.copy2(ab_src, KF_2K / "1-3-09_2k.png")
        compress_image_to_1k(KF_2K / "1-3-09_2k.png", KF_1K / "1-3-09_1k.png", max_side=1024)
        print("[0/14] Promoted verified Spark keyframe -> 1-3-09_2k.png / 1-3-09_1k.png", flush=True)

    jobs = [
        # --- SCENE 1-1: VIP Rooftop Banquet Room (Round Grey Marble Table + Night Skyline Window) ---
        {
            "stem": "1-1_master_4p",
            "seed": 1101,
            "refs": [str(KF_2K / "1-1-01_2k.png"), c_ye_2020, c_lin_banq, c_chu_exec, c_zhao],
            "prompt": (
                "The luxury rooftop VIP dining room, round grey marble table, white gold-trimmed ceremonial chef cap on a silver tray, "
                "crystal champagne glasses, linear ceiling light strips, and night floor-to-ceiling city skyline window in <Picture 1> are <Subject 1>. "
                "The chef in white double-breasted jacket in <Picture 2> is <Subject 2>. The woman in <Picture 3> is <Subject 3>. "
                "The executive man in dark suit in <Picture 4> is <Subject 4>. The chef with red neckerchief in <Picture 5> is <Subject 5>. "
                "The target image shows a medium-wide 4-person standing confrontation around the round grey marble table inside <Subject 1>; "
                "<Subject 1> is partially preserved, keeping the exact round grey marble table, night city skyline window, warm ceiling light strips, and luxury ambiance; "
                "<Subject 2>, <Subject 3>, <Subject 4>, and <Subject 5> are fully preserved in facial identity, hairstyle, and complete outfit from their respective portraits. "
                "On screen-left beside the round grey marble table, <Subject 2> stands upright wearing a thin black neck lanyard with a small gold badge, "
                "next to a dark leather dining chair and an open cylindrical stainless-steel floor trash bin. "
                "On screen-right beside the round grey marble table, <Subject 3> stands linking both hands affectionately around <Subject 4>'s left arm "
                "while <Subject 5> stands smugly on the far right holding the white gold-trimmed ceremonial chef cap at his chest. "
                "Crisp 35mm live-action cinema photography, natural skin texture, zero rectangular hotpot table, zero text or watermarks."
            ),
        },
        {
            "stem": "1-1-04",
            "seed": 1104,
            "refs": [str(KF_2K / "1-1_master_4p_2k.png"), c_ye_2020, c_chu_exec],
            "prompt": (
                "The luxury rooftop VIP dining room, round grey marble table edge, dark leather dining chair, cylindrical stainless-steel floor trash bin, "
                "and night city skyline window in <Picture 1> are <Subject 1>. The chef in <Picture 2> is <Subject 2>. "
                "The executive man in dark suit in <Picture 3> is <Subject 3>. "
                "The target image shows a medium two-shot beside the round grey marble table inside <Subject 1>; "
                "<Subject 1> is partially preserved, keeping the exact round grey marble table, night floor-to-ceiling city window, and warm lighting; "
                "<Subject 2> and <Subject 3> are fully preserved in facial features, hairstyle, and complete outfit. "
                "On screen-left, <Subject 2> (wearing a thin black neck lanyard with a gold badge) stands silently with closed lips beside the dark leather dining chair, "
                "which has a folded faded off-white cotton kitchen cloth draped over its backrest and the open cylindrical stainless-steel trash bin resting on the floor beside its leg. "
                "On screen-right beside the round marble table, <Subject 3> keeps his left hand in his trouser pocket while leaning slightly forward with a disgusted sneer, "
                "reaching two right-hand fingers toward the faded cotton cloth on the chair back. "
                "Crisp 35mm live-action cinema photography, zero rectangular hotpot counter, zero text or watermarks."
            ),
        },
        {
            "stem": "1-1-13_aux",
            "seed": 1113,
            "refs": [str(KF_2K / "1-1_master_4p_2k.png"), c_ye_2020, c_lin_banq, c_chu_exec],
            "prompt": (
                "The luxury rooftop VIP dining room, round grey marble table, night city skyline window, and warm ceiling light strips in <Picture 1> are <Subject 1>. "
                "The chef in white jacket in <Picture 2> is <Subject 2>. The woman in <Picture 3> is <Subject 3>. The man in dark suit in <Picture 4> is <Subject 4>. "
                "The target image shows a wide interior shot looking across the round grey marble table toward dark double wooden exit doors on the right-rear wall of <Subject 1>; "
                "<Subject 1> is partially preserved, keeping the exact round grey marble table (no hotpot burner, no rectangular counter, nobody seated) and night city window; "
                "<Subject 2>, <Subject 3>, and <Subject 4> are fully preserved in appearance and outfit. "
                "On screen-left standing side by side behind the round grey marble table, <Subject 3> and <Subject 4> watch coldly; "
                "at right-rear, <Subject 2> (seen from behind without any neck lanyard) strides resolutely toward the dark double wooden exit doors with his right hand pushing the door handle. "
                "Crisp 35mm live-action cinema photography, zero text or watermarks."
            ),
        },
        # --- SCENE 1-3: Lin Ji Eatery Hall (Square Wooden Table + Bench Backpack + Open Doorway) ---
        {
            "stem": "1-3_post_tear_master",
            "seed": 1312,
            "refs": [str(KF_2K / "1-3-12_aux_2k.png"), c_ye, c_lin, c_chu],
            "prompt": (
                "The sunlit 2005 Chongqing eatery hall, green ceiling fan, square dark-brown wooden table, left wooden bench, right wooden chairs, "
                "terrazzo floor, and white-and-blue floral ceramic spittoon on the floor in <Picture 1> are <Subject 1>. "
                "The young man in <Picture 2> is <Subject 2>. The young woman in <Picture 3> is <Subject 3>. "
                "The young man in floral shirt and dark blazer in <Picture 4> is <Subject 4>. "
                "The target image shows the exact same 3-person medium-wide view of <Subject 1> right after the paper sketch has been torn and discarded; "
                "<Subject 1> is partially preserved, keeping the exact square dark-brown wooden table, ceiling fan, walls, lattice windows, and floor spittoon "
                "(now holding torn white paper scraps inside, while the square wooden tabletop is bare except for one red aluminum cola can near the right edge); "
                "<Subject 2>, <Subject 3>, and <Subject 4> are fully preserved in facial identity, hairstyle, and outfit. "
                "On screen-left, <Subject 2> sits calmly upright on the wooden bench with a zipped faded army-green canvas backpack resting on the wooden bench right beside his left thigh "
                "and his hands resting naturally on top of the backpack; on right-center, <Subject 3> stands glaring down angrily at <Subject 2> with both hands braced on the table edge; "
                "on screen-right, <Subject 4> sits in his wooden chair with arms folded in a smug sneer. "
                "Crisp 35mm live-action cinema photography, zero round table, zero text or watermarks."
            ),
        },
        {
            "stem": "1-3-15",
            "seed": 1315,
            "refs": [str(KF_2K / "1-3_post_tear_master_2k.png"), c_ye],
            "prompt": (
                "The sunlit Chongqing eatery hall, square dark-brown wooden table corner, wooden bench, and zipped faded army-green canvas backpack resting on the wooden bench in <Picture 1> are <Subject 1>. "
                "The young man in <Picture 2> is <Subject 2>. "
                "The target image shows a medium close-up favoring <Subject 2> seated on the wooden bench on screen-left beside the square wooden table in <Subject 1>; "
                "<Subject 1> is partially preserved, keeping the exact square dark-brown wooden table edge on the right foreground and the zipped army-green canvas backpack sitting on the wooden bench beside <Subject 2>'s thigh (never on the floor, never a round table); "
                "<Subject 2> is fully preserved in facial features, hairstyle, and outfit. "
                "<Subject 2> sits calmly upright with closed lips and composed, detached eyes looking steadily toward screen-right, both hands resting naturally on top of the zipped army-green canvas backpack on the bench. "
                "Crisp 35mm live-action cinema photography, zero text or watermarks."
            ),
        },
        {
            "stem": "1-3-18",
            "seed": 1318,
            "refs": [str(KF_2K / "1-3_post_tear_master_2k.png"), c_ye],
            "prompt": (
                "The sunlit Chongqing eatery hall, square dark-brown wooden table corner, wooden bench, and zipped faded army-green canvas backpack resting on the wooden bench in <Picture 1> are <Subject 1>. "
                "The young man in <Picture 2> is <Subject 2>. "
                "The target image shows a medium close-up of <Subject 2> on the wooden bench beside the square wooden table in <Subject 1> just preparing to stand up; "
                "<Subject 1> is partially preserved, keeping the exact square dark-brown wooden table edge on screen-right and wooden bench on screen-left (never a round table, backpack resting on the wooden bench rather than between his shoes); "
                "<Subject 2> is fully preserved in facial features, hairstyle, and outfit. "
                "Leaning slightly forward with cool, resolved eyes directed toward screen-right and closed lips, <Subject 2> grips the shoulder strap of the zipped army-green canvas backpack on the wooden bench with both hands, poised to lift it and rise. "
                "Crisp 35mm live-action cinema photography, zero text or watermarks."
            ),
        },
        {
            "stem": "1-3_doorway_master",
            "seed": 1320,
            "refs": [str(KF_2K / "1-3-21_2k.png"), str(KF_2K / "1-3_post_tear_master_2k.png"), c_ye, c_lin, c_chu],
            "prompt": (
                "The weathered open double wooden shop doors opening onto the sunlit 2005 Chongqing bluestone pedestrian lane in <Picture 1> are <Subject 1>. "
                "The sunlit eatery interior with square dark-brown wooden tables in <Picture 2> is <Subject 2>. "
                "The young man in <Picture 3> is <Subject 3>. The young woman in <Picture 4> is <Subject 4>. The young man in dark blazer in <Picture 5> is <Subject 5>. "
                "The target image shows a wide interior view inside <Subject 2> looking rightward toward the open weathered double wooden front doors of <Subject 1>; "
                "<Subject 1> and <Subject 2> are partially preserved, keeping the exact weathered dark-brown wooden doorway opening onto a quiet sunlit bluestone pedestrian lane with zero modern cars and zero plastic awning; "
                "<Subject 3>, <Subject 4>, and <Subject 5> are fully preserved in appearance and outfit. "
                "At the open wooden doorway threshold on screen-right, <Subject 3> stands alone seen from a three-quarter rear angle with the army-green canvas backpack slung over his right shoulder, pulling the wooden door open onto the bright stone street; "
                "far back on screen-left beside the square wooden table, <Subject 4> remains standing by the table shouting toward the doorway while <Subject 5> sits in his chair. "
                "Crisp 35mm live-action cinema photography, zero text or watermarks."
            ),
        },
        # --- SCENE 2-1: Lin Ji Doorway Stone Steps ---
        {
            "stem": "2-1-04",
            "seed": 2104,
            "refs": [str(KF_2K / "2-1-01_2k.png"), c_lin, c_ye],
            "prompt": (
                "The weathered wooden shop doorway, two flat grey stone steps, and sunlit Chongqing bluestone lane in <Picture 1> are <Subject 1>. "
                "The young woman in <Picture 2> is <Subject 2>. The young man with army-green canvas backpack in <Picture 3> is <Subject 3>. "
                "The target image shows a tighter medium close-up framed from the exact doorway blocking of <Picture 1>; "
                "<Subject 1> is partially preserved, keeping the exact weathered wooden door panels and flat stone step behind <Subject 2>; "
                "<Subject 2> and <Subject 3> are fully preserved in appearance and outfit. "
                "On screen-right standing on the upper stone step, <Subject 2> lifts her chin imperiously looking toward screen-left: "
                "her right hand still grips the taut army-green canvas backpack strap at <Subject 3>'s right shoulder height on the left foreground edge "
                "(showing <Subject 3>'s dark jacket shoulder edge and taut horizontal green strap at chest height, never dangling downward toward the ground), "
                "while <Subject 2> extends her open left palm upward at waist height demanding something. "
                "Crisp 35mm live-action cinema photography, zero text or signboards."
            ),
        },
        {
            "stem": "2-1_post_watch_master",
            "seed": 2107,
            "refs": [str(KF_2K / "2-1-01_2k.png"), c_ye, c_lin, c_chu],
            "prompt": (
                "The weathered double wooden shop doorway, two flat grey stone steps, and sunlit bluestone lane in <Picture 1> are <Subject 1>. "
                "The young man in <Picture 2> is <Subject 2>. The young woman in <Picture 3> is <Subject 3>. "
                "The young man in floral shirt and dark blazer in <Picture 4> is <Subject 4>. "
                "The target image shows a medium 3-person confrontation on the exact stone steps of <Subject 1> right after <Subject 2> returned his wristwatch; "
                "<Subject 1> is partially preserved, keeping the exact weathered wooden doorframe and two flat stone steps (no outdoor brick stoves, no black plastic bags, no signboards); "
                "<Subject 2>, <Subject 3>, and <Subject 4> are fully preserved in facial features, hairstyle, and outfit. "
                "On screen-left on the lower stone step, <Subject 2> stands tall wearing his faded army-green canvas backpack over his right shoulder with his left wrist bare without any watch; "
                "in center-right on the upper stone step, <Subject 3> stands stunned clutching a small black plastic digital wristwatch against her chest with her left hand "
                "while her right hand still holds <Subject 2>'s taut army-green backpack strap (she wears no bag of her own); "
                "on the far right leaning against the wooden doorframe with folded arms, <Subject 4> watches with a smug smirk. "
                "Crisp 35mm live-action cinema photography, zero text or signboards."
            ),
        },
        {
            "stem": "2-1-08",
            "seed": 2108,
            "refs": [str(KF_2K / "2-1_post_watch_master_2k.png"), c_ye],
            "prompt": (
                "The sunlit Chongqing wooden shopfront steps and stone lane background in <Picture 1> are <Subject 1>. "
                "The young man in <Picture 2> is <Subject 2>. "
                "The target image shows a close-up favoring <Subject 2> on screen-left facing screen-right in front of the softly blurred wooden shopfront and stone lane of <Subject 1>; "
                "<Subject 1> is partially preserved in exact midday lighting and wooden doorway background; "
                "<Subject 2> is fully preserved in facial features, hairstyle, and dark jacket over white t-shirt, with the faded army-green canvas backpack strap crossing his right shoulder cleanly (never beige or khaki). "
                "With sharp midday sunlight along his jawline and closed lips, <Subject 2> gazes coldly and resolutely toward screen-right. "
                "Crisp 35mm live-action cinema photography, zero text or signboards."
            ),
        },
        {
            "stem": "2-1-11",
            "seed": 2111,
            "refs": [str(KF_2K / "2-1_post_watch_master_2k.png"), c_lin, c_chu],
            "prompt": (
                "The weathered wooden shop doorway and upper stone step in <Picture 1> are <Subject 1>. "
                "The young woman in <Picture 2> is <Subject 2>. The young man in floral shirt and dark blazer in <Picture 3> is <Subject 3>. "
                "The target image shows a close-up of <Subject 2> on the upper stone step of <Subject 1> turning anxiously toward <Subject 3> leaning softly blurred against the right-rear wooden doorframe; "
                "<Subject 1> is partially preserved in exact wooden doorway texture and midday light; "
                "<Subject 2> and <Subject 3> are fully preserved in facial features, hairstyle, and outfit. "
                "Wearing no shoulder bag of her own, <Subject 2> clutches the small compact black plastic digital wristwatch with thin black wrist strap against her chest with her left hand "
                "(clearly a small wristwatch, never a flashlight or cylindrical object) while turning her head urgently toward right-rear to look at <Subject 3>. "
                "Crisp 35mm live-action cinema photography, zero text or signboards."
            ),
        },
        {
            "stem": "2-1-14",
            "seed": 2114,
            "refs": [str(KF_2K / "2-1_post_watch_master_2k.png"), c_ye, c_lin, c_chu],
            "prompt": (
                "The weathered wooden shop doorway and two flat grey stone steps in <Picture 1> are <Subject 1>. "
                "The young man in <Picture 2> is <Subject 2>. The young woman in <Picture 3> is <Subject 3>. The young man in dark blazer in <Picture 4> is <Subject 4>. "
                "The target image shows a medium 3-person shot on the exact two flat stone steps of <Subject 1> (never a steep mountain staircase); "
                "<Subject 1> is partially preserved in exact doorway woodwork and two flat stone steps; "
                "<Subject 2>, <Subject 3>, and <Subject 4> are fully preserved in appearance and outfit. "
                "On screen-left on the lower flat step, <Subject 2> (bare left wrist) grips the upper part of his own army-green canvas backpack strap on his right shoulder with his right hand, poised to pull it free; "
                "in center-right on the upper step, <Subject 3> clutches the small black plastic wristwatch to her chest with her left hand while her right hand still holds the lower part of <Subject 2>'s taut green strap; "
                "at the right doorframe behind her, <Subject 4> watches smugly. "
                "Crisp 35mm live-action cinema photography, zero text or signboards."
            ),
        },
        {
            "stem": "2-1-14_street_aux",
            "seed": 2115,
            "refs": [str(KF_2K / "2-2-01_2k.png"), str(KF_2K / "2-1-01_2k.png"), c_ye],
            "prompt": (
                "The quiet sunlit 2005 Chongqing bluestone pedestrian lane and clean traditional wooden shopfronts with two grey stone steps and empty sidewalk "
                "(zero outdoor tables, zero outdoor pots, zero text signboards) in <Picture 1> and <Picture 2> are <Subject 1>. "
                "The young man in <Picture 3> is <Subject 2>. "
                "The target image shows a wide sunlit street view along <Subject 1> looking between the two facing traditional wooden shopfronts across the narrow 6-meter bluestone lane; "
                "<Subject 1> is partially preserved with empty clean stone steps and zero outdoor dining tables or signboards; "
                "<Subject 2> is fully preserved in outfit with the faded army-green canvas backpack slung over his right shoulder, seen from behind striding resolutely across the sunlit bluestone road toward the quiet traditional wooden shopfront on the opposite side. "
                "Crisp 35mm live-action cinema photography, zero text or watermarks."
            ),
        },
        # --- SCENE 2-3: Xia Ji Front Hall (Dark Wooden Counter Strictly on SCREEN-RIGHT) ---
        {
            "stem": "2-3-11",
            "seed": 2311,
            "refs": [str(KF_2K / "2-3-13_aux_2k.png"), c_qian, c_ye],
            "prompt": (
                "The bright traditional eatery front hall, dark-brown wooden counter on screen-right with the twine-tied coarse burlap herb bundle resting on the counter surface, "
                "and square wooden dining tables on screen-left in <Picture 1> are <Subject 1>. "
                "The young woman in grey t-shirt and black apron in <Picture 2> is <Subject 2>. The young man in dark jacket in <Picture 3> is <Subject 3>. "
                "The target image shows a medium close-up two-shot beside the dark wooden counter on screen-right inside <Subject 1>, looking toward screen-left; "
                "<Subject 1> is partially preserved, strictly keeping the dark wooden counter and coarse burlap herb bundle on the lower-right foreground and open dining aisle on screen-left (never flipping the counter to screen-left); "
                "<Subject 2> and <Subject 3> are fully preserved in facial features, hairstyle, and outfit. "
                "On screen-right beside the wooden counter, <Subject 3> stands calmly with his faded army-green canvas backpack hanging on his left forearm (army-green canvas, never khaki) "
                "and his right hand resting protectively on the coarse burlap herb bundle on the counter, looking toward screen-left; "
                "right beside him in center-right, <Subject 2> steps half a pace forward past the counter corner raising both hands slightly in anxious concern while looking earnestly toward screen-left. "
                "Crisp 35mm live-action cinema photography, zero text or watermarks."
            ),
        },
    ]

    staged_cache: set[str] = set()
    generated_stems = ["1-3-09"]

    for idx, job in enumerate(jobs, start=1):
        stem = job["stem"]
        out_2k = KF_2K / f"{stem}_2k.png"
        out_1k = KF_1K / f"{stem}_1k.png"
        backup_existing(stem)
        t0 = time.time()
        print(f"[{idx}/{len(jobs)}] Generating {stem} on Spark MiniMax H3 Image ...", flush=True)
        generate_spark_h3_image(
            prompt=job["prompt"],
            out_path=out_2k,
            ref_images=job["refs"],
            aspect_ratio="9:16",
            seed=job["seed"],
            steps=6,
            out_1k_path=out_1k,
            staged_cache=staged_cache,
        )
        dt = time.time() - t0
        print(f"[{idx}/{len(jobs)}] DONE {stem} in {dt:.1f}s -> {out_2k.name}", flush=True)
        generated_stems.append(stem)

    # Render contact sheet of all 15 rebuilt Master Plates & Keyframes
    cols = 5
    rows = (len(generated_stems) + cols - 1) // cols
    cell_w, cell_h = 360, 640
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for i, stem in enumerate(generated_stems):
        im = Image.open(KF_2K / f"{stem}_2k.png").convert("RGB").resize((cell_w, cell_h))
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        sheet.paste(im, (x, y))
        draw.rectangle([x, y, x + 230, y + 28], fill=(0, 0, 0))
        draw.text((x + 8, y + 6), stem, fill=(255, 230, 80))
    sheet_path = AUDIT_DIR / "spark_rebuilt_keyframes_sheet.jpg"
    sheet.save(sheet_path, quality=92)
    print(f"ALL 15 SPARK KEYFRAMES READY -> {sheet_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
