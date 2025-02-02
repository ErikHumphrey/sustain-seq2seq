import sys, os
sys.path.insert(0, '../..')

from collections import OrderedDict
import torch
import torch.nn as nn
from models.components.encodersdecoders.EncoderDecoder import EncoderDecoder
from torch.autograd import Variable


class MyEncoderDecoder(EncoderDecoder):
    def __init__(self, src_lookup, tgt_lookup, encoder, decoder, aux_loss_weight, device):
        super().__init__(src_lookup, tgt_lookup, encoder, decoder, device)

        self.aux_loss_weight = aux_loss_weight
        
        self.to(self.device)

    def forward(self, x_tuple, y_tuple, teacher_forcing_ratio=0.):
        """
        Args:
            x (tensor): The input of the decoder. Shape: [batch_size, seq_len_enc].
            y (tensor): The input of the decoder. Shape: [batch_size, seq_len_dec].

        Returns:
            The output of the Encoder-Decoder with attention. Shape: [batch_size, seq_len_dec, n_class].
        """
        x, x_lenghts, x_mask = x_tuple[0], x_tuple[1], x_tuple[2]
        y, y_lenghts, y_mask = y_tuple[0], y_tuple[1], y_tuple[2]
        batch_size = x.shape[0]
        
        # Calculates the output of the encoder
        encoder_dict = self.encoder.forward(x_tuple)
        enc_output = encoder_dict["output"]
        
        hidden = Variable(next(self.parameters()).data.new(batch_size, self.decoder.num_layers, self.decoder.hidden_dim), requires_grad=False)
        cell = Variable(next(self.parameters()).data.new(batch_size, self.decoder.num_layers, self.decoder.hidden_dim), requires_grad=False)
        dec_states = ( hidden.zero_().permute(1, 0, 2), cell.zero_().permute(1, 0, 2) )

        # Calculates the output of the decoder.
        encoder_dict = self.decoder.forward(x_tuple, y_tuple, enc_output, dec_states, teacher_forcing_ratio)
        output = encoder_dict["output"]
        attention_weights = encoder_dict["attention_weights"]
        coverage_loss = encoder_dict["coverage_loss"]

        # Creates a BOS tensor that must be added to the beginning of the output. [batch_size, 1, dec_vocab_size]
        bos_tensor = torch.zeros(batch_size, 1, self.decoder.vocab_size).to(self.device)
        # Marks the corresponding BOS position with a probability of 1.
        bos_tensor[:, :, self.tgt_bos_token_id] = 1
        # Concatenates the BOS tensor with the output. [batch_size, dec_seq_len-1, dec_vocab_size] -> [batch_size, dec_seq_len, dec_vocab_size]
        
        output = torch.cat((bos_tensor, output), dim=1)

        return output, attention_weights, coverage_loss
    
    def run_batch(self, X_tuple, y_tuple, criterion=None, tf_ratio=.0):
        (x_batch, x_batch_lenghts, x_batch_mask) = X_tuple
        (y_batch, y_batch_lenghts, y_batch_mask) = y_tuple
        
        if hasattr(self.decoder.attention, 'init_batch'):
                self.decoder.attention.init_batch(x_batch.size()[0], x_batch.size()[1])
        
        output, attention_weights, aux_loss = self.forward((x_batch, x_batch_lenghts, x_batch_mask), (y_batch, y_batch_lenghts, y_batch_mask), tf_ratio)
        
        if criterion is not None:
            loss = criterion(output.view(-1, self.decoder.vocab_size), y_batch.contiguous().flatten())        
            total_loss = loss + self.aux_loss_weight*aux_loss
        
            #print("\nloss {:.3f}, aux {:.3f}*{}={:.3f}, total {}\n".format( loss, aux_loss, aux_loss_weight, aux_loss_weight*aux_loss, total_loss))
        else:
            total_loss = 0
            
        display_variables = OrderedDict()
        if criterion is not None:
            display_variables["generator_loss"] = loss.item()
            display_variables["coverage_loss"] = self.aux_loss_weight*aux_loss.item()
        return output, total_loss, attention_weights, display_variables
        
    def transfer_hidden_from_encoder_to_decoder(self, enc_states):
        batch_size = enc_states[0].shape[1]

        # Reshapes the shape of the hidden and cell state of the encoder LSTM layers. Permutes the batch_size to
        # the first dimension, and reshapes them to a 2-D tensor.
        # [enc_num_layers * 2, batch_size, enc_hidden_dim] -> [batch_size, enc_num_layers * enc_hidden_dim * 2].
        enc_states = (enc_states[0].permute(1, 0, 2).reshape(batch_size, -1),
                      enc_states[1].permute(1, 0, 2).reshape(batch_size, -1))

        # Transforms the hidden and the cell state of the encoder lstm layer to correspond to the decoder lstm states dimensions.
        # [batch_size, enc_num_layers * enc_hidden_dim * 2] -> [batch_size, dec_num_layers * dec_hidden_dim].
        dec_states = (torch.tanh(self.h_state_linear(enc_states[0])), torch.tanh(self.c_state_linear(enc_states[1])))

        # Reshapes the states to have the correct shape for the decoder lstm states dimension. Reshape the states from
        # 2-D to 3-D sequence. Permutes the batch_size to the second dimension.
        # [batch_size, dec_num_layers * dec_hidden_dim] -> [dec_num_layers, batch_size, dec_hidden_dim].
        dec_states = (dec_states[0].reshape(batch_size, self.decoder.num_layers, self.decoder.hidden_dim).permute(1, 0, 2),
                      dec_states[1].reshape(batch_size, self.decoder.num_layers, self.decoder.hidden_dim).permute(1, 0, 2))

        return dec_states
        
    def load_checkpoint(self, folder, extension):
        filename = os.path.join(folder, "checkpoint." + extension)
        print("Loading model {} ...".format(filename))
        if not os.path.exists(filename):
            print("\tModel file not found, not loading anything!")
            return {}

        checkpoint = torch.load(filename)
        #self.encoder.load_state_dict(checkpoint["encoder_state_dict"])
        self.decoder.load_state_dict(checkpoint["decoder_state_dict"])

        #self.encoder.to(self.device)
        self.decoder.to(self.device)
        return checkpoint["extra"]

    def save_checkpoint(self, folder, extension, extra={}):
        filename = os.path.join(folder, "checkpoint." + extension)
        checkpoint = {}
        #checkpoint["encoder_state_dict"] = self.encoder.state_dict()
        checkpoint["decoder_state_dict"] = self.decoder.state_dict()
        checkpoint["extra"] = extra
        torch.save(checkpoint, filename)

    
        