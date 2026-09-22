import os

import torch
import soundfile as sf
import librosa
import torch.nn.functional as F

from speechbrain.inference.speaker import EncoderClassifier


TARGET_SAMPLE_RATE = 16000

DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"

PROFILE_DIR = "models/user_voice_profiles"


print("Loading ECAPA speaker model...")

classifier = EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    run_opts={"device": DEVICE}
)

print("ECAPA model loaded!")
print("Device:", DEVICE)


def get_embedding(audio_path: str):

    audio, sample_rate = sf.read(
        audio_path,
        dtype="float32"
    )

    # Convert stereo → mono
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # Convert to 16 kHz
    if sample_rate != TARGET_SAMPLE_RATE:

        audio = librosa.resample(
            audio,
            orig_sr=sample_rate,
            target_sr=TARGET_SAMPLE_RATE
        )

    signal = torch.from_numpy(audio)

    # [samples] → [1, samples]
    signal = signal.unsqueeze(0)

    signal = signal.to(DEVICE)

    with torch.no_grad():

        embedding = classifier.encode_batch(
            signal
        )

    # [1, 1, 192] → [192]
    embedding = embedding.squeeze()

    # Normalize
    embedding = F.normalize(
        embedding,
        p=2,
        dim=0
    )

    return embedding


def create_voice_profile(
    audio_paths: list[str],
    user_id: str
):

    embeddings = []

    for audio_path in audio_paths:

        embedding = get_embedding(
            audio_path
        )

        embeddings.append(
            embedding
        )

    # [number_of_samples, 192]
    embeddings = torch.stack(
        embeddings
    )

    # Average enrollment recordings
    voice_profile = embeddings.mean(
        dim=0
    )

    # Normalize final profile
    voice_profile = F.normalize(
        voice_profile,
        p=2,
        dim=0
    )

    # Make sure directory exists
    os.makedirs(
        PROFILE_DIR,
        exist_ok=True
    )

    profile_path = os.path.join(
        PROFILE_DIR,
        f"{user_id}.pt"
    )

    # Save on CPU
    torch.save(
        voice_profile.cpu(),
        profile_path
    )

    return profile_path

def verify_voice(
    audio_path: str,
    user_id: str,
    threshold: float = 0.3887
):

    profile_path = os.path.join(
        PROFILE_DIR,
        f"{user_id}.pt"
    )

    # Check whether the user has enrolled
    if not os.path.exists(profile_path):
        raise FileNotFoundError(
            "Voice profile not found"
        )

    # Generate embedding for new recording
    test_embedding = get_embedding(
        audio_path
    )

    # Load enrolled profile
    voice_profile = torch.load(
        profile_path,
        map_location=DEVICE,
        weights_only=True
    )

    # Make sure profile is normalized
    voice_profile = F.normalize(
        voice_profile,
        p=2,
        dim=0
    )

    # Cosine similarity
    similarity = torch.dot(
        test_embedding,
        voice_profile
    ).item()

    verified = similarity >= threshold

    return {
        "verified": verified,
        "similarity": similarity,
        "threshold": threshold
    }