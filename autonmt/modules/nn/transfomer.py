import math
import torch.nn as nn
from autonmt.tasks.translation.models import Seq2Seq
from autonmt.modules.layers import PositionalEmbedding


class Transformer(Seq2Seq):
    def __init__(self,
                 src_vocab_size, trg_vocab_size,
                 encoder_embed_dim=256,
                 decoder_embed_dim=256,
                 encoder_layers=3,
                 decoder_layers=3,
                 encoder_attention_heads=8,
                 decoder_attention_heads=8,
                 encoder_ffn_embed_dim=512,
                 decoder_ffn_embed_dim=512,
                 dropout=0.1,
                 activation_fn="relu",
                 max_sequence_length=1024,
                 padding_idx=None,
                 learned=False,
                 **kwargs):
        super().__init__(src_vocab_size, trg_vocab_size, **kwargs)
        self.max_sequence_length = max_sequence_length

        # Model
        self.src_embeddings = nn.Embedding(src_vocab_size, encoder_embed_dim)
        self.trg_embeddings = nn.Embedding(trg_vocab_size, decoder_embed_dim)
        self.src_pos_embeddings = PositionalEmbedding(num_embeddings=max_sequence_length, embedding_dim=encoder_embed_dim, padding_idx=padding_idx, learned=learned)
        self.trg_pos_embeddings = PositionalEmbedding(num_embeddings=max_sequence_length, embedding_dim=decoder_embed_dim, padding_idx=padding_idx, learned=learned)
        self.transformer = nn.Transformer(d_model=encoder_embed_dim,
                                          nhead=encoder_attention_heads,
                                          num_encoder_layers=encoder_layers,
                                          num_decoder_layers=decoder_layers,
                                          dim_feedforward=encoder_ffn_embed_dim,
                                          dropout=dropout,
                                          activation=activation_fn)
        self.output_layer = nn.Linear(encoder_embed_dim, src_vocab_size)
        self.input_dropout = nn.Dropout(dropout)
        # self.src_scale = math.sqrt(encoder_embed_dim)
        # self.trg_scale = math.sqrt(decoder_embed_dim)

        # Checks
        assert encoder_embed_dim == decoder_embed_dim
        assert encoder_attention_heads == decoder_attention_heads
        assert encoder_ffn_embed_dim == decoder_ffn_embed_dim

    def forward(self, x, y):
        memory = self.forward_encoder(x)
        output = self.forward_decoder(y, memory)
        return output

    def forward_encoder(self, x):
        assert x.shape[1] <= self.max_sequence_length

        # Encode src
        x_pos = self.src_pos_embeddings(x)
        x_emb = self.src_embeddings(x)
        x_emb = (x_emb + x_pos).transpose(0, 1)

        memory = self.transformer.encoder(src=x_emb, mask=None, src_key_padding_mask=None)
        return memory

    def forward_decoder(self, y, memory):
        assert y.shape[1] <= self.max_sequence_length

        # Encode trg
        y_pos = self.trg_pos_embeddings(y)
        y_emb = self.trg_embeddings(y)
        y_emb = (y_emb + y_pos).transpose(0, 1)

        # Make trg mask
        tgt_mask = self.transformer.generate_square_subsequent_mask(y_emb.shape[0]).to(y_emb.device)

        output = self.transformer.decoder(tgt=y_emb, memory=memory, tgt_mask=tgt_mask, memory_mask=None,
                                          tgt_key_padding_mask=None, memory_key_padding_mask=None)

        # Get output
        output = output.transpose(0, 1)
        output = self.output_layer(output)
        return output
