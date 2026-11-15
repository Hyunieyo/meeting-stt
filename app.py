"""회의록 변환 웹 화면 (Gradio)."""
import re
import tempfile
from pathlib import Path

import gradio as gr

import transcribe as tr


def run(audio, device_label, terms_text, progress=gr.Progress()):
    if not audio:
        raise gr.Error("녹음 파일을 먼저 올려주세요.")
    device = "gpu" if device_label.startswith("GPU") else "cpu"
    terms = [t for t in re.split(r"[,\n]", terms_text or "") if t.strip()]

    progress(0, desc="모델 로딩 중")
    try:
        tr.load_model(device)
    except Exception as e:
        if device == "gpu":
            raise gr.Error(f"GPU(CUDA)를 사용할 수 없습니다. CPU를 선택하세요. ({e})")
        raise gr.Error(f"모델 로딩 실패: {e}")

    try:
        md = tr.transcribe(audio, terms, device,
                           on_progress=lambda x: progress(x, desc="받아쓰는 중"))
    except Exception as e:
        raise gr.Error(f"변환 실패: {e}")

    out = Path(tempfile.mkdtemp()) / (Path(audio).stem + ".md")
    out.write_text(md, encoding="utf-8")
    return str(out), md


with gr.Blocks(title="회의록 변환") as demo:
    gr.Markdown("# 회의 녹음 → 회의록 마크다운")
    with gr.Row():
        with gr.Column():
            audio = gr.Audio(label="녹음 파일", type="filepath")
            device = gr.Radio(["CPU", "GPU (NVIDIA)"], value="CPU", label="처리 장치")
            terms = gr.Textbox(label="용어 힌트 (줄바꿈이나 쉼표로 구분)", lines=4)
            btn = gr.Button("변환", variant="primary")
        with gr.Column():
            file_out = gr.File(label=".md 파일 다운로드")
            preview = gr.Textbox(label="결과 미리보기", lines=25)
    btn.click(run, [audio, device, terms], [file_out, preview])

if __name__ == "__main__":
    demo.queue().launch(server_name="127.0.0.1", server_port=9999, inbrowser=True)
