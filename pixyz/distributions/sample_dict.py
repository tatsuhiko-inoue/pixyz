from collections import OrderedDict
from collections.abc import Container
from numbers import Number
from typing import Mapping, Iterable

import torch


class ShapeDict(OrderedDict):
    def shape_dims(self, shape_name):
        start_dim = 0
        for shape_name2, shape in self.items():
            if shape_name == shape_name2:
                break
            start_dim += len(shape)
        return list(range(start_dim, start_dim + len(self[shape_name])))


class Sample:
    """Sampled result class. It has info of meaning of shapes.

    Examples
    --------
    >>> import torch
    >>> from torch.nn import functional as F
    >>> from pixyz.distributions import Normal
    >>> # Marginal distribution
    >>> p1 = Normal(loc=torch.tensor(0.), scale=torch.tensor(1.), var=["x"],
    ...             features_shape=[64], name="p1")
    """
    def __init__(self, value, shape_dict=None):
        if shape_dict and not isinstance(shape_dict, ShapeDict):
            raise ValueError
        self.value = value
        self.shape_dict = shape_dict if shape_dict else self._default_shape(value)

    def _default_shape(self, value):
        if isinstance(value, Number):
            return ShapeDict()
        if not isinstance(value, torch.Tensor):
            raise ValueError
        if value.dim() == 0:
            return ShapeDict()
        elif value.dim() == 1:
            return ShapeDict((('feature', [value.shape[0]]),))
        return ShapeDict((('batch', list(value.shape)[:1]),
                          ('feature', list(value.shape)[1:])))

    def detach(self):
        return Sample(self.value.detach(), self.shape_dict)

    def slice(self, index, shape_name='time'):
        if isinstance(index, int):
            index = [index]
        shape_dict = self.shape_dict.copy()
        shape_dims = self.shape_dims(shape_name)
        value = self._slice_value(self.value, index, shape_dims)
        del shape_dict[shape_name]
        return Sample(value, shape_dict)

    def shape_dims(self, shape_name):
        return self.shape_dict.shape_dims(shape_name)

    def _slice_value(self, value, index, shape_dims):
        slices = [slice(None, None, None) if dim not in shape_dims else index[shape_dims.index(dim)]
                  for dim in range(value.dim())]
        return value[slices]

    @property
    def feature_shape(self):
        return self.shape_dict['feature']

    @property
    def n_batch(self):
        return self.shape_dict['batch'][0]

    def sum(self, shape_name):
        self.value = torch.sum(self.value, dim=self.shape_dims(shape_name))
        shape_dict = self.shape_dict.copy()
        del shape_dict[shape_name]
        self.shape_dict = shape_dict
        return self.value

    def __repr__(self):
        return f"{repr(self.value)} --(shape={repr(list(self.shape_dict.items()))})"


