import streamlit as st
import subprocess
import tempfile
import os
import time
import json
import re
import asyncio
from urllib.parse import urlparse, parse_qs

import imageio_ffmpeg
import edge_tts
from google import genai

st.set_page_config(
    page_title="Myanmar AI Movie Recap",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 Myanmar AI Auto Movie Recap")
st.caption("AI Movie Recap • Thiha / Nilar Voice • Myanmar Subtitle")
st.info("Recap Video ကို အများဆုံး ၅ မိနစ်အထိ ဖန်တီးပေးပါတယ်။ ကိုယ်ပိုင် သို့မဟုတ် အသုံးပြုခွင့်ရှိတဲ့ Video များကိုသာ အသုံးပြုပါ။")

VOICES = {
    "Thiha (အမျိုးသားအသံ)": "my-MM-ThihaNeural",
    "Nilar (အမျိုးသမီးအသံ)": "my-MM-NilarNeural"
}
MODEL_NAME = MODEL_NAME = "gemini-3.8-flash"

def get_api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        return st.secrets.get("GEMINI_API_KEY", "").strip()
    except Exception:
        return ""

def run_ffmpeg(command, timeout=1800):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3500:] or "FFmpeg processing failed")
    return result

async def save_tts(text, voice, rate, path):
    communicator = edge_tts.Communicate(text, voice, rate=rate)
    await communicator.save(path)

def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise ValueError("AI က JSON ပုံစံအဖြေ မပေးနိုင်ပါ။ ထပ်စမ်းကြည့်ပါ။")
        return json.loads(match.group(0))

def is_youtube_url(url):
    try:
        parsed = urlparse(url.strip())
        host = (parsed.netloc or "").lower()
        return host.endswith("youtube.com") or host.endswith("youtu.be")
    except Exception:
        return False

def analyze_video_with_gemini(client, uploaded_file=None, youtube_url=None, target_seconds=300):
    prompt = f"""
သင်သည် professional Myanmar movie recap script writer နှင့် video editor ဖြစ်သည်။
ပေးထားသော video ကို ကြည့်ပြီး မြန်မာဘာသာဖြင့် စိတ်ဝင်စားဖွယ် recap တစ်ခု ဖန်တီးပါ။
Output ကို JSON သာ ပြန်ပေးပါ။ Markdown မထည့်ပါနှင့်။

လိုအပ်ချက်များ:
- နောက်ဆုံး video သည် {target_seconds} စက္ကန့်ထက် မကျော်ရ။
- အရေးကြီးသော ဇာတ်ဝင်ခန်း 8 မှ 14 ခု ရွေးပါ။
- scenes တစ်ခုချင်းစီတွင် start နှင့် end ကို စက္ကန့်ဂဏန်း (number) ဖြင့် ပေးပါ။
- start/end သည် မူရင်း video ထဲရှိ အချိန်ဖြစ်ရမည်။ end သည် start ထက်ကြီးရမည်။
- scene များကို ဇာတ်လမ်းအစဉ်လိုက် ရွေးပါ။
- scene တစ်ခုချင်းစီ၏ clip_length ကို 8 မှ 35 စက္ကန့်အတွင်းထားပါ။
- စုစုပေါင်း scene clip အရှည်ကို 260 မှ {target_seconds} စက္ကန့်အတွင်း ဖြစ်နိုင်သမျှထားပါ။ မူရင်း video တိုပါက ရနိုင်သလောက်သာ ရွေးပါ။
- narration ကို မြန်မာလို သဘာဝကျပြီး ဇာတ်လမ်းကို မဖန်တီးမပြောဘဲ video ထဲက အချက်အလက်အပေါ် အခြေခံရေးပါ။
- narration သည် ၅ မိနစ်အတွင်း ပြောနိုင်မည့် အရှည်ဖြစ်ရမည်။
- title ကို မြန်မာလို ပေးပါ။

JSON schema:
{{
  "title": "မြန်မာ recap ခေါင်းစဉ်",
  "narration": "အသံဖတ်ရန် မြန်မာစာသား",
  "scenes": [
    {{"start": 12.0, "end": 30.0, "reason": "ဘာကြောင့် ဒီအခန်းရွေးသလဲ"}}
  ]
}}
"""
    if youtube_url:
        interaction = client.interactions.create(
            model=MODEL_NAME,
            input=[
                {"type": "video", "uri": youtube_url.strip()},
                {"type": "text", "text": prompt}
            ]
        )
    else:
        uploaded = client.files.upload(file=uploaded_file)
        deadline = time.time() + 900
        while True:
            current = client.files.get(name=uploaded.name)
            state = getattr(current, "state", None)
            state_name = getattr(state, "name", str(state)).upper() if state else ""
            if state_name == "ACTIVE":
                uploaded = current
                break
            if state_name == "FAILED":
                raise RuntimeError("Gemini က Video ကို ဖတ်မရပါ။ MP4 format နဲ့ ထပ်စမ်းပါ။")
            if time.time() > deadline:
                raise TimeoutError("Video processing ကြာလွန်းနေပါတယ်။ File ပိုသေးတာနဲ့ ထပ်စမ်းပါ။")
            time.sleep(5)

        interaction = client.interactions.create(
            model=MODEL_NAME,
            input=[
                {"type": "video", "uri": uploaded.uri, "mime_type": uploaded.mime_type},
                {"type": "text", "text": prompt}
            ]
        )
    output_text = getattr(interaction, "output_text", None)
    if not output_text:
        raise RuntimeError("Gemini က စာသားအဖြေ မပြန်ပေးပါ။")
    return extract_json(output_text)

