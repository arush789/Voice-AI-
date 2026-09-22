import numpy as np
import torch
import torch.nn as nn


MODEL_FILE = "models/rakhsha_keyword_cnn.pt"

TARGET_FRAMES = 200

DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"


# ==========================================
# CNN MODEL
# ==========================================

class KeywordCNN(nn.Module):

    def __init__(self):

        super().__init__()

        self.features = nn.Sequential(

            nn.Conv2d(
                1,
                16,
                kernel_size=3,
                padding=1
            ),

            nn.ReLU(),

            nn.MaxPool2d(2),

            nn.Conv2d(
                16,
                32,
                kernel_size=3,
                padding=1
            ),

            nn.ReLU(),

            nn.MaxPool2d(2)
        )

        self.classifier = nn.Sequential(

            nn.Flatten(),

            nn.Linear(
                32 * 20 * 50,
                64
            ),

            nn.ReLU(),

            nn.Dropout(0.3),

            nn.Linear(
                64,
                1
            )
        )


    def forward(self, x):

        x = self.features(x)

        x = self.classifier(x)

        return x.squeeze(1)


# ==========================================
# LOAD MODEL
# ==========================================

print("Loading keyword model...")

checkpoint = torch.load(
    MODEL_FILE,
    map_location=DEVICE,
    weights_only=False
)

model = KeywordCNN().to(DEVICE)

model.load_state_dict(
    checkpoint["model_state_dict"]
)

model.eval()

MEAN = checkpoint["mean"]
STD = checkpoint["std"]

print("Keyword model loaded!")
print("Device:", DEVICE)


# ==========================================
# KEYWORD DETECTION
# ==========================================

def detect_keyword(feature):

    # Same normalization used during training
    feature = (
        feature - MEAN
    ) / (
        STD + 1e-8
    )

    # NumPy → PyTorch
    tensor = torch.tensor(
        feature,
        dtype=torch.float32
    )

    # [80, 200]
    # ↓
    # [1, 1, 80, 200]

    tensor = tensor.unsqueeze(0)
    tensor = tensor.unsqueeze(0)

    tensor = tensor.to(DEVICE)

    with torch.no_grad():

        logit = model(tensor)

        probability = torch.sigmoid(
            logit
        ).item()

    return probability

import soundfile as sf
import librosa


TARGET_SAMPLE_RATE = 16000
N_MELS = 80
N_FFT = 512
HOP_LENGTH = 160


def extract_keyword_feature(audio_path: str):

    audio, sample_rate = sf.read(
        audio_path,
        dtype="float32"
    )

    # Stereo → mono
    if audio.ndim > 1:

        audio = audio.mean(axis=1)


    # Resample → 16 kHz
    if sample_rate != TARGET_SAMPLE_RATE:

        audio = librosa.resample(
            audio,
            orig_sr=sample_rate,
            target_sr=TARGET_SAMPLE_RATE
        )


    # Mel spectrogram
    mel = librosa.feature.melspectrogram(
        y=audio,
        sr=TARGET_SAMPLE_RATE,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
        n_mels=N_MELS
    )


    # Convert power → dB
    mel_db = librosa.power_to_db(
        mel,
        ref=np.max
    )


    # Make exactly 200 frames
    if mel_db.shape[1] < TARGET_FRAMES:

        padding = (
            TARGET_FRAMES
            - mel_db.shape[1]
        )

        mel_db = np.pad(
            mel_db,
            (
                (0, 0),
                (0, padding)
            ),
            mode="constant",
            constant_values=mel_db.min()
        )


    elif mel_db.shape[1] > TARGET_FRAMES:

        mel_db = mel_db[
            :, :TARGET_FRAMES
        ]


    return mel_db