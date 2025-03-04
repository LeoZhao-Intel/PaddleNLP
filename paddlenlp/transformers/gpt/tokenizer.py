# Copyright (c) 2021 PaddlePaddle Authors. All Rights Reserved.
# Copyright 2018 The Open AI Team Authors and The HuggingFace Inc. team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import shutil
from functools import lru_cache

import jieba
import sentencepiece as spm
from paddle.utils import try_import

from .. import AddedToken, PretrainedTokenizer

__all__ = [
    "GPTTokenizer",
    "GPTChineseTokenizer",
]

PRETRAINED_POSITIONAL_EMBEDDINGS_SIZES = {
    "gpt-cpm-large-cn": 1024,
    "gpt-cpm-small-cn-distill": 1024,
    "gpt3-175B-en": 1024,
    "gpt3-89B-en": 1024,
    "gpt3-13B-en": 1024,
    "gpt3-6.7B-en": 1024,
    "gpt3-1.3B-en": 1024,
    "gpt2-xl-en": 1024,
    "gpt2-large-en": 1024,
    "gpt2-medium-en": 1024,
    "gpt2-en": 1024,
    "gpt2-small-en": 1024,
}


@lru_cache()
def bytes_to_unicode():
    """
    Returns list of utf-8 byte and a corresponding list of unicode strings.
    The reversible bpe codes work on unicode strings.
    This means you need a large # of unicode characters in your vocab if you want to avoid UNKs.
    When you're at something like a 10B token dataset you end up needing around 5K for decent coverage.
    This is a signficant percentage of your normal, say, 32K bpe vocab.
    To avoid that, we want lookup tables between utf-8 bytes and unicode strings.
    And avoids mapping to whitespace/control characters the bpe code barfs on.
    """
    _chr = chr
    bs = (
        list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    )
    cs = bs[:]
    n = 0
    for b in range(2**8):
        if b not in bs:
            bs.append(b)
            cs.append(2**8 + n)
            n += 1
    cs = [_chr(n) for n in cs]
    return dict(zip(bs, cs))


def get_pairs(word):
    """Return set of symbol pairs in a word.

    Word is represented as tuple of symbols (symbols being variable-length strings).
    """
    pairs = set()
    prev_char = word[0]
    for char in word[1:]:
        pairs.add((prev_char, char))
        prev_char = char
    return pairs


