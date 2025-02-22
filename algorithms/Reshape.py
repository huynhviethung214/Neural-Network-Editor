import torch
import numpy as np
from torch.nn import Module


# IMPORT AS MANY MODULES AS YOU NEED


# `self` has `properties` attribute which contain `inputs` that you have been
# added in the `Node Editor`
from utility.utils import map_properties


class reshape(Module):
    def __init__(self, x, y):
        super(reshape, self).__init__()
        self.x = x
        self.y = y

    def forward(self, x):
        # print(x.shape)
        # x = x.cpu()
        # cast_tensor = torch.from_numpy(np.reshape(x.detach().numpy(), (self.y,)))
        #
        # if self.x != 0:
        #     cast_tensor = np.reshape(x.detach().numpy(), (self.x, self.y))
        # return torch.FloatTensor(cast_tensor)
        # print(self.x, self.y)
        return x.view(self.x, self.y)


@map_properties
def algorithm(self):
    # YOUR CODE GOES HERE
    return reshape
