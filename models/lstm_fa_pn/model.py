import sys, os
sys.path.insert(0, '../..')

from collections import OrderedDict
import torch
import torch.nn as nn
import numpy as np
import torch.nn.functional as F
import scipy.stats
from models.components.encodersdecoders.EncoderDecoder import EncoderDecoder

class MyEncoderDecoder(EncoderDecoder):
    def __init__(self, src_lookup, tgt_lookup, encoder, decoder, dec_transfer_hidden, coverage_loss_weight, attention_loss_weight, device):
        super().__init__(src_lookup, tgt_lookup, encoder, decoder, device)

        self.coverage_loss_weight = coverage_loss_weight
        self.attention_loss_weight = attention_loss_weight
        self.dec_transfer_hidden = dec_transfer_hidden
       
        if dec_transfer_hidden == True:
            assert encoder.num_layers == decoder.num_layers, "For transferring the last hidden state from encoder to decoder, both must have the same number of layers."

        # Transform h from encoder's [num_layers * 2, batch_size, enc_hidden_dim/2] to decoder's [num_layers * 1, batch_size, dec_hidden_dim], same for c; batch_size = 1 (last timestep only)
        self.h_state_linear = nn.Linear(int(encoder.hidden_dim * encoder.num_layers/1), decoder.hidden_dim * decoder.num_layers * 1)
        self.c_state_linear = nn.Linear(int(encoder.hidden_dim * encoder.num_layers/1), decoder.hidden_dim * decoder.num_layers * 1)

        self.attention_criterion = nn.KLDivLoss(reduction='batchmean')
    
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
        enc_states = encoder_dict["states"]
        # enc_states is a tuple of size ( h=[enc_num_layers*2, batch_size, enc_hidden_dim/2], c=[same-as-h] )

        if self.dec_transfer_hidden == True:
            dec_states = self.transfer_hidden_from_encoder_to_decoder(enc_states)
        else:
            hidden = Variable(next(self.parameters()).data.new(batch_size, self.decoder.num_layers, self.decoder.hidden_dim), requires_grad=False)
            cell = Variable(next(self.parameters()).data.new(batch_size, self.decoder.num_layers, self.decoder.hidden_dim), requires_grad=False)
            dec_states = ( hidden.zero_().permute(1, 0, 2), cell.zero_().permute(1, 0, 2) )

        # Calculates the output of the decoder.
        decoder_dict = self.decoder.forward(x_tuple, y_tuple, enc_output, dec_states, teacher_forcing_ratio)
        output = decoder_dict["output"]
        attention_weights = decoder_dict["attention_weights"]
        coverage_loss = decoder_dict["coverage_loss"]

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
        
        output, attention_weights, coverage_loss = self.forward((x_batch, x_batch_lenghts, x_batch_mask), (y_batch, y_batch_lenghts, y_batch_mask), tf_ratio)
        
        display_variables = OrderedDict()
        
        
        disp_total_loss = 0
        disp_gen_loss = 0
        disp_cov_loss = 0
        disp_att_loss = 0        
        total_loss = 0
        if criterion is not None:            
            gen_loss = criterion(output.view(-1, self.decoder.vocab_size), y_batch.contiguous().flatten())        
            disp_gen_loss = gen_loss.item()            
            total_loss = gen_loss + self.coverage_loss_weight*coverage_loss        
            disp_cov_loss = self.coverage_loss_weight*coverage_loss.item()
            
            #print("\nloss {:.3f}, aux {:.3f}*{}={:.3f}, total {}\n".format( loss, coverage_loss, coverage_loss_weight, coverage_loss_weight*coverage_loss, total_loss))
            
            if tf_ratio>.0: # additional loss for attention distribution , attention_weights is [batch_size, seq_len] and is a list              
                batch_size = attention_weights.size(0)
                dec_seq_len = attention_weights.size(1)
                enc_seq_len = attention_weights.size(2)
                
                x = np.linspace(0, enc_seq_len, enc_seq_len)
                
                # create target distribution
                target_attention_distribution = attention_weights.new_full((batch_size, dec_seq_len, enc_seq_len), 1e-31)
                for decoder_index in range(0, dec_seq_len):
                    y = scipy.stats.norm.pdf(x, decoder_index, 2) # loc (mean) is decoder_step, scale (std dev) = 1.        
                    y = y / np.sum(y) # rescale to make it a PDF
                    gaussian_dist = torch.tensor(y, dtype = attention_weights.dtype, device = self.device) # make it a tensor, it's [seq_len]
                    target_attention_distribution[:,decoder_index, :] = gaussian_dist.repeat(batch_size, 1) # same for all examples in batch, now it's [batch_size, seq_len]
                
                target_attention_distribution[target_attention_distribution<1e-31] = 1e-31
                attention_weights[attention_weights<1e-31] = 1e-31
                
                #print(target_attention_distribution[0,0,:])                                
                #print(attention_weights_tensor[0,0,:])                
                
                attention_loss = tf_ratio * self.attention_criterion(target_attention_distribution.log().permute(0,2,1), attention_weights.permute(0,2,1)) * self.attention_loss_weight
                disp_att_loss = attention_loss.item()
                total_loss += attention_loss     
        
            display_variables["gen_loss"] = disp_gen_loss
            display_variables["cov_loss"] = disp_cov_loss
            display_variables["att_loss"] = disp_att_loss
            
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


    
        