class GPTChineseTokenizer(PretrainedTokenizer):
    """
    Constructs a GPT Chinese tokenizer based on `SentencePiece <https://github.com/google/sentencepiece>`__.

    This tokenizer inherits from :class:`~paddlenlp.transformers.tokenizer_utils.PretrainedTokenizer`
    which contains most of the main methods. For more information regarding those methods,
    please refer to this superclass.

    Args:
        vocab_file (str):
            The vocabulary file required to instantiate
            a `SentencePiece <https://github.com/google/sentencepiece>`__ tokenizer.
        max_len (int):
            The maximum value of the input sequence length.
            Defaults to `512`.
        unk_token (str):
            A special token representing the *unknown (out-of-vocabulary)* token.
            An unknown token is set to be `unk_token` inorder to be converted to an ID.
            Defaults to "[UNK]".

    Examples:
        .. code-block::

            from paddlenlp.transformers import GPTChineseTokenizer

            tokenizer = GPTChineseTokenizer.from_pretrained('gpt-cpm-large-cn')
            print(tokenizer('欢迎使用百度飞桨！'))
            '''
            {'input_ids': [2092, 260, 1014, 1596, 17620, 45], 'token_type_ids': [0, 0, 0, 0, 0, 0]}
            '''
    """

    resource_files_names = {"model_file": "sentencepiece.model"}  # for save_pretrained

    cpm_model_link = "https://bj.bcebos.com/paddlenlp/models/transformers/gpt/gpt-cpm-cn-sentencepiece.model"
    pretrained_resource_files_map = {
        "model_file": {
            "gpt-cpm-large-cn": cpm_model_link,
            "gpt-cpm-small-cn-distill": cpm_model_link,
        }
    }
    pretrained_init_configuration = {
        "gpt-cpm-large-cn": {},
        "gpt-cpm-small-cn-distill": {},
    }

    def __init__(
        self,
        model_file,
        max_len=512,
        unk_token="<unk>",
        bos_token="<bod>",
        eos_token="<eod>",
        eol_token="\u2583",
        **kwargs  # The token of newline.
    ):
        self._model_file = model_file
        self.eol_token = eol_token
        if not os.path.isfile(model_file):
            raise ValueError(
                "Can't find a model file at path '{}'. To load the "
                "model from a pretrained model please use "
                "`tokenizer = GPTTokenizer.from_pretrained(PRETRAINED_MODEL_NAME)`".format(model_file)
            )
        self.max_len = max_len if max_len is not None else int(1e12)
        self.sp = spm.SentencePieceProcessor()
        self.sp.Load(model_file)
        self.translator = str.maketrans(" \n", "\u2582\u2583")

    @property
    def eol_token_id(self):
        if self.eol_token is None:
            return None
        return self.convert_tokens_to_ids(self.eol_token)

    def _tokenize(self, text):
        """Tokenize a string."""
        seg_list = [x.translate(self.translator) for x in jieba.cut(text, cut_all=False)]
        new_seg = " ".join(seg_list)
        return self.sp.encode(new_seg, out_type=str)

    def _convert_token_to_id(self, token):
        """Converts a token (str) to an id using the vocab."""
        return self.sp.PieceToId(token)

    def _convert_id_to_token(self, index):
        """Converts an index (integer) to a token (str) using the vocab."""
        return self.sp.IdToPiece(index)

    '''
    def convert_tokens_to_ids(self, tokens):
        """
        Converts a single token or a sequence of tokens to an index or a
        sequence of indices.

        Args:
            tokens (str|List[str]|tuple(str)):
                A single token or a sequence of tokens.

        Returns:
            int|List[int]: The converted token id or token ids.

        Example:
            .. code-block::

                from paddlenlp.transformers import GPTChineseTokenizer

                tokenizer = GPTChineseTokenizer.from_pretrained('gpt-cpm-large-cn')
                print(tokenizer.convert_tokens_to_ids(['▁欢迎', '▁使用', '▁百度', '▁飞', '桨', '▁!']))
                # [2092, 260, 1014, 1596, 17620, 45]
        """

        if not isinstance(tokens, (list, tuple)):
            return self._convert_token_to_id(tokens)
        else:
            return [self._convert_token_to_id(token) for token in tokens]
    '''

    def convert_ids_to_tokens(self, ids, skip_special_tokens=False):
        """
        Converts a single index or a sequence of indices to a token or a
        sequence of tokens.

        Args:
            ids (int|List[int]|tuple(int)):
                The token id (or token ids) to be converted to token(s).

        Returns:
            str|List[str]: The converted token or sequence of tokens.

        Example:
            .. code-block::

                from paddlenlp.transformers import GPTChineseTokenizer

                tokenizer = GPTChineseTokenizer.from_pretrained('gpt-cpm-large-cn')
                print(tokenizer.convert_ids_to_tokens([2092, 260, 1014, 1596, 17620, 45]))
                #['▁欢迎', '▁使用', '▁百度', '▁飞', '桨', '▁!']

        """

        if not isinstance(ids, (list, tuple)):
            return self._convert_id_to_token(ids)
        tokens = [self._convert_id_to_token(_id) for _id in ids]
        return tokens

    @property
    def vocab_size(self):
        """
        Returns the size of vocabulary.

        Returns:
            int: The size of vocabulary.

        Example:
            .. code-block::

                from paddlenlp.transformers import GPTChineseTokenizer
                tokenizer = GPTChineseTokenizer.from_pretrained('gpt-cpm-large-cn')
                print(tokenizer.vocab_size)
                # 50257

        """
        return len(self.sp)

    def get_vocab(self):
        """
        Returns the vocabulary as a dictionary of token to index.

        `tokenizer.get_vocab()[token]` is equivalent to `tokenizer.convert_tokens_to_ids(token)` when `token` is in the
        vocab.

        Returns:
            `Dict[str, int]`: The vocabulary.
        """
        return dict({self.sp.IdToPiece(i): i for i in range(self.sp.GetPieceSize())}, **self.added_tokens_encoder)

    def convert_ids_to_string(self, ids):
        """
        Converts a single index or a sequence of indices to texts.

        Args:
            ids (int|List[int]):
                The token id (or token ids) to be converted to text.

        Returns:
            str: The decoded text.

        Example:
            .. code-block::

                from paddlenlp.transformers import GPTChineseTokenizer
                tokenizer = GPTChineseTokenizer.from_pretrained('gpt-cpm-large-cn')
                print(tokenizer.convert_ids_to_string([2092, 260, 1014, 1596, 17620, 45]))
                # '欢迎使用百度飞桨!'

        """

        text = self.sp.decode(ids)
        text = text.replace(" ", "").replace("\u2582", " ").replace("\u2583", "\n")
        return text

    def save_resources(self, save_directory):
        """
        Save tokenizer related resources to files under `save_directory`.

        Args:
            save_directory (str): Directory to save files into.
        """
        for name, file_name in self.resource_files_names.items():
            save_path = os.path.join(save_directory, file_name)
            shutil.copyfile(getattr(self, "_%s" % name), save_path)