def create_srt(text, duration, path):
    # စာကြောင်းတိုများကို subtitle အဖြစ် အချိန်ခွဲပြသည်။
    parts = [p.strip() for p in re.split(r"(?<=[။!?])\s*", text) if p.strip()]
    if not parts:
        parts = [text.strip()]
    total_chars = sum(max(len(p), 1) for p in parts)
    cursor = 0.0
    entries = []
    for part in parts:
        span = max(2.0, duration * max(len(part), 1) / max(total_chars, 1))
        start = cursor
        end = min(duration, cursor + span)
        entries.append((start, end, part))
        cursor = end
    def stamp(seconds):
        ms = int(max(0, seconds) * 1000)
        hh = ms // 3600000
        mm = (ms % 3600000) // 60000
        ss = (ms % 60000) // 1000
        milli = ms % 1000
        return f"{hh:02}:{mm:02}:{ss:02},{milli:03}"
    with open(path, "w", encoding="utf-8") as f:
        for i, (start, end, part) in enumerate(entries, 1):
            f.write(f"{i}\n{stamp(start)} --> {stamp(end)}\n{part}\n\n")

def make_recap(source_file, analysis, voice_id, voice_rate, output_path, srt_path, progress):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    scenes = analysis.get("scenes", [])
    narration = str(analysis.get("narration", "")).strip()
    if not narration or not scenes:
        raise ValueError("AI အဖြေမှာ narration သို့မဟုတ် scene မပါဝင်ပါ။")
    cleaned = []
    for scene in scenes:
        try:
            start = max(0.0, float(scene["start"]))
            end = max(0.0, float(scene["end"]))
            if end > start:
                cleaned.append((start, end))
        except Exception:
            continue
    if not cleaned:
        raise ValueError("AI ရွေးထားတဲ့ scene timestamp မမှန်ပါ။ ထပ်စမ်းပါ။")

    with tempfile.TemporaryDirectory() as work:
        clip_paths = []
        total = 0.0
        list_path = os.path.join(work, "clips.txt")
        for index, (start, end) in enumerate(cleaned, 1):
            if total >= 295:
                break
            clip_len = min(end - start, 35.0, 295.0 - total)
            if clip_len < 2:
                continue
            clip_path = os.path.join(work, f"clip_{index:02d}.mp4")
            cmd = [
                ffmpeg, "-y", "-ss", str(start), "-i", source_file,
                "-t", str(clip_len),
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                "-pix_fmt", "yuv420p", clip_path
            ]
            run_ffmpeg(cmd, timeout=900)
            clip_paths.append(clip_path)
            total += clip_len
            progress.progress(min(0.55, 0.08 + 0.45 * len(clip_paths) / max(len(cleaned), 1)),
                              text=f"ဇာတ်ဝင်ခန်း {len(clip_paths)} ကို ပြင်ဆင်နေပါတယ်...")
        if not clip_paths:
            raise ValueError("အသုံးပြုနိုင်တဲ့ ဇာတ်ဝင်ခန်း မတွေ့ပါ။")

        with open(list_path, "w", encoding="utf-8") as f:
            for path in clip_paths:
                safe = path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{safe}'\n")

        joined = os.path.join(work, "joined.mp4")
        run_ffmpeg([
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", list_path,
            "-c", "copy", joined
        ], timeout=900)

        voice_path = os.path.join(work, "narration.mp3")
        asyncio.run(save_tts(narration, voice_id, voice_rate, voice_path))
        create_srt(narration, min(total, 300), srt_path)

        run_ffmpeg([
            ffmpeg, "-y", "-i", joined, "-i", voice_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", "tpad=stop_mode=clone:stop_duration=300",
            "-af", "apad",
            "-t", "300",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", output_path
        ], timeout=1800)
        progress.progress(1.0, text="Recap Video ပြီးပါပြီ!")

