
import streamlit as st
import subprocess
import tempfile
import os
import asyncio
import imageio_ffmpeg
import edge_tts

st.set_page_config(
    page_title="Myanmar AI Auto Video Editor",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 MYANMAR AI AUTO VIDEO EDITOR")
st.write("မြန်မာ AI Video Editing & Voice Studio")

st.success("Thiha / Nilar Myanmar AI Voice ပါဝင်ပါပြီ")

# Voice settings
VOICES = {
    "Thiha (အမျိုးသားအသံ)": "my-MM-ThihaNeural",
    "Nilar (အမျိုးသမီးအသံ)": "my-MM-NilarNeural"
}

st.header("🎙️ Myanmar AI Voice")

voice_text = st.text_area(
    "အသံပြောင်းလိုသော မြန်မာစာထည့်ပါ",
    height=150,
    placeholder="မင်္ဂလာပါ။ ကျွန်တော်တို့ရဲ့ Video ကို ကြည့်ရှုပေးတဲ့အတွက် ကျေးဇူးတင်ပါတယ်။"
)

voice_name = st.selectbox(
    "AI Voice ရွေးချယ်ပါ",
    list(VOICES.keys())
)

voice_rate = st.select_slider(
    "အသံအမြန်နှုန်း",
    options=["-20%", "-10%", "+0%", "+10%", "+20%"],
    value="+0%"
)

async def make_voice(text, voice, rate):
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "voice.mp3")
        communicate = edge_tts.Communicate(
            text,
            voice,
            rate=rate
        )
        await communicate.save(path)

        with open(path, "rb") as f:
            return f.read()

if st.button("🎙️ GENERATE AI VOICE", type="primary"):
    if not voice_text.strip():
        st.warning("မြန်မာစာ အရင်ထည့်ပါ")
    else:
        try:
            with st.spinner("AI Voice ဖန်တီးနေပါတယ်..."):
                audio = asyncio.run(
                    make_voice(
                        voice_text,
                        VOICES[voice_name],
                        voice_rate
                    )
                )
                st.session_state["voice_mp3"] = audio

            st.success("AI Voice ထုတ်ပြီးပါပြီ!")
        except Exception as e:
            st.error("AI Voice မထုတ်နိုင်ပါ")
            st.code(str(e))

if "voice_mp3" in st.session_state:
    st.audio(
        st.session_state["voice_mp3"],
        format="audio/mp3"
    )
    st.download_button(
        "⬇️ DOWNLOAD MP3",
        data=st.session_state["voice_mp3"],
        file_name="myanmar_ai_voice.mp3",
        mime="audio/mpeg"
    )

st.divider()

# Video editor
st.header("🎬 AUTO VIDEO EDITOR")

video = st.file_uploader(
    "📤 Video Upload လုပ်ပါ",
    type=["mp4", "mov", "mkv"]
)

duration = st.slider(
    "Video အရှည် (စက္ကန့်)",
    10, 300, 60
)

ratio = st.selectbox(
    "Video အမျိုးအစား",
    [
        "TikTok / Reels (9:16)",
        "YouTube (16:9)",
        "Square (1:1)"
    ]
)

if video:
    st.video(video)

    has_voice = "voice_mp3" in st.session_state

    if has_voice:
        add_voice = st.checkbox(
            "Video ထဲ AI Voice ထည့်ရန် (မူရင်းအသံကို အစားထိုး)",
            value=True
        )
    else:
        add_voice = False
        st.info("AI Voice ထည့်လိုပါက အပေါ်မှာ အရင် Generate လုပ်ပါ")

    if st.button("✨ START AUTO EDIT", type="primary"):

        try:
            with st.spinner("Video ကို Auto Edit လုပ်နေပါတယ်..."):

                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

                sizes = {
                    "TikTok / Reels (9:16)": "720:1280",
                    "YouTube (16:9)": "1280:720",
                    "Square (1:1)": "1080:1080"
                }

                w, h = sizes[ratio].split(":")

                with tempfile.TemporaryDirectory() as folder:

                    input_path = os.path.join(
                        folder, "input.mp4"
                    )
                    output_path = os.path.join(
                        folder, "edited.mp4"
                    )

                    with open(input_path, "wb") as f:
                        f.write(video.getbuffer())

                    command = [
                        ffmpeg,
                        "-y",
                        "-i", input_path
                    ]

                    if add_voice:
                        voice_path = os.path.join(
                            folder, "voice.mp3"
                        )

                        with open(voice_path, "wb") as f:
                            f.write(
                                st.session_state["voice_mp3"]
                            )

                        command += ["-i", voice_path]

                    command += [
                        "-t", str(duration),
                        "-vf",
                        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                        f"crop={w}:{h},setsar=1",
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-crf", "23",
                        "-map", "0:v:0"
                    ]

                    if add_voice:
                        command += [
                            "-map", "1:a:0",
                            "-af", "apad",
                            "-c:a", "aac",
                            "-b:a", "128k"
                        ]
                    else:
                        command += [
                            "-map", "0:a?",
                            "-c:a", "aac",
                            "-b:a", "128k"
                        ]

                    command += [
                        "-movflags", "+faststart",
                        output_path
                    ]

                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=900
                    )

                    if result.returncode != 0:
                        raise Exception(result.stderr[-3000:])

                    with open(output_path, "rb") as f:
                        edited_video = f.read()

                    st.success("✅ Auto Editing ပြီးပါပြီ!")

                    st.video(edited_video)

                    st.download_button(
                        "⬇️ DOWNLOAD FINAL MP4",
                        data=edited_video,
                        file_name="myanmar_ai_edited.mp4",
                        mime="video/mp4"
                    )

        except Exception as e:
            st.error("Video Editing မအောင်မြင်ပါ")
            st.code(str(e))

st.divider()
st.caption("Myanmar AI Auto Video Editor | Thiha & Nilar Voice")
