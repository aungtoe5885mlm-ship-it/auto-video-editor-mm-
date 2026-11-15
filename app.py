
import streamlit as st
import subprocess
import tempfile
import os
import imageio_ffmpeg

st.set_page_config(
    page_title="AI Auto Video Editor",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 AI AUTO VIDEO EDITOR")
st.write("မြန်မာ Auto Video Editing App")

st.success("Video တင်ပြီး အလိုအလျောက် Edit လုပ်နိုင်ပါပြီ")

video = st.file_uploader(
    "📤 သင့် Video ကို Upload လုပ်ပါ",
    type=["mp4", "mov", "mkv"]
)

duration = st.slider(
    "Video အရှည် (စက္ကန့်)",
    10, 300, 60
)

ratio = st.selectbox(
    "Video အမျိုးအစား",
    ["TikTok / Reels (9:16)", "YouTube (16:9)", "Square (1:1)"]
)

if video:
    st.video(video)

    if st.button("✨ START AUTO EDIT", type="primary"):

        with st.spinner("Video ကို Auto Edit လုပ်နေပါတယ်..."):

            try:
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

                sizes = {
                    "TikTok / Reels (9:16)": "720:1280",
                    "YouTube (16:9)": "1280:720",
                    "Square (1:1)": "1080:1080"
                }

                size = sizes[ratio]
                w, h = size.split(":")

                with tempfile.TemporaryDirectory() as folder:

                    input_path = os.path.join(folder, "input.mp4")
                    output_path = os.path.join(folder, "edited.mp4")

                    with open(input_path, "wb") as f:
                        f.write(video.getbuffer())

                    command = [
                        ffmpeg,
                        "-y",
                        "-i", input_path,
                        "-t", str(duration),
                        "-vf",
                        f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1",
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-crf", "23",
                        "-map", "0:v:0",
                        "-map", "0:a?",
                        "-c:a", "aac",
                        "-b:a", "128k",
                        "-movflags", "+faststart",
                        output_path
                    ]

                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True
                    )

                    if result.returncode != 0:
                        raise Exception(result.stderr[-2000:])

                    with open(output_path, "rb") as f:
                        edited_video = f.read()

                    st.success("✅ Video Editing ပြီးပါပြီ!")

                    st.video(edited_video)

                    st.download_button(
                        "⬇️ DOWNLOAD MP4",
                        data=edited_video,
                        file_name="auto_edited_video.mp4",
                        mime="video/mp4"
                    )

            except Exception as e:
                st.error("Video Editing မအောင်မြင်ပါ")
                st.code(str(e))
