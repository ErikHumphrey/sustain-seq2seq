# add package root
import os, sys
sys.path.insert(0, '..')

import torch
import torch.nn as nn

from lstm_att.lstm import LSTMEncoderDecoderAtt

# loading data
import loaders.loaders
#import loaders.dummyloaders
data_folder = os.path.join("..","..","data","ready","cnndm.8K.bpe.model")
#data_folder = os.path.join("..","..","data","ready_semi_dummy","cnndm.1K.bpe.model")
#batch_size = 16 #64
batch_size = 14
print("Loading data ...")
train_loader, valid_loader, test_loader, w2i, i2w = loaders.loaders.prepare_dataloaders(data_folder, batch_size, 1500)
#train_loader, valid_loader, test_loader, w2i, i2w = loaders.dummyloaders.prepare_dataloaders(data_folder, batch_size)
print("Loading done, train instances {}, dev instances {}, test instances {}, vocab size {}\n".format(
    len(train_loader.dataset.X),
    len(valid_loader.dataset.X),
    len(test_loader.dataset.X),
    len(w2i)))


# x and y start with BOS (2), end with EOS(3), are padded with PAD (0) and unknown words are UNK (1)
# example batch
dataiter = iter(train_loader)
# x_sequence, x_pos, y_sequence, y_pos = dataiter.next() # if pos loader is used
x_sequence, y_sequence = dataiter.next()
from pprint import pprint
pprint(x_sequence[0])
print(y_sequence[0]) # ex: tensor([    2, 12728, 49279, 13516,  4576, 25888,  1453,     1,  7975, 38296, ...])


# Instantiate the model w/ hyperparams
embedding_dim = 256 #128 #10 #100
encoder_hidden_dim = 256 #256 #128 #256
decoder_hidden_dim = 512 #encoder_hidden_dim*2 # for bidirectional LSTM in the encoder
encoder_n_layers = 2
decoder_n_layers = 1
encoder_drop_prob = 0.3
decoder_drop_prob = 0.3
lr = 0.001

net = LSTMEncoderDecoderAtt(w2i, i2w, embedding_dim, encoder_hidden_dim, decoder_hidden_dim, encoder_n_layers, decoder_n_layers, encoder_drop_prob=encoder_drop_prob, decoder_drop_prob=decoder_drop_prob, lr = lr, model_store_path = "../../train/lstm_att")

print(net)

# train
net.load_checkpoint("last")
net.train(train_loader, valid_loader, test_loader, batch_size)


# run
net.load_checkpoint("best")
#input = [ [4,5,6,7,8,9], [9,8,7,6] ]
#output = net.run(input)
output = net.run(valid_loader, batch_size)
print(output)