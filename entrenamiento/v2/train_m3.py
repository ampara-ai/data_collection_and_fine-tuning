"""Lanza el fine-tuning M3 de FlagEmbedding con la corrección que el notebook v1 aplicaba editando la librería instalada.

FlagEmbedding falla al guardar un checkpoint si el trainer no tiene tokenizer. El notebook v1 reescribía el archivo del
paquete en site-packages; aquí se parcha la clase en memoria antes de ejecutar el módulo, sin tocar la instalación.
torchrun ejecuta este archivo con los mismos argumentos que recibiría `-m FlagEmbedding.finetune.embedder.encoder_only.m3`.
"""
import os
import runpy
import sys

from transformers import AutoTokenizer

import FlagEmbedding.finetune.embedder.encoder_only.m3.trainer as m3_trainer

BASE_MODEL = os.environ.get("BASE_MODEL", "BAAI/bge-m3")

trainers = [v for v in vars(m3_trainer).values()
            if isinstance(v, type) and v.__module__ == m3_trainer.__name__ and hasattr(v, "_save")]
if not trainers:
    sys.exit("no encuentro el trainer M3 de FlagEmbedding: revisa la versión instalada")
for cls in trainers:
    original = cls._save

    def _save(self, output_dir=None, state_dict=None, _original=original):
        if getattr(self, "tokenizer", None) is None:
            self.tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
        return _original(self, output_dir=output_dir, state_dict=state_dict)

    cls._save = _save

runpy.run_module("FlagEmbedding.finetune.embedder.encoder_only.m3", run_name="__main__", alter_sys=True)
