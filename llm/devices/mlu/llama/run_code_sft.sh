# Copyright (c) 2024 PaddlePaddle Authors. All Rights Reserved.
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

python -m paddle.distributed.launch --devices '0,1,2,3,4,5,6,7' \
                                     --log_dir ./log_finetune/code_sft \
                                     ../../../run_finetune.py \
                                    config/llama_sft_argument.json \
                                    --output_dir ./output/code/sft  \
                                    --logging_dir ./log_code_sft/code/sft \
                                    --dataset_name_or_path ./eng_data/data_code \
                                    2>&1 | tee log_sft_code