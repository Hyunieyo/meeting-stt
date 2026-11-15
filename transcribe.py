"""회의 녹음 → 회의록 마크다운 변환 (faster-whisper large-v3)."""
import argparse
import functools
import os
import sys
from pathlib import Path

def _add_cuda_dll_dirs():
    """Windows: pip로 설치한 nvidia-cublas/cudnn DLL 경로를 등록."""
    if os.name != "nt":
        return
    try:
        import nvidia
    except ImportError:
        return
    for base in nvidia.__path__:
        for sub in ("cublas", "cudnn"):
            d = os.path.join(base, sub, "bin")
            if os.path.isdir(d):
                os.add_dll_directory(d)
                os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]


_add_cuda_dll_dirs()

MODEL_NAME = "large-v3"
GAP = 2.0  # 이 시간(초) 이상 쉬면 새 문단


@functools.lru_cache(maxsize=None)
def load_model(device="cpu"):
    from faster_whisper import WhisperModel

    if device == "gpu":
        return WhisperModel(MODEL_NAME, device="cuda", compute_type="float16")
    return WhisperModel(MODEL_NAME, device="cpu", compute_type="int8",
                        cpu_threads=os.cpu_count() or 4)


def fmt_time(sec):
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def group_segments(segments, on_progress=None, duration=0.0):
    """세그먼트를 문단 [(시작초, 텍스트)] 로 묶는다."""
    paras = []
    last_end = None
    for seg in segments:
        if on_progress and duration:
            on_progress(min(seg.end / duration, 1.0))
        text = seg.text.strip()
        if not text:
            continue
        if paras and last_end is not None and seg.start - last_end < GAP:
            paras[-1][1].append(text)
        else:
            paras.append((seg.start, [text]))
        last_end = seg.end
    return [(start, " ".join(parts)) for start, parts in paras]


def build_markdown(name, duration, paras):
    lines = [
        f"# 회의록 - {name}",
        "",
        f"- 길이: {fmt_time(duration)}",
        "- 참석자:",
        "",
        "## 요약",
        "",
        "",
        "## 결정사항",
        "",
        "",
        "## 할 일 (담당 / 기한)",
        "",
        "- [ ] ",
        "",
        "---",
        "",
        "## 원문 기록",
        "",
    ]
    for start, text in paras:
        lines += [f"**[{fmt_time(start)}]** {text}", ""]
    return "\n".join(lines)


def transcribe(audio, terms=(), device="cpu", on_progress=None):
    audio = str(audio)
    if not os.path.isfile(audio):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {audio}")
    terms = [t.strip() for t in terms if t and t.strip()]
    model = load_model(device)
    segments, info = model.transcribe(
        audio,
        language="ko",
        vad_filter=True,
        condition_on_previous_text=False,
        beam_size=5,
        initial_prompt=("회의 용어: " + ", ".join(terms)) if terms else None,
    )
    paras = group_segments(segments, on_progress, info.duration)
    if on_progress:
        on_progress(1.0)
    return build_markdown(Path(audio).name, info.duration, paras)


def main():
    p = argparse.ArgumentParser(description="회의 녹음 → 회의록 마크다운")
    p.add_argument("audio")
    p.add_argument("--terms", help="용어 파일 (한 줄에 하나)")
    p.add_argument("--gpu", action="store_true")
    a = p.parse_args()

    terms = ()
    if a.terms:
        terms = Path(a.terms).read_text(encoding="utf-8").splitlines()

    def prog(x):
        sys.stdout.write(f"\r진행률: {x * 100:5.1f}%")
        sys.stdout.flush()

    print("모델 로딩 중...")
    md = transcribe(a.audio, terms, "gpu" if a.gpu else "cpu", prog)
    out = Path(a.audio).with_suffix(".md")
    out.write_text(md, encoding="utf-8")
    print(f"\n저장 완료: {out}")


if __name__ == "__main__":
    main()
