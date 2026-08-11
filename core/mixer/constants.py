"""The shared audio contract: 16 kHz mono 16-bit, 20 ms frames. Change together."""
SAMPLE_RATE = 16000
FRAME_MS = 20
SAMPLES_PER_FRAME = 320  # SAMPLE_RATE * FRAME_MS / 1000
BYTES_PER_FRAME = 640    # SAMPLES_PER_FRAME * 2 bytes per int16 sample
DTYPE = '<i2'            # little-endian signed 16-bit audio