tab_recap, tab_voice, tab_info = st.tabs(["🎬 AI Movie Recap", "🎙️ Voice Studio", "ℹ️ အသုံးပြုပုံ"])

with tab_recap:
    st.subheader("🎬 အလိုအလျောက် Movie Recap")
    source_mode = st.radio("Video ထည့်သွင်းနည်း", ["ဖုန်းထဲမှ Upload", "Public YouTube Link"], horizontal=False)
    uploaded_video = None
    youtube_url = ""
    if source_mode == "ဖုန်းထဲမှ Upload":
        uploaded_video = st.file_uploader("Movie / Video Upload (MP4, MOV, MKV, WEBM)", type=["mp4", "mov", "mkv", "webm"])
        if uploaded_video:
            st.video(uploaded_video)
            st.caption(f"ဖိုင်အရွယ်အစား: {uploaded_video.size / (1024*1024):.1f} MB")
            if uploaded_video.size > 1800 * 1024 * 1024:
                st.error("Free Gemini File API အတွက် 2GB ထက်မကြီးရပါ။ ပိုသေးတဲ့ဖိုင်ကို သုံးပါ။")
    else:
        youtube_url = st.text_input("Public YouTube URL ထည့်ပါ", placeholder="https://www.youtube.com/watch?v=...")
        st.caption("YouTube public video များသာ လက်ခံနိုင်ပါတယ်။ TikTok URL ကို လောလောဆယ် မပံ့ပိုးသေးပါ။")
        if youtube_url and not is_youtube_url(youtube_url):
            st.warning("YouTube URL မှန်ကန်စွာ ထည့်ပါ။")

    voice_name = st.selectbox("မြန်မာ AI အသံ", list(VOICES.keys()), key="recap_voice")
    voice_rate = st.select_slider("အသံအမြန်နှုန်း", options=["-15%", "-10%", "+0%", "+10%", "+15%"], value="+0%", key="recap_rate")
    st.caption("Output: 16:9 MP4 • အများဆုံး ၅ မိနစ် • Myanmar narration + SRT subtitle")

    if st.button("✨ AUTO RECAP ဖန်တီးမယ်", type="primary", use_container_width=True):
        api_key = get_api_key()
        if not api_key:
            st.error("GEMINI_API_KEY မတွေ့ပါ။ Render Environment မှာ GEMINI_API_KEY ထည့်ပါ။")
        elif source_mode == "ဖုန်းထဲမှ Upload" and not uploaded_video:
            st.warning("အရင်ဆုံး Video Upload လုပ်ပါ။")
        elif source_mode == "Public YouTube Link" and not is_youtube_url(youtube_url):
            st.warning("Public YouTube URL မှန်ကန်စွာ ထည့်ပါ။")
        else:
            try:
                client = genai.Client(api_key=api_key)
                progress = st.progress(0, text="AI က Movie ကို စစ်ဆေးနေပါတယ်...")
                with tempfile.TemporaryDirectory() as temp_dir:
                    input_path = None
                    if uploaded_video:
                        suffix = os.path.splitext(uploaded_video.name)[1].lower() or ".mp4"
                        input_path = os.path.join(temp_dir, "source" + suffix)
                        with open(input_path, "wb") as f:
                            f.write(uploaded_video.getbuffer())
                    analysis = analyze_video_with_gemini(
                        client,
                        uploaded_file=input_path,
                        youtube_url=youtube_url if source_mode == "Public YouTube Link" else None,
                        target_seconds=300
                    )
                    st.session_state["last_recap_script"] = analysis.get("narration", "")
                    st.session_state["last_recap_title"] = analysis.get("title", "Myanmar Movie Recap")
                    st.write("### " + str(analysis.get("title", "Myanmar Movie Recap")))
                    st.write(analysis.get("narration", ""))
                    if source_mode == "Public YouTube Link":
                        st.warning("YouTube Link ကို AI က သုံးသပ်ပြီး Script ထုတ်ပေးနိုင်ပါတယ်။ MP4 ဖန်တီးရန် မူရင်း Video ဖိုင်ကို Upload လုပ်ရန် လိုအပ်သေးပါတယ်။ YouTube link တစ်ခုတည်းဖြင့် Video ကို ပြန်လည် Download မလုပ်ပါ။")
                        st.success("AI Recap Script ရရှိပါပြီ။ Video ကို ဖန်တီးရန် တူညီသော Video ကို Upload နဲ့ ပြန်ထည့်ပြီး Auto Recap လုပ်ပါ။")
                    else:
                        progress.progress(0.58, text="Thiha / Nilar အသံနှင့် Video တည်ဆောက်နေပါတယ်...")
                        out_path = os.path.join(temp_dir, "myanmar_movie_recap.mp4")
                        srt_path = os.path.join(temp_dir, "myanmar_movie_recap.srt")
                        make_recap(input_path, analysis, VOICES[voice_name], voice_rate, out_path, srt_path, progress)
                        with open(out_path, "rb") as f:
                            output_bytes = f.read()
                        with open(srt_path, "rb") as f:
                            subtitle_bytes = f.read()
                        st.session_state["recap_mp4"] = output_bytes
                        st.session_state["recap_srt"] = subtitle_bytes
                        st.success("🎉 Myanmar Movie Recap ပြီးပါပြီ!")
                        st.video(output_bytes)
            except Exception as e:
                st.error("Recap ဖန်တီးရာတွင် အမှားဖြစ်နေပါတယ်။")
                st.code(str(e))

    if "recap_mp4" in st.session_state:
        st.download_button("⬇️ DOWNLOAD RECAP MP4", st.session_state["recap_mp4"],
                           file_name="myanmar_movie_recap.mp4", mime="video/mp4",
                           use_container_width=True)
    if "recap_srt" in st.session_state:
        st.download_button("⬇️ DOWNLOAD MYANMAR SUBTITLE (SRT)", st.session_state["recap_srt"],
                           file_name="myanmar_movie_recap.srt", mime="application/x-subrip",
                           use_container_width=True)

