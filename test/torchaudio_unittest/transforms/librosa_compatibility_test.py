"""Test suites for numerical compatibility with librosa"""
import os
import unittest

import torch
import torchaudio
import torchaudio.functional as F
from torchaudio._internal.module_utils import is_module_available
from parameterized import parameterized, param

LIBROSA_AVAILABLE = is_module_available('librosa')

if LIBROSA_AVAILABLE:
    import librosa
    import scipy

from torchaudio_unittest import common_utils


def _load_audio_asset(*asset_paths, **kwargs):
    file_path = common_utils.get_asset_path(*asset_paths)
    sound, sample_rate = torchaudio.load(file_path, **kwargs)
    return sound, sample_rate


@unittest.skipIf(not LIBROSA_AVAILABLE, "Librosa not available")
class TestTransforms(common_utils.TorchaudioTestCase):
    """Test suite for functions in `transforms` module."""

    @parameterized.expand([
        param(n_fft=400, hop_length=200, power=2.0),
        param(n_fft=600, hop_length=100, power=2.0),
        param(n_fft=400, hop_length=200, power=3.0),
        param(n_fft=200, hop_length=50, power=2.0),
    ])
    def test_spectrogram(self, n_fft, hop_length, power):
        sample_rate = 16000
        sound = common_utils.get_sinusoid(n_channels=1, sample_rate=sample_rate)
        sound_librosa = sound.cpu().numpy().squeeze()
        spect_transform = torchaudio.transforms.Spectrogram(
            n_fft=n_fft, hop_length=hop_length, power=power)
        out_librosa, _ = librosa.core.spectrum._spectrogram(
            y=sound_librosa, n_fft=n_fft, hop_length=hop_length, power=power)

        out_torch = spect_transform(sound).squeeze().cpu()
        self.assertEqual(out_torch, torch.from_numpy(out_librosa), atol=1e-5, rtol=1e-5)

    def test_spectrogram_complex(self):
        n_fft = 400
        hop_length = 200
        sample_rate = 16000
        sound = common_utils.get_sinusoid(n_channels=1, sample_rate=sample_rate)
        sound_librosa = sound.cpu().numpy().squeeze()
        spect_transform = torchaudio.transforms.Spectrogram(
            n_fft=n_fft, hop_length=hop_length, power=None, return_complex=True)
        out_librosa, _ = librosa.core.spectrum._spectrogram(
            y=sound_librosa, n_fft=n_fft, hop_length=hop_length, power=1)

        out_torch = spect_transform(sound).squeeze()
        self.assertEqual(out_torch.abs(), torch.from_numpy(out_librosa), atol=1e-5, rtol=1e-5)

    @parameterized.expand([
        param(norm=norm, mel_scale=mel_scale, **p.kwargs)
        for p in [
            param(n_fft=400, hop_length=200, n_mels=128),
            param(n_fft=600, hop_length=100, n_mels=128),
            param(n_fft=200, hop_length=50, n_mels=128),
        ]
        for norm in [None, 'slaney']
        for mel_scale in ['htk', 'slaney']
    ])
    def test_mel_spectrogram(self, n_fft, hop_length, n_mels, norm, mel_scale):
        sample_rate = 16000
        sound = common_utils.get_sinusoid(n_channels=1, sample_rate=sample_rate)
        sound_librosa = sound.cpu().numpy().squeeze()
        melspect_transform = torchaudio.transforms.MelSpectrogram(
            sample_rate=sample_rate, window_fn=torch.hann_window,
            hop_length=hop_length, n_mels=n_mels, n_fft=n_fft, norm=norm, mel_scale=mel_scale)
        librosa_mel = librosa.feature.melspectrogram(
            y=sound_librosa, sr=sample_rate, n_fft=n_fft,
            hop_length=hop_length, n_mels=n_mels, htk=mel_scale == "htk", norm=norm)
        librosa_mel_tensor = torch.from_numpy(librosa_mel)
        torch_mel = melspect_transform(sound).squeeze().cpu()
        self.assertEqual(
            torch_mel.type(librosa_mel_tensor.dtype), librosa_mel_tensor, atol=5e-3, rtol=1e-5)

    @parameterized.expand([
        param(norm=norm, mel_scale=mel_scale, **p.kwargs)
        for p in [
            param(n_fft=400, hop_length=200, power=2.0, n_mels=128),
            param(n_fft=600, hop_length=100, power=2.0, n_mels=128),
            param(n_fft=400, hop_length=200, power=3.0, n_mels=128),
            # NOTE: Test passes offline, but fails on TravisCI (and CircleCI), see #372.
            param(n_fft=200, hop_length=50, power=2.0, n_mels=128, skip_ci=True),
        ]
        for norm in [None, 'slaney']
        for mel_scale in ['htk', 'slaney']
    ])
    def test_s2db(self, n_fft, hop_length, power, n_mels, norm, mel_scale, skip_ci=False):
        if skip_ci and 'CI' in os.environ:
            self.skipTest('Test is known to fail on CI')
        sample_rate = 16000
        sound = common_utils.get_sinusoid(n_channels=1, sample_rate=sample_rate)
        sound_librosa = sound.cpu().numpy().squeeze()
        spect_transform = torchaudio.transforms.Spectrogram(
            n_fft=n_fft, hop_length=hop_length, power=power)
        out_librosa, _ = librosa.core.spectrum._spectrogram(
            y=sound_librosa, n_fft=n_fft, hop_length=hop_length, power=power)
        melspect_transform = torchaudio.transforms.MelSpectrogram(
            sample_rate=sample_rate, window_fn=torch.hann_window,
            hop_length=hop_length, n_mels=n_mels, n_fft=n_fft, norm=norm, mel_scale=mel_scale)
        librosa_mel = librosa.feature.melspectrogram(
            y=sound_librosa, sr=sample_rate, n_fft=n_fft,
            hop_length=hop_length, n_mels=n_mels, htk=mel_scale == "htk", norm=norm)

        power_to_db_transform = torchaudio.transforms.AmplitudeToDB('power', 80.)
        power_to_db_torch = power_to_db_transform(spect_transform(sound)).squeeze().cpu()
        power_to_db_librosa = librosa.core.spectrum.power_to_db(out_librosa)
        self.assertEqual(power_to_db_torch, torch.from_numpy(power_to_db_librosa), atol=5e-3, rtol=1e-5)

        mag_to_db_transform = torchaudio.transforms.AmplitudeToDB('magnitude', 80.)
        mag_to_db_torch = mag_to_db_transform(torch.abs(sound)).squeeze().cpu()
        mag_to_db_librosa = librosa.core.spectrum.amplitude_to_db(sound_librosa)
        self.assertEqual(mag_to_db_torch, torch.from_numpy(mag_to_db_librosa), atol=5e-3, rtol=1e-5)

        power_to_db_torch = power_to_db_transform(melspect_transform(sound)).squeeze().cpu()
        db_librosa = librosa.core.spectrum.power_to_db(librosa_mel)
        db_librosa_tensor = torch.from_numpy(db_librosa)
        self.assertEqual(
            power_to_db_torch.type(db_librosa_tensor.dtype), db_librosa_tensor, atol=5e-3, rtol=1e-5)

    @parameterized.expand([
        param(n_fft=400, hop_length=200, n_mels=128, n_mfcc=40),
        param(n_fft=600, hop_length=100, n_mels=128, n_mfcc=20),
        param(n_fft=200, hop_length=50, n_mels=128, n_mfcc=50),
    ])
    def test_mfcc(self, n_fft, hop_length, n_mels, n_mfcc):
        sample_rate = 16000
        sound = common_utils.get_sinusoid(n_channels=1, sample_rate=sample_rate)
        sound_librosa = sound.cpu().numpy().squeeze()
        librosa_mel = librosa.feature.melspectrogram(
            y=sound_librosa, sr=sample_rate, n_fft=n_fft,
            hop_length=hop_length, n_mels=n_mels, htk=True, norm=None)
        db_librosa = librosa.core.spectrum.power_to_db(librosa_mel)

        # librosa.feature.mfcc doesn't pass kwargs properly since some of the
        # kwargs for melspectrogram and mfcc are the same. We just follow the
        # function body in
        # https://librosa.github.io/librosa/_modules/librosa/feature/spectral.html#melspectrogram
        # to mirror this function call with correct args:
        #
        # librosa_mfcc = librosa.feature.mfcc(
        #     y=sound_librosa, sr=sample_rate, n_mfcc = n_mfcc,
        #     hop_length=hop_length, n_fft=n_fft, htk=True, norm=None, n_mels=n_mels)

        librosa_mfcc = scipy.fftpack.dct(db_librosa, axis=0, type=2, norm='ortho')[:n_mfcc]
        librosa_mfcc_tensor = torch.from_numpy(librosa_mfcc)

        melkwargs = {'hop_length': hop_length, 'n_fft': n_fft}
        mfcc_transform = torchaudio.transforms.MFCC(
            sample_rate=sample_rate, n_mfcc=n_mfcc, norm='ortho', melkwargs=melkwargs)
        torch_mfcc = mfcc_transform(sound).squeeze().cpu()

        self.assertEqual(
            torch_mfcc.type(librosa_mfcc_tensor.dtype), librosa_mfcc_tensor, atol=5e-3, rtol=1e-5)

    @parameterized.expand([
        param(n_fft=400, hop_length=200),
        param(n_fft=600, hop_length=100),
        param(n_fft=200, hop_length=50),
    ])
    def test_spectral_centroid(self, n_fft, hop_length):
        sample_rate = 16000
        sound = common_utils.get_sinusoid(n_channels=1, sample_rate=sample_rate)
        sound_librosa = sound.cpu().numpy().squeeze()
        spect_centroid = torchaudio.transforms.SpectralCentroid(
            sample_rate=sample_rate, n_fft=n_fft, hop_length=hop_length)
        out_torch = spect_centroid(sound).squeeze().cpu()

        out_librosa = librosa.feature.spectral_centroid(
            y=sound_librosa, sr=sample_rate, n_fft=n_fft, hop_length=hop_length)
        out_librosa = torch.from_numpy(out_librosa)[0]

        self.assertEqual(out_torch.type(out_librosa.dtype), out_librosa, atol=1e-5, rtol=1e-5)

    def test_MelScale(self):
        """MelScale transform is comparable to that of librosa"""
        n_fft = 2048
        n_mels = 256
        hop_length = n_fft // 4
        sample_rate = 44100
        sound = common_utils.get_whitenoise(sample_rate=sample_rate, duration=60)
        sound = sound.mean(dim=0, keepdim=True)
        spec_ta = F.spectrogram(
            sound, pad=0, window=torch.hann_window(n_fft), n_fft=n_fft,
            hop_length=hop_length, win_length=n_fft, power=2, normalized=False)
        spec_lr = spec_ta.cpu().numpy().squeeze()
        # Perform MelScale with torchaudio and librosa
        melspec_ta = torchaudio.transforms.MelScale(n_mels=n_mels, sample_rate=sample_rate)(spec_ta)
        melspec_lr = librosa.feature.melspectrogram(
            S=spec_lr, sr=sample_rate, n_fft=n_fft, hop_length=hop_length,
            win_length=n_fft, center=True, window='hann', n_mels=n_mels, htk=True, norm=None)
        # Note: Using relaxed rtol instead of atol
        self.assertEqual(melspec_ta, torch.from_numpy(melspec_lr[None, ...]), atol=1e-8, rtol=1e-3)
