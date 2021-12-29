import autonmt as al

from autonmt import DatasetBuilder
from autonmt.modules.nn import Transformer
from autonmt.tasks.translation.bundle.report import generate_report
from autonmt import utils


def main():
    # Create datasets for training
    tr_datasets = DatasetBuilder(
        base_path="/home/salva/datasets/",
        datasets=[
            {"name": "multi30k", "languages": ["de-en"], "sizes": [("original", None)]},
        ],
        subword_models=["word"],
        vocab_sizes=[8000],
        merge_vocabs=True,
        force_overwrite=False,
        interactive=True,
        use_cmd=False,
        conda_env_name=None,
    ).build(make_plots=False, safe=True)

    # Create datasets for testing
    ts_datasets = tr_datasets

    # Train & Score a model for each dataset
    scores = []
    for ds in tr_datasets:
        model = al.Translator(model=Transformer,
                              model_ds=ds, safe_seconds=2,
                              force_overwrite=True, interactive=False,
                              use_cmd=False,
                              conda_env_name="mltests")  # Conda envs will soon be deprecated
        model.fit(max_epochs=10, learning_rate=0.001, criterion="cross_entropy", optimizer="adam", clip_norm=1.0,
                  update_freq=1, max_tokens=None, batch_size=64, patience=10, seed=1234, num_gpus=1)
        eval_scores = model.predict(ts_datasets, metrics={"bleu"}, beams=[1])
        scores.append(eval_scores)

    # Show results
    d = scores[0][0]['beams']
    print(d)

    # Make report
    # generate_report(scores=scores, metric_id="beam1__sacrebleu_bleu_score", output_path=".outputs/autonmt",
    #                 save_figures=True, show_figures=False)


if __name__ == "__main__":
    main()