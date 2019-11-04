#!/usr/bin/env python

from __future__ import print_function

import audioop
import math
import os
import re
import wave
from collections import deque

import kaldi
import pyaudio
from kaldi.asr import NnetLatticeFasterRecognizer
from kaldi.decoder import LatticeFasterDecoderOptions
from kaldi.nnet3 import NnetSimpleComputationOptions
from kaldi.util.table import SequentialMatrixReader

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 5
REL = RATE / CHUNK

THRESHOLD = 6000
# The threshold intensity that defines silence
# and noise signal (an int. lower than THRESHOLD is silence).

SILENCE_LIMIT = 1
# Silence limit in seconds. The max amount of seconds where
# only silence is recorded. When this time passes the
# recording finishes and the file is delivered.

PREV_AUDIO = 0.5
# Previous audio (in seconds) to prepend. When noise
# is detected, how much of previously recorded audio is
# prepended. This helps to prevent chopping the begining
# of the phrase.


def configure_paths(dir_path, relative_path, delimiter, regex):
    with open(dir_path + relative_path, 'r+') as fp:
        lines = fp.readlines()
        for i in range(0, len(lines)):
            line_components = lines[i].split(delimiter)
            if re.match(regex, line_components[-1]):
                line_components[-1] = dir_path + "/" + line_components[-1]
                lines[i] = delimiter.join(line_components)

        with open(dir_path + relative_path, 'w') as fp:
            fp.writelines(lines)


def open_audio_stream():
    p_ref = pyaudio.PyAudio()
    stream = p_ref.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        frames_per_buffer=1024)
    return p_ref, stream


class SpeechRecognizer:
    def __init__(self):
        kaldi.base.set_verbose_level(0)
        self.__dir_path = os.path.dirname(os.path.realpath(__file__))
        self.__wave_file = "utt1.wav"
        self.__save_path = self.__dir_path + '/data/test'
        self.__initialize_path()

    def __save_speech(self, data, p):
        """ Saves mic data to temporary WAV file. Returns filename of saved
            file """
        filename = os.path.join(self.__save_path, self.__wave_file)
        # writes data to WAV file
        _data = b''.join(data)
        wf = wave.open(filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(_data)
        wf.close()
        return filename

    def recognize_speech(self, asr):
        # Define feature pipelines as Kaldi rspecifiers
        feats_rspec = (
                "ark:compute-mfcc-feats --config=%(path)s/conf/mfcc_hires.conf scp:%(path)s/data/test/wav.scp ark:- |"
                % {
                    "path": self.__dir_path
                }
        )
        ivectors_rspec = (
                "ark:compute-mfcc-feats --config=%(path)s/conf/mfcc_hires.conf scp:%(path)s/data/test/wav.scp ark:- | "
                "ivector-extract-online2 --config=%(path)s/conf/ivector_extractor.conf ark:%(path)s/data/test/spk2utt "
                "ark:- ark:- |"
                % {
                    "path": self.__dir_path
                }
        )

        # Decode wav files
        with SequentialMatrixReader(feats_rspec) as f, \
                SequentialMatrixReader(ivectors_rspec) as i:
            for (key, feats), (_, ivectors) in zip(f, i):
                out = asr.decode((feats, ivectors))
                return out["text"]

    def __initialize_path(self):
        regex = "^([A-z0-9-_+]+\/){1,}([A-z0-9]+(\.(conf|mat|stats|dubm|ie|wav|scp))?)$"
        configure_paths(self.__dir_path, '/exp/nnet3_chain/ivectors_test_hires/conf/ivector_extractor.conf', '=', regex)
        configure_paths(self.__dir_path, '/data/test/wav.scp', ' ', regex)

    def init_asr_kaldi(self):
        # Construct recognizer
        decoder_opts = LatticeFasterDecoderOptions()
        decoder_opts.beam = 13
        decoder_opts.max_active = 7000
        decodable_opts = NnetSimpleComputationOptions()
        decodable_opts.acoustic_scale = 1.0
        decodable_opts.frame_subsampling_factor = 3
        decodable_opts.frames_per_chunk = 150
        asr = NnetLatticeFasterRecognizer.from_files(
            self.__dir_path + "/exp/nnet3_chain/tdnn_f/final.mdl",
            self.__dir_path + "/exp/nnet3_chain/tdnn_f/graph/HCLG.fst",
            self.__dir_path + "/data/lang/words.txt",
            decoder_opts=decoder_opts,
            decodable_opts=decodable_opts)
        return asr

    def main(self):
        asr = self.init_asr_kaldi()
        p, stream = open_audio_stream()

        print("[Speech] Listening...")

        audio2send = []
        slid_win = deque(maxlen=int(SILENCE_LIMIT * REL) + 1)
        prev_audio = deque(maxlen=int(PREV_AUDIO * REL) + 1)
        started = False

        while True:
            try:
                cur_data = stream.read(CHUNK)
                slid_win.append(math.sqrt(abs(audioop.avg(cur_data, 4))))
                if sum([x > THRESHOLD for x in slid_win]) > 0:
                    if not started:
                        started = True
                    audio2send.append(cur_data)
                elif started is True:
                    # The limit was reached, finish capture and deliver.
                    filename = self.__save_speech(list(prev_audio) + audio2send, p)
                    r = self.recognize_speech(asr)
                    print("[Speech] Detected speech: ", r)
                    # Remove temp file. Comment line to review.
                    os.remove(filename)
                    # Reset all
                    started = False
                    slid_win = deque(maxlen=int(SILENCE_LIMIT * REL) + 1)
                    prev_audio = deque(maxlen=int(PREV_AUDIO * REL) + 1)
                    audio2send = []
                else:
                    prev_audio.append(cur_data)
            except KeyboardInterrupt:
                break

        stream.stop_stream()
        stream.close()
        p.terminate()


if __name__ == "__main__":
    sr = SpeechRecognizer()
    sr.main()