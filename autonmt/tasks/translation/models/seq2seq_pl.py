import os

import torch
import torch.nn as nn
import torch.utils.data as tud
import tqdm
from autonmt.tasks.translation.bundle.translation_dataset import TranslationDataset
from abc import ABC, abstractmethod

import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader
from torch.utils.data import random_split
import pytorch_lightning as pl


class LitSeq2Seq(pl.LightningModule):

    def __init__(self, src_vocab_size, trg_vocab_size, padding_idx,
                 criterion="cross_entropy", learning_rate=0.001, optimizer="adam", weight_decay=0, **kwargs):
        super().__init__()
        self.src_vocab_size = src_vocab_size
        self.trg_vocab_size = trg_vocab_size

        # Hyperparams
        self.learning_rate = learning_rate
        self.criterion = criterion
        self.optimizer = optimizer
        self.weight_decay = weight_decay

        # Set criterion
        self.criterion_fn = self.configure_criterion(padding_idx)

        # Other
        self.save_hyperparameters()

    def configure_optimizers(self):
        if self.optimizer == "adam":
            optimizer = torch.optim.Adam(self.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        elif self.optimizer == "sgd":
            optimizer = torch.optim.SGD(self.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        else:
            raise ValueError("Unknown value for optimizer")
        return optimizer

    def configure_criterion(self, padding_idx):
        if self.criterion == "cross_entropy":
            criterion_fn = nn.CrossEntropyLoss(ignore_index=padding_idx)
        else:
            raise ValueError("Unknown value for optimizer")
        return criterion_fn

    def training_step(self, batch, batch_idx):
        return self._step(batch, batch_idx, log_prefix="train")

    def validation_step(self, batch, batch_idx):
        return self._step(batch, batch_idx, log_prefix="val")

    def _step(self, batch, batch_idx, log_prefix):
        x, y = batch

        # Forward
        output = self.forward_encoder(x)
        output = self.forward_decoder(y, output)

        # Compute loss
        output = output.transpose(1, 2)[:, :, :-1]  # Remove last index to match shape with 'y[1:]'
        y = y[:, 1:]  # Remove <sos>
        loss = self.criterion_fn(output, y)

        # Log params
        self.log(f"{log_prefix}_loss", loss)
        return loss
