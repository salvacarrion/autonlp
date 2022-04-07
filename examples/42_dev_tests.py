import datetime

from tokenizers import normalizers
from tokenizers.normalizers import NFKC, Strip, Lowercase

from autonmt.bundle.report import generate_report
from autonmt.modules.models import Transformer
from autonmt.preprocessing import DatasetBuilder
from autonmt.toolkits import AutonmtTranslator
from autonmt.vocabularies import Vocabulary
from autonmt.toolkits.fairseq import FairseqTranslator


def main(fairseq_args=None):
    # Create preprocessing for training
    builder = DatasetBuilder(
        base_path="/home/scarrion/datasets/nn/translation",
        datasets=[
            # {"name": "cf", "languages": ["es-en", "fr-en", "de-en"], "sizes": [("100k", 100000)]},
            # {"name": "cf", "languages": ["es-en", "fr-en", "de-en"], "sizes": [("100k", 100000)]},
            # {"name": "cf", "languages": ["es-en"], "sizes": [("1k", 1000)], "split_sizes": (None, 100, 100)},
            {"name": "cf/multi30k", "languages": ["de-en"], "sizes": [("original", None)]},
        ],
        encoding=[
            # {"subword_models": ["word", "unigram+bytes", "char+bytes"], "vocab_sizes": [8000, 16000]},
            # {"subword_models": ["word", "unigram+bytes"], "vocab_sizes": [8000, 16000, 32000]},
            # {"subword_models": ["char", "unigram+bytes"], "vocab_sizes": [8000]},
            {"subword_models": ["word+bytes", "unigram"], "vocab_sizes": [4000, 5000]},
        ],
        normalizer=normalizers.Sequence([NFKC(), Strip(), Lowercase()]).normalize_str,
        merge_vocabs=False,
        eval_mode="compatible",
    ).build(make_plots=False, force_overwrite=False)

    # Create preprocessing for training and testing
    tr_datasets = builder.get_train_ds()
    ts_datasets = builder.get_test_ds()

    # Train & Score a model for each dataset
    scores = []
    for train_ds in tr_datasets:
        model = FairseqTranslator()
        model.fit(train_ds, max_epochs=5, learning_rate=0.001, optimizer="adam", batch_size=128, seed=1234, patience=10, num_workers=12, strategy="dp", fairseq_args=fairseq_args, force_overwrite=False)
        m_scores = model.predict(ts_datasets, metrics={"bleu", "bertscore"}, beams=[1], model_ds=train_ds, force_overwrite=False)
        scores.append(m_scores)

    # Make report and print it
    output_path = f".outputs/autonmt/{str(datetime.datetime.now())}"
    df_report, df_summary = generate_report(scores=scores, output_path=output_path, plot_metric="beam1__sacrebleu_bleu_score")
    print("Summary:")
    print(df_summary.to_string(index=False))



if __name__ == "__main__":
    # These args are pass to fairseq using our pipeline
    # Fairseq Command-line tools: https://fairseq.readthedocs.io/en/latest/command_line_tools.html
    fairseq_cmd_args = [
        "--arch transformer",
        "--encoder-embed-dim 256",
        "--decoder-embed-dim 256",
        "--encoder-layers 3",
        "--decoder-layers 3",
        "--encoder-attention-heads 8",
        "--decoder-attention-heads 8",
        "--encoder-ffn-embed-dim 512",
        "--decoder-ffn-embed-dim 512",
        "--dropout 0.1",
        "--no-epoch-checkpoints",
        "--maximize-best-checkpoint-metric",
        "--best-checkpoint-metric bleu",
        "--eval-bleu",
        "--eval-bleu-print-samples",
        "--scoring sacrebleu",
        "--log-format simple",
        "--task translation",
        "--task translation",
    ]

    # Run grid
    main(fairseq_args=fairseq_cmd_args)

