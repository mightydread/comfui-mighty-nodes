import os
import os.path
import folder_paths
import re
import sys
import subprocess
import pkg_resources
import random

mightydread_dir = os.path.dirname(os.path.realpath(__file__))
comfy_dir = os.path.abspath(os.path.join(mightydread_dir, '..', '..'))
sys.path.insert(0, comfy_dir)
sys.path.insert(0, mightydread_dir)
required  = {'dynamicprompts'}

installed = {pkg.key for pkg in pkg_resources.working_set}
missing   = required - installed

try:
    from dynamicprompts.generators import RandomPromptGenerator
    from dynamicprompts.wildcards.wildcard_manager import WildcardManager
except ImportError:
    try:
        python = sys.executable
        subprocess.check_call([python, '-m', 'pip', 'install', *missing], stdout=subprocess.DEVNULL)
    except Exception as install_error:
        print(f"Error installing required packages: {install_error}")
        sys.exit(1)


from pathlib import Path
 
wm = WildcardManager(Path(os.path.join(os.path.dirname(__file__), "..", "..", "wildcards")))
generator = RandomPromptGenerator(wildcard_manager=wm)
#------ Lora
class Text_LoRA_Stacker:
    def __init__(self):
        self.lora_spec_re = re.compile("(<(?:lora|lyco):[^>]+>)")
        self.lora_items = []
        self.loras = []
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": { "text": ("STRING", {
                                "multiline": True,
                                "default": ""})},
                "optional": {"lora_stack": ("LORA_STACK", )}
                            }


    RETURN_TYPES = ("LORA_STACK", "STRING",)
    RETURN_NAMES = ("LORA_STACK", "leftover STRING",)
    FUNCTION = "lora_stacker"
    CATEGORY = "mightydread/stackers"

    def lora_stacker(self, text, lora_stack=None):
        try:
            loras = []
            lora_text = self.process_text(text)[1]
            leftover_text = self.process_text(text)[0]
            available_loras = self.available_loras()
            self.update_current_lora_items_with_new_items(
                self.items_from_lora_text_with_available_loras(lora_text, available_loras)
            )
            lora_count = 0
            if len(self.lora_items) > 0:
                for item in self.lora_items:
                    if item.lora_name in available_loras:
                        print(item.lora_name)
                        # result = item.apply_lora(result[0], result[1])
                    else:
                        raise ValueError(f"Unable to find lora with name '{item.lora_name}'")

                loras = [self.lora_items[i].lora_name for i in range(0, len(self.lora_items))]
                model_strs = [self.lora_items[i].strength_model for i in range(0, len(self.lora_items))]
                clip_strs = [self.lora_items[i].strength_clip for i in range(0, len(self.lora_items))]
                loras = [(lora_name, model_str, clip_str) for lora_name, model_str, clip_str in zip(loras, model_strs, clip_strs) if lora_name != "None"]
                print(loras)
            # If lora_stack is not None, extend the loras list with lora_stack
            if lora_stack is not None:
                loras.extend([l for l in lora_stack if l[0] != "None"])
                print(loras)

            return (loras, leftover_text, )

        except Exception as e:
            raise ValueError(f"Error in Text_LoRA_Stacker: {e}")


    def process_text(self, text):
        extracted_loras = self.lora_spec_re.findall(text)
        filtered_text = self.lora_spec_re.sub("", text)

        return (filtered_text, "\n".join(extracted_loras))

    def available_loras(self):
        return folder_paths.get_filename_list("loras")

    def items_from_lora_text_with_available_loras(self, lora_text, available_loras):
        return LoraItemsParser.parse_lora_items_from_text(lora_text, self.dictionary_with_short_names_for_loras(available_loras))

    def dictionary_with_short_names_for_loras(self, available_loras):
        result = {}

        for path in available_loras:
            result[os.path.splitext(os.path.basename(path))[0]] = path

        return result

    def update_current_lora_items_with_new_items(self, lora_items):
        if self.lora_items != lora_items:


            self.lora_items = lora_items

class LoraItemsParser:

    @classmethod
    def parse_lora_items_from_text(cls, lora_text, loras_by_short_names = {}, default_weight=1, weight_separator=":"):
        return cls(lora_text, loras_by_short_names, default_weight, weight_separator).execute()

    def __init__(self, lora_text, loras_by_short_names, default_weight, weight_separator):
        self.lora_text = lora_text
        self.loras_by_short_names = loras_by_short_names
        self.default_weight = default_weight
        self.weight_separator = weight_separator
        self.prefix_trim_re = re.compile("\A<(lora|lyco):")
        self.comment_trim_re = re.compile("\s*#.*\Z")

    def execute(self):
        return [LoraItem(elements[0], elements[1], elements[2])
            for line in self.lora_text.splitlines()
            for elements in [self.parse_lora_description(self.description_from_line(line))] if elements[0] is not None]

    def parse_lora_description(self, description):
        if description is None:
            return (None,)

        lora_name = None
        strength_model = self.default_weight
        strength_clip = None

        remaining, sep, strength = description.rpartition(self.weight_separator)
        if sep == self.weight_separator:
            lora_name = remaining
            strength_model = float(strength)

            remaining, sep, strength = remaining.rpartition(self.weight_separator)
            if sep == self.weight_separator:
                strength_clip = strength_model
                strength_model = float(strength)
                lora_name = remaining
        else:
            lora_name = description

        if strength_clip is None:
            strength_clip = strength_model

        return (self.loras_by_short_names.get(lora_name, lora_name), strength_model, strength_clip)

    def description_from_line(self, line):
        result = self.comment_trim_re.sub("", line.strip())
        result = self.prefix_trim_re.sub("", result.removesuffix(">"))
        return result if len(result) > 0 else None

class LoraItem:
    def __init__(self, lora_name, strength_model, strength_clip):
        self.lora_name = lora_name
        self.strength_model = strength_model
        self.strength_clip = strength_clip

    def __eq__(self, other):
        return self.lora_name == other.lora_name and self.strength_model == other.strength_model and self.strength_clip == other.strength_clip

    def get_lora_path(self):
        return folder_paths.get_full_path("loras", self.lora_name)

    @property
    def is_noop(self):
        return self.strength_model == 0 and self.strength_clip == 0

#------ Wildcard

class MightyWildcardInjector:
    @classmethod
    def INPUT_TYPES(s):
        return {
        "required": {
            "text": ("STRING", {"multiline": True}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),

        }
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("STRING",)
    FUNCTION = "inject"

    CATEGORY = "mightydread/util"
   

    def inject(self, seed, text):
        try:
            random.seed(seed)
            print(f"text : ", text)
            text = generator.generate(text, 1, seeds=seed)
            print(f"result : ", text)
            return (text[0], )

        except Exception as e:
            raise ValueError(f"Error in MightyWildcardInjector: {e}")


# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    "Text_LoRA_Stacker": Text_LoRA_Stacker,
    "MightyWildCardInjector": MightyWildcardInjector
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "Text_LoRA_Stacker": "Text To LoRa Stack",
    "MightyWildcardInjector": "Wildcard Inject"
}