class GPTTokenizer(PretrainedTokenizer):
    """
    Constructs a GPT tokenizer based on byte-level Byte-Pair-Encoding.

    This tokenizer inherits from :class:`~paddlenlp.transformers.tokenizer_utils.PretrainedTokenizer`
    which contains most of the main methods. For more information regarding those methods,
    please refer to this superclass.

    Args:
        vocab_file (str):
            Path to the vocab file.
            The vocab file contains a mapping from vocabulary strings to indices.
        merges_file (str):
            Path to the merge file.
            The merge file is used to split the input sentence into "subword" units.
            The vocab file is then used to encode those units as intices.
        errors (str):
            Paradigm to follow when decoding bytes to UTF-8.
            Defaults to `'replace'`.
        max_len (int, optional):
            The maximum value of the input sequence length.
            Defaults to `None`.

    Examples:
        .. code-block::

            from paddlenlp.transformers import GPTTokenizer

            tokenizer = GPTTokenizer.from_pretrained('gpt2-medium-en')
            print(tokenizer('Welcome to use PaddlePaddle and PaddleNLP'))

            '''
            {'input_ids': [14618, 284, 779, 350, 37382, 47, 37382, 290, 350, 37382, 45, 19930],
            'token_type_ids': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}
            '''

    """

    resource_files_names = {"vocab_file": "vocab.json", "merges_file": "merges.txt"}  # for save_pretrained
    gpt_vocab_link = "http://bj.bcebos.com/paddlenlp/models/transformers/gpt/gpt-en-vocab.json"
    gpt_merges_link = "http://bj.bcebos.com/paddlenlp/models/transformers/gpt/gpt-en-merges.txt"
    pretrained_resource_files_map = {
        "vocab_file": {
            "gpt3-175B-en": gpt_vocab_link,
            "gpt3-89B-en": gpt_vocab_link,
            "gpt3-13B-en": gpt_vocab_link,
            "gpt3-6.7B-en": gpt_vocab_link,
            "gpt3-1.3B-en": gpt_vocab_link,
            "gpt2-xl-en": gpt_vocab_link,
            "gpt2-large-en": gpt_vocab_link,
            "gpt2-medium-en": gpt_vocab_link,
            "gpt2-en": gpt_vocab_link,
            "gpt2-small-en": gpt_vocab_link,
        },
        "merges_file": {
            "gpt3-175B-en": gpt_merges_link,
            "gpt3-89B-en": gpt_merges_link,
            "gpt3-13B-en": gpt_merges_link,
            "gpt3-6.7B-en": gpt_merges_link,
            "gpt3-1.3B-en": gpt_merges_link,
            "gpt2-xl-en": gpt_merges_link,
            "gpt2-large-en": gpt_merges_link,
            "gpt2-medium-en": gpt_merges_link,
            "gpt2-en": gpt_merges_link,
            "gpt2-small-en": gpt_merges_link,
        },
    }
    pretrained_init_configuration = {
        "gpt3-175B-en": {},
        "gpt3-89B-en": {},
        "gpt3-13B-en": {},
        "gpt3-6.7B-en": {},
        "gpt3-1.3B-en": {},
        "gpt2-xl-en": {},
        "gpt2-large-en": {},
        "gpt2-medium-en": {},
        "gpt2-en": {},
        "gpt2-small-en": {},
    }

    def __init__(
        self,
        vocab_file,
        merges_file,
        errors="replace",
        max_len=None,
        pad_token="<|endoftext|>",
        eos_token="<|endoftext|>",
        unk_token="<|endoftext|>",
        eol_token="\u010a",
        add_prefix_space=False,
        add_bos_token=False,
        **kwargs  # The token of newline.
    ):
        pad_token = AddedToken(pad_token, lstrip=False, rstrip=False) if isinstance(pad_token, str) else pad_token
        eos_token = AddedToken(eos_token, lstrip=False, rstrip=False) if isinstance(eos_token, str) else eos_token
        unk_token = AddedToken(unk_token, lstrip=False, rstrip=False) if isinstance(unk_token, str) else unk_token
        self.eol_token = eol_token
        self._build_special_tokens_map_extended(
            bos_token=pad_token if getattr(self, "bos_token", None) is None else self.bos_token,
            eos_token=eos_token,
            unk_token=unk_token,
        )

        self._vocab_file = vocab_file
        self._merges_file = merges_file
        self.max_len = max_len if max_len is not None else int(1e12)
        self.num_command_tokens = 2
        self.num_type_tokens = 2

        with open(vocab_file, "r", encoding="utf-8") as f:
            self.encoder = json.load(f)

        self.decoder = {v: k for k, v in self.encoder.items()}

        self.num_tokens = len(self.encoder)
        self.num_text_tokens = self.num_tokens - 1
        self.errors = errors  # how to handle errors in decoding
        self.byte_encoder = bytes_to_unicode()
        self.byte_decoder = {v: k for k, v in self.byte_encoder.items()}

        with open(merges_file, encoding="utf-8") as f:
            bpe_data = f.read().split("\n")[1:-1]

        bpe_merges = [tuple(merge.split()) for merge in bpe_data]
        self.bpe_ranks = dict(zip(bpe_merges, range(len(bpe_merges))))
        self.cache = {}
        self.add_prefix_space = add_prefix_space
        self.add_bos_token = add_bos_token

        re = try_import("regex")
        self.pat = re.compile(r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+""")

    @property
    def vocab_size(self):
        """
        Returns the size of vocabulary.

        Returns:
            int: The sum of size of vocabulary and the size of speical tokens.

        """

        return len(self.encoder)

    @property
    def eol_token_id(self):
        if self.eol_token is None:
            return None
        return self.convert_tokens_to_ids(self.eol_token)

    def bpe(self, token):
        if token in self.cache:
            return self.cache[token]
        word = tuple(token)
        pairs = get_pairs(word)

        if not pairs:
            return token

        while True:
            bigram = min(pairs, key=lambda pair: self.bpe_ranks.get(pair, float("inf")))
            if bigram not in self.bpe_ranks:
                break
            first, second = bigram
            new_word = []
            i = 0
            while i < len(word):
                try:
                    j = word.index(first, i)
                    new_word.extend(word[i:j])
                    i = j
                except:
                    new_word.extend(word[i:])
                    break

                if word[i] == first and i < len(word) - 1 and word[i + 1] == second:
                    new_word.append(first + second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            new_word = tuple(new_word)
            word = new_word
            if len(word) == 1:
                break
            else:
                pairs = get_pairs(word)
        word = " ".join(word)
        self.cache[token] = word
        return word

    def _tokenize(self, text):
        """Tokenize a string."""
        bpe_tokens = []
        re = try_import("regex")
        for token in re.findall(self.pat, text):
            token = "".join(self.byte_encoder[b] for b in token.encode("utf-8"))
            bpe_tokens.extend(bpe_token for bpe_token in self.bpe(token).split(" "))
        return bpe_tokens

    def _convert_token_to_id(self, token):
        return self.encoder.get(token, self.encoder.get(self.unk_token))

    def _convert_id_to_token(self, index):
        return self.decoder[index]

    def convert_ids_to_string(self, ids):
        """
        Converts a single index or a sequence of indices to texts.

        Args:
            ids (int|List[int]):
                The token id (or token ids) to be converted to text.

        Returns:
            str: The decoded text.

        Example:
            .. code-block::

                from paddlenlp.transformers import GPTTokenizer
                tokenizer = GPTTokenizer.from_pretrained('gpt2-medium-en')
                print(tokenizer.convert_ids_to_string(tokenizer.convert_ids_to_string([14618, 284, 779, 350, 37382, 47, 37382, 290, 350, 37382, 45, 19930]))
                # 'Welcome to use PaddlePaddle and PaddleNLP'

        """

        text = "".join([self.decoder[id] for id in ids])
        text = bytearray([self.byte_decoder[c] for c in text]).decode("utf-8", errors=self.errors)
        return text

    def save_resources(self, save_directory):
        """
        Saves `SentencePiece <https://github.com/google/sentencepiece>`__ file
        (ends with '.spm') under `save_directory`.

        Args:
            save_directory (str): Directory to save files into.
        """
        for name, file_name in self.resource_files_names.items():
            source_path = getattr(self, "_%s" % name)

            save_path = os.path.join(save_directory, file_name)
            if os.path.abspath(source_path) != os.path.abspath(save_path):
                shutil.copyfile(source_path, save_path)

    def convert_tokens_to_string(self, tokens):
        """
        Converts a sequence of tokens (string) in a single string.
        """
        text = "".join(tokens)
        text = bytearray([self.byte_decoder[c] for c in text]).decode("utf-8", errors=self.errors)
        return text

    def get_vocab(self):
        return dict(self.encoder, **self.added_tokens_encoder)

    def prepare_for_tokenization(self, text, is_split_into_words=False, **kwargs):
        add_prefix_space = kwargs.pop("add_prefix_space", self.add_prefix_space)
        if is_split_into_words or add_prefix_space:
            text = " " + text
        return (text, kwargs)

    def build_inputs_with_special_tokens(self, token_ids_0, token_ids_1=None):
        if self.add_bos_token:
            bos_token_ids = [self.bos_token_id]
        else:
            bos_token_ids = []

        output = bos_token_ids + token_ids_0

        if token_ids_1 is None:
            return output

        return output + bos_token_ids + token_ids_1
