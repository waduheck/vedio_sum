#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置管理模块
"""
from typing import Dict, Any, Optional
import os
import yaml
from pathlib import Path

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径，如果为None则使用默认路径

    Returns:
        Dict[str, Any]: 配置字典
        
    Raises:
        FileNotFoundError: 配置文件不存在时抛出
    """
    if config_path is None:
        config_path = str(Path(__file__).parent.parent.parent / 'config' / 'config.yaml')
        
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        
    # 处理环境变量
    process_env_vars(config)
    
    return config

def process_env_vars(config: Dict[str, Any]) -> None:
    """
    处理配置中的环境变量引用

    Args:
        config: 配置字典
    """
    for section in config:
        if isinstance(config[section], dict):
            for key in config[section]:
                if isinstance(config[section][key], str) and config[section][key].startswith('${') and config[section][key].endswith('}'):
                    env_var = config[section][key][2:-1]
                    config[section][key] = os.environ.get(env_var, '') 