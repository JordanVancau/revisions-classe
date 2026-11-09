"""
Pipeline Automatisé de Création de Cours pour la Plateforme de Révision
Prend en entrée la structure d'un cours, génère l'audio (Edge-TTS),
les diapositives 1080p (Pillow), la vidéo MP4 (FFmpeg),
la page web dédiée et met à jour le catalogue central courses.json.
"""

import os
import sys
import json
import re
import asyncio
import subprocess
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import edge_tts
import imageio_ffmpeg

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COURSES_DIR = os.path.join(BASE_DIR, "cours")
DATA_FILE = os.path.join(BASE_DIR, "courses.json")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Fonts
REGULAR_FONT = "C:/Windows/Fonts/segoeui.ttf"
BOLD_FONT = "C:/Windows/Fonts/segoeuib.ttf"
SEMIBOLD_FONT = "C:/Windows/Fonts/seguisb.ttf"
if not os.path.exists(REGULAR_FONT):
    REGULAR_FONT = "C:/Windows/Fonts/arial.ttf"
    BOLD_FONT = "C:/Windows/Fonts/arialbd.ttf"
    SEMIBOLD_FONT = BOLD_FONT

def get_font(size, weight="regular"):
    if weight == "bold":
        return ImageFont.truetype(BOLD_FONT, size)
    elif weight == "semibold":
        return ImageFont.truetype(SEMIBOLD_FONT, size)
    return ImageFont.truetype(REGULAR_FONT, size)

