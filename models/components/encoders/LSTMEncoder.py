import os, sys
sys.path.insert(0, '../../..')

import torch
import torch.nn as nn

class LSTMEncoder(nn.Module):
    def __init__(self, vocab_size, emb_dim, hidden_dim, num_layers, lstm_dropout, device):
        """
        Creates an Encoder model.

        Args:
            vocab_size (int): Number of classes/ Vocabulary size.
            emb_dim (int): Embeddings dimension.
            hidden_dim (int): LSTM hidden layer dimension.
            num_layers (int): Number of LSTM layers.
            lstm_dropout (float): LSTM dropout.
            device : The device to run the model on.
        """
        assert hidden_dim % 2 == 0, "LSTMEncoder hidden_dim should be even as the LSTM is bidirectional."
        super(LSTMEncoder, self).__init__()

        self.embedding = nn.Embedding(vocab_size, emb_dim)        
        self.lstm = nn.LSTM(emb_dim, int(hidden_dim/2), num_layers, dropout=lstm_dropout, bidirectional=True, batch_first=True)

        self.to(device)

    def forward(self, input):
        """
        Args:
            input (tensor): The input of the encoder. It must be a 2-D tensor of integers. 
                Shape: [batch_size, seq_len_enc].

        Returns:
            A tuple containing the output and the states of the last LSTM layer. The states of the LSTM layer is also a
            tuple that contains the hidden and the cell state, respectively . 
                Output shape:            [batch_size, seq_len_enc, hidden_dim * 2]
                Hidden/cell state shape: [num_layers*2, batch_size, hidden_dim]
        """

        # Creates the embeddings. [batch_size, seq_len] -> [batch_size, seq_len, emb_dim].
        embeddings = self.embedding(input)

        # Computes the output and the two states of the lstm layer. See function returns docs for details.
        output, states = self.lstm(embeddings)

        return output, states