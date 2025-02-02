# add package root
import os, sys
sys.path.insert(0, '../..')

import torch
torch.manual_seed(0)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
import torch.nn as nn
import numpy as np
np.random.seed(0)
import random
random.seed(0)

from models.util.trainer import train
from models.util.lookup import Lookup
from models.util.loaders.standard import loader
from models.util.utils import select_processing_device

from models.gpt2_lstm_pn.model import GPT2LSTMPNEncoderDecoder
from models.components.encoders.GPT2Encoder import Encoder
from models.components.decoders.LSTMDecoderWithAttentionAndPointerGenerator import Decoder

if __name__ == "__main__":    
   
    # DATA PREPARATION ######################################################
    print("Loading data ...")
    """ FR-EN 
    batch_size = 8
    min_seq_len_X = 0
    max_seq_len_X = 500
    min_seq_len_y = min_seq_len_X
    max_seq_len_y = max_seq_len_X    
    data_folder = os.path.join("..", "..", "data", "fren", "ready", "bpe")
    src_lookup_prefix = os.path.join("..", "..", "data", "fren", "lookup", "bpe","src-4096")
    tgt_lookup_prefix = os.path.join("..", "..", "data", "fren", "lookup", "bpe","tgt-4096")    
    """
    """ CMU DICT """
    batch_size = 64
    min_seq_len_X = 3
    max_seq_len_X = 20
    min_seq_len_y = min_seq_len_X
    max_seq_len_y = max_seq_len_X    
    data_folder = os.path.join("..", "..", "data", "cmudict", "ready", "gpt2")
    src_lookup_prefix = os.path.join("..", "..", "data", "cmudict", "lookup", "gpt2","src")
    tgt_lookup_prefix = os.path.join("..", "..", "data", "cmudict", "lookup", "gpt2","tgt")
    
    
    src_lookup = Lookup(type="gpt2")
    src_lookup.load(src_lookup_prefix)
    tgt_lookup = Lookup(type="gpt2")
    tgt_lookup.load(tgt_lookup_prefix)
    train_loader, valid_loader, test_loader = loader(data_folder, batch_size, src_lookup, tgt_lookup, min_seq_len_X, max_seq_len_X, min_seq_len_y, max_seq_len_y)
    
    print("Loading done, train instances {}, dev instances {}, test instances {}, vocab size src/tgt {}/{}\n".format(
        len(train_loader.dataset.X),
        len(valid_loader.dataset.X),
        len(test_loader.dataset.X),
        len(src_lookup), len(tgt_lookup)))
    # ######################################################################
    
    # GPU SELECTION ########################################################
    device = select_processing_device(verbose = True)
    # ######################################################################
    
    # MODEL TRAINING #######################################################
    
    aux_loss_weight = 0.1
    
    encoder = Encoder(     
                vocab_size=len(src_lookup._tokenizer),
                device=device)
    decoder = Decoder(                
                emb_dim=768,
                input_size=768,                 
                hidden_dim=512,
                num_layers=2,
                lstm_dropout=0.4,
                dropout=0.4,
                vocab_size=len(tgt_lookup),                
                device=device)
        
    model = GPT2LSTMPNEncoderDecoder(src_lookup = src_lookup, tgt_lookup = tgt_lookup, encoder = encoder, decoder = decoder, aux_loss_weight = aux_loss_weight, device = device)
                
    print("_"*80+"\n")
    print(model)
    print("_"*80+"\n")
    
    """
    optimizer = torch.optim.SGD(model.parameters(), lr=1., momentum=0.9)
    from models.util.lr_scheduler import cyclical_lr
    end_lr = 500.
    step_size = len(train_loader)
    factor = 4
    clr = cyclical_lr(step_size, min_lr=end_lr/factor, max_lr=end_lr) #, decay_factor_per_step=.97)
    print("Step-size: {}, lr: {} -> {}".format(step_size, end_lr/factor, end_lr))
    lr_scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, [clr])
    """
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, amsgrad=True)#, weight_decay=1e-3)
    #optimizer = torch.optim.SGD(model.parameters(), lr=.1, momentum=0.9)
    
    lr_scheduler = None
    
    criterion = nn.NLLLoss(ignore_index=tgt_lookup.convert_tokens_to_ids(tgt_lookup.pad_token))
        
    train(model, 
          train_loader, 
          valid_loader,
          test_loader,                          
          model_store_path = os.path.join("..", "..", "train", "gpt2_lstm_pn"), 
          resume = False, 
          max_epochs = 500, 
          patience = 50, 
          optimizer = optimizer,
          lr_scheduler = lr_scheduler,
          tf_start_ratio=1.0,
          tf_end_ratio=0.1,
          tf_epochs_decay=50)
          
    # ######################################################################