class SampleDict(Mapping):
    """Container class of sampled results. Each result has info of meaning of shapes.

    Examples
    --------
    >>> import torch
    >>> from torch.nn import functional as F
    >>> from pixyz.distributions import Normal
    >>> # Marginal distribution
    >>> p1 = Normal(loc=torch.tensor(0.), scale=torch.tensor(1.), var=["x"],
    ...             features_shape=[64], name="p1")
    """
    def __init__(self, variables):
        if isinstance(variables, dict):
            variables = variables.items()
        elif isinstance(variables, SampleDict):
            variables = variables._dict.items()
        self._dict = {key: value if isinstance(value, Sample) else Sample(value) for key, value in variables}

    def __iter__(self):
        return self._dict.__iter__()

    def __getitem__(self, var_name):
        return self._dict[var_name].value

    def __setitem__(self, var_name, value):
        self._dict[var_name] = Sample(value)

    def get_shape(self, var_name):
        return self._dict[var_name].shape_dict

    def get_sample(self, var_name):
        return self._dict[var_name]

    def items(self):
        return ((key, sample.value) for key, sample in self._dict.items())

    def keys(self):
        return self._dict.keys()

    def __contains__(self, key):
        return self._dict.__contains__(key)

    def __len__(self):
        return self._dict.__len__()

    def __eq__(self, other):
        if not isinstance(other, SampleDict):
            return False
        return self._dict.__eq__(other._dict)

    def __str__(self):
        return str(dict(self.items()))

    def __repr__(self):
        return self._dict.__repr__()

    def add(self, var_name, value, shape_dict=None):
        if shape_dict and not isinstance(shape_dict, ShapeDict):
            if isinstance(shape_dict, Iterable):
                shape_dict = ShapeDict(shape_dict)
            else:
                raise ValueError
        self._dict[var_name] = Sample(value, shape_dict)

    def update(self, variables):
        if isinstance(variables, dict):
            variables = SampleDict(variables)
        if not isinstance(variables, SampleDict):
            raise ValueError
        self._dict.update(variables._dict)

    def copy(self):
        return SampleDict(self._dict)

    def detach(self):
        """Detach all values in `SampleDicts`.

        Parameters
        ----------

        Returns
        -------
        SampleDict
        """
        return SampleDict((var_name, sample.detach()) for var_name, sample in self._dict.items())

    def slice(self, index, shape_name='time'):
        return SampleDict((var_name, sample.slice(index, shape_name)) for var_name, sample in self._dict.items())

    def values(self):
        return (sample.value for sample in self._dict.values())

    def dict_from_keys(self, var, return_tensors=True):
        """Get values from `dicts` specified by `keys`.

        When `return_dict` is True, return values are in dictionary format.

        Parameters
        ----------
        var : list

        return_tensors : bool

        Returns
        -------
        dict or list

        Examples
        --------
        >>> SampleDict({"a":1,"b":2,"c":3}).dict_from_keys(["b"])
        [2]
        >>> SampleDict({"a":1,"b":2,"c":3}).dict_from_keys(["b", "d"], return_tensors=False)
        {'b': 2 --(shape=[])}
        """
        if return_tensors:
            return list(sample.value for var_name, sample in self._dict.items() if var_name in var)
        return SampleDict((var_name, sample) for var_name, sample in self._dict.items() if var_name in var)

    def dict_except_for_keys(self, var: Container):
        """Delete values from `dicts` specified by `keys`.

        Parameters
        ----------
        var : Container

        Returns
        -------
        new_dicts : SampleDict

        Examples
        --------
        >>> SampleDict({"a":1,"b":2,"c":3}).dict_except_for_keys(["b","d"])
        {'a': 1 --(shape=[]), 'c': 3 --(shape=[])}
        """
        return SampleDict((var_name, sample) for var_name, sample in self._dict.items() if var_name not in var)

    def dict_with_replaced_keys(self, replace_list_dict):
        """ Replace values in `dicts` according to `replace_list_dict`.

        Parameters
        ----------
        replace_list_dict : dict
            Dictionary.

        Returns
        -------
        replaced_dicts : SampleDict

        Examples
        --------
        >>> SampleDict({"a":1,"b":2,"c":3}).dict_with_replaced_keys({"a":"x","b":"y"})
        {'x': 1 --(shape=[]), 'y': 2 --(shape=[]), 'c': 3 --(shape=[])}
        >>> SampleDict({"a":1,"b":2,"c":3}).dict_with_replaced_keys({"a":"x","e":"y"})  # keys of `replace_list_dict`
        {'x': 1 --(shape=[]), 'b': 2 --(shape=[]), 'c': 3 --(shape=[])}
        """
        return SampleDict((replace_list_dict[var_name] if var_name in replace_list_dict else var_name, sample)
                          for var_name, sample in self._dict.items())

    def split_by_replace_keys(self, replace_list_dict):
        """ Replace values in `dicts` according to :attr:`replace_list_dict`.

        Replaced dict is splitted by :attr:`replaced_dict` and :attr:`remain_dict`.

        Parameters
        ----------
        replace_list_dict : dict
            Dictionary.

        Returns
        -------
        replaced_dict : dict
            Dictionary.
        remain_dict : dict
            Dictionary.

        Examples
        --------
        >>> replace_list_dict = {'a': 'loc'}
        >>> x_dict = SampleDict({'a': 0, 'b': 1})
        >>> print(x_dict.split_by_replace_keys(replace_list_dict))
        ({'loc': 0 --(shape=[])}, {'b': 1 --(shape=[])})

        """
        replaced_sample = SampleDict((replace_list_dict[var_name], sample)
                                     for var_name, sample in self._dict.items() if var_name in replace_list_dict)

        remain_sample = SampleDict((var_name, sample)
                                   for var_name, sample in self._dict.items() if var_name not in replace_list_dict)

        return replaced_sample, remain_sample

    @property
    def max_shape(self):
        result = []
        for var_name, sample in self._dict.items():
            for i, (shape_name, shape) in enumerate(reversed(sample.shape_dict.items())):
                if len(result) <= i:
                    result.append((shape_name, shape))
                    continue
                if shape_name != result[i][0]:
                    raise ValueError
                if len(result[i][1]) == 0:
                    result[i] = (result[i][0], shape)
                elif len(result[i][1]) != len(shape):
                    raise ValueError
        return ShapeDict(reversed(result))

    def feature_shape(self, var_name):
        return self._dict[var_name].feature_shape

    def n_batch(self, var_name):
        return self._dict[var_name].n_batch