"""Mix two 16 kHz mono 16-bit WAV files into one."""
import sys
import wave

from mixer.constants import SAMPLE_RATE
from mixer.mixing import mix_streams
from mixer.wav import encode_wav


def read_wav(path):
    with wave.open(path, "rb") as w:
        rate, channels, sampwidth = w.getframerate(), w.getnchannels(), w.getsampwidth()
        if (rate, channels, sampwidth) != (SAMPLE_RATE, 1, 2):
            raise ValueError(
                f"{path}: expected {SAMPLE_RATE} Hz mono 16-bit WAV, "
                f"got {rate} Hz, {channels} channel(s), {sampwidth * 8}-bit"
            )
        return w.readframes(w.getnframes())


def write_wav(path, audio):
    with open(path, "wb") as f:
        f.write(encode_wav(audio))


def main():
    if len(sys.argv) != 4:
        sys.exit(f"usage: {sys.argv[0]} input1.wav input2.wav output.wav")
    in1, in2, out = sys.argv[1], sys.argv[2], sys.argv[3]
    write_wav(out, mix_streams([read_wav(in1), read_wav(in2)]))


if __name__ == "__main__":
    main()
