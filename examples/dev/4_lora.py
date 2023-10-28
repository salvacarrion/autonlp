import datetime
import time
import os
import torch
torch.set_float32_matmul_precision("high")

from autonmt.modules.models import Transformer
from autonmt.preprocessing import DatasetBuilder
from autonmt.toolkits import AutonmtTranslator
from autonmt.vocabularies import Vocabulary

from autonmt.bundle.report import generate_report
from autonmt.bundle.plots import plot_metrics

from autonmt.preprocessing.processors import preprocess_pairs, preprocess_lines, normalize_lines
from tokenizers.normalizers import NFKC, Strip, Lowercase

from minlora import add_lora, LoRAParametrization, apply_to_lora, disable_lora, enable_lora, get_lora_params, merge_lora, name_is_lora, remove_lora, load_multiple_lora, select_lora, get_lora_state_dict
from functools import partial
from torch import nn

# Preprocess functions
normalize_fn = lambda x: normalize_lines(x, seq=[NFKC(), Strip()])
preprocess_raw_fn = lambda x, y: preprocess_pairs(x, y, normalize_fn=normalize_fn, min_len=1, max_len=None, remove_duplicates=False, shuffle_lines=False)
preprocess_splits_fn = lambda x, y: preprocess_pairs(x, y, normalize_fn=normalize_fn, shuffle_lines=True)
preprocess_predict_fn = lambda x: preprocess_lines(x, normalize_fn=normalize_fn)

# BASE_PATH1 = "/home/salvacarrion/Documents/datasets/translation"  # Local
BASE_PATH2 = "/home/scarrion/datasets/translate"  # Remote
BASE_PATH3 = "/app/data"  # Docker
BASE_PATH = BASE_PATH2 if os.environ.get("DEBUG", 0) else BASE_PATH3


