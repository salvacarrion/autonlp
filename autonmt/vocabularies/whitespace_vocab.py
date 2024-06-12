from collections import Counter

from autonmt.bundle.utils import read_file_lines, write_file_lines, flatten
from autonmt.vocabularies.base_vocab import BaseVocabulary


class Vocabulary(BaseVocabulary):

    def __init__(self,
                 unk_id=0, sos_id=1, eos_id=2, pad_id=3,
                 unk_piece="<unk>", sos_piece="<s>", eos_piece="</s>", pad_piece="<pad>", lang=None, max_tokens=None):
        super().__init__(sos_id=sos_id, eos_id=eos_id, pad_id=pad_id,
                         sos_piece=sos_piece, eos_piece=eos_piece, pad_piece=pad_piece,
                         lang=lang, max_tokens=max_tokens)

        # Set special tokens
        self.unk_id = unk_id
        self.unk_piece = unk_piece

        # Build vocab
        self.voc2idx = {}
        self.idx2voc = {}
        self.voc2freq = {}
        self.vocab_path = None
        self.model_path = None
        self.pretok_flag = None
        self.subword_model = None
        self.spm_model = None

    def __len__(self):
        return len(self.voc2idx)

    def _assert_vocab(self):
        assert self.idx2voc[self.unk_id] == self.unk_piece
        assert self.idx2voc[self.sos_id] == self.sos_piece
        assert self.idx2voc[self.eos_id] == self.eos_piece
        assert self.idx2voc[self.pad_id] == self.pad_piece

    def special_tokens(self):
        return [(self.unk_piece, self.unk_id)] + super().special_tokens()

    def build_from_tokens(self, tokens):
        # Tokens must include the special tokens
        self.voc2idx = {tok: idx for idx, (tok, log_prob) in enumerate(tokens)}
        self.idx2voc = {idx: tok for idx, (tok, log_prob) in enumerate(tokens)}
        self.voc2freq = {tok: log_prob.strip() for idx, (tok, log_prob) in enumerate(tokens)}
        self._assert_vocab()
        return self

    def build_from_bytes(self):
        tokens = [(f'0x{byte:02x}', "0") for byte in range(256)]

        # Move special tokens to the end
        self.unk_id = self.unk_id+256
        self.sos_id = self.sos_id+256
        self.eos_id = self.eos_id+256
        self.pad_id = self.pad_id+256

        special_tokens = [(tok, "0") for tok, tok_id in self.special_tokens()]  # Includes unknown token
        tokens = tokens + special_tokens  # Do not sort. It could lead to different idxs
        self.build_from_tokens(tokens)
        self._assert_vocab()
        return self

    def build_from_vocab(self, filename, includes_special_tokes=True):
        # Parse file. Special tokens must appear first in the file
        tokens = [line.split('\t') for line in read_file_lines(filename, autoclean=False)]
        special_tokens = [(tok, "0") for tok, tok_id in self.special_tokens()] if not includes_special_tokes else []
        tokens = special_tokens + tokens  # Do not sort. It could lead to different idxs
        self.build_from_tokens(tokens)
        self._assert_vocab()
        return self

    def _load_spm_model_from_path(self, path):
        import sentencepiece as spm
        self.spm_model = spm.SentencePieceProcessor(model_file=path)

    def build_from_ds(self, ds, lang=None):
        self.lang = ds.dataset_lang_pair if lang is None else lang
        self.pretok_flag = ds.pretok_flag
        self.subword_model = ds.subword_model

        # Select subword tokenizer
        if ds.subword_model in {None, "none"}:
            pass
        elif ds.subword_model in {"bytes"}:
            self.build_from_bytes()
        else:
            # Load spm vocab
            self.vocab_path = ds.get_vocab_path(self.lang) + ".vocab"
            self.model_path = ds.get_vocab_path(self.lang) + ".model"
            self._load_spm_model_from_path(self.model_path)

            # Build vocab
            self.build_from_vocab(self.vocab_path)
        self._assert_vocab()
        return self

    def get_tokens(self):
        # Tokens must be returned in their correct order
        return [self.idx2voc[i] for i in range(len(self.idx2voc))]

    def encode(self, text, add_special_tokens=True):
        if self.subword_model in {"bytes"}:
            return self.encode_bytes(text, add_special_tokens)
        else:
            return self.encode_text(text, add_special_tokens)

    def encode_text(self, text, add_special_tokens):
        tokens = text.strip().split(' ')
        idxs = [self.voc2idx.get(tok, self.unk_id) for tok in tokens]
        idxs = idxs[
               :self.max_tokens - 2 * int(add_special_tokens)] if self.max_tokens else idxs  # count <sos> and <eos>
        idxs = [self.sos_id] + idxs + [self.eos_id] if add_special_tokens else idxs
        return idxs

    def decode(self, idxs, remove_special_tokens=True):
        if self.subword_model in {"bytes"}:
            return self.decode_bytes(idxs, remove_special_tokens)
        else:
            return self.decode_text(idxs, remove_special_tokens)

    def decode_text(self, idxs, remove_special_tokens):
        # Remove special tokens
        if remove_special_tokens:
            try:
                # Remove <sos>
                sos_pos = idxs.index(self.sos_id)  # Get first sos (important!)
                idxs = idxs[sos_pos+1:]
            except ValueError:
                pass
            try:
                # Remove <eos>
                eos_pos = idxs.index(self.eos_id)   # Get first eos (important!)
                idxs = idxs[:eos_pos]
            except ValueError:
                pass

        # Decode sentences
        tokens = [self.idx2voc.get(idx, self.unk_piece) for idx in idxs]
        s = ' '.join(tokens)
        return s

    def encode_bytes(self, text, add_special_tokens=True, hex_input=True):
        if hex_input:
            b_list = [int(x, base=16) for x in text.split(' ')]
        else:
            s_bytes = text.encode()  # b'Hello world! \xf0\x9f\x8c\xb1'
            b_list = [int(b) for b in s_bytes]  # [72, 101, 108,...]
        idxs = b_list[:self.max_tokens - 2 * int(add_special_tokens)] if self.max_tokens else b_list  # count <sos> and <eos>
        idxs = [self.sos_id] + idxs + [self.eos_id] if add_special_tokens else b_list
        return idxs

    def decode_bytes(self, idxs, remove_special_tokens=True, encoding="utf-8", hex_input=False):
        # Remove special tokens
        if remove_special_tokens:
            try:
                # Remove <sos>
                sos_pos = idxs.index(self.sos_id)
                idxs = idxs[sos_pos+1:]
            except ValueError:
                pass
            try:
                # Remove <eos>
                eos_pos = idxs.index(self.eos_id)
                idxs = idxs[:eos_pos]
            except ValueError:
                pass

        # Decode idxs
        if hex_input:
            text = " ".join([hex(x) for x in idxs])
        else:
            b_enc = bytes(idxs)
            text = b_enc.decode(encoding, errors="replace")
        return text

    def save(self, filename, include_special_tokens=True):
        lines = []

        # Add special tokens
        if include_special_tokens:
            lines.append((self.unk_piece, 0))
            lines.append((self.sos_piece, 0))
            lines.append((self.eos_piece, 0))
            lines.append((self.pad_piece, 0))

        # Add tokens
        for voc, idx in self.voc2idx.items():
            lines.append(f"{voc}\t{self.voc2freq.get(voc, 0)}")

        # Save file
        write_file_lines(lines=lines, filename=filename, insert_break_line=True)

