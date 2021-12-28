import os


class Dataset:
    def __init__(self, base_path, parent_ds,
                 dataset_name, dataset_lang_pair, dataset_size_name, dataset_lines,
                 subword_model, vocab_size, merge_vocabs,
                 train_name="train", val_name="val", test_name="test",
                 raw_path=os.path.join("data", "raw"), splits_path=os.path.join("data", "splits"),
                 encoded_path=os.path.join("data", "encoded"), pretokenized_path=os.path.join("data", "pretokenized"),
                 models_path="models", models_data_bin_path="data-bin", models_runs_path="runs",
                 models_checkpoints_path="checkpoints", model_logs_path="logs", models_eval_path="eval",
                 models_beam_path="beams", models_scores_path="scores", vocab_path=os.path.join("vocabs"),
                 plots_path="plots"):
        # Add properties
        self.base_path = base_path
        self.parent_ds = parent_ds
        self.dataset_name = dataset_name.strip()
        self.dataset_lang_pair = dataset_lang_pair.strip().lower()
        self.dataset_size_name = dataset_size_name.strip()
        self.dataset_lines = dataset_lines
        self.langs = self.dataset_lang_pair.split("-")
        self.src_lang, self.trg_lang = self.langs

        # Dataset versions
        self.subword_model = str(subword_model).lower() if subword_model else subword_model
        self.vocab_size = str(vocab_size).lower() if vocab_size else vocab_size
        self.pretok_flag = (self.subword_model == "word")
        self.merge_vocabs = merge_vocabs

        # Constants: split names
        self.train_name = train_name
        self.val_name = val_name
        self.test_name = test_name
        self.split_names = (self.train_name, self.val_name, self.test_name)
        self.split_names_lang = [f"{name}.{lang}" for name in self.split_names for lang in self.langs]

        # Add default paths
        self.data_raw_path = raw_path
        self.data_splits_path = splits_path
        self.data_encoded_path = encoded_path
        self.data_pretokenized_path = pretokenized_path
        self.models_path = models_path
        self.models_data_bin_path = models_data_bin_path
        self.models_runs_path = models_runs_path
        self.models_checkpoints_path = models_checkpoints_path
        self.model_logs_path = model_logs_path
        self.models_eval_path = models_eval_path
        self.models_beam_path = models_beam_path
        self.models_scores_path = models_scores_path
        self.vocab_path = vocab_path
        self.plots_path = plots_path

    def __str__(self):
        if self.parent_ds:
            return '_'.join(list(self.id())).lower()
        else:
            return '_'.join(list(self.id()) + [str(self.subword_model), str(self.vocab_size)]).lower()

    def vocab_size_id(self):
        if self.subword_model in {None, "none"}:
            return ["none"]
        elif self.subword_model in {"bytes"}:
            return ["bytes"]
        else:
            return self.subword_model, self.vocab_size

    def id(self):
        return self.dataset_name, self.dataset_lang_pair, self.dataset_size_name

    def get_path(self):
        return os.path.join(self.base_path, *self.id())

    def get_raw_path(self, fname=""):
        return os.path.join(self.base_path, *self.id(), self.data_raw_path, fname)

    def get_pretok_path(self, fname=""):
        return os.path.join(self.base_path, *self.id(), self.data_pretokenized_path, fname)

    def get_split_path(self, fname=""):
        return os.path.join(self.base_path, *self.id(), self.data_splits_path, fname)

    def get_encoded_path(self, fname=""):
        if self.subword_model in {None, "none"}:
            return os.path.join(self.base_path, *self.id(), self.data_encoded_path, fname)
        else:
            return os.path.join(self.base_path, *self.id(), self.data_encoded_path, *self.vocab_size_id(), fname)

    def get_vocab_path(self, fname="", base=False):
        _vocab_size_id = [] if base else self.vocab_size_id()
        return os.path.join(self.base_path, *self.id(), self.vocab_path, *_vocab_size_id, fname)

    def get_vocab_file(self, lang=None):
        # "none" has no vocabs
        if self.subword_model in {None, "none"}:
            return None

        # Select vocab type
        if self.merge_vocabs:
            return os.path.join(self.base_path, *self.id(), self.vocab_path, *self.vocab_size_id(), f"{self.src_lang}-{self.trg_lang}")
        else:
            return os.path.join(self.base_path, *self.id(), self.vocab_path, *self.vocab_size_id(), f"{lang}")

    def get_model_data_bin(self, toolkit, fname=""):
        return os.path.join(self.base_path, *self.id(), self.models_path, toolkit, self.models_data_bin_path, *self.vocab_size_id(), fname)

    def get_model_eval_path(self, toolkit, run_name, eval_name):
        return os.path.join(self.base_path, *self.id(), self.models_path, toolkit, self.models_runs_path, run_name, self.models_eval_path, eval_name)

    def get_model_eval_data_split_path(self, toolkit, run_name, eval_name, fname=""):
        return os.path.join(self.base_path, *self.id(), self.models_path, toolkit, self.models_runs_path, run_name, self.models_eval_path, eval_name, self.data_splits_path, fname)

    def get_model_eval_data_pretok_path(self, toolkit, run_name, eval_name, fname=""):
        return os.path.join(self.base_path, *self.id(), self.models_path, toolkit, self.models_runs_path, run_name, self.models_eval_path, eval_name, self.data_pretokenized_path, fname)

    def get_model_eval_data_encoded_path(self, toolkit, run_name, eval_name, fname=""):
        return os.path.join(self.base_path, *self.id(), self.models_path, toolkit, self.models_runs_path, run_name, self.models_eval_path, eval_name, self.data_encoded_path, fname)

    def get_model_eval_data_bin_path(self, toolkit, run_name, eval_name, fname=""):
        return os.path.join(self.base_path, *self.id(), self.models_path, toolkit, self.models_runs_path, run_name, self.models_eval_path, eval_name, self.models_data_bin_path, fname)

    def get_model_beam_path(self, toolkit, run_name, eval_name, beam=""):
        beam_n = f"beam{str(beam)}" if beam else ""
        return os.path.join(self.base_path, *self.id(), self.models_path, toolkit, self.models_runs_path, run_name, self.models_eval_path, eval_name, self.models_beam_path, beam_n)

    def get_model_scores_path(self, toolkit, run_name, eval_name, beam):
        return os.path.join(self.get_model_beam_path(toolkit, run_name, eval_name, beam), self.models_scores_path)

    def get_model_logs_path(self, toolkit, run_name):
        return os.path.join(self.base_path, *self.id(), self.models_path, toolkit, self.models_runs_path, run_name, self.model_logs_path)

    def get_model_checkpoints_path(self, toolkit, run_name, fname=""):
        return os.path.join(self.base_path, *self.id(), self.models_path, toolkit, self.models_runs_path, run_name, self.models_checkpoints_path, fname)

    def get_plots_path(self):
        return os.path.join(self.base_path, *self.id(), self.plots_path, *self.vocab_size_id())

    def get_split_files(self):
        return [f"{fname}.{ext}" for fname in self.split_names for ext in (self.src_lang, self.trg_lang)]

