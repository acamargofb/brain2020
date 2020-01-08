from __future__ import print_function, division
import os
import torch
import torch.nn as nn
import numpy as np
import random
import copy


"""
models are defined in this scripts:

    1. FCN
        (a). details

    2. MLP 
        (a). details

    3. CNN 
        (a). details
        
"""

class _FCN(nn.Module):
    def __init__(self, num, p):
        super(_FCN, self).__init__()
        self.features = nn.Sequential(
            # 47, 47, 47
            nn.Conv3d(1, num, 4, 1, 0, bias=False),
            nn.MaxPool3d(2, 1, 0),
            nn.BatchNorm3d(num),
            nn.LeakyReLU(),
            nn.Dropout(0.1),
            # 43, 43, 43
            nn.Conv3d(num, 2*num, 4, 1, 0, bias=False),
            nn.MaxPool3d(2, 2, 0),
            nn.BatchNorm3d(2*num),
            nn.LeakyReLU(),
            nn.Dropout(0.1),
            # 20, 20, 20
            nn.Conv3d(2*num, 4*num, 3, 1, 0, bias=False),
            nn.MaxPool3d(2, 2, 0),
            nn.BatchNorm3d(4*num),
            nn.LeakyReLU(),
            nn.Dropout(0.1),
            # 9, 9, 9
            nn.Conv3d(4*num, 8*num, 3, 1, 0, bias=False),
            nn.MaxPool3d(2, 1, 0),
            nn.BatchNorm3d(8*num),
            nn.LeakyReLU(),
            # 6, 6, 6
        )
        self.classifier = nn.Sequential(
            nn.Dropout(p),
            nn.Linear(8*num*6*6*6, 30),
            nn.LeakyReLU(),
            nn.Dropout(p),
            nn.Linear(30, 2),
        )
        self.feature_length = 8*num*6*6*6
        self.num = num

    def forward(self, x, stage='train'):
        x = self.features(x)
        if stage != 'inference':
            x = x.view(-1, self.feature_length)
        x = self.classifier(x)
        return x

    def dense_to_conv(self):
        fcn = copy.deepcopy(self)
        A = fcn.classifier[1].weight.view(30, 8*self.num, 6, 6, 6)
        B = fcn.classifier[4].weight.view(2, 30, 1, 1, 1)
        C = fcn.classifier[1].bias
        D = fcn.classifier[4].bias
        fcn.classifier[1] = nn.Conv3d(160, 30, 6, 1, 0).cuda()
        fcn.classifier[4] = nn.Conv3d(30, 2, 1, 1, 0).cuda()
        fcn.classifier[1].weight = nn.Parameter(A)
        fcn.classifier[4].weight = nn.Parameter(B)
        fcn.classifier[1].bias = nn.Parameter(C)
        fcn.classifier[4].bias = nn.Parameter(D)
        return fcn



class _CNN(nn.Module):
    def __init__(self, num, p):
        super(_CNN, self).__init__()
        self.features = nn.Sequential(
            nn.Conv3d(1, num, 3, 1, 0),
            nn.ReLU(),
            nn.Conv3d(num, num, 3, 1, 0),
            nn.ReLU(),
            nn.MaxPool3d(2, 2, 0),

            nn.Conv3d(num, 2*num, 3, 1, 0),
            nn.ReLU(),
            nn.Conv3d(2*num, 2*num, 3, 1, 0),
            nn.ReLU(),
            nn.MaxPool3d(2, 2, 0),

            nn.Conv3d(2*num, 4*num, 3, 1, 0),
            nn.ReLU(),
            nn.Conv3d(4*num, 4*num, 3, 1, 0),
            nn.ReLU(),
            nn.Conv3d(4*num, 4*num, 3, 1, 0),
            nn.ReLU(),
            nn.MaxPool3d(2, 2, 0),

            nn.Conv3d(4*num, 8*num, 3, 1, 0),
            nn.ReLU(),
            nn.Conv3d(8*num, 8*num, 3, 1, 0),
            nn.ReLU(),
            nn.Conv3d(8*num, 8*num, 3, 1, 0),
            nn.ReLU(),
            nn.MaxPool3d(2, 2, 0),
        )
        self.feature_length = 8*num*6*6*8
        self.classifier = nn.Sequential(
            nn.Linear(8*num*6*6*8, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(p),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 2),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(-1, self.feature_length)
        x = self.classifier(x)
        return x


class _MLP(nn.Module):
    def __init__(self, dr, hw, dim_bn, dim_no_bn):
        super(_MLP, self).__init__()        
        self.bn1 = nn.BatchNorm1d(dim_bn) if dim_bn != 0 else None
        self.fc1 = nn.Linear(dim_no_bn+dim_bn, hw)
        self.fc2 = nn.Linear(hw, 2)
        self.do1 = nn.Dropout(dr)
        self.do2 = nn.Dropout(dr) 
        self.ac1 = nn.LeakyReLU()
    
    def forward(self, X_bn, X_no_bn):
        if X_bn is None and X_no_bn is not None:
            X = X_no_bn
        elif X_bn is not None and X_no_bn is None:
            X = X_bn
        else:
            X = torch.cat((X_no_bn, self.bn1(X_bn)), 1)  
        out = self.do1(X)
        out = self.fc1(out)
        out = self.ac1(out)
        out = self.do2(out)
        out = self.fc2(out)
        return out