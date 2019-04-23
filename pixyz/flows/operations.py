import numpy as np
from .flows import Flow


class SqueezeLayer(Flow):
    """
    Squeeze operation.

    c * s * s -> 4c * s/2 * s/2

    Examples
    --------
    >>> import torch
    >>> a = torch.tensor([i+1 for i in range(16)]).view(1,1,4,4)
    >>> print(a)
    tensor([[[[ 1,  2,  3,  4],
              [ 5,  6,  7,  8],
              [ 9, 10, 11, 12],
              [13, 14, 15, 16]]]])
    >>> f = SqueezeLayer()
    >>> print(f(a))
    tensor([[[[ 1,  3],
              [ 9, 11]],
    <BLANKLINE>
             [[ 2,  4],
              [10, 12]],
    <BLANKLINE>
             [[ 5,  7],
              [13, 15]],
    <BLANKLINE>
             [[ 6,  8],
              [14, 16]]]])

    >>> print(f.inverse(f(a)))
    tensor([[[[ 1,  2,  3,  4],
              [ 5,  6,  7,  8],
              [ 9, 10, 11, 12],
              [13, 14, 15, 16]]]])

    """

    def __init__(self):
        super().__init__(None)
        self._logdet_jacobian = 0

    def forward(self, x, compute_jacobian=True):
        [_, channels, height, width] = x.shape

        if height % 2 != 0 or width % 2 != 0:
            raise ValueError

        x = x.permute(0, 2, 3, 1)

        x = x.view(-1, height // 2, 2, width // 2, 2, channels)
        x = x.permute(0, 1, 3, 5, 2, 4)
        x = x.contiguous().view(-1, height // 2, width // 2, channels * 4)

        z = x.permute(0, 3, 1, 2)

        return z

    def inverse(self, z):
        [_, channels, height, width] = z.shape

        if channels % 4 != 0:
            raise ValueError

        z = z.permute(0, 2, 3, 1)

        z = z.view(-1, height, width, channels // 4, 2, 2)
        z = z.permute(0, 1, 4, 2, 5, 3)
        z = z.contiguous().view(-1, 2 * height, 2 * width, channels // 4)

        x = z.permute(0, 3, 1, 2)

        return x


class UnsqueezeLayer(SqueezeLayer):
    """
    Unsqueeze operation.

    c * s * s -> c/4 * 2s * 2s

    Examples
    --------
    >>> import torch
    >>> a = torch.tensor([i+1 for i in range(16)]).view(1,4,2,2)
    >>> print(a)
    tensor([[[[ 1,  2],
              [ 3,  4]],
    <BLANKLINE>
             [[ 5,  6],
              [ 7,  8]],
    <BLANKLINE>
             [[ 9, 10],
              [11, 12]],
    <BLANKLINE>
             [[13, 14],
              [15, 16]]]])
    >>> f = UnsqueezeLayer()
    >>> print(f(a))
    tensor([[[[ 1,  5,  2,  6],
              [ 9, 13, 10, 14],
              [ 3,  7,  4,  8],
              [11, 15, 12, 16]]]])
    >>> print(f.inverse(f(a)))
    tensor([[[[ 1,  2],
              [ 3,  4]],
    <BLANKLINE>
             [[ 5,  6],
              [ 7,  8]],
    <BLANKLINE>
             [[ 9, 10],
              [11, 12]],
    <BLANKLINE>
             [[13, 14],
              [15, 16]]]])

    """

    def forward(self, x, compute_jacobian=True):
        return super().inverse(x)

    def inverse(self, z):
        return super().forward(z)


class PermutationLayer(Flow):
    """
    Examples
    --------
    >>> import torch
    >>> a = torch.tensor([i+1 for i in range(16)]).view(1,4,2,2)
    >>> print(a)
    tensor([[[[ 1,  2],
              [ 3,  4]],
    <BLANKLINE>
             [[ 5,  6],
              [ 7,  8]],
    <BLANKLINE>
             [[ 9, 10],
              [11, 12]],
    <BLANKLINE>
             [[13, 14],
              [15, 16]]]])
    >>> perm = [0,3,1,2]
    >>> f = PermutationLayer(perm)
    >>> f(a)
    tensor([[[[ 1,  2],
              [ 3,  4]],
    <BLANKLINE>
             [[13, 14],
              [15, 16]],
    <BLANKLINE>
             [[ 5,  6],
              [ 7,  8]],
    <BLANKLINE>
             [[ 9, 10],
              [11, 12]]]])
    >>> f.inverse(f(a))
    tensor([[[[ 1,  2],
              [ 3,  4]],
    <BLANKLINE>
             [[ 5,  6],
              [ 7,  8]],
    <BLANKLINE>
             [[ 9, 10],
              [11, 12]],
    <BLANKLINE>
             [[13, 14],
              [15, 16]]]])

    """

    def __init__(self, permute_indices):
        super().__init__(len(permute_indices))
        self.permute_indices = permute_indices
        self.inv_permute_indices = np.argsort(self.permute_indices)
        self._logdet_jacobian = 0

    def forward(self, x, compute_jacobian=True):
        return x[:, self.permute_indices, :, :]

    def inverse(self, z):
        return z[:, self.inv_permute_indices, :, :]


class ShuffleLayer(PermutationLayer):
    def __init__(self, in_channels):
        permute_indices = np.random.permutation(in_channels)
        super().__init__(permute_indices)


class ReverseLayer(PermutationLayer):
    def __init__(self, in_channels):
        permute_indices = np.array(np.arange(0, in_channels)[::-1])
        super().__init__(permute_indices)