def main():
    # Create preprocessing for training
    builder = DatasetBuilder(
        # Root folder for datasets
        base_path=BASE_PATH,

        # Set of datasets, languages, training sizes to try
        datasets=[
            # {"name": "multi30k/neutral", "languages": ["de-es"], "sizes": [("original", None)], "split_sizes": (None, 1014, 1000)},
            # {"name": "multi30k/informal", "languages": ["de-es"], "sizes": [("original", None)], "split_sizes": (None, 1014, 1000)},
            # {"name": "multi30k/formal", "languages": ["de-es"], "sizes": [("original", None)], "split_sizes": (None, 1014, 1000)},
            {"name": "multi30k/neutral-formal", "languages": ["en-es"], "sizes": [("original", None)]},
            {"name": "multi30k/neutral-informal", "languages": ["en-es"], "sizes": [("original", None)]},
            # {"name": "multi30k/merged-neutral-formal-informal", "languages": ["en-es", "de-es"], "sizes": [("original", None)]},
        ],

        # Set of subword models and vocab sizes to try
        encoding=[
            {"subword_models": ["bpe+bytes"], "vocab_sizes": [8000]},
        ],

        # Preprocessing functions
        preprocess_raw_fn=preprocess_raw_fn,
        preprocess_splits_fn=preprocess_splits_fn,

        # Additional args
        merge_vocabs=False,
    ).build(make_plots=False, force_overwrite=False)

    builder_ts = DatasetBuilder(
        # Root folder for datasets
        base_path=BASE_PATH,

        # Set of datasets, languages, training sizes to try
        datasets=[
            {"name": "multi30k/neutral", "languages": ["en-es", "de-es"], "sizes": [("original", None)], "split_sizes": (None, 1014, 1000)},
            {"name": "multi30k/informal", "languages": ["en-es", "de-es"], "sizes": [("original", None)], "split_sizes": (None, 1014, 1000)},
            {"name": "multi30k/formal", "languages": ["en-es", "de-es"], "sizes": [("original", None)], "split_sizes": (None, 1014, 1000)},
        ],
    )

    # Create preprocessing for training and testing
    tr_datasets = builder.get_train_ds()
    ts_datasets = builder_ts.get_test_ds()

    # Train & Score a model for each dataset
    scores = []
    for i, train_ds in enumerate(tr_datasets, 1):
        for rank in [1, 2, 4, 8, 16, 32, 64]:
            # Instantiate vocabs and model
            src_vocab = Vocabulary(max_tokens=150).build_from_ds(ds=train_ds, lang=train_ds.src_lang)
            trg_vocab = Vocabulary(max_tokens=150).build_from_ds(ds=train_ds, lang=train_ds.trg_lang)
            model = Transformer(src_vocab_size=len(src_vocab), trg_vocab_size=len(trg_vocab), padding_idx=src_vocab.pad_id)

            # Load checkpoint
            path = os.path.join(BASE_PATH, "multi30k/neutral/en-es/original/models/autonmt/runs/multi30k-neutral_en-es_bpe+bytes_8000/checkpoints")
            checkpoint_path = os.path.join(path, "epoch=014-val_loss=1.397__best.pt")
            if checkpoint_path:
                print(f"\t- Loading previous checkpoint: {checkpoint_path}")
                model_state_dict = torch.load(checkpoint_path)
                model_state_dict = model_state_dict.get("state_dict", model_state_dict)
                model.load_state_dict(model_state_dict)

            # Apply LORA
            config = {  # specify which layers to add lora to, by default only add to linear layers
                nn.Linear: {
                    "weight": partial(LoRAParametrization.from_linear, rank=rank),
                },
            }
            add_lora(model, lora_config=config)

            # Select LoRA parameters
            parameters = [
                {"params": list(get_lora_params(model))},
            ]
            optimizer = torch.optim.AdamW(parameters, lr=1e-3)
            num_lora_params = sum([p.numel() for p in parameters[0]["params"]])

            # Define trainer
            runs_dir = train_ds.get_runs_path(toolkit="autonmt")
            run_prefix = f"ft_lora-rank{rank}__" + '_'.join(train_ds.id()[:2]).replace('/', '-')
            run_name = train_ds.get_run_name(run_prefix=run_prefix)
            trainer = AutonmtTranslator(model=model, src_vocab=src_vocab, trg_vocab=trg_vocab,
                                        runs_dir=runs_dir, run_name=run_name)

            # Print info
            print(f"=> Training model...")
            print(f"\t- TRAINING ({i}/{len(tr_datasets)}): {str(train_ds)}")
            print(f"\t- TESTING ({len(ts_datasets)}): {', '.join([str(x) for x in ts_datasets])}")
            print(f"\t- MODEL PREFIX: {run_prefix}")
            print(f"\t- LoRA params: {num_lora_params}")

            # Train model
            wandb_params = dict(project="continual-learning", entity="salvacarrion", reinit=True)
            comet_params = None  #dict(api_key="SPbJIBtSiGmnWI9Pc7ZuDJ4Wc", project_name="continual-learning", workspace="salvacarrion")
            trainer.fit(train_ds, max_epochs=100, learning_rate=0.001, optimizer=optimizer, batch_size=512, seed=1234,
                        patience=10, num_workers=0, accelerator="auto", strategy="auto", save_best=True, save_last=True, print_samples=1,
                        wandb_params=wandb_params, comet_params=comet_params)

            # Test model: LORA
            m_scores = trainer.predict(ts_datasets, metrics={"bleu"}, beams=[1], load_checkpoint=None,
                                       preprocess_fn=preprocess_predict_fn, eval_mode="compatible", force_overwrite=True)
            for ms in m_scores:
                ms['train_dataset'] = f"ft_lora-rank{rank}__" + str(train_ds)
                ms['lora_params'] = num_lora_params
            scores.append(m_scores)

            # Save LoRA
            lora_state_dict = get_lora_state_dict(model)
            file_path = trainer.get_model_checkpoints_path(f'lora_rank{rank}.pth')
            torch.save(lora_state_dict, file_path)
            #
            # # Remove LoRA
            # remove_lora(model)
            #
            # # Test model: No-LoRA
            # m_scores = trainer.predict(ts_datasets, metrics={"bleu"}, beams=[1], load_checkpoint=None,
            #                            preprocess_fn=preprocess_predict_fn, eval_mode="compatible", force_overwrite=True)
            # for ms in m_scores:
            #     ms['train_dataset'] = "No-LoRA"
            # scores.append(m_scores)

    # Make report
    output_path = os.path.join(BASE_PATH, f".outputs/autonmt/{str(datetime.datetime.now())}")
    df_report, df_summary = generate_report(scores=scores, output_path=output_path)

    # Print summary
    print("Summary:")
    print(df_summary.to_string(index=False))

    # Plot metrics
    plots_path = os.path.join(output_path, "plots")
    plot_metrics(output_path=plots_path, df_report=df_report, plot_metric="translations.beam1.sacrebleu_bleu_score",
                 xlabel="MT Models", ylabel="BLEU Score", title="Model comparison")


if __name__ == "__main__":
    main()

    # ##### Reference output #######################################
    # Summary:
    # lang_pair  vocab_size subword_model train_dataset eval_dataset  translations.beam1.sacrebleu_bleu_score
    #     de-en        4000          word  no_specified     multi30k                                33.194409
    #     de-en        4000     bpe+bytes  no_specified     multi30k                                34.062475
    ################################################################