def slugify(text):
    text = text.lower()
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def get_video_duration(video_path):
    cmd = [FFMPEG, "-i", video_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', res.stderr)
    if m:
        sec = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
        mins = int(sec // 60)
        secs = int(sec % 60)
        return f"{mins:02d}:{secs:02d}", sec
    return "00:00", 0

async def build_course(course_meta, slides_data, quiz_data=None):
    course_id = course_meta.get("id") or slugify(course_meta["title"])
    target_dir = os.path.join(COURSES_DIR, course_id)
    slides_dir = os.path.join(target_dir, "slides")
    audio_dir = os.path.join(target_dir, "audio")
    clips_dir = os.path.join(target_dir, "temp_clips")
    video_path = os.path.join(target_dir, "video.mp4")
    
    os.makedirs(slides_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(clips_dir, exist_ok=True)
    
    print(f"\n🚀 [PIPELINE] Création du cours : '{course_meta['title']}' ({course_id})")
    
    # 1. Génération audio avec Edge-TTS
    print("🎙️ Étape 1 : Synthèse vocale naturelle (fr-FR-DeniseNeural)...")
    for idx, slide in enumerate(slides_data, 1):
        mp3_path = os.path.join(audio_dir, f"voice_{idx:02d}.mp3")
        comm = edge_tts.Communicate(slide["audio"], "fr-FR-DeniseNeural", rate="-2%")
        await comm.save(mp3_path)
    
    # 2. Rendu des diapositives PNG 1080p
    print("🎨 Étape 2 : Rendu des diapositives 1080p...")
    for idx, slide in enumerate(slides_data, 1):
        png_path = os.path.join(slides_dir, f"slide_{idx:02d}.png")
        render_slide_to_png(slide, idx, len(slides_data), png_path)
        
    # 3. Compilation des clips et vidéo MP4 avec FFmpeg
    print("🎬 Étape 3 : Compilation vidéo MP4 avec FFmpeg...")
    clip_files = []
    timestamps = [0.0]
    current_time = 0.0
    
    for idx in range(1, len(slides_data) + 1):
        png_path = os.path.join(slides_dir, f"slide_{idx:02d}.png")
        mp3_path = os.path.join(audio_dir, f"voice_{idx:02d}.mp3")
        clip_path = os.path.join(clips_dir, f"clip_{idx:02d}.mp4")
        
        cmd = [
            FFMPEG, "-y",
            "-loop", "1",
            "-i", png_path,
            "-i", mp3_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            clip_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        clip_files.append(clip_path)
        
        # calculate clip duration
        _, duration_sec = get_video_duration(clip_path)
        current_time += duration_sec
        if idx < len(slides_data):
            timestamps.append(round(current_time, 2))
            
    # Concaténation finale
    concat_txt = os.path.join(clips_dir, "concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in clip_files:
            f.write(f"file '{c.replace(chr(92), '/')}'\n")
            
    subprocess.run([
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        video_path
    ], capture_output=True, check=True)
    
    # Nettoyage clips temporaires
    for c in clip_files:
        try: os.remove(c)
        except: pass
    try: os.remove(concat_txt)
    except: pass
    try: os.rmdir(clips_dir)
    except: pass
    
    formatted_duration, total_seconds = get_video_duration(video_path)
    print(f"✅ Vidéo compilée avec succès : {video_path} (Durée: {formatted_duration})")
    
    # 4. Génération de la page HTML du cours
    print("📄 Étape 4 : Génération de la page web dédiée index.html...")
    generate_course_page(course_meta, slides_data, timestamps, formatted_duration, target_dir, quiz_data)
    
    # 5. Mise à jour de courses.json
    print("📊 Étape 5 : Mise à jour du catalogue central courses.json...")
    update_catalog(course_meta, course_id, formatted_duration, len(slides_data))
    
    # 6. Déploiement automatique en ligne via Git Push
    print("🚀 Étape 6 : Publication automatique en ligne sur GitHub Pages...")
    try:
        git_exe = r"C:\Users\jorda\AppData\Local\Programs\Git\cmd\git.exe"
        subprocess.run([git_exe, "add", "."], cwd=BASE_DIR, check=True)
        commit_msg = f"Ajout automatique du cours: {course_meta['title']}"
        subprocess.run([git_exe, "commit", "-m", commit_msg], cwd=BASE_DIR, check=True)
        subprocess.run([git_exe, "push", "origin", "main"], cwd=BASE_DIR, check=True)
        print("🌍 Site mis à jour en ligne avec succès sur GitHub Pages !")
    except Exception as e:
        print(f"⚠️ Note Git : {e}")
        
    print(f"\n🎉 [SUCCÈS] Le cours '{course_meta['title']}' est prêt et en ligne sur votre site !")

def render_slide_to_png(slide, idx, total, output_path):
    img = Image.new("RGB", (1920, 1080), color=(11, 19, 43))
    draw = ImageDraw.Draw(img)
    
    # Top banner
    draw.rectangle([0, 0, 1920, 6], fill=(99, 102, 241))
    
    # Title
    draw.rounded_rectangle([80, 50, 480, 95], radius=8, fill=(99, 102, 241))
    draw.text((100, 60), f"MODULE {idx} / {total}", fill=(255, 255, 255), font=get_font(18, "bold"))
    
    draw.text((80, 120), slide["title"], fill=(255, 255, 255), font=get_font(46, "bold"))
    if slide.get("subtitle"):
        draw.text((80, 185), slide["subtitle"], fill=(148, 163, 184), font=get_font(24, "regular"))
        
    draw.line([(80, 240), (1840, 240)], fill=(30, 41, 59), width=2)
    
    # Content cards or bullet points
    cards = slide.get("cards", [])
    if cards:
        card_w = (1760 - (len(cards) - 1) * 30) // len(cards)
        for c_idx, c in enumerate(cards):
            cx = 80 + c_idx * (card_w + 30)
            cy = 280
            ch = 680
            color = c.get("color", (99, 102, 241))
            draw.rounded_rectangle([cx, cy, cx + card_w, cy + ch], radius=16, fill=(18, 28, 52), outline=color, width=2)
            draw.rounded_rectangle([cx, cy, cx + card_w, cy + 70], radius=16, fill=color)
            draw.text((cx + 25, cy + 20), c["title"], fill=(255, 255, 255), font=get_font(22, "bold"))
            
            py = cy + 100
            for pt in c.get("points", []):
                draw.ellipse([cx + 25, py + 8, cx + 35, py + 18], fill=color)
                # Word wrap
                words = pt.split()
                lines = []
                cur = ""
                for w in words:
                    test = cur + (" " if cur else "") + w
                    if len(test) > (card_w // 15):
                        lines.append(cur)
                        cur = w
                    else:
                        cur = test
                if cur: lines.append(cur)
                for l in lines:
                    draw.text((cx + 45, py), l, fill=(226, 232, 240), font=get_font(20, "regular"))
                    py += 28
                py += 14
    else:
        # Simple text box
        draw.rounded_rectangle([80, 280, 1840, 960], radius=18, fill=(18, 28, 52), outline=(99, 102, 241), width=2)
        py = 320
        for pt in slide.get("points", []):
            draw.text((120, py), f"• {pt}", fill=(226, 232, 240), font=get_font(26, "regular"))
            py += 60

    # Bottom progress bar
    prog = int((1840 - 80) * (idx / total))
    draw.line([(80, 1030), (1840, 1030)], fill=(30, 41, 59), width=4)
    draw.line([(80, 1030), (80 + prog, 1030)], fill=(99, 102, 241), width=4)
    draw.text((80, 1045), "PORTAIL DE RÉVISION SCOLAIRE • VIDÉO OFFICIELLE", fill=(100, 116, 139), font=get_font(16, "semibold"))
    
    img.save(output_path)

def generate_course_page(course_meta, slides_data, timestamps, duration, target_dir, quiz_data):
    # Builds an HTML file using the template
    chapters_html = ""
    for idx, slide in enumerate(slides_data):
        active_cls = " active" if idx == 0 else ""
        sub = slide.get("subtitle") or ""
        chapters_html += f"""
        <div class="chapter-item{active_cls}" onclick="jumpTo({idx})">
            <div class="chapter-num">{idx + 1}</div>
            <div class="chapter-info">
                <div class="chapter-title">{slide['title']}</div>
                <div class="chapter-sub">{sub}</div>
            </div>
        </div>
        """
        
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{course_meta['title']} • Révision Vidéo</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0b132b;
            --surface: #131c38;
            --surface-card: #1c2a4f;
            --border: #2a3b68;
            --primary: #6366f1;
            --emerald: #10b981;
            --rose: #f43f5e;
            --text: #f8fafc;
            --text-muted: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; min-height: 100vh; display: flex; flex-direction: column; }}
        header {{ background: #0e1733; border-bottom: 1px solid var(--border); padding: 1.5rem 2rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }}
        .btn {{ background: var(--surface-card); border: 1px solid var(--border); color: var(--text); padding: 0.6rem 1.2rem; border-radius: 10px; font-weight: 600; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 0.5rem; }}
        .btn-primary {{ background: var(--primary); border-color: #818cf8; }}
        main {{ flex: 1; max-width: 1400px; width: 100%; margin: 0 auto; padding: 2rem; display: grid; grid-template-columns: 1fr 380px; gap: 2rem; }}
        @media (max-width: 1024px) {{ main {{ grid-template-columns: 1fr; }} }}
        .video-container {{ background: var(--surface); border: 1px solid var(--border); border-radius: 20px; overflow: hidden; }}
        .screen-frame {{ aspect-ratio: 16 / 9; background: #000; }}
        video {{ width: 100%; height: 100%; }}
        .sidebar {{ display: flex; flex-direction: column; gap: 1.5rem; }}
        .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem; }}
        .chapter-item {{ display: flex; align-items: center; gap: 0.8rem; padding: 0.75rem 1rem; background: var(--surface-card); border-radius: 12px; cursor: pointer; margin-bottom: 0.5rem; }}
        .chapter-item.active {{ border: 1px solid var(--primary); background: rgba(99, 102, 241, 0.2); }}
        .chapter-num {{ width: 28px; height: 28px; border-radius: 8px; background: var(--primary); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem; }}
        .chapter-title {{ font-size: 0.9rem; font-weight: 600; }}
        .chapter-sub {{ font-size: 0.75rem; color: var(--text-muted); }}
        footer {{ text-align: center; padding: 2rem; color: var(--text-muted); border-top: 1px solid var(--border); margin-top: auto; }}
    </style>
</head>
<body>
<header>
    <div>
        <a href="../../index.html" class="btn" style="margin-bottom: 0.6rem; font-size: 0.85rem; padding: 0.4rem 0.8rem;">← Retour au portail</a>
        <h1 style="font-size: 1.6rem; font-weight: 800;">{course_meta['title']}</h1>
    </div>
    <a href="video.mp4" class="btn btn-primary" download>📥 Télécharger la vidéo ({duration})</a>
</header>
<main>
    <div class="video-container">
        <div class="screen-frame">
            <video id="mainVideo" controls poster="slides/slide_01.png">
                <source src="video.mp4" type="video/mp4">
            </video>
        </div>
        <div style="padding: 1.25rem 1.5rem; display: flex; justify-content: space-between;">
            <span style="font-weight: 700;" id="currentSlideTitle">{slides_data[0]['title']}</span>
            <span style="font-family: 'JetBrains Mono', monospace; color: var(--text-muted);">{duration}</span>
        </div>
    </div>
    <div class="sidebar">
        <div class="card">
            <h3 style="margin-bottom: 1rem;">📑 Chapitres de la vidéo</h3>
            <div style="max-height: 480px; overflow-y: auto;">
                {chapters_html}
            </div>
        </div>
    </div>
</main>
<footer>Plateforme de révision scolaire • Conçue pour la classe</footer>
<script>
    const video = document.getElementById('mainVideo');
    const items = document.querySelectorAll('.chapter-item');
    const titleDisplay = document.getElementById('currentSlideTitle');
    const timestamps = {json.dumps(timestamps)};

    function jumpTo(index) {{
        if (index >= 0 && index < timestamps.length) {{
            video.currentTime = timestamps[index];
            video.play();
            updateActive(index);
        }}
    }}

    function updateActive(index) {{
        items.forEach((item, idx) => {{
            if (idx === index) {{
                item.classList.add('active');
                titleDisplay.innerText = item.querySelector('.chapter-title').innerText;
            }} else {{
                item.classList.remove('active');
            }}
        }});
    }}

    video.addEventListener('timeupdate', () => {{
        const ct = video.currentTime;
        for (let i = timestamps.length - 1; i >= 0; i--) {{
            if (ct >= timestamps[i]) {{
                updateActive(i);
                break;
            }}
        }}
    }});
</script>
</body>
</html>
"""
    with open(os.path.join(target_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

def update_catalog(course_meta, course_id, duration, slides_count):
    catalog = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                catalog = json.load(f)
        except:
            catalog = []
            
    # Check if course exists
    exists = False
    for c in catalog:
        if c.get("id") == course_id:
            c.update({
                "title": course_meta["title"],
                "subject": course_meta.get("subject", "Général"),
                "duration": duration,
                "slides_count": slides_count,
                "description": course_meta.get("description", ""),
                "date": datetime.now().strftime("%Y-%m-%d")
            })
            exists = True
            break
            
    if not exists:
        catalog.append({
            "id": course_id,
            "title": course_meta["title"],
            "subject": course_meta.get("subject", "Général"),
            "badge_color": course_meta.get("badge_color", "#6366f1"),
            "duration": duration,
            "slides_count": slides_count,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": course_meta.get("description", ""),
            "thumbnail": f"cours/{course_id}/slides/slide_01.png",
            "link": f"cours/{course_id}/index.html",
            "tags": course_meta.get("tags", [])
        })
        
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    print("Course pipeline helper ready.")