with tab_voice:
    st.subheader("🎙️ Myanmar AI Voice Studio")
    voice_text = st.text_area("အသံပြောင်းလိုသော မြန်မာစာ", height=160)
    voice_name = st.selectbox("အသံရွေးချယ်ပါ", list(VOICES.keys()), key="studio_voice")
    voice_rate = st.select_slider("အသံအမြန်နှုန်း", options=["-20%", "-10%", "+0%", "+10%", "+20%"], value="+0%", key="studio_rate")
    if st.button("🎙️ Generate MP3", type="primary"):
        if not voice_text.strip():
            st.warning("မြန်မာစာ အရင်ထည့်ပါ။")
        else:
            try:
                with tempfile.TemporaryDirectory() as folder:
                    mp3_path = os.path.join(folder, "voice.mp3")
                    asyncio.run(save_tts(voice_text, VOICES[voice_name], voice_rate, mp3_path))
                    with open(mp3_path, "rb") as f:
                        st.session_state["studio_mp3"] = f.read()
                st.success("အသံဖိုင် ပြီးပါပြီ။")
            except Exception as e:
                st.error(str(e))
    if "studio_mp3" in st.session_state:
        st.audio(st.session_state["studio_mp3"], format="audio/mp3")
        st.download_button("⬇️ DOWNLOAD MP3", st.session_state["studio_mp3"],
                           file_name="myanmar_ai_voice.mp3", mime="audio/mpeg")

with tab_info:
    st.subheader("အသုံးပြုပုံနှင့် ကန့်သတ်ချက်")
    st.markdown("""
- **Upload:** ဖုန်းထဲမှ ကိုယ်ပိုင်/အသုံးပြုခွင့်ရှိသော MP4, MOV, MKV, WEBM ဖိုင်တင်ပါ။
- **YouTube:** Public YouTube URL ဖြင့် AI Recap Script ထုတ်နိုင်သည်။ MP4 ပြုလုပ်ရန် မူရင်း Video ဖိုင်ကို Upload လုပ်ရန် လိုအပ်သည်။
- **TikTok:** လောလောဆယ် URL တိုက်ရိုက်မပံ့ပိုးသေးပါ။
- **အသံ:** Thiha / Nilar Edge TTS ကို အသုံးပြုသည်။ Internet လိုအပ်သည်။
- **Subtitle:** မြန်မာ SRT ဖိုင်ကို သီးခြား Download လုပ်နိုင်သည်။
- **Free Tier:** Gemini Free Tier နှင့် Render Free Instance တို့တွင် request, processing time, file size နှင့် sleeping ကန့်သတ်ချက်များရှိနိုင်သည်။
- Gemini video analysis သည် တစ်စက္ကန့်လျှင် frame တစ်ခုခန့်သာ စစ်ဆေးနိုင်သောကြောင့် လှုပ်ရှားမှုမြန်သောအခန်းအချို့ လွတ်နိုင်သည်။
""")
    st.caption("Myanmar AI Movie Recap | Thiha & Nilar Neural Voice")
